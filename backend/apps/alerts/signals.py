"""Evaluate alert rules automatically when a risk run finishes (if the active policy has auto_evaluate on)."""

from django.db import transaction as db_transaction

from .models import AlertPolicy, AlertRun


def on_risk_run_saved(sender, instance, created, **kwargs):  # noqa: ANN001, ANN003, ANN201
    if instance.status != "succeeded" or AlertRun.objects.filter(source_risk_run=instance.pk).exists():
        return
    policy = AlertPolicy.objects.filter(is_active=True).first()
    if policy is None or not policy.config.get("auto_evaluate", False):
        return
    from .services import start_run
    from .tasks import evaluate_task

    run = start_run(dataset=instance.dataset, user=instance.created_by, trigger="risk_run", source_risk_run=instance.pk)
    db_transaction.on_commit(lambda: evaluate_task.delay(run.pk))
