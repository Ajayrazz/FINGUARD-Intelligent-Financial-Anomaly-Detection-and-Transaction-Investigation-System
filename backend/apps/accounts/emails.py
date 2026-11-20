"""Account emails (verification, password reset, approval). Sent by Celery so the request time does not depend on
SMTP and cannot reveal whether an address is registered. Bodies contain a link and no other personal data."""

from __future__ import annotations

import logging
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.core.mail import send_mail
from django.db import transaction
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .models import User

log = logging.getLogger(__name__)
VERIFY_SALT = "finguard.verify-email"
VERIFY_MAX_AGE = 24 * 3600


def verification_token(user: User) -> str:
    return signing.dumps({"u": user.pk, "e": user.email}, salt=VERIFY_SALT)


def read_verification_token(token: str) -> User | None:
    """The user the token was issued for, or None if it is forged, expired or the address has since changed."""
    try:
        data = signing.loads(token, salt=VERIFY_SALT, max_age=VERIFY_MAX_AGE)
        user = User.objects.select_related("role").get(pk=data["u"])
    except (signing.BadSignature, User.DoesNotExist, KeyError, TypeError):
        return None
    return user if user.email == data.get("e") else None


def reset_uid_and_token(user: User) -> tuple[str, str]:
    return urlsafe_base64_encode(force_bytes(user.pk)), default_token_generator.make_token(user)


def read_reset(uid: str, token: str) -> User | None:
    try:
        user = User.objects.select_related("role").get(pk=urlsafe_base64_decode(uid).decode())
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        return None
    return user if default_token_generator.check_token(user, token) else None


def _link(path: str, **params: str) -> str:
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}{path}?{urlencode(params)}"


def _send(to: list[str], subject: str, body: str) -> None:
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, to, fail_silently=False)


def send_account_email(kind: str, user_id: int) -> None:
    user = User.objects.filter(pk=user_id).first()
    if user is None:
        return
    if kind == "verify":
        link = _link("/verify-email", token=verification_token(user))
        _send([user.email], "Confirm your FinGuard email address",
              f"Hello {user.full_name},\n\nConfirm your email address to continue:\n{link}\n\nThe link works for 24 hours. "
              "After that an administrator must approve your account before you can sign in.\n\nIf you did not register, ignore this email.\n")  # fmt: skip
    elif kind == "reset":
        uid, token = reset_uid_and_token(user)
        link = _link("/reset-password", uid=uid, token=token)
        _send([user.email], "Reset your FinGuard password",
              f"Hello {user.full_name},\n\nUse this link to choose a new password:\n{link}\n\nThe link works once and expires in "
              "one hour. If you did not ask for it, ignore this email; your password is unchanged.\n")  # fmt: skip
    elif kind == "approved":
        _send([user.email], "Your FinGuard account is approved",
              f"Hello {user.full_name},\n\nAn administrator approved your account. You can sign in now:\n{_link('/login')}\n")  # fmt: skip
    elif kind == "pending_notice":  # to administrators
        admins = list(User.objects.filter(is_active=True, role__name="super_admin").values_list("email", flat=True))
        if admins:
            _send(admins, "A new FinGuard account is waiting for approval",
                  f"{user.full_name} ({user.email}) confirmed their email address.\n\nReview it under User Management:\n{_link('/users')}\n")  # fmt: skip


def queue_account_email(kind: str, user: User) -> None:
    """Send after the surrounding transaction commits; a broken mail setup must not break the request."""
    from .tasks import send_account_email_task

    def _go() -> None:
        try:
            send_account_email_task.delay(kind, user.pk)
        except Exception:  # noqa: BLE001 - broker down: the user can use "resend"
            log.exception("could not queue %s email for user %s", kind, user.pk)

    transaction.on_commit(_go)
