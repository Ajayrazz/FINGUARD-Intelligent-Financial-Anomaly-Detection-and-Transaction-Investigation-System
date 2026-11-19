import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.models import AuditLog

from .conftest import STRONG_PASSWORD

pytestmark = pytest.mark.django_db
LOGIN = "/api/v1/auth/login/"


def login(client, email, password=STRONG_PASSWORD):
    return client.post(LOGIN, {"email": email, "password": password}, format="json")


def test_login_returns_access_token_and_httponly_refresh_cookie(make_user):
    user = make_user("auditor")
    res = login(APIClient(), user.email)
    assert res.status_code == 200
    assert res.data["user"]["role"] == "auditor"
    assert "audit.read" in res.data["user"]["permissions"]
    assert "refresh" not in res.data  # refresh token never in the body
    cookie = res.cookies["fg_refresh"]
    assert cookie["httponly"] and cookie["samesite"] == "Strict"
    assert AuditLog.objects.filter(action="auth.login", actor=user).count() == 1


def test_access_token_authorises_requests(make_user):
    user = make_user("auditor")
    client = APIClient()
    token = login(client, user.email).data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert client.get("/api/v1/auth/me/").data["email"] == user.email


def test_requests_without_token_are_401(db):
    assert APIClient().get("/api/v1/auth/me/").status_code == 401
    assert APIClient().get("/api/v1/users/").status_code == 401


def test_wrong_password_is_generic_401_and_audited(make_user):
    user = make_user()
    res = login(APIClient(), user.email, "wrong-password-123")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "invalid_credentials"
    unknown = login(APIClient(), "nobody@example.com")
    assert unknown.json()["error"]["message"] == res.json()["error"]["message"]  # no user enumeration
    assert AuditLog.objects.filter(action="auth.login_failed").count() == 2


def test_account_locks_after_five_failures_even_with_correct_password(make_user):
    user = make_user()
    client = APIClient()
    for _ in range(4):
        assert login(client, user.email, "bad-password-xyz").status_code == 401
    assert login(client, user.email, "bad-password-xyz").status_code == 429  # 5th triggers lockout
    assert login(client, user.email).status_code == 429  # correct password still refused
    assert AuditLog.objects.filter(action="auth.login_locked_out").exists()
    user.refresh_from_db()
    assert user.is_locked


def test_inactive_user_cannot_login(make_user):
    user = make_user(is_active=False)
    assert login(APIClient(), user.email).status_code == 401


def test_login_endpoint_is_throttled(make_user):
    client = APIClient()
    codes = [login(client, f"nobody{i}@example.com").status_code for i in range(12)]
    assert codes[-1] == 429 and 401 in codes


def test_refresh_rotates_and_old_token_is_blacklisted(make_user):
    user = make_user()
    client = APIClient()
    login(client, user.email)
    old = client.cookies["fg_refresh"].value
    res = client.post("/api/v1/auth/refresh/")
    assert res.status_code == 200 and "access" in res.data
    new = res.cookies["fg_refresh"].value
    assert new != old
    replay = APIClient()
    replay.cookies["fg_refresh"] = old
    assert replay.post("/api/v1/auth/refresh/").status_code == 401  # reuse of rotated token rejected


def test_refresh_without_cookie_is_401(db):
    assert APIClient().post("/api/v1/auth/refresh/").status_code == 401


def test_logout_blacklists_refresh_token_and_is_audited(make_user):
    user = make_user()
    client = APIClient()
    login(client, user.email)
    token = client.cookies["fg_refresh"].value
    assert client.post("/api/v1/auth/logout/").status_code == 204
    replay = APIClient()
    replay.cookies["fg_refresh"] = token
    assert replay.post("/api/v1/auth/refresh/").status_code == 401
    assert AuditLog.objects.filter(action="auth.logout", actor=user).exists()


def test_deactivation_revokes_existing_refresh_tokens(make_user, api_as):
    admin = make_user("super_admin")
    victim = make_user()
    token = str(RefreshToken.for_user(victim))
    res = api_as(admin).patch(f"/api/v1/users/{victim.pk}/", {"is_active": False}, format="json")
    assert res.status_code == 200
    client = APIClient()
    client.cookies["fg_refresh"] = token
    assert client.post("/api/v1/auth/refresh/").status_code == 401


def test_passwords_are_stored_with_bcrypt(make_user):
    assert make_user().password.startswith("bcrypt_sha256$")
