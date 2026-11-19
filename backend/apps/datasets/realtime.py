import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import ImportJob

log = logging.getLogger(__name__)


def job_payload(job: ImportJob) -> dict:
    return {
        "type": "import.progress",
        "data": {
            "id": job.pk, "status": job.status, "rows_total": job.rows_total, "rows_processed": job.rows_processed,
            "rows_accepted": job.rows_accepted, "rows_rejected": job.rows_rejected,
            "rows_duplicate": job.rows_duplicate, "error_summary": job.error_summary,
        },
    }  # fmt: skip


def publish_progress(job: ImportJob) -> None:
    """Push progress to the creator's WebSocket group. Never lets a realtime failure break an import."""
    if job.created_by_id is None:
        return
    try:
        async_to_sync(get_channel_layer().group_send)(
            f"user.{job.created_by_id}", {"type": "push.event", "payload": job_payload(job)}
        )
    except Exception:  # noqa: BLE001
        log.warning("Could not publish import progress for job %s", job.pk, exc_info=True)
