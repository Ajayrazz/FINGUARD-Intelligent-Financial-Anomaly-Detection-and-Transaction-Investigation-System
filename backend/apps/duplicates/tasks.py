from celery import shared_task

from .services import execute_scan, process_invoice


@shared_task(name="duplicates.process_invoice", time_limit=600)
def process_invoice_task(document_id: int) -> None:
    process_invoice(document_id)


@shared_task(name="duplicates.run_scan", time_limit=2 * 3600)
def run_scan_task(run_id: int) -> None:
    execute_scan(run_id)
