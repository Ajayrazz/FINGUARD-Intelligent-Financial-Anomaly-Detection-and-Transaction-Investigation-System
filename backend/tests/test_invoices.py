"""Invoice upload -> real Tesseract OCR -> extraction -> matching -> human review, on the synthetic invoice set."""

import io
import shutil
from functools import lru_cache

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.audit.models import AuditLog
from apps.duplicates.models import DuplicateCandidate, Invoice, InvoiceDocument
from duplicates_lib import synthetic

pytestmark = pytest.mark.django_db


@lru_cache(maxsize=1)
def synthetic_set():
    return synthetic.build_set()


@pytest.fixture
def analyst(make_user, api_as):
    return api_as(make_user("financial_analyst"))


def upload(api, name, data, mime="image/png", run_tasks=None):
    f = SimpleUploadedFile(name, data, content_type=mime)
    if run_tasks is None:
        return api.post("/api/v1/invoices/upload/", {"file": f}, format="multipart")
    with run_tasks(execute=True):
        return api.post("/api/v1/invoices/upload/", {"file": f}, format="multipart")


@pytest.fixture
def uploaded_set(analyst, run_tasks):
    """The whole synthetic set uploaded and processed (OCR really runs)."""
    docs, _ = synthetic_set()
    ids = {}
    for d in docs:
        res = upload(analyst, f"{d['name']}.png", d["bytes"], d["mime"], run_tasks)
        assert res.status_code == 202, res.content
        ids[d["name"]] = res.data["id"]
    return ids


def test_tesseract_is_installed_and_runs():
    """Acceptance: OCR is executed on real files - the build fails if the engine is missing."""
    assert shutil.which("tesseract"), "Tesseract OCR is not installed in this environment"
    import pytesseract

    docs, _ = synthetic_set()
    text = pytesseract.image_to_string(Image.open(io.BytesIO(docs[0]["bytes"])))
    assert "INVOICE" in text.upper()


def test_ocr_extracts_fields_with_confidence_and_measured_accuracy(uploaded_set):
    docs, _ = synthetic_set()
    total = correct = 0
    misses = []
    for d in docs:
        inv = Invoice.objects.get(pk=uploaded_set[d["name"]])
        assert inv.document.status == "needs_review"  # a human must verify before anything is final
        assert inv.document.ocr_confidence and inv.document.ocr_confidence > 50 and len(inv.document.phash) == 16
        s = d["spec"]
        checks = {
            "vendor": inv.vendor_name.lower().replace(".", "") == s.vendor.lower().replace(".", ""),
            "number": inv.invoice_number == s.number,
            "date": inv.invoice_date == s.when,
            "amount": inv.amount is not None and float(inv.amount) == s.total,
        }
        for field, ok in checks.items():
            total += 1
            correct += ok
            if not ok:
                misses.append(
                    (
                        d["name"],
                        field,
                        getattr(
                            inv,
                            {
                                "vendor": "vendor_name",
                                "number": "invoice_number",
                                "date": "invoice_date",
                                "amount": "amount",
                            }[field],
                        ),
                    )
                )
        assert set(inv.field_confidence) >= {"vendor", "invoice_number"}
    accuracy = correct / total
    print(f"\nOCR field accuracy on the synthetic set: {correct}/{total} = {accuracy:.1%}; misses: {misses}")
    assert accuracy >= 0.85, misses


def test_synthetic_set_is_classified_as_expected(uploaded_set):
    _, expected = synthetic_set()

    def cand(a, b):
        ia, ib = sorted((uploaded_set[a], uploaded_set[b]))
        return DuplicateCandidate.objects.filter(kind="invoice", record_a_id=ia, record_b_id=ib).first()

    wrong = []
    for a, b, cls in expected:
        c = cand(a, b)
        got = c.match_class if c else None
        if got != cls:
            wrong.append((a, b, cls, got))
    print(f"\nPair classification: {len(expected) - len(wrong)}/{len(expected)} as expected; wrong: {wrong}")
    assert not wrong, wrong
    assert not DuplicateCandidate.objects.exclude(review_status="pending").exists()  # nothing is auto-confirmed


def test_confirmed_requires_a_human_and_is_audited(uploaded_set, analyst, make_user, api_as):
    c = DuplicateCandidate.objects.filter(match_class="exact").first()
    assert c.review_status == "pending" and c.reviewed_by is None
    assert (
        api_as(make_user("auditor"))
        .post(f"/api/v1/duplicates/candidates/{c.pk}/review/", {"decision": "confirmed_duplicate"}, format="json")
        .status_code
        == 403
    )
    assert (
        analyst.post(
            f"/api/v1/duplicates/candidates/{c.pk}/review/", {"decision": "auto_confirm"}, format="json"
        ).status_code
        == 400
    )
    investigator = api_as(make_user("fraud_investigator"))
    res = investigator.post(
        f"/api/v1/duplicates/candidates/{c.pk}/review/",
        {"decision": "confirmed_duplicate", "notes": "same PO"},
        format="json",
    )
    assert (
        res.status_code == 200
        and res.json()["review_status"] == "confirmed_duplicate"
        and res.json()["reviewed_by_email"]
    )
    c.refresh_from_db()
    assert c.reviewed_by and c.reviewed_at and c.notes == "same PO"
    assert AuditLog.objects.filter(action="duplicates.reviewed", resource_id=str(c.pk)).exists()


def test_correcting_fields_marks_reviewed_rematches_and_keeps_human_decisions(uploaded_set, analyst):
    a, b = uploaded_set["globex_a"], uploaded_set["globex_b"]
    cand = DuplicateCandidate.objects.get(kind="invoice", record_a_id=min(a, b), record_b_id=max(a, b))
    analyst.post(f"/api/v1/duplicates/candidates/{cand.pk}/review/", {"decision": "not_duplicate"}, format="json")
    res = analyst.patch(
        f"/api/v1/invoices/{b}/fields/", {"invoice_number": "GL-88120"}, format="json"
    )  # reviewer fixes the number
    assert res.status_code == 200 and res.json()["status"] == "reviewed" and res.json()["verified_by_email"]
    inv = Invoice.objects.get(pk=b)
    assert (
        inv.invoice_number_normalized == "GL88120" and inv.extracted_fields["invoice_number"] == "GL-88175"
    )  # OCR output kept
    cand.refresh_from_db()
    assert cand.review_status == "not_duplicate"  # re-matching never overwrites the human decision
    assert AuditLog.objects.filter(action="invoice.fields_corrected").exists()


def test_upload_validation_rejects_bad_files_and_never_uses_the_client_name(analyst, settings):
    docs, _ = synthetic_set()
    png = docs[0]["bytes"]
    assert (
        upload(analyst, "invoice.png", b"MZ\x90\x00 not an image").status_code == 400
    )  # wrong content, even with an image name
    assert upload(analyst, "invoice.png", png[:200]).status_code == 400  # truncated image
    assert upload(analyst, "invoice.png", b"").status_code == 400
    settings.INVOICE_MAX_BYTES = 1000
    assert upload(analyst, "big.png", png).status_code == 400
    settings.INVOICE_MAX_BYTES = 10 * 1024 * 1024
    assert analyst.post("/api/v1/invoices/upload/", {}, format="multipart").status_code == 400
    res = upload(analyst, "../../etc/passwd.png", png)
    assert res.status_code == 202
    doc = InvoiceDocument.objects.get(pk=Invoice.objects.get(pk=res.data["id"]).document_id)
    assert "passwd" not in doc.file_path and "etc" not in doc.file_path and doc.original_name == "passwd.png"


def test_pdf_invoice_is_rendered_and_ocrd(analyst, run_tasks):
    docs, _ = synthetic_set()
    buf = io.BytesIO()
    Image.open(io.BytesIO(docs[0]["bytes"])).convert("RGB").save(buf, "PDF")
    res = upload(analyst, "scan.pdf", buf.getvalue(), "application/pdf", run_tasks)
    assert res.status_code == 202
    inv = Invoice.objects.get(pk=res.data["id"])
    assert (
        inv.document.mime == "application/pdf" and inv.invoice_number == "INV-2026-0412" and float(inv.amount) == 1416.0
    )


def test_identical_file_uploaded_twice_is_an_exact_candidate(analyst, run_tasks):
    docs, _ = synthetic_set()
    a = upload(analyst, "a.png", docs[7]["bytes"], run_tasks=run_tasks).data["id"]
    b = upload(analyst, "b.png", docs[7]["bytes"], run_tasks=run_tasks).data["id"]
    c = DuplicateCandidate.objects.get(kind="invoice", record_a_id=min(a, b), record_b_id=max(a, b))
    assert c.match_class == "exact" and c.similarity_score == 100.0


def test_file_endpoint_is_authenticated_and_nosniff_and_report_is_a_pdf(uploaded_set, analyst, make_user, api_as):
    inv_id = uploaded_set["initech"]
    res = analyst.get(f"/api/v1/invoices/{inv_id}/file/")
    assert res.status_code == 200 and res["Content-Type"] == "image/png" and res["X-Content-Type-Options"] == "nosniff"
    assert "invoice-" in res["Content-Disposition"] and b"".join(res.streaming_content)[:4] == b"\x89PNG"
    assert api_as(make_user("management")).get(f"/api/v1/invoices/{inv_id}/file/").status_code == 403
    cand = DuplicateCandidate.objects.first()
    rep = analyst.get(f"/api/v1/duplicates/candidates/{cand.pk}/report/")
    assert rep.status_code == 200 and rep["Content-Type"] == "application/pdf" and rep.content.startswith(b"%PDF")
    detail = analyst.get(f"/api/v1/duplicates/candidates/{cand.pk}/").json()
    assert detail["record_a"]["type"] == "invoice" and "evidence" in detail and "label" not in str(detail).lower()


def test_candidate_filters(uploaded_set, analyst):
    only = analyst.get("/api/v1/duplicates/candidates/?match_class=legitimate_repeat&kind=invoice").json()
    assert only["count"] == 2 and {r["match_class"] for r in only["results"]} == {"legitimate_repeat"}
    high = analyst.get("/api/v1/duplicates/candidates/?min_score=95").json()
    assert all(r["similarity_score"] >= 95 for r in high["results"])
    scores = [r["similarity_score"] for r in analyst.get("/api/v1/duplicates/candidates/").json()["results"]]
    assert scores == sorted(scores, reverse=True)
