"""Import pipeline: source -> clean -> duplicate policy -> bulk load, one transaction per chunk.

Restartability: counters and rows are committed together per chunk, so `rows_processed` is an exact checkpoint;
`run_import(job)` on a failed/cancelled job skips that many rows and continues.
"""

import json
import logging
from dataclasses import dataclass, field

import pandas as pd
from django.conf import settings
from django.db import connection, transaction
from django.db.models import F
from django.utils import timezone

from apps.audit import services as audit

from ..models import Dataset, ImportJob, ImportRowError
from ..realtime import publish_progress
from . import loader
from .cleaning import RowError, clean_chunk
from .mapping import normalise_mapping, validate_mapping
from .sources import CsvSource, ExcelSource, IngestionSource, RawChunk

log = logging.getLogger(__name__)


@dataclass
class ChunkResult:
    consumed: int = 0
    accepted: int = 0
    duplicates: int = 0
    errors: list[RowError] = field(default_factory=list)
    accepted_rows: set[int] = field(default_factory=set)
    skipped_rows: list[int] = field(default_factory=list)
    flagged_rows: list[int] = field(default_factory=list)


def build_source(job: ImportJob) -> IngestionSource:
    opts = normalise_mapping(job.mapping)["options"]
    if job.stored_path.endswith(".xlsx"):
        return ExcelSource(job.stored_path, opts.get("sheet"))
    return CsvSource(job.stored_path, opts.get("encoding", "utf-8-sig"))


def _apply_duplicate_policy(job: ImportJob, good: pd.DataFrame, res: ChunkResult) -> pd.DataFrame:
    if good.empty:
        return good
    repeated = good.duplicated("transaction_id", keep="first")
    existing = loader.existing_transaction_ids(job.dataset_id, list(good["transaction_id"].unique()))
    in_db = good["transaction_id"].isin(existing)
    is_dup = repeated | in_db
    res.duplicates = int(is_dup.sum())
    if not res.duplicates:
        return good
    rows = good.loc[is_dup]
    if job.dup_policy == "reject":
        for _, r in rows.iterrows():
            where = "already exists in this dataset" if r["transaction_id"] in existing else "repeated in the file"
            res.errors.append(
                RowError(int(r["row_number"]), "duplicate_transaction_id", f"Duplicate transaction ID ({where})")
            )
        return good.loc[~is_dup].reset_index(drop=True)
    if job.dup_policy == "skip":
        res.skipped_rows = [int(x) for x in rows["row_number"]]
        return good.loc[~is_dup].reset_index(drop=True)
    # flag: import under a derived id so nothing is lost, and record the link in metadata
    good = good.copy()
    for idx in rows.index:
        original = good.at[idx, "transaction_id"]
        row_no = int(good.at[idx, "row_number"])
        meta = json.loads(good.at[idx, "metadata"] or "{}")
        meta.update({"flagged_duplicate_of": original, "flagged_in_import": job.pk})
        good.at[idx, "metadata"] = json.dumps(meta)
        good.at[idx, "transaction_id"] = f"{original[:40]}#dup{job.pk}-{row_no}"
        res.flagged_rows.append(row_no)
    return good


def process_chunk(job: ImportJob, chunk: RawChunk, mapping: dict, *, stored_errors: int) -> ChunkResult:
    """Clean + persist one chunk atomically and update job counters in the same transaction."""
    res = ChunkResult(consumed=chunk.consumed)
    remaining_raw = max(0, settings.IMPORT_MAX_STORED_ERRORS - stored_errors)
    with transaction.atomic():
        loader.lock_dataset(job.dataset_id)
        good, errors = clean_chunk(
            chunk.frame, mapping, chunk.first_row_number, f"G{job.dataset_id}-{job.pk}", remaining_raw
        )
        res.errors.extend(errors)
        width = len(chunk.frame.columns)
        for row_no, cells in chunk.malformed:
            res.errors.append(
                RowError(
                    row_no,
                    "malformed_row",
                    f"Expected {width} columns, found {len(cells)}",
                    {"cells": cells[:50]},
                )
            )
        good = _apply_duplicate_policy(job, good, res)
        res.accepted = loader.copy_transactions(job.dataset_id, job.pk, good, mapping["options"])
        res.accepted_rows = {int(x) for x in good["row_number"]} if not good.empty else set()

        to_store = res.errors[: max(0, settings.IMPORT_MAX_STORED_ERRORS - stored_errors)]
        ImportRowError.objects.bulk_create(
            [
                ImportRowError(job=job, row_number=e.row_number, raw=e.raw, error_code=e.code, message=e.message)
                for e in to_store
            ]
        )
        ImportJob.objects.filter(pk=job.pk).update(
            rows_processed=F("rows_processed") + res.consumed,
            rows_accepted=F("rows_accepted") + res.accepted,
            rows_rejected=F("rows_rejected") + len(res.errors),
            rows_duplicate=F("rows_duplicate") + res.duplicates,
        )
        Dataset.objects.filter(pk=job.dataset_id).update(row_count=F("row_count") + res.accepted)
    return res


def _finish(job: ImportJob, status: str, summary: str = "") -> ImportJob:
    ImportJob.objects.filter(pk=job.pk).update(status=status, finished_at=timezone.now(), error_summary=summary)
    job.refresh_from_db()
    publish_progress(job)
    audit.log(
        f"import.{status}", actor=job.created_by, actor_email="" if job.created_by else "system",
        resource_type="import", resource_id=job.pk,
        changes={"accepted": job.rows_accepted, "rejected": job.rows_rejected, "duplicates": job.rows_duplicate},
    )  # fmt: skip
    return job


def run_import(job_id: int, source: IngestionSource | None = None) -> ImportJob:
    """Run (or continue) an import. A per-job advisory lock guarantees a single active worker, so a duplicate
    task (e.g. a forced resume of a job whose worker is actually alive) exits without touching anything."""
    job = ImportJob.objects.select_related("dataset", "created_by").get(pk=job_id)
    if job.status in {ImportJob.Status.COMPLETED, ImportJob.Status.COMPLETED_WITH_ERRORS}:
        return job
    if not loader.try_lock_job(job_id):
        log.warning("Import %s is already being processed by another worker; skipping", job_id)
        return job
    try:
        return _run_locked(job, source)
    finally:
        loader.unlock_job(job_id)


def _run_locked(job: ImportJob, source: IngestionSource | None) -> ImportJob:
    job_id = job.pk
    mapping = normalise_mapping(job.mapping)
    try:
        source = source or build_source(job)
        ImportJob.objects.filter(pk=job.pk).update(
            status=ImportJob.Status.VALIDATING,
            cancel_requested=False,
            started_at=job.started_at or timezone.now(),
        )
        problems = validate_mapping(mapping, source.header())
        if problems:
            return _finish(job, ImportJob.Status.FAILED, " ".join(problems))
        if not job.rows_total:
            ImportJob.objects.filter(pk=job.pk).update(rows_total=source.estimate_rows() or 0)
        ImportJob.objects.filter(pk=job.pk).update(status=ImportJob.Status.RUNNING)
        job.refresh_from_db()
        publish_progress(job)

        stored = job.row_errors.count()
        for chunk in source.chunks(settings.IMPORT_CHUNK_ROWS, skip_rows=job.rows_processed):
            if ImportJob.objects.filter(pk=job.pk, cancel_requested=True).exists():
                return _finish(job, ImportJob.Status.CANCELLED, "Cancelled by user. Rows already imported were kept.")
            res = process_chunk(job, chunk, mapping, stored_errors=stored)
            stored = min(settings.IMPORT_MAX_STORED_ERRORS, stored + len(res.errors))
            job.refresh_from_db()
            publish_progress(job)

        loader.refresh_account_activity(job.dataset_id, job.pk)
        if job.rows_accepted > 10_000:
            with connection.cursor() as cur:
                cur.execute("ANALYZE transactions_account")
        job.refresh_from_db()
        note = ""
        if job.rows_rejected > settings.IMPORT_MAX_STORED_ERRORS:
            cap = settings.IMPORT_MAX_STORED_ERRORS
            note = f"Only the first {cap} row errors are stored; {job.rows_rejected} rows were rejected."
        status = ImportJob.Status.COMPLETED_WITH_ERRORS if job.rows_rejected else ImportJob.Status.COMPLETED
        return _finish(job, status, note)
    except Exception as exc:  # noqa: BLE001 - job must end in a terminal state with a readable reason
        log.exception("Import %s failed", job_id)
        job.refresh_from_db()
        return _finish(job, ImportJob.Status.FAILED, f"{type(exc).__name__}: {str(exc)[:300]}")
