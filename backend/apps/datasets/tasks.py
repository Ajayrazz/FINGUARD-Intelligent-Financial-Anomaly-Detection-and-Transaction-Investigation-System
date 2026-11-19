from celery import shared_task

from .ingestion.pipeline import run_import


@shared_task(name="datasets.run_import", time_limit=6 * 3600)
def run_import_task(job_id: int) -> None:
    run_import(job_id)
