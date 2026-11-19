"""Synchronous micro-batch ingestion for the API (<= IMPORT_API_MAX_BATCH records), reusing the file pipeline."""

from typing import Any

from django.utils import timezone

from ..models import Dataset, ImportJob
from ..realtime import publish_progress
from .mapping import CANONICAL_FIELDS, normalise_mapping, validate_mapping
from .pipeline import ChunkResult, process_chunk
from .sources import RecordsSource


def ingest_records(
    *, dataset: Dataset, user: Any, records: list[dict[str, Any]], dup_policy: str
) -> tuple[ImportJob, list[dict[str, Any]], list[str]]:
    """Returns (job, per-record results, batch-level problems). Idempotent for dup_policy=skip."""
    source = RecordsSource(records)
    columns = {k: k for k in source.header() if k in CANONICAL_FIELDS}
    mapping = normalise_mapping({"columns": columns})
    problems = validate_mapping(mapping, source.header())
    job = ImportJob.objects.create(
        dataset=dataset, source=ImportJob.Source.API, mapping=mapping, dup_policy=dup_policy,
        file_name="api-ingest", rows_total=len(records), created_by=user, started_at=timezone.now(),
        status=ImportJob.Status.RUNNING,
    )  # fmt: skip
    if problems:
        job.status, job.error_summary, job.finished_at = (
            ImportJob.Status.FAILED,
            " ".join(problems),
            timezone.now(),
        )
        job.save(update_fields=["status", "error_summary", "finished_at"])
        return job, [], problems

    result = ChunkResult()
    for chunk in source.chunks(len(records) or 1):
        result = process_chunk(job, chunk, mapping, stored_errors=0)
    errors_by_row = {e.row_number: e for e in result.errors}
    results: list[dict[str, Any]] = []
    for i in range(1, len(records) + 1):
        if i in errors_by_row:
            e = errors_by_row[i]
            results.append({"index": i - 1, "status": "rejected", "code": e.code, "message": e.message})
        elif i in result.skipped_rows:
            results.append({"index": i - 1, "status": "duplicate_skipped"})
        elif i in result.flagged_rows:
            results.append({"index": i - 1, "status": "accepted_flagged_duplicate"})
        else:
            results.append({"index": i - 1, "status": "accepted"})
    from .loader import refresh_account_activity

    refresh_account_activity(dataset.pk, job.pk)
    job.refresh_from_db()
    job.status = ImportJob.Status.COMPLETED_WITH_ERRORS if job.rows_rejected else ImportJob.Status.COMPLETED
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "finished_at"])
    publish_progress(job)
    return job, results, []
