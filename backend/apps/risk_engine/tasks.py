from celery import shared_task

from .services import execute_run


@shared_task(name="risk.run_scoring", time_limit=3 * 3600)
def run_scoring_task(run_id: int) -> None:
    execute_run(run_id)
