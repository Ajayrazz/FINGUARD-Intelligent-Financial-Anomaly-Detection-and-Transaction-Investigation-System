"""Case management: creation, the validated state machine, notes with revisions, hashed evidence, history."""

from __future__ import annotations

import hashlib
import logging
import secrets
from pathlib import Path
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.db import transaction as db_transaction
from django.utils import timezone

from apps.alerts import services as alert_services
from apps.alerts.models import SEVERITY_RANK, Alert, AlertEvent
from apps.audit import services as audit
from apps.transactions.models import Account, Transaction

from .models import (
    OUTCOMES,
    PRIORITIES,
    TRANSITIONS,
    Case,
    CaseAlert,
    CaseEvent,
    CaseEvidence,
    CaseNote,
    CaseNoteRevision,
    CaseTransaction,
)

log = logging.getLogger(__name__)
# permission needed to move a case INTO each status (docs/10: resolution and closure are separate actions)
TARGET_PERMISSION = {
    "under_review": "cases.transition",
    "investigation": "cases.transition",
    "escalated": "cases.escalate",
    "resolved": "cases.resolve",
    "closed": "cases.close",
}
OUTCOME_TO_ALERT = {
    "confirmed_suspicious": "true_positive",
    "false_positive": "false_positive",
    "inconclusive": "other",
    "referred": "other",
}
SEVERITY_TO_PRIORITY = {"low": "low", "medium": "medium", "high": "high", "critical": "critical"}
EVIDENCE_TYPES = {
    b"%PDF": ("application/pdf", "pdf"),
    b"\x89PNG\r\n\x1a\n": ("image/png", "png"),
    b"\xff\xd8\xff": ("image/jpeg", "jpg"),
}


class CaseError(Exception):
    """A request cannot be served. `status` is the suggested HTTP status; the message is safe to show."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def _event(
    case: Case,
    event_type: str,
    actor: Any = None,
    from_status: str = "",
    to_status: str = "",
    payload: dict[str, Any] | None = None,
) -> CaseEvent:
    return CaseEvent.objects.create(
        case=case,
        event_type=event_type,
        actor=actor,
        from_status=from_status,
        to_status=to_status,
        payload=payload or {},
    )


def ensure_open(case: Case) -> None:
    if case.status == "closed":
        raise CaseError("This case is closed: it is read-only, but its history remains viewable.", 409)


def next_case_ref() -> str:
    with connection.cursor() as cur:
        cur.execute("SELECT nextval('cases_case_ref_seq')")
        n = cur.fetchone()[0]
    return f"FG-{timezone.now().year}-{n:06d}"


def _push(case: Case, kind: str) -> None:
    """Realtime nudge to the assignee only; never lets a push failure break a case action."""
    if case.assignee_id is None:
        return
    try:
        async_to_sync(get_channel_layer().group_send)(
            f"user.{case.assignee_id}",
            {
                "type": "push.event",
                "payload": {"type": kind, "data": {"id": case.pk, "case_ref": case.case_ref, "status": case.status}},
            },
        )
    except Exception:  # noqa: BLE001
        log.warning("could not push case %s", case.pk, exc_info=True)


# ------------------------------------------------------------------------------------ creation and linking
def create_case(
    *,
    user: Any,
    title: str,
    description: str = "",
    priority: str = "medium",
    dataset: Any = None,
    alert: Alert | None = None,
    auto: bool = False,
) -> Case:
    if priority not in PRIORITIES:
        raise CaseError(f"priority must be one of {PRIORITIES}")
    if not title.strip():
        raise CaseError("A case needs a title.")
    with db_transaction.atomic():
        case = Case.objects.create(
            case_ref=next_case_ref(),
            title=title.strip()[:200],
            description=description,
            priority=priority,
            dataset=dataset,
            created_by=user,
            auto_created=auto,
        )
        _event(case, "created", user, "", "new", {"auto": auto, "priority": priority})
        if alert is not None:
            link_alert(case, alert, user, _quiet=True)
    audit.log(
        "case.created",
        actor=user,
        resource_type="case",
        resource_id=case.pk,
        changes={"case_ref": case.case_ref, "auto": auto, "alert": alert.pk if alert else None},
    )
    return case


def link_alert(case: Case, alert: Alert, user: Any, *, _quiet: bool = False) -> CaseAlert:
    ensure_open(case)
    link, created = CaseAlert.objects.get_or_create(case=case, alert=alert, defaults={"linked_by": user})
    if not created:
        raise CaseError("That alert is already linked to this case.", 409)
    if alert.transaction_id:
        CaseTransaction.objects.get_or_create(
            case=case,
            transaction_id=alert.transaction_id,
            defaults={"added_by": user, "note": f"from alert #{alert.pk}"},
        )
    _event(
        case,
        "alert_linked",
        user,
        payload={"alert": alert.pk, "alert_type": alert.alert_type, "severity": alert.severity},
    )
    AlertEvent.objects.create(alert=alert, event_type="case_linked", actor=user, payload={"case_ref": case.case_ref})
    if alert.status == "new" and user is not None:
        alert_services.acknowledge(alert, user)
    if not _quiet:
        audit.log(
            "case.alert_linked", actor=user, resource_type="case", resource_id=case.pk, changes={"alert": alert.pk}
        )
    return link


def add_transaction(case: Case, tx: Transaction, user: Any, note: str = "") -> CaseTransaction:
    ensure_open(case)
    link, created = CaseTransaction.objects.get_or_create(
        case=case, transaction=tx, defaults={"added_by": user, "note": note[:300]}
    )
    if not created:
        raise CaseError("That transaction is already in this case.", 409)
    _event(case, "transaction_added", user, payload={"transaction": tx.pk, "external_id": tx.transaction_id})
    audit.log(
        "case.transaction_added", actor=user, resource_type="case", resource_id=case.pk, changes={"transaction": tx.pk}
    )
    return link


def on_alert_created(sender, alert: Alert, policy, **kwargs):  # noqa: ANN001, ANN003, ANN201
    """Rule-based automatic case creation: an alert at or above the policy's severity opens a case, or joins the open
    case already covering the same account (so one account's alerts do not become a pile of cases)."""
    cfg = (policy.config or {}).get("auto_case", {"enabled": True, "min_severity": "critical"})
    if not cfg.get("enabled") or SEVERITY_RANK[alert.severity] < SEVERITY_RANK[cfg.get("min_severity", "critical")]:
        return
    if alert.case_links.exists():  # already part of a case (a severity raise after the case was opened)
        return
    existing = None
    if alert.account_id:
        existing = (
            Case.objects.filter(case_alerts__alert__account_id=alert.account_id)
            .exclude(status="closed")
            .order_by("-opened_at")
            .first()
        )
    if existing is not None:
        link_alert(existing, alert, None)
        return
    create_case(
        user=None,
        title=f"{alert.alert_type.replace('_', ' ').capitalize()}: {alert.reason[:120]}",
        description=alert.reason,
        priority=SEVERITY_TO_PRIORITY[alert.severity],
        dataset=alert.dataset,
        alert=alert,
        auto=True,
    )


# ------------------------------------------------------------------------------------ state machine
def allowed_transitions(case: Case, user: Any) -> list[str]:
    perms = user.permission_codenames
    return sorted(t for t in TRANSITIONS[case.status] if TARGET_PERMISSION[t] in perms)


def transition(
    case: Case, user: Any, to_status: str, *, reason: str = "", outcome: str = "", summary: str = ""
) -> Case:
    """The only way a case changes status. Everything the machine does not list is rejected (409)."""
    if to_status not in TRANSITIONS:
        raise CaseError(f"Unknown status '{to_status}'.")
    if to_status not in TRANSITIONS[case.status]:
        raise CaseError(
            f"A case that is {case.status.replace('_', ' ')} cannot move to {to_status.replace('_', ' ')}.", 409
        )
    needed = TARGET_PERMISSION[to_status]
    if needed not in user.permission_codenames:
        raise CaseError("You do not have permission to make this change.", 403)
    old = case.status
    payload: dict[str, Any] = {"reason": reason[:2000]} if reason else {}
    if to_status == "escalated" and not reason.strip():
        raise CaseError("An escalation needs a reason.")
    if to_status == "resolved":
        if outcome not in OUTCOMES:
            raise CaseError(f"An outcome is required: one of {OUTCOMES}.")
        if not summary.strip():
            raise CaseError("A resolution needs a summary.")
        case.outcome, case.resolution_summary, case.resolved_by, case.resolved_at = (
            outcome,
            summary[:5000],
            user,
            timezone.now(),
        )
        payload.update({"outcome": outcome})
    if to_status == "closed":
        if settings.CASE_CLOSE_REQUIRES_DIFFERENT_USER and case.resolved_by_id == user.pk:
            raise CaseError("Closure needs a second person: the user who resolved the case cannot close it.", 403)
        case.closed_by, case.closed_at = user, timezone.now()
    case.status = to_status
    with db_transaction.atomic():
        case.save()
        _event(case, "status_changed", user, old, to_status, payload)
        if to_status == "closed":
            _close_linked_alerts(case, user)
    audit.log(
        f"case.{to_status}",
        actor=user,
        resource_type="case",
        resource_id=case.pk,
        changes={"from": old, "to": to_status, **payload},
    )
    _push(case, "case.updated")
    return case


def _close_linked_alerts(case: Case, user: Any) -> None:
    for link in case.case_alerts.select_related("alert"):
        a = link.alert
        if a.status != "closed":
            alert_services.close(
                a,
                user,
                OUTCOME_TO_ALERT[case.outcome],
                f"Closed with case {case.case_ref} ({case.outcome.replace('_', ' ')}).",
            )


def assign(case: Case, user: Any, assignee: Any) -> Case:
    ensure_open(case)
    if "cases.read" not in assignee.permission_codenames:
        raise CaseError("That user cannot work on cases.")
    old = case.assignee_id
    case.assignee = assignee
    case.save(update_fields=["assignee"])
    _event(case, "assigned", user, payload={"from": old, "to": assignee.pk})
    audit.log("case.assigned", actor=user, resource_type="case", resource_id=case.pk, changes={"assignee": assignee.pk})
    _push(case, "case.updated")
    return case


def update_fields(case: Case, user: Any, values: dict[str, Any]) -> Case:
    ensure_open(case)
    changed: dict[str, Any] = {}
    for key in ("title", "description", "priority"):
        if key in values and values[key] != getattr(case, key):
            if key == "priority" and values[key] not in PRIORITIES:
                raise CaseError(f"priority must be one of {PRIORITIES}")
            if key == "title" and not str(values[key]).strip():
                raise CaseError("A case needs a title.")
            changed[key] = [
                getattr(case, key) if key != "description" else "...",
                values[key] if key != "description" else "...",
            ]
            setattr(case, key, values[key])
    if changed:
        case.save(update_fields=list(changed))
        _event(case, "updated", user, payload=changed)
        audit.log("case.updated", actor=user, resource_type="case", resource_id=case.pk, changes=changed)
    return case


# ------------------------------------------------------------------------------------ notes
def add_note(case: Case, user: Any, kind: str, body: str) -> CaseNote:
    ensure_open(case)
    if kind not in ("comment", "note"):
        raise CaseError("kind must be comment or note.")
    if kind == "note" and "cases.note" not in user.permission_codenames:
        raise CaseError("You do not have permission to write investigation notes.", 403)
    if not body.strip():
        raise CaseError("A note cannot be empty.")
    with db_transaction.atomic():
        note = CaseNote.objects.create(case=case, author=user, kind=kind)
        CaseNoteRevision.objects.create(note=note, revision=1, body=body, edited_by=user)
        _event(case, "note_added", user, payload={"note": note.pk, "kind": kind})
    audit.log(
        "case.note_added",
        actor=user,
        resource_type="case",
        resource_id=case.pk,
        changes={"note": note.pk, "kind": kind},
    )
    return note


def edit_note(note: CaseNote, user: Any, body: str) -> CaseNoteRevision:
    """Editing adds a revision; earlier text stays. Only the author may edit, and never on a closed case."""
    ensure_open(note.case)
    if note.author_id != user.pk:
        raise CaseError("Only the author can edit a note.", 403)
    if not body.strip():
        raise CaseError("A note cannot be empty.")
    last = note.revisions.order_by("-revision").first()
    assert last is not None
    if last.body == body:
        raise CaseError("Nothing changed.", 409)
    with db_transaction.atomic():
        rev = CaseNoteRevision.objects.create(note=note, revision=last.revision + 1, body=body, edited_by=user)
        _event(note.case, "note_edited", user, payload={"note": note.pk, "revision": rev.revision})
    audit.log(
        "case.note_edited",
        actor=user,
        resource_type="case",
        resource_id=note.case_id,
        changes={"note": note.pk, "revision": rev.revision},
    )
    return rev


# ------------------------------------------------------------------------------------ evidence
def add_evidence(case: Case, user: Any, uploaded, description: str = "") -> CaseEvidence:  # noqa: ANN001
    """Validate by content (PDF/PNG/JPEG/plain text), hash, and store under a random name."""
    ensure_open(case)
    data = uploaded.read(settings.CASE_EVIDENCE_MAX_BYTES + 1)
    if not data:
        raise CaseError("The file is empty.")
    if len(data) > settings.CASE_EVIDENCE_MAX_BYTES:
        raise CaseError(f"The file is larger than {settings.CASE_EVIDENCE_MAX_BYTES // (1024 * 1024)} MB.")
    kind = next(((m, e) for magic, (m, e) in EVIDENCE_TYPES.items() if data.startswith(magic)), None)
    if kind is None:
        try:
            text = data[:65536].decode("utf-8")
        except UnicodeDecodeError:
            text = None
        if text is None or "\x00" in text:
            raise CaseError(
                "Only PDF, PNG, JPEG and plain-text/CSV evidence is accepted (checked by file content, not name)."
            )
        kind = ("text/plain", "txt")
    mime, ext = kind
    root = Path(settings.MEDIA_ROOT) / "cases" / case.case_ref
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{secrets.token_hex(16)}.{ext}"  # random name: the client's name never reaches the filesystem
    path.write_bytes(data)
    name = (
        "".join(ch for ch in Path(str(getattr(uploaded, "name", "evidence"))).name if ch.isprintable())[:200]
        or "evidence"
    )
    with db_transaction.atomic():
        ev = CaseEvidence.objects.create(
            case=case,
            file_path=str(path),
            original_name=name,
            sha256=hashlib.sha256(data).hexdigest(),
            mime=mime,
            size=len(data),
            description=description[:300],
            uploaded_by=user,
        )
        _event(case, "evidence_added", user, payload={"evidence": ev.pk, "sha256": ev.sha256, "size": ev.size})
    audit.log(
        "case.evidence_added",
        actor=user,
        resource_type="case",
        resource_id=case.pk,
        changes={"evidence": ev.pk, "sha256": ev.sha256},
    )
    return ev


def read_evidence(ev: CaseEvidence, user: Any) -> bytes:
    """Return the file bytes after checking they still match the stored SHA-256; every download is audited."""
    data = Path(ev.file_path).read_bytes()
    if hashlib.sha256(data).hexdigest() != ev.sha256:
        audit.log(
            "case.evidence_integrity_failure",
            actor=user,
            resource_type="case",
            resource_id=ev.case_id,
            changes={"evidence": ev.pk},
        )
        raise CaseError("This evidence file no longer matches its recorded hash and was not served.", 409)
    audit.log(
        "case.evidence_downloaded",
        actor=user,
        resource_type="case",
        resource_id=ev.case_id,
        changes={"evidence": ev.pk},
    )
    return data


# ------------------------------------------------------------------------------------ views over a case
def involved_accounts(case: Case) -> list[dict[str, Any]]:
    ids: dict[int, set[str]] = {}
    for t in Transaction.objects.filter(case_links__case=case).values_list("sender_id", "receiver_id"):
        ids.setdefault(t[0], set()).add("sender")
        if t[1]:
            ids.setdefault(t[1], set()).add("receiver")
    for a in Alert.objects.filter(case_links__case=case, account__isnull=False).values_list("account_id", flat=True):
        ids.setdefault(a, set()).add("alert subject")
    accts = {a.pk: a for a in Account.objects.filter(pk__in=ids)}
    return [
        {"id": i, "account_ref": accts[i].account_ref, "account_type": accts[i].account_type, "roles": sorted(r)}
        for i, r in sorted(ids.items())
        if i in accts
    ]


def eligible_assignees():  # noqa: ANN201
    return (
        get_user_model()
        .objects.filter(is_active=True, role__permissions__codename="cases.read")
        .distinct()
        .order_by("full_name", "email")
    )
