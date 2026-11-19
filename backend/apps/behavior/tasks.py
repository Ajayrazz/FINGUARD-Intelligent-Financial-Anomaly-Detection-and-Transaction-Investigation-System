from celery import shared_task

from .services import execute_run


@shared_task(name="behavior.run_behavior", time_limit=2 * 3600)
def run_behavior_task(run_id: int) -> None:
    execute_run(run_id)
