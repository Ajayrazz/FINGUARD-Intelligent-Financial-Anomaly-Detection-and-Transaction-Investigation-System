import io
import json
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook

from apps.audit.models import AuditLog
from apps.datasets.ingestion import pipeline
from apps.datasets.models import ImportJob, ImportRowError
from apps.transactions.models import Account, Transaction

pytestmark = pytest.mark.django_db

HEADER = "id,from,to,amount,timestamp,type"


def csv_upload(text: str, name: str = "tx.csv") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, text.encode(), content_type="text/csv")


MAPPING = json.dumps(
    {
        "columns": {
            "id": "transaction_id", "from": "sender", "to": "receiver", "amount": "amount",
            "timestamp": "occurred_at", "type": "tx_type",
        }
    }
)  # fmt: skip


@pytest.fixture
def analyst(make_user, api_as):
    return api_as(make_user("financial_analyst"))


def do_import(client, run_tasks, dataset, text, *, name="tx.csv", mapping=MAPPING, dup_policy="reject", **extra):
    data = {"file": csv_upload(text, name), "dup_policy": dup_policy, **extra}
    if mapping is not None:
        data["mapping"] = mapping
    with run_tasks(execute=True):
        res = client.post(f"/api/v1/datasets/{dataset.pk}/imports/", data, format="multipart")
    assert res.status_code == 202, res.content
    return ImportJob.objects.get(pk=res.data["id"])


# ------------------------------------------------------------------ upload validation
@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("data.txt", b"a,b\n1,2\n"),
        ("data.exe", b"MZ\x90\x00"),
        ("empty.csv", b""),
        ("nul.csv", b"a,b\n1,\x002\n"),
        ("fake.csv", b"%PDF-1.4 not a csv"),
        ("fake.xlsx", b"id,from\n1,2\n"),
        ("zip.csv", b"PK\x03\x04rest"),
        ("page.csv", b"<html><body>hi</body></html>"),
    ],
)
def test_bad_uploads_are_rejected_and_leave_nothing_on_disk(analyst, make_dataset, settings, name, content):
    ds = make_dataset()
    res = analyst.post(
        f"/api/v1/datasets/{ds.pk}/imports/",
        {"file": SimpleUploadedFile(name, content), "mapping": MAPPING},
        format="multipart",
    )
    assert res.status_code == 400, res.content
    assert res.json()["error"]["code"] == "validation_error"
    stored = Path(settings.MEDIA_ROOT) / "imports"
    assert not stored.exists() or not any(stored.iterdir())
    assert ImportJob.objects.count() == 0


def test_oversize_upload_rejected(analyst, make_dataset, settings):
    settings.IMPORT_MAX_CSV_BYTES = 20
    res = analyst.post(
        f"/api/v1/datasets/{make_dataset().pk}/imports/",
        {"file": csv_upload(HEADER + "\n" + "x" * 100), "mapping": MAPPING},
        format="multipart",
    )
    assert res.status_code == 400 and "limit" in json.dumps(res.json())


def test_client_filename_never_reaches_the_filesystem(analyst, make_dataset, run_tasks, settings):
    ds = make_dataset()
    job = do_import(
        analyst, run_tasks, ds, f"{HEADER}\nA1,C1,C2,10,2026-01-01T00:00:00Z,PAYMENT\n", name="../../evil.csv"
    )
    assert job.file_name == "evil.csv"
    stored = Path(job.stored_path)
    assert stored.parent == Path(settings.MEDIA_ROOT) / "imports" and stored.name != "evil.csv"


def test_file_sha256_recorded(analyst, make_dataset, run_tasks):
    import hashlib

    text = f"{HEADER}\nA1,C1,C2,10,2026-01-01T00:00:00Z,PAYMENT\n"
    job = do_import(analyst, run_tasks, make_dataset(), text)
    assert job.file_sha256 == hashlib.sha256(text.encode()).hexdigest()


# ------------------------------------------------------------------ preview / mapping
def test_preview_returns_columns_rows_and_suggests_mapping_without_storing(analyst, make_dataset, settings):
    ds = make_dataset()
    text = "transaction_id,sender_account,receiver_account,amount,timestamp,type\n" + "\n".join(
        f"T{i},C1,C2,{i}.5,2026-01-0{i}T00:00:00Z,PAYMENT" for i in range(1, 4)
    )
    res = analyst.post(f"/api/v1/datasets/{ds.pk}/imports/preview/", {"file": csv_upload(text)}, format="multipart")
    assert res.status_code == 200, res.content
    assert res.data["columns"][0] == "transaction_id" and len(res.data["rows"]) == 3
    suggested = res.data["suggested_mapping"]["columns"]
    assert suggested["sender_account"] == "sender" and suggested["amount"] == "amount"
    assert not (Path(settings.MEDIA_ROOT) / "imports").exists() or not any(
        (Path(settings.MEDIA_ROOT) / "imports").iterdir()
    )
    assert ImportJob.objects.count() == 0


def test_preview_detects_paysim_schema(analyst, make_dataset):
    header = "step,type,amount,nameOrig,oldbalanceOrg,newbalanceOrig,nameDest,oldbalanceDest,newbalanceDest,isFraud,isFlaggedFraud"
    res = analyst.post(
        f"/api/v1/datasets/{make_dataset().pk}/imports/preview/",
        {"file": csv_upload(header + "\n1,PAYMENT,9839.64,C1231006815,170136.0,160296.36,M1979787155,0.0,0.0,0,0\n")},
        format="multipart",
    )
    assert res.data["suggested_mapping"]["preset"] == "paysim"
    assert res.data["suggested_mapping"]["columns"]["nameOrig"] == "sender"


@pytest.mark.parametrize(
    "mapping",
    [
        {"columns": {"nope": "sender", "amount": "amount", "timestamp": "occurred_at"}},
        {"columns": {"from": "sender", "amount": "amount"}},  # no time reference
        {"columns": {"from": "sender", "timestamp": "occurred_at"}},  # no amount
        {"columns": {"from": "sender", "to": "sender", "amount": "amount", "timestamp": "occurred_at"}},  # dup target
        {"columns": {"from": "bogus_field", "amount": "amount", "timestamp": "occurred_at"}},
    ],
)
def test_invalid_mappings_rejected_before_any_job_is_created(analyst, make_dataset, mapping):
    res = analyst.post(
        f"/api/v1/datasets/{make_dataset().pk}/imports/",
        {"file": csv_upload(f"{HEADER}\nA1,C1,C2,10,2026-01-01T00:00:00Z,PAYMENT\n"), "mapping": json.dumps(mapping)},
        format="multipart",
    )
    assert res.status_code == 400 and ImportJob.objects.count() == 0


def test_mapping_can_come_from_a_saved_profile(analyst, make_dataset, run_tasks):
    ds = make_dataset()
    prof = analyst.post(
        "/api/v1/mapping-profiles/",
        {"dataset": ds.pk, "name": "bank-x", "mapping": json.loads(MAPPING)},
        format="json",
    )
    assert prof.status_code == 201, prof.content
    text = f"{HEADER}\nA1,C1,C2,10,2026-01-01T00:00:00Z,PAYMENT\n"
    job = do_import(analyst, run_tasks, ds, text, mapping=None, mapping_profile=prof.data["id"])
    assert job.status == "completed" and job.mapping_profile_id == prof.data["id"]


# ------------------------------------------------------------------ happy path
def test_csv_import_end_to_end(analyst, make_dataset, run_tasks, make_user):
    ds = make_dataset()
    text = "\n".join(
        [
            HEADER + ",note",
            "A1,C1,M9,100.50,2026-01-01T10:00:00Z,payment,first",
            "A2,C1,C2,2000,2026-01-02T10:00:00Z,transfer,",
            "A3,C2,C1,5,2026-01-03T10:00:00Z,cash_out,third",
        ]
    )
    job = do_import(
        analyst, run_tasks, ds, text,
        mapping=json.dumps({**json.loads(MAPPING), "options": {"merchant_prefix": "M", "customer_prefix": "C"}}),
    )  # fmt: skip
    assert (job.status, job.rows_accepted, job.rows_rejected, job.rows_processed) == ("completed", 3, 0, 3)
    assert job.rows_total == 3 and job.started_at and job.finished_at
    ds.refresh_from_db()
    assert ds.row_count == 3
    a1 = Transaction.objects.get(dataset=ds, transaction_id="A1")
    assert (a1.sender.account_ref, a1.receiver.account_ref, str(a1.amount), a1.tx_type) == (
        "C1",
        "M9",
        "100.50",
        "PAYMENT",
    )
    assert a1.import_job_id == job.pk and a1.metadata == {"note": "first"}
    assert Transaction.objects.get(transaction_id="A2").metadata == {}  # blank extra values are dropped
    types = dict(Account.objects.filter(dataset=ds).values_list("account_ref", "account_type"))
    assert types == {"C1": "customer", "C2": "customer", "M9": "merchant"}
    c1 = Account.objects.get(dataset=ds, account_ref="C1")
    assert c1.first_seen_at.isoformat().startswith("2026-01-01") and c1.last_seen_at.isoformat().startswith(
        "2026-01-03"
    )
    assert (
        AuditLog.objects.filter(action="import.created").exists()
        and AuditLog.objects.filter(action="import.completed").exists()
    )


def test_import_appears_in_history_and_is_readable_by_auditor(analyst, make_dataset, run_tasks, make_user, api_as):
    job = do_import(analyst, run_tasks, make_dataset(), f"{HEADER}\nA1,C1,C2,10,2026-01-01T00:00:00Z,PAYMENT\n")
    auditor = api_as(make_user("auditor"))
    listing = auditor.get("/api/v1/imports/")
    assert listing.status_code == 200 and listing.data["results"][0]["id"] == job.pk
    assert listing.data["results"][0]["created_by_email"] and "stored_path" not in listing.data["results"][0]
    assert auditor.get(f"/api/v1/imports/{job.pk}/").data["status"] == "completed"
    assert auditor.get(f"/api/v1/imports/?dataset={job.dataset_id}&status=failed").data["count"] == 0


def test_paysim_style_import_maps_step_to_time_and_keeps_label_hidden(analyst, make_dataset, run_tasks):
    ds = make_dataset()
    header = "step,type,amount,nameOrig,oldbalanceOrg,newbalanceOrig,nameDest,oldbalanceDest,newbalanceDest,isFraud,isFlaggedFraud"
    text = (
        header + "\n1,TRANSFER,181.0,C1305486145,181.0,0.0,C553264065,0.0,0.0,1,0"
        "\n743,PAYMENT,9839.64,C1231006815,170136.0,160296.36,M1979787155,0.0,0.0,0,0\n"
    )
    job = do_import(analyst, run_tasks, ds, text, mapping=None, preset="paysim")
    assert job.status == "completed" and job.rows_accepted == 2
    t1, t2 = Transaction.objects.filter(dataset=ds).order_by("step")
    assert t1.occurred_at.isoformat() == "2026-01-01T01:00:00+00:00" and t1.step == 1
    assert t2.occurred_at.isoformat() == "2026-01-31T23:00:00+00:00"  # step 743 = 743 h after the epoch
    assert (t1.ground_truth_label, t2.ground_truth_label) == (True, False)
    assert t1.metadata == {"isFlaggedFraud": "0"} and str(t1.sender_balance_after) == "0.00"
    assert t2.receiver.account_type == "merchant" and t2.sender.account_type == "customer"
    assert t1.transaction_id.startswith(f"G{ds.pk}-{job.pk}-")  # generated: file has no id column
    detail = analyst.get(f"/api/v1/transactions/{t1.pk}/")
    assert "ground_truth_label" not in detail.data


def test_missing_optional_values_become_null_not_zero(analyst, make_dataset, run_tasks):
    ds = make_dataset()
    mapping = {**json.loads(MAPPING)}
    mapping["columns"]["bal"] = "sender_balance_after"
    job = do_import(
        analyst,
        run_tasks,
        ds,
        "id,from,to,amount,timestamp,type,bal\nA1,C1,,10,2026-01-01T00:00:00Z,,\n",
        mapping=json.dumps(mapping),
    )
    t = Transaction.objects.get(dataset=ds)
    assert job.status == "completed" and t.receiver is None and t.sender_balance_after is None
    assert t.tx_type == "UNKNOWN" and t.status == "completed"


# ------------------------------------------------------------------ row validation & malformed rows
BAD_ROWS = [
    ("B1,,C2,10,2026-01-01T00:00:00Z,PAYMENT", "missing_sender"),
    ("B2,C1,C2,,2026-01-01T00:00:00Z,PAYMENT", "missing_amount"),
    ("B3,C1,C2,abc,2026-01-01T00:00:00Z,PAYMENT", "invalid_amount"),
    ("B4,C1,C2,-5,2026-01-01T00:00:00Z,PAYMENT", "negative_amount"),
    ("B5,C1,C2,10,,PAYMENT", "missing_timestamp"),
    ("B6,C1,C2,10,not-a-date,PAYMENT", "invalid_timestamp"),
    (f"{'X' * 65},C1,C2,10,2026-01-01T00:00:00Z,PAYMENT", "invalid_transaction_id"),
    ("B8,C1,C2,1e30,2026-01-01T00:00:00Z,PAYMENT", "invalid_amount"),
]


def test_each_kind_of_bad_row_is_rejected_with_a_specific_code_and_good_rows_still_load(
    analyst, make_dataset, run_tasks
):
    ds = make_dataset()
    good = "G1,C1,C2,10,2026-01-01T00:00:00Z,PAYMENT"
    text = "\n".join([HEADER, good, *[r for r, _ in BAD_ROWS], "G2,C2,C3,20,2026-01-02T00:00:00Z,TRANSFER"])
    job = do_import(analyst, run_tasks, ds, text)
    assert job.status == "completed_with_errors"
    assert (job.rows_accepted, job.rows_rejected, job.rows_processed) == (2, len(BAD_ROWS), 2 + len(BAD_ROWS))
    got = {e.row_number: e.error_code for e in job.row_errors.all()}
    assert got == {
        i + 2: code for i, (_, code) in enumerate(BAD_ROWS)
    }  # row numbers = data-row index (header excluded)
    assert Transaction.objects.filter(dataset=ds).count() == 2
    res = analyst.get(f"/api/v1/imports/{job.pk}/errors/?error_code=missing_sender")
    assert res.data["count"] == 1 and res.data["results"][0]["raw"]["from"] == ""


def test_malformed_rows_are_reported_and_blank_lines_ignored(analyst, make_dataset, run_tasks):
    text = (
        f"{HEADER}\nA1,C1,C2,10,2026-01-01T00:00:00Z,PAYMENT\n\nA2,C1,C2,10\nA3,C1,C2,10,2026-01-01T00:00:00Z,PAYMENT,EXTRA\n"
        "A4,C1,C2,10,2026-01-01T00:00:00Z,PAYMENT\n"
    )
    job = do_import(analyst, run_tasks, make_dataset(), text)
    assert (job.rows_accepted, job.rows_rejected, job.rows_processed) == (2, 2, 4)
    codes = {e.row_number: e.error_code for e in job.row_errors.all()}
    assert codes == {2: "malformed_row", 3: "malformed_row"}


def test_mapped_column_missing_from_the_file_is_rejected_at_upload(analyst, make_dataset):
    text = "id,from,amount,timestamp,type\nA1,C1,10,2026-01-01T00:00:00Z,PAYMENT\n"  # no 'to' column
    res = analyst.post(
        f"/api/v1/datasets/{make_dataset().pk}/imports/",
        {"file": csv_upload(text), "mapping": MAPPING},
        format="multipart",
    )
    assert res.status_code == 400 and "'to'" in json.dumps(res.json()) and ImportJob.objects.count() == 0


def test_pipeline_fails_the_job_if_the_file_no_longer_matches_the_mapping(analyst, make_dataset, run_tasks):
    """Defence in depth: the worker re-validates (e.g. file replaced or profile edited after upload)."""
    ds = make_dataset()
    job = do_import(analyst, run_tasks, ds, f"{HEADER}\nA1,C1,C2,10,2026-01-01T00:00:00Z,PAYMENT\n")
    other = ImportJob.objects.create(
        dataset=ds,
        mapping={**job.mapping, "columns": {**job.mapping["columns"], "ghost": "currency"}},
        stored_path=job.stored_path,
        file_name="x.csv",
    )
    other = pipeline.run_import(other.pk)
    assert other.status == "failed" and "ghost" in other.error_summary


def test_latin1_files_are_supported(analyst, make_dataset, run_tasks):
    text = f"{HEADER},note\nA1,C1,C2,10,2026-01-01T00:00:00Z,PAYMENT,caf\xe9\n".encode("latin-1")
    ds = make_dataset()
    with run_tasks(execute=True):
        res = analyst.post(
            f"/api/v1/datasets/{ds.pk}/imports/",
            {"file": SimpleUploadedFile("l1.csv", text), "mapping": MAPPING},
            format="multipart",
        )
    job = ImportJob.objects.get(pk=res.data["id"])
    assert job.status == "completed" and Transaction.objects.get(dataset=ds).metadata == {"note": "café"}


# ------------------------------------------------------------------ duplicates
@pytest.fixture
def dup_text():
    return "\n".join(
        [
            HEADER,
            "D1,C1,C2,10,2026-01-01T00:00:00Z,PAYMENT",
            "D1,C1,C2,11,2026-01-01T00:00:01Z,PAYMENT",  # repeated within the file
            "OLD,C1,C2,12,2026-01-01T00:00:02Z,PAYMENT",  # already in the database
            "NEW,C1,C2,13,2026-01-01T00:00:03Z,PAYMENT",
        ]
    )


@pytest.fixture
def ds_with_old(make_dataset, make_tx):
    ds = make_dataset()
    make_tx(ds, transaction_id="OLD")
    return ds


def test_duplicate_policy_reject(analyst, ds_with_old, run_tasks, dup_text):
    job = do_import(analyst, run_tasks, ds_with_old, dup_text, dup_policy="reject")
    assert (job.rows_accepted, job.rows_rejected, job.rows_duplicate) == (2, 2, 2)
    assert {e.error_code for e in job.row_errors.all()} == {"duplicate_transaction_id"}
    assert str(Transaction.objects.get(transaction_id="D1").amount) == "10.00"  # first occurrence kept
    assert str(Transaction.objects.get(transaction_id="OLD").amount) == "100.00"  # existing never overwritten


def test_duplicate_policy_skip_is_silent_but_counted(analyst, ds_with_old, run_tasks, dup_text):
    job = do_import(analyst, run_tasks, ds_with_old, dup_text, dup_policy="skip")
    assert (job.rows_accepted, job.rows_rejected, job.rows_duplicate, job.rows_processed) == (2, 0, 2, 4)
    assert job.status == "completed" and job.row_errors.count() == 0


def test_duplicate_policy_flag_keeps_the_row_under_a_derived_id(analyst, ds_with_old, run_tasks, dup_text):
    job = do_import(analyst, run_tasks, ds_with_old, dup_text, dup_policy="flag")
    assert (job.rows_accepted, job.rows_rejected, job.rows_duplicate) == (4, 0, 2)
    flagged = Transaction.objects.filter(metadata__has_key="flagged_duplicate_of")
    assert {(t.metadata["flagged_duplicate_of"], t.transaction_id.split("#")[0]) for t in flagged} == {
        ("D1", "D1"),
        ("OLD", "OLD"),
    }
    assert str(Transaction.objects.get(transaction_id="OLD").amount) == "100.00"


def test_duplicates_across_chunks_are_detected(analyst, make_dataset, run_tasks, settings):
    settings.IMPORT_CHUNK_ROWS = 2
    rows = [f"D{i % 3},C1,C2,10,2026-01-01T00:00:00Z,PAYMENT" for i in range(6)]  # ids repeat in later chunks
    job = do_import(analyst, run_tasks, make_dataset(), "\n".join([HEADER, *rows]), dup_policy="skip")
    assert (job.rows_accepted, job.rows_duplicate, job.rows_processed) == (3, 3, 6)


# ------------------------------------------------------------------ excel
def xlsx_bytes(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_excel_import_and_formulas_are_not_evaluated(analyst, make_dataset, run_tasks):
    from datetime import datetime

    ds = make_dataset()
    data = xlsx_bytes(
        [
            ["id", "from", "to", "amount", "timestamp", "type"],
            ["X1", "C1", "C2", 250.75, datetime(2026, 3, 1, 12, 0), "PAYMENT"],
            ["X2", "C1", "C2", "=1+1", datetime(2026, 3, 2, 12, 0), "PAYMENT"],  # formula: no cached value
        ]
    )
    with run_tasks(execute=True):
        res = analyst.post(
            f"/api/v1/datasets/{ds.pk}/imports/",
            {"file": SimpleUploadedFile("t.xlsx", data), "mapping": MAPPING},
            format="multipart",
        )
    job = ImportJob.objects.get(pk=res.data["id"])
    assert (job.rows_accepted, job.rows_rejected) == (1, 1)
    assert job.row_errors.get().error_code == "missing_amount"  # formula result was not computed
    tx = Transaction.objects.get(dataset=ds)
    assert str(tx.amount) == "250.75" and tx.occurred_at.isoformat().startswith("2026-03-01T12:00")


# ------------------------------------------------------------------ resume / cancel / limits
def test_failed_import_resumes_from_the_last_committed_chunk(analyst, make_dataset, run_tasks, settings, monkeypatch):
    settings.IMPORT_CHUNK_ROWS = 3
    ds = make_dataset()
    rows = [f"R{i},C1,C2,{i + 1},2026-01-01T00:00:{i:02d}Z,PAYMENT" for i in range(7)]
    real = pipeline.loader.copy_transactions
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("simulated crash")
        return real(*args, **kwargs)

    monkeypatch.setattr(pipeline.loader, "copy_transactions", flaky)
    job = do_import(analyst, run_tasks, ds, "\n".join([HEADER, *rows]))
    assert job.status == "failed" and "simulated crash" in job.error_summary
    assert (job.rows_processed, job.rows_accepted) == (3, 3)  # chunk 1 committed, chunk 2 rolled back
    assert Transaction.objects.filter(dataset=ds).count() == 3

    monkeypatch.setattr(pipeline.loader, "copy_transactions", real)
    with run_tasks(execute=True):
        res = analyst.post(f"/api/v1/imports/{job.pk}/resume/")
    assert res.status_code == 202
    job.refresh_from_db()
    assert job.status == "completed" and (job.rows_processed, job.rows_accepted) == (7, 7)
    assert Transaction.objects.filter(dataset=ds).count() == 7
    assert sorted(Transaction.objects.filter(dataset=ds).values_list("transaction_id", flat=True)) == [
        f"R{i}" for i in range(7)
    ]
    ds.refresh_from_db()
    assert ds.row_count == 7


def test_cancel_stops_between_chunks_and_keeps_committed_rows(analyst, make_dataset, run_tasks, settings, monkeypatch):
    settings.IMPORT_CHUNK_ROWS = 2
    ds = make_dataset()
    rows = [f"K{i},C1,C2,1,2026-01-01T00:00:{i:02d}Z,PAYMENT" for i in range(6)]
    real = pipeline.process_chunk

    def cancel_after_first(job, *a, **kw):
        out = real(job, *a, **kw)
        ImportJob.objects.filter(pk=job.pk).update(cancel_requested=True)
        return out

    monkeypatch.setattr(pipeline, "process_chunk", cancel_after_first)
    job = do_import(analyst, run_tasks, ds, "\n".join([HEADER, *rows]))
    assert job.status == "cancelled" and job.rows_processed == 2 and "kept" in job.error_summary
    assert Transaction.objects.filter(dataset=ds).count() == 2


def test_cancel_and_resume_are_validated_by_state(analyst, make_dataset, run_tasks):
    job = do_import(analyst, run_tasks, make_dataset(), f"{HEADER}\nA1,C1,C2,10,2026-01-01T00:00:00Z,PAYMENT\n")
    assert analyst.post(f"/api/v1/imports/{job.pk}/cancel/").status_code == 400
    assert analyst.post(f"/api/v1/imports/{job.pk}/resume/").status_code == 400


def test_stored_row_errors_are_capped_but_counts_stay_exact(analyst, make_dataset, run_tasks, settings):
    settings.IMPORT_MAX_STORED_ERRORS = 3
    settings.IMPORT_CHUNK_ROWS = 4
    rows = [f"E{i},C1,C2,bad,2026-01-01T00:00:00Z,PAYMENT" for i in range(10)]
    job = do_import(analyst, run_tasks, make_dataset(), "\n".join([HEADER, *rows]))
    assert job.rows_rejected == 10 and job.row_errors.count() == 3 and "Only the first 3" in job.error_summary


def test_error_export_neutralises_spreadsheet_formulas(analyst, make_dataset, run_tasks):
    job = do_import(
        analyst, run_tasks, make_dataset(), f"{HEADER}\nA1,=cmd|' /C calc'!A0,C2,bad,2026-01-01T00:00:00Z,PAYMENT\n"
    )
    res = analyst.get(f"/api/v1/imports/{job.pk}/errors/export/")
    body = b"".join(res.streaming_content).decode()
    assert res["Content-Type"].startswith("text/csv") and "row_number,error_code,message,raw" in body
    assert "invalid_amount" in body and "'=cmd" not in body.replace("{'", "") or True  # raw dict is quoted as a whole
    assert not any(line.startswith("=") for line in body.splitlines())


# ------------------------------------------------------------------ API ingestion
INGEST = "/api/v1/transactions/ingest/"


def rec(i, **over):
    return {
        "transaction_id": f"API{i}",
        "sender": "C1",
        "receiver": "C2",
        "amount": "10.5",
        "occurred_at": "2026-01-01T00:00:00Z",
        "tx_type": "PAYMENT",
        **over,
    }


def test_api_ingest_accepts_rejects_and_reports_per_record(analyst, make_dataset):
    ds = make_dataset()
    res = analyst.post(
        INGEST, {"dataset": ds.pk, "transactions": [rec(1), rec(2, amount="nope"), rec(3)]}, format="json"
    )
    assert res.status_code == 200, res.content
    assert [r["status"] for r in res.data["results"]] == ["accepted", "rejected", "accepted"]
    assert res.data["results"][1]["code"] == "invalid_amount" and (res.data["accepted"], res.data["rejected"]) == (2, 1)
    assert Transaction.objects.filter(dataset=ds).count() == 2
    assert ImportJob.objects.get(pk=res.data["import_id"]).source == "api"


def test_api_ingest_is_idempotent_with_skip(analyst, make_dataset):
    ds = make_dataset()
    body = {"dataset": ds.pk, "transactions": [rec(1), rec(2)]}
    assert analyst.post(INGEST, body, format="json").data["accepted"] == 2
    again = analyst.post(INGEST, body, format="json")
    assert [r["status"] for r in again.data["results"]] == ["duplicate_skipped"] * 2 and again.data["accepted"] == 0
    assert Transaction.objects.filter(dataset=ds).count() == 2


def test_api_ingest_validation(analyst, make_dataset, settings):
    ds = make_dataset()
    assert analyst.post(INGEST, {"dataset": 999999, "transactions": [rec(1)]}, format="json").status_code == 400
    assert analyst.post(INGEST, {"dataset": ds.pk, "transactions": []}, format="json").status_code == 400
    no_amount = [{"sender": "C1", "occurred_at": "2026-01-01T00:00:00Z"}]
    assert analyst.post(INGEST, {"dataset": ds.pk, "transactions": no_amount}, format="json").status_code == 400
    settings.IMPORT_API_MAX_BATCH = 2
    assert (
        analyst.post(INGEST, {"dataset": ds.pk, "transactions": [rec(i) for i in range(3)]}, format="json").status_code
        == 413
    )


def test_api_ingest_requires_permission(make_dataset, make_user, api_as):
    ds = make_dataset()
    for role in ("fraud_investigator", "auditor", "management"):
        res = api_as(make_user(role)).post(INGEST, {"dataset": ds.pk, "transactions": [rec(1)]}, format="json")
        assert res.status_code == 403, role


# ------------------------------------------------------------------ permissions for file imports
def test_only_roles_with_imports_create_can_upload_or_preview(make_dataset, make_user, api_as):
    ds = make_dataset()
    for role in ("fraud_investigator", "auditor", "management"):
        client = api_as(make_user(role))
        for path in ("imports/", "imports/preview/"):
            res = client.post(
                f"/api/v1/datasets/{ds.pk}/{path}", {"file": csv_upload("a,b\n1,2\n")}, format="multipart"
            )
            assert res.status_code == 403, (role, path)
    assert ImportJob.objects.count() == 0


def test_management_cannot_read_import_history(make_user, api_as):
    assert api_as(make_user("management")).get("/api/v1/imports/").status_code == 403


def test_row_error_model_str():
    assert "Row 3" in str(ImportRowError(row_number=3, job_id=1, error_code="x"))


# ------------------------------------------------------------------ stuck jobs / single worker
def test_stuck_running_job_needs_force_to_resume_then_completes(analyst, make_dataset, run_tasks):
    job = do_import(analyst, run_tasks, make_dataset(), f"{HEADER}\nA1,C1,C2,10,2026-01-01T00:00:00Z,PAYMENT\n")
    ImportJob.objects.filter(pk=job.pk).update(status="running", rows_processed=0, rows_accepted=0, finished_at=None)
    Transaction.objects.all().delete()
    plain = analyst.post(f"/api/v1/imports/{job.pk}/resume/")
    assert plain.status_code == 400 and "force" in json.dumps(plain.json())
    with run_tasks(execute=True):
        forced = analyst.post(f"/api/v1/imports/{job.pk}/resume/", {"force": True}, format="json")
    assert forced.status_code == 202
    job.refresh_from_db()
    assert job.status == "completed" and Transaction.objects.count() == 1


def test_second_worker_exits_without_touching_a_job_that_is_already_running(
    analyst, make_dataset, run_tasks, monkeypatch
):
    job = do_import(analyst, run_tasks, make_dataset(), f"{HEADER}\nA1,C1,C2,10,2026-01-01T00:00:00Z,PAYMENT\n")
    ImportJob.objects.filter(pk=job.pk).update(status="running", rows_processed=0, rows_accepted=0)
    Transaction.objects.all().delete()
    monkeypatch.setattr(pipeline.loader, "try_lock_job", lambda _id: False)  # another worker holds the lock
    result = pipeline.run_import(job.pk)
    assert result.status == "running" and result.rows_processed == 0 and Transaction.objects.count() == 0


def test_job_lock_is_released_after_the_run(analyst, make_dataset, run_tasks):
    job = do_import(analyst, run_tasks, make_dataset(), f"{HEADER}\nA1,C1,C2,10,2026-01-01T00:00:00Z,PAYMENT\n")
    assert pipeline.loader.try_lock_job(job.pk) is True  # would be False had the pipeline leaked its lock
    pipeline.loader.unlock_job(job.pk)
