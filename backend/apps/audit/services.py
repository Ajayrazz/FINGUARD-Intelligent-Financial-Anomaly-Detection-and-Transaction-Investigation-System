from typing import Any

from .models import AuditLog

_SENSITIVE = ("password", "token", "secret")


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: "***" if any(s in str(k).lower() for s in _SENSITIVE) else _redact(v) for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def log(
    action: str,
    *,
    request: Any = None,
    actor: Any = None,
    actor_email: str = "",
    resource_type: str = "",
    resource_id: object = "",
    changes: dict[str, Any] | None = None,
) -> AuditLog:
    """Write one audit record. Secrets in `changes` are redacted. Use for every security-relevant action."""
    if actor is None and request is not None:
        user = getattr(request, "user", None)
        actor = user if user is not None and user.is_authenticated else None
    meta = getattr(request, "META", {}) if request is not None else {}
    return AuditLog.objects.create(
        actor=actor,
        actor_email=(actor.email if actor is not None else actor_email)[:254],
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        ip_address=meta.get("REMOTE_ADDR") or None,
        user_agent=str(meta.get("HTTP_USER_AGENT", ""))[:300],
        request_id=str(getattr(request, "request_id", ""))[:64],
        changes=_redact(changes or {}),
    )
