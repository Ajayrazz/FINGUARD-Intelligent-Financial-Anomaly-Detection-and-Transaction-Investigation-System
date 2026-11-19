"""Duplicate detection services: invoice upload + OCR pipeline, matching, transaction scans, human review."""

from __future__ import annotations

import hashlib
import logging
import secrets
from pathlib import Path
from typing import Any

import pandas as pd
from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.transactions.models import Transaction
from duplicates_lib import CONFIG, matching, normalize, ocr
from duplicates_lib.extract import extract_fields

from .models import DuplicateCandidate, DuplicateScanRun, Invoice, InvoiceDocument

log = logging.getLogger(__name__)
ALLOWED = {
    b"\x89PNG\r\n\x1a\n": ("image/png", ".png"),
    b"\xff\xd8\xff": ("image/jpeg", ".jpg"),
    b"%PDF": ("application/pdf", ".pdf"),
}
DECISIONS = {"confirmed_duplicate", "not_duplicate", "legitimate_repeat"}


class DuplicateError(Exception):
    """A request cannot be served (message is safe to show)."""


# ------------------------------------------------------------------------------------ upload
def store_invoice_upload(uploaded, user: Any) -> InvoiceDocument:
    """Validate (size, magic bytes, decodable, page/pixel limits) and store under a random name."""
    data = uploaded.read(settings.INVOICE_MAX_BYTES + 1)
    if not data:
        raise DuplicateError("The file is empty.")
    if len(data) > settings.INVOICE_MAX_BYTES:
        raise DuplicateError(f"The file is larger than {settings.INVOICE_MAX_BYTES // (1024 * 1024)} MB.")
    mime, ext = next(((m, e) for magic, (m, e) in ALLOWED.items() if data.startswith(magic)), (None, None))
    if mime is None or ext is None:
        raise DuplicateError("Only PNG, JPEG and PDF invoices are accepted (checked by file content, not name).")
    try:
        pages = ocr.load_pages(data, mime)
    except Exception as exc:  # noqa: BLE001 - corrupt, truncated, bomb: all the same to the user
        raise DuplicateError("The file could not be read as an image or PDF.") from exc
    root = Path(settings.MEDIA_ROOT) / "invoices"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{secrets.token_hex(16)}{ext}"  # random name: the client filename never touches the filesystem
    path.write_bytes(data)
    name = (
        "".join(ch for ch in Path(str(getattr(uploaded, "name", "invoice"))).name if ch.isprintable())[:200]
        or "invoice"
    )
    doc = InvoiceDocument.objects.create(
        file_path=str(path), original_name=name, sha256=hashlib.sha256(data).hexdigest(), mime=mime, size=len(data),
        page_count=len(pages), uploaded_by=user,
    )  # fmt: skip
    audit.log("invoice.uploaded", actor=user, resource_type="invoice_document", resource_id=doc.pk,
              changes={"sha256": doc.sha256, "size": doc.size, "mime": mime})  # fmt: skip
    return doc


# ------------------------------------------------------------------------------------ OCR pipeline
def _apply_fields(inv: Invoice, fields: dict[str, Any]) -> None:
    get = lambda k: (fields.get(k) or {}).get("value")  # noqa: E731
    inv.vendor_name = get("vendor") or ""
    inv.vendor_normalized = normalize.normalize_vendor(inv.vendor_name)
    inv.invoice_number = get("invoice_number") or ""
    inv.invoice_number_normalized = normalize.normalize_invoice_number(inv.invoice_number)
    amt = get("amount")
    inv.amount = normalize.parse_amount(amt) if amt else None
    inv.currency = get("currency") or ""
    d = get("invoice_date")
    inv.invoice_date = normalize.parse_date(d) if d else None


def process_invoice(document_id: int) -> None:
    """validate -> preprocess -> OCR (Tesseract) -> extract -> normalise -> match. Always ends in needs_review or failed:
    a human must verify the fields before anything is called confirmed."""
    doc = InvoiceDocument.objects.get(pk=document_id)
    if doc.status not in (InvoiceDocument.Status.UPLOADED, InvoiceDocument.Status.FAILED):
        return
    try:
        pages = ocr.load_pages(Path(doc.file_path).read_bytes(), doc.mime)
        lines: list[tuple[str, float]] = []
        for page in pages[:3]:
            lines += ocr.ocr_lines(page)
        fields = extract_fields(lines)
        doc.ocr_text = "\n".join(t for t, _ in lines)
        doc.ocr_confidence = sum(c for _, c in lines) / len(lines) if lines else 0.0
        doc.phash = f"{ocr.phash(pages[0]):016x}"
        with db_transaction.atomic():
            inv, _ = Invoice.objects.get_or_create(document=doc)
            _apply_fields(inv, fields)
            inv.extracted_fields = {k: (v or {}).get("value") for k, v in fields.items()}
            inv.field_confidence = {k: round((v or {}).get("confidence", 0.0), 1) for k, v in fields.items() if v}
            inv.save()
            doc.status, doc.error_message = InvoiceDocument.Status.NEEDS_REVIEW, ""
            doc.save()
        match_invoice(inv)
    except ocr.OcrUnavailable:
        _fail(doc, "OCR engine (Tesseract) is not available on the server.")
    except Exception:  # noqa: BLE001
        log.exception("invoice %s failed", document_id)
        _fail(doc, "The invoice could not be processed.")


def _fail(doc: InvoiceDocument, message: str) -> None:
    doc.status, doc.error_message = InvoiceDocument.Status.FAILED, message
    doc.save(update_fields=["status", "error_message"])
    audit.log(
        "invoice.failed",
        actor=doc.uploaded_by,
        resource_type="invoice_document",
        resource_id=doc.pk,
        changes={"error": message},
    )


# ------------------------------------------------------------------------------------ matching
def _features(inv: Invoice) -> dict[str, Any]:
    ph = inv.document.phash if inv.document is not None and inv.document.phash else None
    return {
        "vendor_normalized": inv.vendor_normalized, "invoice_number_normalized": inv.invoice_number_normalized,
        "amount": inv.amount, "invoice_date": inv.invoice_date, "phash": int(ph, 16) if ph else None,
    }  # fmt: skip


def _upsert_candidate(
    kind: str, a_type: str, a_id: int, b_type: str, b_id: int, res: dict[str, Any], run: DuplicateScanRun | None
) -> bool:
    """Create the pair (ordered a<b) or refresh its score/evidence; a human decision is never overwritten."""
    if (a_type, a_id) > (b_type, b_id):
        a_type, a_id, b_type, b_id = b_type, b_id, a_type, a_id
    cand, created = DuplicateCandidate.objects.get_or_create(
        kind=kind, record_a_type=a_type, record_a_id=a_id, record_b_type=b_type, record_b_id=b_id,
        defaults={"match_class": res["match_class"], "similarity_score": res["score"], "evidence": res["evidence"], "scan_run": run},
    )  # fmt: skip
    if not created and cand.review_status == DuplicateCandidate.ReviewStatus.PENDING:
        cand.match_class, cand.similarity_score, cand.evidence = res["match_class"], res["score"], res["evidence"]
        cand.save(update_fields=["match_class", "similarity_score", "evidence"])
    return created


def match_invoice(inv: Invoice, run: DuplicateScanRun | None = None) -> int:
    """Compare one invoice with every other and store candidates. Blocking keeps this near-linear: only invoices
    sharing a number, a vendor prefix, an amount or an image hash neighbourhood are compared."""
    from django.db.models import Q

    q = Q(pk=-1)
    if inv.invoice_number_normalized:
        q |= Q(invoice_number_normalized__startswith=inv.invoice_number_normalized[:3])
    if inv.vendor_normalized:
        q |= Q(vendor_normalized__startswith=inv.vendor_normalized[:4])
    if inv.amount is not None:
        q |= Q(amount__gte=inv.amount * 99 / 100, amount__lte=inv.amount * 101 / 100)
    me = _features(inv)
    created = 0
    others = Invoice.objects.exclude(pk=inv.pk).select_related("document")
    for other in others.filter(q) | others.exclude(document__phash="").filter(document__phash__isnull=False):
        res = matching.compare_invoices(me, _features(other))
        if res:
            created += _upsert_candidate("invoice", "invoice", inv.pk, "invoice", other.pk, res, run)
    # identical file bytes uploaded twice is the strongest possible signal
    if inv.document is not None:
        for twin in InvoiceDocument.objects.filter(sha256=inv.document.sha256).exclude(pk=inv.document.pk):
            twin_inv = Invoice.objects.filter(document=twin).first()
            if twin_inv:
                other = twin_inv
                ev = {"identical_file": True, "sha256": inv.document.sha256}
                created += _upsert_candidate(
                    "invoice",
                    "invoice",
                    inv.pk,
                    "invoice",
                    other.pk,
                    {"match_class": "exact", "score": 100.0, "evidence": ev},
                    run,
                )
    return created


def run_invoice_scan(run: DuplicateScanRun) -> int:
    n = 0
    for inv in Invoice.objects.select_related("document").order_by("pk"):
        n += match_invoice(inv, run)
    return n


def run_transaction_scan(run: DuplicateScanRun) -> int:
    """(1) same external transaction_id in more than one dataset, (2) rows flagged duplicate during import,
    (3) repeated payments: same sender/receiver/amount/type close in time (strong/potential) or in a regular series."""
    n = 0
    base = Transaction.objects.all()
    if run.dataset_id:
        base = base.filter(dataset_id=run.dataset_id)
    if base.count() > settings.DUPLICATE_MAX_ROWS:
        raise DuplicateError(f"Scan exceeds the limit of {settings.DUPLICATE_MAX_ROWS:,} transactions.")
    # (1) exact transaction ids across datasets
    from django.db.models import Count

    dup_ids = (Transaction.objects.values("transaction_id").annotate(n=Count("dataset", distinct=True)).filter(n__gt=1)
               .values_list("transaction_id", flat=True)[:5000])  # fmt: skip
    for tid in dup_ids:
        rows = list(base.filter(transaction_id=tid).order_by("id").values_list("id", "dataset_id"))
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                ev = {"transaction_id": tid, "datasets": [rows[i][1], rows[j][1]]}
                n += _upsert_candidate("transaction", "transaction", rows[i][0], "transaction", rows[j][0],
                                       {"match_class": "exact", "score": 100.0, "evidence": ev}, run)  # fmt: skip
    # (2) rows the importer flagged as duplicates of an earlier id
    for tx in base.filter(metadata__has_key="flagged_duplicate_of").only(
        "id", "dataset_id", "metadata", "transaction_id"
    ):
        original = Transaction.objects.filter(
            dataset_id=tx.dataset_id, transaction_id=tx.metadata["flagged_duplicate_of"]
        ).first()
        if original:
            ev = {
                "transaction_id": tx.metadata["flagged_duplicate_of"],
                "flagged_in_import": tx.metadata.get("flagged_in_import"),
            }
            n += _upsert_candidate(
                "transaction",
                "transaction",
                original.pk,
                "transaction",
                tx.pk,
                {"match_class": "exact", "score": 100.0, "evidence": ev},
                run,
            )
    # (3) repeated payments, per dataset
    for dataset_id in (
        base.order_by().values_list("dataset_id", flat=True).distinct()
    ):  # order_by(): the model default ordering would defeat DISTINCT
        df = pd.DataFrame.from_records(
            Transaction.objects.filter(dataset_id=dataset_id, receiver__isnull=False).values_list("id", "sender_id", "receiver_id", "amount", "tx_type", "occurred_at"),
            columns=["tx_id", "sender", "receiver", "amount", "tx_type", "occurred_at"],
        )  # fmt: skip
        if df.empty:
            continue
        df["amount"] = df["amount"].astype(float)
        df["t"] = (
            pd.to_datetime(df["occurred_at"], utc=True) - pd.Timestamp("1970-01-01", tz="UTC")
        ).dt.total_seconds()
        for c in matching.find_repeated_payments(df, CONFIG):
            n += _upsert_candidate("transaction", "transaction", c["a"], "transaction", c["b"], c, run)
    return n


def execute_scan(run_id: int) -> None:
    run = DuplicateScanRun.objects.get(pk=run_id)
    if run.status == DuplicateScanRun.Status.SUCCEEDED:
        return
    run.status = DuplicateScanRun.Status.RUNNING
    run.save(update_fields=["status"])
    try:
        n = run_invoice_scan(run) if run.kind == "invoice" else run_transaction_scan(run)
        run.candidates_found, run.status, run.finished_at = n, DuplicateScanRun.Status.SUCCEEDED, timezone.now()
        run.save()
        audit.log("duplicates.scan.completed", actor=run.created_by, resource_type="duplicate_scan", resource_id=run.pk,
                  changes={"kind": run.kind, "new_candidates": n})  # fmt: skip
    except Exception as exc:  # noqa: BLE001
        log.exception("duplicate scan %s failed", run_id)
        run.status, run.finished_at = DuplicateScanRun.Status.FAILED, timezone.now()
        run.error_message = str(exc)[:300] if isinstance(exc, DuplicateError) else "Unexpected error."
        run.save()


# ------------------------------------------------------------------------------------ human review
def review_candidate(cand: DuplicateCandidate, *, user: Any, decision: str, notes: str) -> DuplicateCandidate:
    if decision not in DECISIONS:
        raise DuplicateError(f"decision must be one of {sorted(DECISIONS)}")
    old = cand.review_status
    cand.review_status, cand.reviewed_by, cand.reviewed_at, cand.notes = decision, user, timezone.now(), notes[:2000]
    cand.save()
    audit.log("duplicates.reviewed", actor=user, resource_type="duplicate_candidate", resource_id=cand.pk,
              changes={"from": old, "to": decision, "match_class": cand.match_class, "score": cand.similarity_score})  # fmt: skip
    return cand


def correct_invoice_fields(inv: Invoice, *, user: Any, values: dict[str, Any]) -> Invoice:
    """Human correction of OCR output. Recomputes normalised fields, marks the document reviewed, and re-matches."""
    changed: dict[str, Any] = {}
    for key in ("vendor_name", "invoice_number", "currency"):
        if key in values and values[key] != getattr(inv, key):
            changed[key] = [getattr(inv, key), values[key]]
            setattr(inv, key, values[key])
    if "amount" in values:
        new = None if values["amount"] in (None, "") else normalize.parse_amount(str(values["amount"]))
        if new != inv.amount:
            changed["amount"] = [str(inv.amount), str(new)]
            inv.amount = new
    if "invoice_date" in values:
        new_d = values["invoice_date"]
        if new_d != inv.invoice_date:
            changed["invoice_date"] = [str(inv.invoice_date), str(new_d)]
            inv.invoice_date = new_d
    inv.vendor_normalized = normalize.normalize_vendor(inv.vendor_name)
    inv.invoice_number_normalized = normalize.normalize_invoice_number(inv.invoice_number)
    inv.verified_by, inv.verified_at = user, timezone.now()
    inv.save()
    if inv.document is not None:
        inv.document.status = InvoiceDocument.Status.REVIEWED
        inv.document.save(update_fields=["status"])
    audit.log("invoice.fields_corrected", actor=user, resource_type="invoice", resource_id=inv.pk, changes=changed)
    match_invoice(inv)
    return inv
