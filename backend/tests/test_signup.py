"""Self-registration (approval queue), email verification, password reset: the whole account lifecycle."""

import re
from datetime import timedelta

import pytest
from django.core import mail, signing
from django.test.utils import CaptureQueriesContext  # noqa: F401
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import emails
from apps.accounts.models import Role, User
from apps.audit.models import AuditLog

from .conftest import STRONG_PASSWORD

pytestmark = pytest.mark.django_db
REGISTER = "/api/v1/auth/register/"
NEW = {
    "email": "New.Person@Example.com",
    "full_name": "New  Person",
    "password": "Correct-Horse-Battery-9",
    "accept_terms": True,
}


def token_from_mail(index=-1):
    m = re.search(r"token=([^\s&]+)", mail.outbox[index].body)
    assert m, mail.outbox[index].body
    return m.group(1)


def reset_params_from_mail(index=-1):
    body = mail.outbox[index].body
    return re.search(r"uid=([^&\s]+)", body).group(1), re.search(r"token=([^\s&]+)", body).group(1)


@pytest.fixture
def anon():
    return APIClient()


@pytest.fixture
def registered(anon, run_tasks):
    with run_tasks(execute=True):
        res = anon.post(REGISTER, NEW, format="json")
    assert res.status_code == 202
    return User.objects.get(email="new.person@example.com")


# ------------------------------------------------------------------ registration
def test_registration_creates_a_pending_unverified_account_with_no_access(registered):
    u = registered
    assert u.approval_status == "pending" and u.email_verified_at is None and u.role.name == "pending_user"
    assert u.full_name == "New Person" and u.email == "new.person@example.com"  # normalised
    assert u.permission_codenames == frozenset()
    assert u.check_password(NEW["password"]) and NEW["password"] not in u.password
    assert AuditLog.objects.filter(action="user.registered", resource_id=str(u.pk)).exists()
    assert len(mail.outbox) == 1 and "Confirm your FinGuard email" in mail.outbox[0].subject
    assert NEW["password"] not in mail.outbox[0].body


def test_registration_response_never_reveals_whether_an_email_exists(anon, run_tasks, make_user):
    existing = make_user("auditor", email="taken@example.com")
    with run_tasks(execute=True):
        fresh = anon.post(REGISTER, {**NEW, "email": "fresh@example.com"}, format="json")
        dup = anon.post(REGISTER, {**NEW, "email": existing.email}, format="json")
    assert fresh.status_code == dup.status_code == 202 and fresh.json() == dup.json()
    assert User.objects.filter(email__iexact=existing.email).count() == 1
    assert len(mail.outbox) == 1  # only the new address got a link
    assert AuditLog.objects.filter(action="user.register_duplicate").exists()


@pytest.mark.parametrize(
    "patch,field",
    [({"password": "short"}, "password"), ({"password": "password1234"}, "password"), ({"email": "not-an-email"}, "email"),
     ({"full_name": "x"}, "full_name"), ({"accept_terms": False}, "accept_terms"), ({"password": "new.person@example.com"}, "password")],
)  # fmt: skip
def test_registration_validates_input(anon, patch, field):
    res = anon.post(REGISTER, {**NEW, **patch}, format="json")
    assert res.status_code == 400 and field in str(res.json()), res.json()
    assert not User.objects.filter(email="new.person@example.com").exists()


def test_weak_password_error_is_reported_on_the_password_field(anon):
    res = anon.post(REGISTER, {**NEW, "password": "password1234"}, format="json")
    assert (
        res.status_code == 400
        and "password" in res.json()["error"]["details"]
        and "non_field_errors" not in res.json()["error"]["details"]
    )


def test_registration_cannot_choose_a_role_or_approval(anon, run_tasks):
    with run_tasks(execute=True):
        anon.post(
            REGISTER,
            {
                **NEW,
                "role": "super_admin",
                "approval_status": "approved",
                "is_active": True,
                "email_verified_at": "2020-01-01T00:00:00Z",
            },
            format="json",
        )
    u = User.objects.get(email="new.person@example.com")
    assert u.role.name == "pending_user" and u.approval_status == "pending" and u.email_verified_at is None


def test_registration_is_throttled(anon, settings):
    from django.core.cache import cache

    cache.clear()
    codes = [anon.post(REGISTER, {**NEW, "email": f"u{i}@example.com"}, format="json").status_code for i in range(7)]
    assert codes[:5] == [202] * 5 and 429 in codes[5:]


# ------------------------------------------------------------------ login gates and verification
def test_unverified_and_unapproved_accounts_cannot_sign_in_but_only_after_the_password_is_right(registered, anon):
    login = lambda pw: anon.post("/api/v1/auth/login/", {"email": registered.email, "password": pw}, format="json")  # noqa: E731
    wrong = login("Wrong-password-123!")
    assert (
        wrong.status_code == 401 and wrong.json()["error"]["code"] == "invalid_credentials"
    )  # nothing about the account state
    res = login(NEW["password"])
    assert res.status_code == 403 and res.json()["error"]["code"] == "email_not_verified"
    assert "fg_refresh" not in res.cookies


def test_verification_link_confirms_the_email_and_notifies_administrators(registered, anon, make_user, run_tasks):
    admin = make_user("super_admin", email="boss@example.com")
    mail.outbox.clear()
    token = emails.verification_token(registered)
    with run_tasks(execute=True):
        res = anon.post("/api/v1/auth/verify-email/", {"token": token}, format="json")
    assert res.status_code == 200 and res.json() == {"status": "pending_approval"}
    registered.refresh_from_db()
    assert registered.email_verified_at is not None and registered.approval_status == "pending"
    assert [m.to for m in mail.outbox] == [[admin.email]] and "waiting for approval" in mail.outbox[0].subject
    login = anon.post("/api/v1/auth/login/", {"email": registered.email, "password": NEW["password"]}, format="json")
    assert login.status_code == 403 and login.json()["error"]["code"] == "pending_approval"
    assert anon.post("/api/v1/auth/verify-email/", {"token": token}, format="json").json() == {
        "status": "pending_approval"
    }  # idempotent


def test_verification_tokens_that_are_forged_expired_or_for_a_changed_address_are_refused(registered, anon):
    good = emails.verification_token(registered)
    forged = signing.dumps({"u": registered.pk, "e": registered.email}, salt="some-other-salt")
    expired = signing.dumps({"u": registered.pk, "e": registered.email}, salt=emails.VERIFY_SALT)
    for token in ("garbage", good[:-3] + "xyz", forged, ""):
        assert anon.post("/api/v1/auth/verify-email/", {"token": token}, format="json").status_code in (400,), token
    # expiry: move the clock past 24 hours
    import time

    real = time.time
    time.time = lambda: real() + emails.VERIFY_MAX_AGE + 60
    try:
        assert anon.post("/api/v1/auth/verify-email/", {"token": expired}, format="json").status_code == 400
    finally:
        time.time = real
    registered.email = "changed@example.com"
    registered.save()
    assert anon.post("/api/v1/auth/verify-email/", {"token": good}, format="json").status_code == 400


def test_resend_only_for_unverified_pending_accounts_with_a_generic_answer(registered, anon, run_tasks, make_user):
    mail.outbox.clear()
    other = make_user("auditor", email="done@example.com")
    with run_tasks(execute=True):
        a = anon.post("/api/v1/auth/resend-verification/", {"email": registered.email}, format="json")
        b = anon.post("/api/v1/auth/resend-verification/", {"email": other.email}, format="json")
        c = anon.post("/api/v1/auth/resend-verification/", {"email": "nobody@example.com"}, format="json")
    assert a.status_code == b.status_code == c.status_code == 202 and a.json() == b.json() == c.json()
    assert len(mail.outbox) == 1 and mail.outbox[0].to == [registered.email]


# ------------------------------------------------------------------ admin approval
def verified_pending(anon, run_tasks):
    with run_tasks(execute=True):
        anon.post(REGISTER, NEW, format="json")
        u = User.objects.get(email="new.person@example.com")
        anon.post("/api/v1/auth/verify-email/", {"token": emails.verification_token(u)}, format="json")
    u.refresh_from_db()
    return u


def test_admin_approves_with_a_role_and_the_user_can_then_sign_in(anon, run_tasks, make_user, api_as):
    admin = api_as(make_user("super_admin"))
    u = verified_pending(anon, run_tasks)
    listed = admin.get("/api/v1/users/", {"approval_status": "pending"}).json()["results"]
    assert [x["email"] for x in listed] == [u.email] and listed[0]["email_verified"] is True
    mail.outbox.clear()
    with run_tasks(execute=True):
        res = admin.post(f"/api/v1/users/{u.pk}/approve/", {"role": "financial_analyst"}, format="json")
    assert (
        res.status_code == 200
        and res.json()["approval_status"] == "approved"
        and res.json()["role"] == "financial_analyst"
    )
    assert "approved" in mail.outbox[0].subject and AuditLog.objects.filter(action="user.approved").exists()
    login = anon.post("/api/v1/auth/login/", {"email": u.email, "password": NEW["password"]}, format="json")
    assert login.status_code == 200 and "transactions.read" in login.json()["user"]["permissions"]


def test_approval_rules(anon, run_tasks, make_user, api_as, registered):
    admin = api_as(make_user("super_admin"))
    assert (
        admin.post(f"/api/v1/users/{registered.pk}/approve/", {"role": "auditor"}, format="json").status_code == 400
    )  # not verified
    u = verified_pending(anon, run_tasks)
    assert (
        admin.post(f"/api/v1/users/{u.pk}/approve/", {"role": "pending_user"}, format="json").status_code == 400
    )  # no-access role
    assert admin.post(f"/api/v1/users/{u.pk}/approve/", {"role": "nonexistent"}, format="json").status_code == 400
    assert admin.post(f"/api/v1/users/{u.pk}/approve/", {"role": "auditor"}, format="json").status_code == 200
    assert (
        admin.post(f"/api/v1/users/{u.pk}/approve/", {"role": "auditor"}, format="json").status_code == 400
    )  # already approved
    for role in ("financial_analyst", "fraud_investigator", "auditor", "management"):
        assert (
            api_as(make_user(role))
            .post(f"/api/v1/users/{u.pk}/approve/", {"role": "auditor"}, format="json")
            .status_code
            == 403
        )


def test_rejection_blocks_the_account_without_revealing_why(anon, run_tasks, make_user, api_as):
    admin = api_as(make_user("super_admin"))
    u = verified_pending(anon, run_tasks)
    assert admin.post(f"/api/v1/users/{u.pk}/reject/").status_code == 200
    u.refresh_from_db()
    assert u.approval_status == "rejected" and not u.is_active
    res = anon.post("/api/v1/auth/login/", {"email": u.email, "password": NEW["password"]}, format="json")
    assert res.status_code == 401 and res.json()["error"]["code"] == "invalid_credentials"
    assert admin.post(f"/api/v1/users/{u.pk}/reject/").status_code == 400  # not pending any more


def test_admin_created_users_are_verified_and_approved_and_can_sign_in(make_user, api_as, anon):
    admin = api_as(make_user("super_admin"))
    res = admin.post(
        "/api/v1/users/",
        {"email": "made@example.com", "full_name": "Made", "role": "auditor", "password": "Correct-Horse-Battery-9"},
        format="json",
    )
    assert res.status_code == 201 and res.json()["email_verified"] and res.json()["approval_status"] == "approved"
    assert (
        anon.post(
            "/api/v1/auth/login/", {"email": "made@example.com", "password": "Correct-Horse-Battery-9"}, format="json"
        ).status_code
        == 200
    )


def test_existing_pending_role_gives_no_access_even_if_a_token_existed(registered, api_as):
    c = api_as(registered)
    for url in (
        "/api/v1/transactions/",
        "/api/v1/cases/",
        "/api/v1/alerts/",
        "/api/v1/users/",
        "/api/v1/analytics/overview/",
        "/api/v1/audit/logs/",
    ):
        assert c.get(url).status_code == 403, url


# ------------------------------------------------------------------ password reset
def test_password_reset_flow_changes_the_password_revokes_sessions_and_the_link_works_once(make_user, anon, run_tasks):
    user = make_user("auditor", email="reset@example.com")
    login = anon.post("/api/v1/auth/login/", {"email": user.email, "password": STRONG_PASSWORD}, format="json")
    cookie = login.cookies["fg_refresh"].value
    mail.outbox.clear()
    with run_tasks(execute=True):
        assert anon.post("/api/v1/auth/password-reset/", {"email": user.email}, format="json").status_code == 202
    assert len(mail.outbox) == 1 and "Reset your FinGuard password" in mail.outbox[0].subject
    uid, token = reset_params_from_mail()
    weak = anon.post(
        "/api/v1/auth/password-reset/confirm/", {"uid": uid, "token": token, "new_password": "short"}, format="json"
    )
    assert weak.status_code == 400 and "new_password" in str(weak.json())
    ok = anon.post(
        "/api/v1/auth/password-reset/confirm/",
        {"uid": uid, "token": token, "new_password": "Brand-New-Passphrase-42"},
        format="json",
    )
    assert ok.status_code == 204
    again = anon.post(
        "/api/v1/auth/password-reset/confirm/",
        {"uid": uid, "token": token, "new_password": "Another-Passphrase-77"},
        format="json",
    )
    assert again.status_code == 400  # one use only
    assert (
        anon.post("/api/v1/auth/login/", {"email": user.email, "password": STRONG_PASSWORD}, format="json").status_code
        == 401
    )
    assert (
        anon.post(
            "/api/v1/auth/login/", {"email": user.email, "password": "Brand-New-Passphrase-42"}, format="json"
        ).status_code
        == 200
    )
    stale = APIClient()
    stale.cookies["fg_refresh"] = cookie
    assert stale.post("/api/v1/auth/refresh/").status_code == 401  # old session revoked
    assert AuditLog.objects.filter(action="auth.password_reset_completed").exists()


def test_password_reset_request_is_generic_and_only_emails_real_active_accounts(anon, run_tasks, make_user, registered):
    real = make_user("auditor", email="real@example.com")
    inactive = make_user("auditor", email="off@example.com", is_active=False)
    mail.outbox.clear()
    with run_tasks(execute=True):
        answers = [
            anon.post("/api/v1/auth/password-reset/", {"email": e}, format="json")
            for e in (real.email, "ghost@example.com", inactive.email, registered.email)
        ]
    assert {a.status_code for a in answers} == {202} and len({str(a.json()) for a in answers}) == 1
    assert [m.to for m in mail.outbox] == [[real.email]]  # not unknown, inactive, nor an unverified pending account


def test_reset_tokens_that_are_forged_or_for_other_users_fail(make_user, anon, run_tasks):
    a, b = make_user("auditor", email="a@example.com"), make_user("auditor", email="b@example.com")
    uid_a, tok_a = emails.reset_uid_and_token(a)
    uid_b, _ = emails.reset_uid_and_token(b)
    for uid, tok in ((uid_a, "bogus"), (uid_b, tok_a), ("!!", tok_a), (uid_a, tok_a[:-2] + "zz")):
        res = anon.post(
            "/api/v1/auth/password-reset/confirm/",
            {"uid": uid, "token": tok, "new_password": "Brand-New-Passphrase-42"},
            format="json",
        )
        assert res.status_code == 400, (uid, tok)


def test_reset_clears_a_lockout(make_user, anon):
    user = make_user("auditor", email="locked@example.com")
    user.locked_until = timezone.now() + timedelta(minutes=10)
    user.failed_login_count = 3
    user.save()
    uid, tok = emails.reset_uid_and_token(user)
    assert (
        anon.post(
            "/api/v1/auth/password-reset/confirm/",
            {"uid": uid, "token": tok, "new_password": "Brand-New-Passphrase-42"},
            format="json",
        ).status_code
        == 204
    )
    user.refresh_from_db()
    assert user.locked_until is None and user.failed_login_count == 0


def test_pending_role_is_seeded_with_no_permissions():
    assert Role.objects.get(name="pending_user").permissions.count() == 0
