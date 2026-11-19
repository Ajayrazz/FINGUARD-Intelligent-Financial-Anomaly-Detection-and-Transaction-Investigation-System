from celery import shared_task


@shared_task
def ping(value: str = "pong") -> str:
    """Infrastructure smoke-test task (Phase 1). Not a business feature."""
    return value
