from typing import Any

from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.audit import services as audit

from .emails import queue_account_email
from .models import Approval, Role, User
from .registry import PENDING_USER, SUPER_ADMIN


def revoke_all_tokens(user: User) -> None:
    """Blacklist every outstanding refresh token (deactivation, password reset, role downgrade)."""
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


def _active_super_admin_count() -> int:
    return User.objects.filter(is_active=True, role__name=SUPER_ADMIN).count()


def _guard_last_super_admin(user: User, *, new_role: Role | None, new_active: bool | None) -> None:
    """Refuse changes that would leave the system without an active Super Admin."""
    if not (user.is_active and user.is_super_admin):
        return
    demoted = new_role is not None and new_role.name != SUPER_ADMIN
    deactivated = new_active is False
    if (demoted or deactivated) and _active_super_admin_count() <= 1:
        raise exceptions.ValidationError({"detail": "Cannot remove or deactivate the last active Super Admin."})


@transaction.atomic
def create_user(*, actor: User, request: Any, validated: dict[str, Any]) -> User:
    user = User.objects.create_user(
        email=validated["email"],
        password=validated["password"],
        role=validated["role"],
        full_name=validated["full_name"],
        is_active=validated.get("is_active", True),
        email_verified_at=timezone.now(),
        approval_status=Approval.APPROVED,
    )
    audit.log(
        "user.created", request=request, actor=actor, resource_type="user", resource_id=user.pk,
        changes={"email": user.email, "role": user.role.name},
    )  # fmt: skip
    return user


@transaction.atomic
def update_user(*, actor: User, request: Any, user: User, validated: dict[str, Any]) -> User:
    user = User.objects.select_for_update().select_related("role").get(pk=user.pk)
    new_role: Role | None = validated.get("role")
    new_active: bool | None = validated.get("is_active")
    _guard_last_super_admin(user, new_role=new_role, new_active=new_active)

    changes: dict[str, Any] = {}
    for field, new in validated.items():
        old = getattr(user, field)
        if old != new:
            changes[field] = {
                "from": getattr(old, "name", old),
                "to": getattr(new, "name", new),
            }
            setattr(user, field, new)
    if changes:
        user.save()
        if "is_active" in changes and not user.is_active or "role" in changes:
            revoke_all_tokens(user)
        audit.log(
            "user.updated", request=request, actor=actor, resource_type="user", resource_id=user.pk,
            changes=changes,
        )  # fmt: skip
    return user


@transaction.atomic
def reset_password(*, actor: User, request: Any, user: User, new_password: str) -> None:
    user.set_password(new_password)
    user.failed_login_count = 0
    user.locked_until = None
    user.save()
    revoke_all_tokens(user)
    audit.log("user.password_reset", request=request, actor=actor, resource_type="user", resource_id=user.pk)


@transaction.atomic
def register_user(*, request: Any, email: str, full_name: str, password: str) -> User:
    """Self-registration: no permissions (pending role), unverified, awaiting approval."""
    user = User.objects.create_user(
        email=email, password=password, role=Role.objects.get(name=PENDING_USER), full_name=full_name,
        email_verified_at=None, approval_status=Approval.PENDING,
    )  # fmt: skip
    audit.log(
        "user.registered",
        request=request,
        actor=None,
        actor_email=email[:254],
        resource_type="user",
        resource_id=user.pk,
    )
    queue_account_email("verify", user)
    return user


@transaction.atomic
def verify_email(*, request: Any, user: User) -> User:
    if user.is_email_verified:
        return user
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at", "updated_at"])
    audit.log("user.email_verified", request=request, actor=user, resource_type="user", resource_id=user.pk)
    if user.approval_status == Approval.PENDING:
        queue_account_email("pending_notice", user)
    return user


@transaction.atomic
def complete_password_reset(*, request: Any, user: User, new_password: str) -> None:
    user.set_password(new_password)
    user.failed_login_count = 0
    user.locked_until = None
    user.save()
    revoke_all_tokens(user)
    audit.log("auth.password_reset_completed", request=request, actor=user, resource_type="user", resource_id=user.pk)


@transaction.atomic
def approve_user(*, actor: User, request: Any, user: User, role: Role) -> User:
    user = User.objects.select_for_update().select_related("role").get(pk=user.pk)
    if user.approval_status != Approval.PENDING:
        raise exceptions.ValidationError({"detail": "This account is not waiting for approval."})
    if not user.is_email_verified:
        raise exceptions.ValidationError({"detail": "The user has not confirmed their email address yet."})
    user.role, user.approval_status, user.is_active = role, Approval.APPROVED, True
    user.save()
    audit.log(
        "user.approved",
        request=request,
        actor=actor,
        resource_type="user",
        resource_id=user.pk,
        changes={"role": role.name},
    )
    queue_account_email("approved", user)
    return user


@transaction.atomic
def reject_user(*, actor: User, request: Any, user: User) -> User:
    user = User.objects.select_for_update().select_related("role").get(pk=user.pk)
    if user.approval_status != Approval.PENDING:
        raise exceptions.ValidationError({"detail": "This account is not waiting for approval."})
    user.approval_status, user.is_active = Approval.REJECTED, False
    user.save()
    audit.log("user.rejected", request=request, actor=actor, resource_type="user", resource_id=user.pk)
    return user
