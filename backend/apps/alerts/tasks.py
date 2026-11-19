from celery import shared_task

from .services import execute_run, send_email


@shared_task(name="alerts.evaluate", time_limit=1800)
def evaluate_task(run_id: int) -> None:
    execute_run(run_id)


@shared_task(name="alerts.send_email", time_limit=120)
def send_email_task(alert_id: int, kind: str, recipients: list[str]) -> None:
    send_email(alert_id, kind, recipients)
