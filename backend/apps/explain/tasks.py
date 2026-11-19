from celery import shared_task

from .services import execute_job


@shared_task(name="explain.generate", time_limit=1800)
def generate_task(job_id: int) -> None:
    execute_job(job_id)
