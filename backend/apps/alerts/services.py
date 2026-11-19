"""Alert evaluation, deduplication, lifecycle and notifications."""

from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db import transaction as db_transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.datasets.models import Dataset

from . import rules
from .models import SEVERITY_RANK, Alert, AlertEvent, AlertPolicy, AlertRun, NotificationLog
from .signals import alert_created, alert_raised

log = logging.getLogger(__name__)
ALERTS_GROUP = "alerts"
OPEN = ("new", "acknowledged", "escalated")
TRANSITIONS = {"acknowledge": {"new"}, "escalate": {"new", "acknowledged"}, "close": set(OPEN)}


class AlertError(Exception):
    """A request cannot be served (message is safe to show)."""


# ------------------------------------------------------------------------------------ policy
def active_policy() -> AlertPolicy:
    p = AlertPolicy.objects.filter(is_active=True).first()
    if p is None:
        raise AlertError("No active alert policy.")
    return p


def create_policy(*, user: Any, settings_dict: dict[str, Any], notes: str = "") -> AlertPolicy:
    try:
        rules.validate_policy(settings_dict)
    except rules.PolicyError as exc:
        raise AlertError(str(exc)) from exc
    with db_transaction.atomic():
        version = (AlertPolicy.objects.order_by("-version").values_list("version", flat=True).first() or 0) + 1
        pol = AlertPolicy.objects.create(version=version, config=settings_dict, notes=notes[:2000], created_by=user)
    audit.log(
        "alert.policy.created",
        actor=user,
        resource_type="alert_policy",
        resource_id=pol.pk,
        changes={"version": version},
    )
    return pol


def activate_policy(pol: AlertPolicy, user: Any) -> AlertPolicy:
    with db_transaction.atomic():
        AlertPolicy.objects.filter(is_active=True).exclude(pk=pol.pk).update(is_active=False)
        AlertPolicy.objects.filter(pk=pol.pk).update(is_active=True)
    audit.log(
        "alert.policy.activated",
        actor=user,
        resource_type="alert_policy",
        resource_id=pol.pk,
        changes={"version": pol.version},
    )
    pol.refresh_from_db()
    return pol


# ------------------------------------------------------------------------------------ events and notifications
def _event(alert: Alert, event_type: str, actor: Any = None, payload: dict[str, Any] | None = None) -> AlertEvent:
    return AlertEvent.objects.create(alert=alert, event_type=event_type, actor=actor, payload=payload or {})


def _publish(alert: Alert, kind: str) -> None:
    """WebSocket push to everyone who may read alerts. A realtime failure never blocks alert creation."""
    status = "sent"
    err = ""
    try:
        async_to_sync(get_channel_layer().group_send)(ALERTS_GROUP, {"type": "push.event", "payload": {"type": kind, "data": {
            "id": alert.pk, "alert_type": alert.alert_type, "severity": alert.severity, "status": alert.status, "reason": alert.reason[:200],
            "transaction": alert.transaction_id, "account": alert.account_id}}})  # fmt: skip
    except Exception as exc:  # noqa: BLE001
        status, err = "failed", str(exc)[:200]
        log.warning("could not push alert %s", alert.pk, exc_info=True)
    NotificationLog.objects.create(
        alert=alert, channel="websocket", recipient=f"group:{ALERTS_GROUP}", status=status, error=err
    )


def _email_recipients(alert: Alert, policy: dict[str, Any]) -> list[str]:
    e = policy["email"]
    if SEVERITY_RANK[alert.severity] < SEVERITY_RANK[e["min_severity"]]:
        return []
    return [str(r) for r in e["recipients"]]


def _notify(alert: Alert, kind: str, policy: dict[str, Any]) -> None:
    from .tasks import send_email_task

    _publish(alert, kind)
    recipients = _email_recipients(alert, policy)
    if recipients:
        db_transaction.on_commit(lambda: send_email_task.delay(alert.pk, kind, recipients))
    else:
        NotificationLog.objects.create(
            alert=alert,
            channel="email",
            recipient="-",
            status="skipped",
            error="no recipients configured or severity below the email threshold",
        )


def send_email(alert_id: int, kind: str, recipients: list[str]) -> None:
    from django.conf import settings
    from django.core.mail import send_mail

    alert = Alert.objects.get(pk=alert_id)
    label = rules.TYPE_LABEL.get(alert.alert_type, alert.alert_type)
    subject = f"[FinGuard] {alert.severity.upper()} alert #{alert.pk}: {label}"
    # no amounts or account numbers in email: it leaves the system. The link opens the alert behind sign-in.
    body = (f"{label} ({alert.severity}) - {'severity raised' if kind == 'alert.updated' else 'new alert'}.\n\n"
            f"Open it in FinGuard: {settings.FRONTEND_BASE_URL}/alerts?open={alert.pk}\n\n"
            "This is an automated notification that something was flagged for review. It is not a finding of wrongdoing.")  # fmt: skip
    for rcpt in recipients:
        try:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [rcpt], fail_silently=False)
            NotificationLog.objects.create(alert=alert, channel="email", recipient=rcpt, status="sent")
        except Exception as exc:  # noqa: BLE001 - a failed email is recorded, never raised into the alert flow
            NotificationLog.objects.create(
                alert=alert, channel="email", recipient=rcpt, status="failed", error=str(exc)[:300]
            )
            log.warning("email for alert %s to %s failed", alert_id, rcpt, exc_info=True)


# ------------------------------------------------------------------------------------ evaluation
def start_run(*, dataset: Dataset, user: Any, trigger: str = "manual", source_risk_run: int | None = None) -> AlertRun:
    pol = active_policy()
    run = AlertRun.objects.create(
        dataset=dataset, policy_version=pol.version, trigger=trigger, created_by=user, source_risk_run=source_risk_run
    )
    audit.log(
        "alert.run.created",
        actor=user,
        resource_type="alert_run",
        resource_id=run.pk,
        changes={"dataset": dataset.pk, "trigger": trigger},
    )
    return run


def execute_run(run_id: int) -> None:
    run = AlertRun.objects.select_related("dataset").get(pk=run_id)
    if run.status == AlertRun.Status.SUCCEEDED:
        return
    run.status = AlertRun.Status.RUNNING
    run.save(update_fields=["status"])
    try:
        pol = AlertPolicy.objects.get(version=run.policy_version)
        candidates, suppressed = rules.evaluate(run.dataset, pol.config)
        result = {**persist(candidates, pol, run.dataset), "suppressed": suppressed}
        run.result, run.status, run.finished_at = result, AlertRun.Status.SUCCEEDED, timezone.now()
        run.save()
        audit.log(
            "alert.run.completed", actor=run.created_by, resource_type="alert_run", resource_id=run.pk, changes=result
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("alert run %s failed", run_id)
        run.status, run.finished_at = AlertRun.Status.FAILED, timezone.now()
        run.error_message = str(exc)[:300] if isinstance(exc, AlertError) else "Unexpected error."
        run.save()


def persist(candidates: list[rules.Candidate], policy: AlertPolicy, dataset: Dataset) -> dict[str, Any]:
    """One open alert per dedup key. A repeat of the same event is ignored; the same event at a higher severity raises
    the existing alert (history kept); a different type, subject or time bucket - or the same key after closure - is a
    new alert. Evidence is snapshotted at creation and never rewritten."""
    created = deduplicated = raised = 0
    by_type: dict[str, int] = {}
    for c in candidates:
        existing = Alert.objects.filter(dedup_key=c.dedup_key).exclude(status="closed").first()
        if existing is not None:
            if SEVERITY_RANK[c.severity] > SEVERITY_RANK[existing.severity]:
                old, old_reason = existing.severity, existing.reason
                existing.severity, existing.reason = (
                    c.severity,
                    c.reason,
                )  # the headline follows the latest facts; the evidence snapshot does not
                existing.save(update_fields=["severity", "reason"])
                _event(
                    existing,
                    "severity_raised",
                    None,
                    {
                        "from": old,
                        "to": c.severity,
                        "reason": c.reason,
                        "previous_reason": old_reason,
                        "evidence": c.evidence,
                    },
                )
                _notify(existing, "alert.updated", policy.config)
                alert_raised.send(sender=Alert, alert=existing, policy=policy)
                raised += 1
            else:
                deduplicated += 1
            continue
        try:
            with db_transaction.atomic():
                alert = Alert.objects.create(
                    alert_type=c.alert_type, severity=c.severity, dedup_key=c.dedup_key, dataset=dataset, transaction_id=c.transaction_id, account_id=c.account_id,
                    assessment_id=c.assessment_id, reason=c.reason, evidence_snapshot={**c.evidence, "signals": c.signals}, policy_version=policy.version,
                )  # fmt: skip
                _event(alert, "created", None, {"severity": c.severity, "rule": c.alert_type})
        except IntegrityError:  # a concurrent evaluation created it first
            deduplicated += 1
            continue
        created += 1
        by_type[c.alert_type] = by_type.get(c.alert_type, 0) + 1
        _notify(alert, "alert.created", policy.config)
        alert_created.send(sender=Alert, alert=alert, policy=policy)
    return {
        "candidates": len(candidates),
        "created": created,
        "deduplicated": deduplicated,
        "raised": raised,
        "by_type": by_type,
    }


# ------------------------------------------------------------------------------------ lifecycle
def _guard(alert: Alert, action: str) -> None:
    if alert.status not in TRANSITIONS[action]:
        raise AlertError(
            f"An alert that is {alert.status} cannot be {'acknowledged' if action == 'acknowledge' else 'escalated' if action == 'escalate' else 'closed'}."
        )


def acknowledge(alert: Alert, user: Any) -> Alert:
    _guard(alert, "acknowledge")
    alert.status, alert.acknowledged_by, alert.acknowledged_at = Alert.Status.ACKNOWLEDGED, user, timezone.now()
    alert.save(update_fields=["status", "acknowledged_by", "acknowledged_at"])
    _event(alert, "acknowledged", user)
    audit.log("alert.acknowledged", actor=user, resource_type="alert", resource_id=alert.pk)
    _publish(alert, "alert.updated")
    return alert


def assign(alert: Alert, user: Any, assignee: Any) -> Alert:
    if alert.status == "closed":
        raise AlertError("A closed alert cannot be assigned.")
    old = alert.assignee_id
    alert.assignee = assignee
    alert.save(update_fields=["assignee"])
    _event(alert, "assigned", user, {"from": old, "to": assignee.pk})
    audit.log(
        "alert.assigned", actor=user, resource_type="alert", resource_id=alert.pk, changes={"assignee": assignee.pk}
    )
    _publish(alert, "alert.updated")
    from .tasks import send_email_task

    if assignee.email and assignee.pk != getattr(user, "pk", None):
        db_transaction.on_commit(lambda: send_email_task.delay(alert.pk, "alert.assigned", [assignee.email]))
    return alert


def escalate(alert: Alert, user: Any, reason: str) -> Alert:
    _guard(alert, "escalate")
    if not reason.strip():
        raise AlertError("An escalation needs a reason.")
    alert.status, alert.escalated_at, alert.escalation_reason = Alert.Status.ESCALATED, timezone.now(), reason[:2000]
    alert.save(update_fields=["status", "escalated_at", "escalation_reason"])
    _event(alert, "escalated", user, {"reason": reason[:2000]})
    audit.log("alert.escalated", actor=user, resource_type="alert", resource_id=alert.pk)
    _publish(alert, "alert.updated")
    return alert


def close(alert: Alert, user: Any, outcome: str, notes: str) -> Alert:
    _guard(alert, "close")
    if outcome not in {o.value for o in Alert.Outcome}:
        raise AlertError(f"outcome must be one of {sorted(o.value for o in Alert.Outcome)}")
    alert.status, alert.closed_by, alert.closed_at, alert.outcome, alert.close_notes = (
        Alert.Status.CLOSED,
        user,
        timezone.now(),
        outcome,
        notes[:2000],
    )
    alert.save(update_fields=["status", "closed_by", "closed_at", "outcome", "close_notes"])
    _event(alert, "closed", user, {"outcome": outcome, "notes": notes[:2000]})
    audit.log("alert.closed", actor=user, resource_type="alert", resource_id=alert.pk, changes={"outcome": outcome})
    _publish(alert, "alert.updated")
    return alert


def eligible_assignees():  # noqa: ANN201
    U = get_user_model()
    return (
        U.objects.filter(is_active=True, role__permissions__codename="alerts.read")
        .distinct()
        .order_by("full_name", "email")
    )
