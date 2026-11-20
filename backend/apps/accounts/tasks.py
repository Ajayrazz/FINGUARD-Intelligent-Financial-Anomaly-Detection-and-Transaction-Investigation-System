from celery import shared_task

from .emails import send_account_email


@shared_task(name="accounts.send_email", time_limit=120)
def send_account_email_task(kind: str, user_id: int) -> None:
    send_account_email(kind, user_id)
