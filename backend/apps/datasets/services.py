import json
from typing import Any

from django.db import transaction
from rest_framework import serializers

from apps.audit import services as audit

from .ingestion.mapping import PRESETS, normalise_mapping, suggest_mapping, validate_mapping
from .ingestion.sources import CsvSource, ExcelSource
from .models import ColumnMappingProfile, Dataset, ImportJob
from .tasks import run_import_task
from .uploads import StoredUpload, store_upload


def resolve_mapping(
    raw_mapping: str | dict | None,
    preset: str | None,
    profile: ColumnMappingProfile | None,
    header: list[str],
    encoding: str,
) -> dict[str, Any]:
    """Pick the mapping source in order: explicit JSON > saved profile > preset > auto-suggestion."""
    if raw_mapping:
        try:
            data = json.loads(raw_mapping) if isinstance(raw_mapping, str) else raw_mapping
        except json.JSONDecodeError as exc:
            raise serializers.ValidationError({"mapping": "Mapping must be valid JSON."}) from exc
        if not isinstance(data, dict):
            raise serializers.ValidationError({"mapping": "Mapping must be a JSON object."})
    elif profile is not None:
        data = profile.mapping
    elif preset:
        if preset not in PRESETS:
            raise serializers.ValidationError({"preset": f"Unknown preset. Available: {sorted(PRESETS)}"})
        data = PRESETS[preset]
    else:
        data = suggest_mapping(header)
    mapping = normalise_mapping(data)
    mapping["options"]["encoding"] = mapping["options"].get("encoding") or encoding
    if encoding == "latin-1":
        mapping["options"]["encoding"] = "latin-1"
    problems = validate_mapping(mapping, header)
    if problems:
        raise serializers.ValidationError({"mapping": problems})
    return mapping


def _source_for(stored: StoredUpload, encoding: str):  # noqa: ANN202
    return ExcelSource(stored.path) if stored.extension == ".xlsx" else CsvSource(stored.path, encoding)


def preview_upload(uploaded, rows: int) -> dict[str, Any]:
    """Parse the head of an upload and suggest a mapping. Nothing is persisted (file is deleted)."""
    from pathlib import Path

    stored = store_upload(uploaded)
    try:
        source = _source_for(stored, stored.encoding)
        header = source.header()
        sample = next(iter(source.chunks(rows)), None)
        data = sample.frame.head(rows).fillna("").values.tolist() if sample is not None else []
        return {
            "file_name": stored.original_name, "format": stored.extension.lstrip("."), "columns": header,
            "rows": data, "suggested_mapping": suggest_mapping(header), "estimated_rows": source.estimate_rows(),
            "encoding": stored.encoding,
        }  # fmt: skip
    finally:
        Path(stored.path).unlink(missing_ok=True)


def create_file_import(
    *, dataset: Dataset, user: Any, request: Any, uploaded, raw_mapping, preset, profile, dup_policy: str
) -> ImportJob:
    from pathlib import Path

    stored = store_upload(uploaded)
    try:
        header = _source_for(stored, stored.encoding).header()
        mapping = resolve_mapping(raw_mapping, preset, profile, header, stored.encoding)
    except Exception:
        Path(stored.path).unlink(missing_ok=True)
        raise
    with transaction.atomic():
        job = ImportJob.objects.create(
            dataset=dataset, source=ImportJob.Source.FILE, mapping=mapping, dup_policy=dup_policy,
            mapping_profile=profile, file_name=stored.original_name, file_size=stored.size,
            file_sha256=stored.sha256, stored_path=stored.path, created_by=user,
        )  # fmt: skip
        audit.log(
            "import.created", request=request, actor=user, resource_type="import", resource_id=job.pk,
            changes={
                "dataset": dataset.pk, "file": stored.original_name, "sha256": stored.sha256,
                "dup_policy": dup_policy,
            },
        )  # fmt: skip
        transaction.on_commit(lambda: _enqueue(job.pk))
    return job


def _enqueue(job_id: int) -> None:
    result = run_import_task.delay(job_id)
    ImportJob.objects.filter(pk=job_id).update(celery_task_id=str(result.id or "")[:64])


def cancel_import(job: ImportJob, *, user: Any, request: Any) -> ImportJob:
    if job.status not in {ImportJob.Status.PENDING, ImportJob.Status.VALIDATING, ImportJob.Status.RUNNING}:
        raise serializers.ValidationError({"detail": f"A {job.status} import cannot be cancelled."})
    ImportJob.objects.filter(pk=job.pk).update(cancel_requested=True)
    audit.log("import.cancel_requested", request=request, actor=user, resource_type="import", resource_id=job.pk)
    job.refresh_from_db()
    return job


def resume_import(job: ImportJob, *, user: Any, request: Any, force: bool = False) -> ImportJob:
    """Continue a failed/cancelled import from its last committed chunk.

    `force` also allows a job stuck in pending/validating/running (its worker died). This is safe even if the
    worker is in fact alive: the per-job advisory lock makes the second run exit immediately.
    """
    active = {ImportJob.Status.PENDING, ImportJob.Status.VALIDATING, ImportJob.Status.RUNNING}
    resumable = {ImportJob.Status.FAILED, ImportJob.Status.CANCELLED} | (active if force else set())
    if job.status not in resumable:
        hint = " Use force=true if its worker has died." if job.status in active else ""
        raise serializers.ValidationError(
            {"detail": f"Only failed or cancelled imports can be resumed (this one is {job.status}).{hint}"}
        )
    if job.source != ImportJob.Source.FILE:
        raise serializers.ValidationError({"detail": "API ingestion batches cannot be resumed; resubmit them."})
    ImportJob.objects.filter(pk=job.pk).update(
        status=ImportJob.Status.PENDING, cancel_requested=False, error_summary="", finished_at=None
    )
    audit.log(
        "import.resumed", request=request, actor=user, resource_type="import", resource_id=job.pk,
        changes={"from_row": job.rows_processed},
    )  # fmt: skip
    transaction.on_commit(lambda: _enqueue(job.pk))
    job.refresh_from_db()
    return job
