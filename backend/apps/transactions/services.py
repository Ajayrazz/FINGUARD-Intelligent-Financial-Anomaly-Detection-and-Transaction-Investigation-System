from typing import Any

from django.db import transaction as db_transaction
from rest_framework import exceptions

from apps.audit import services as audit

from .models import Transaction, TransactionEvent


def record_event(
    tx: Transaction, event_type: str, *, actor: Any = None, payload: dict[str, Any] | None = None
) -> TransactionEvent:
    return TransactionEvent.objects.create(transaction=tx, event_type=event_type, actor=actor, payload=payload or {})


@db_transaction.atomic
def change_status(*, tx_id: int, new_status: str, reason: str, actor: Any, request: Any) -> Transaction:
    """Change monitoring status with row lock; writes a transaction event and an audit record."""
    tx = Transaction.objects.select_for_update().get(pk=tx_id)
    if tx.status == new_status:
        raise exceptions.ValidationError({"status": f"Transaction is already '{new_status}'."})
    old = tx.status
    tx.status = new_status
    tx.save(update_fields=["status"])
    payload = {"from": old, "to": new_status, "reason": reason}
    record_event(tx, "status_changed", actor=actor, payload=payload)
    audit.log(
        "transaction.status_changed", request=request, actor=actor, resource_type="transaction",
        resource_id=tx.pk, changes=payload,
    )  # fmt: skip
    return tx
