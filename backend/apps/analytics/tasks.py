from celery import shared_task

from . import services


@shared_task(name="analytics.refresh_all")
def refresh_all() -> dict[int, int]:
    """Beat job: rebuild every dataset's daily rollup (idempotent)."""
    return services.refresh_all()
