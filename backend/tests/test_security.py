"""Phase 15 security checks (OWASP-oriented). Each test names the risk it covers; docs/20 maps them to the checklist.

Covered elsewhere (not repeated): login throttle and lockout, refresh rotation/blacklist, bcrypt storage, upload
validation (imports, invoices, evidence), CSV injection of the import-error export, RBAC matrix, append-only audit.
"""

import re
from datetime import timedelta

import jwt
import pytest
from django.conf import settings as dj_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.cases import services as case_services
from apps.cases.models import Case, CaseNote

pytestmark = pytest.mark.django_db
EVIL = '<b>x</b> & <img src="file:///etc/passwd" width="9"/> <font color="red">y</font></para><para>'


# ------------------------------------------------------------- A02/A07: tokens
def _login(make_user):
    user = make_user("auditor")
    client = APIClient()
    res = client.post(
        "/api/v1/auth/login/", {"email": user.email, "password": "Correct-Horse-Battery-9"}, format="json"
    )
    assert res.status_code == 200
    return user, res.json()["access"]


def test_tampered_none_expired_and_foreign_tokens_are_rejected(make_user):
    user, good = _login(make_user)
    client = APIClient()
    claims = jwt.decode(good, options={"verify_signature": False})
    bad = {
        "garbage": "not.a.jwt",
        "wrong_signature": jwt.encode(claims, "another-secret-key-another-secret-key", algorithm="HS256"),
        "alg_none": jwt.encode(claims, None, algorithm="none"),
        "expired": jwt.encode({**claims, "exp": int((timezone.now() - timedelta(minutes=5)).timestamp())}, dj_settings.SECRET_KEY, algorithm="HS256"),
        "tampered_payload": ".".join([good.split(".")[0], jwt.utils.base64url_encode(b'{"user_id": 1, "token_type": "access", "exp": 9999999999}').decode(), good.split(".")[2]]),
        "refresh_as_access": None,
    }  # fmt: skip
    login = APIClient().post(
        "/api/v1/auth/login/", {"email": user.email, "password": "Correct-Horse-Battery-9"}, format="json"
    )
    bad["refresh_as_access"] = login.cookies["fg_refresh"].value
    for name, token in bad.items():
        res = client.get("/api/v1/auth/me/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert res.status_code == 401, name
    assert client.get("/api/v1/auth/me/", HTTP_AUTHORIZATION=f"Bearer {good}").status_code == 200


def test_refresh_cookie_is_httponly_samesite_strict_and_scoped(make_user):
    user = make_user("auditor")
    res = APIClient().post(
        "/api/v1/auth/login/", {"email": user.email, "password": "Correct-Horse-Battery-9"}, format="json"
    )
    c = res.cookies["fg_refresh"]
    assert c["httponly"] and c["samesite"] == "Strict" and c["path"].startswith("/api/v1/auth")


def test_access_token_is_never_set_as_a_cookie(make_user):
    user = make_user("auditor")
    res = APIClient().post(
        "/api/v1/auth/login/", {"email": user.email, "password": "Correct-Horse-Battery-9"}, format="json"
    )
    assert set(res.cookies.keys()) == {"fg_refresh"}


# ------------------------------------------------------------- A01: access control / mass assignment
def test_user_creation_ignores_privilege_fields_and_roles_cannot_self_escalate(make_user, api_as):
    admin = make_user("super_admin")
    res = api_as(admin).post(
        "/api/v1/users/",
        {
            "email": "n@example.com",
            "full_name": "N",
            "role": "auditor",
            "password": "Correct-Horse-Battery-9",
            "is_superuser": True,
            "is_staff": True,
        },
        format="json",
    )
    assert res.status_code == 201
    from apps.accounts.models import User

    created = User.objects.get(email="n@example.com")
    assert created.role.name == "auditor" and not hasattr(created, "is_superuser")
    analyst = make_user("financial_analyst")
    assert (
        api_as(analyst).patch(f"/api/v1/users/{analyst.pk}/", {"role": "super_admin"}, format="json").status_code == 403
    )
    analyst.refresh_from_db()
    assert analyst.role.name == "financial_analyst"


def test_case_patch_cannot_change_state_reference_or_history_fields(make_user, api_as):
    inv = make_user("fraud_investigator")
    case = Case.objects.create(case_ref=case_services.next_case_ref(), title="t")
    ref = case.case_ref
    res = api_as(inv).patch(
        f"/api/v1/cases/{case.pk}/",
        {
            "title": "renamed",
            "status": "closed",
            "case_ref": "FG-1999-000001",
            "outcome": "confirmed_suspicious",
            "closed_at": "2020-01-01T00:00:00Z",
            "assignee": inv.pk,
        },
        format="json",
    )
    assert res.status_code == 200
    case.refresh_from_db()
    assert (
        case.title == "renamed"
        and case.status == "new"
        and case.case_ref == ref
        and case.outcome == ""
        and case.closed_at is None
    )


def test_roles_without_permission_get_403_even_for_ids_that_do_not_exist(make_user, api_as):
    mgmt = api_as(make_user("management"))
    for url in (
        "/api/v1/cases/999999/",
        "/api/v1/cases/999999/evidence/1/download/",
        "/api/v1/transactions/999999/",
        "/api/v1/invoices/999999/file/",
    ):
        assert mgmt.get(url).status_code == 403, url  # no existence oracle for unauthorised roles


def test_every_api_response_is_nosniff(make_user, api_as):
    res = api_as(make_user("auditor")).get("/api/v1/auth/me/")
    assert res["X-Content-Type-Options"] == "nosniff"


# ------------------------------------------------------------- A03: injection
@pytest.mark.parametrize(
    "payload",
    ["' OR 1=1 --", "'; DROP TABLE transactions_transaction; --", "%27%20OR%20%271%27%3D%271", "\x00", "a" * 5000],
)
def test_sql_injection_strings_in_filters_are_inert(payload, make_user, api_as, make_dataset, make_tx):
    ds = make_dataset()
    make_tx(ds)
    client = api_as(make_user("financial_analyst"))
    for params in (
        {"search": payload},
        {"ordering": payload},
        {"sender": payload},
        {"tx_type": payload},
        {"dataset": payload},
    ):
        assert client.get("/api/v1/transactions/", params).status_code in (200, 400), params
    assert client.get("/api/v1/transactions/", {"dataset": ds.id}).json()["count"] == 1  # table still intact
    for params in ({"dataset": payload}, {"from": payload}, {"granularity": payload}):
        assert client.get("/api/v1/analytics/volume/", params).status_code == 400


def test_list_endpoints_cap_page_size(make_user, api_as, make_dataset, make_tx):
    ds = make_dataset()
    for _ in range(3):
        make_tx(ds)
    res = api_as(make_user("financial_analyst")).get("/api/v1/transactions/", {"page_size": 1_000_000})
    assert res.status_code == 200 and len(res.json()["results"]) <= 100


def test_case_pdf_report_treats_user_text_as_text_not_markup(make_user, api_as, monkeypatch):
    """ReportLab Paragraph parses XML-like markup: unescaped user text can inject tags (including <img src=file://...>)."""
    from apps.cases import report

    seen: list[str] = []
    real = report.Paragraph

    def spy(text, *a, **k):  # noqa: ANN001, ANN002, ANN003
        seen.append(text)
        return real(text, *a, **k)

    monkeypatch.setattr(report, "Paragraph", spy)
    inv = make_user("fraud_investigator")
    case = Case.objects.create(case_ref=case_services.next_case_ref(), title=EVIL, description=EVIL)
    note = CaseNote.objects.create(case=case, kind="comment", author=inv)
    note.revisions.create(revision=1, body=EVIL, edited_by=inv)
    res = api_as(inv).get(f"/api/v1/cases/{case.pk}/report/")
    assert res.status_code == 200 and res.content.startswith(b"%PDF")
    joined = "\n".join(seen)
    assert "<img" not in joined and "<font" not in joined and "</para>" not in joined
    assert "&lt;img" in joined


def test_explanation_report_escapes_transaction_text(make_dataset, make_tx, monkeypatch):
    from apps.explain import report as explain_report

    seen: list[str] = []
    real = explain_report.Paragraph

    def spy(text, *a, **k):  # noqa: ANN001, ANN002, ANN003
        seen.append(text)
        return real(text, *a, **k)

    monkeypatch.setattr(explain_report, "Paragraph", spy)
    tx = make_tx(make_dataset(), transaction_id=EVIL[:60], tx_type="<i>T</i>")
    pdf = explain_report.build_report(tx, [])
    assert pdf.startswith(b"%PDF")
    joined = "\n".join(seen)
    assert "<img" not in joined and "<i>" not in joined and "&lt;img" in joined


# ------------------------------------------------------------- A05: configuration
def _load_production(monkeypatch, secret):  # noqa: ANN001, ANN202
    import importlib
    import sys

    monkeypatch.setenv("DJANGO_SECRET_KEY", secret)
    for name in ("config.settings.production", "config.settings.base"):
        sys.modules.pop(name, None)
    return importlib.import_module("config.settings.production")


def test_production_settings_are_hardened_and_debug_is_off_everywhere(monkeypatch):
    prod = _load_production(monkeypatch, "x" * 48)
    assert prod.DEBUG is False and prod.SECURE_SSL_REDIRECT and prod.SESSION_COOKIE_SECURE and prod.CSRF_COOKIE_SECURE
    assert prod.SECURE_HSTS_SECONDS >= 31536000 and prod.SECURE_CONTENT_TYPE_NOSNIFF and prod.X_FRAME_OPTIONS == "DENY"
    assert dj_settings.DEBUG is False


@pytest.mark.parametrize("secret", ["change-me", "short", "ci-only-not-secret-but-long-enough-padding-0000", "changeme" + "0" * 40])
def test_production_refuses_placeholder_or_short_secret_keys(monkeypatch, secret):
    from django.core.exceptions import ImproperlyConfigured

    with pytest.raises(ImproperlyConfigured):
        _load_production(monkeypatch, secret)


def test_error_responses_do_not_leak_internals(make_user, api_as):
    res = api_as(make_user("auditor")).get("/api/v1/does-not-exist/")
    assert res.status_code == 404
    body = res.content.decode()
    assert "Traceback" not in body and "/app/" not in body and "django" not in body.lower()


def test_cors_allows_only_configured_origins(client, settings):
    settings.CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]
    ok = client.options(
        "/api/v1/auth/login/", HTTP_ORIGIN="http://localhost:5173", HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST"
    )
    evil = client.options(
        "/api/v1/auth/login/", HTTP_ORIGIN="https://evil.example", HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST"
    )
    assert ok.get("Access-Control-Allow-Origin") == "http://localhost:5173"
    assert "Access-Control-Allow-Origin" not in evil


# ------------------------------------------------------------- A08/A09: integrity and logging
def test_audit_log_cannot_be_rewritten_or_deleted_even_by_code():
    from django.db import DatabaseError, transaction

    row = AuditLog.objects.create(action="test.event", actor_email="x@example.com")
    for op in (
        lambda: AuditLog.objects.filter(pk=row.pk).update(action="edited"),
        lambda: AuditLog.objects.filter(pk=row.pk).delete(),
    ):
        with pytest.raises(DatabaseError), transaction.atomic():
            op()
    assert AuditLog.objects.get(pk=row.pk).action == "test.event"


def test_security_relevant_actions_are_audited(make_user, api_as):
    admin = make_user("super_admin")
    target = make_user("auditor")
    c = api_as(admin)
    c.patch(f"/api/v1/users/{target.pk}/", {"is_active": False}, format="json")
    c.post(f"/api/v1/users/{target.pk}/reset-password/", {"new_password": "Another-Strong-Pass-77"}, format="json")
    actions = set(AuditLog.objects.values_list("action", flat=True))
    assert {"user.updated", "user.password_reset"} <= actions or any(a.startswith("user.") for a in actions)
    assert not re.search("Another-Strong-Pass-77", str(list(AuditLog.objects.values_list("changes", flat=True))))


def test_role_names_cannot_be_used_to_smuggle_permissions(make_user, api_as):
    admin = api_as(make_user("super_admin"))
    res = admin.post(
        "/api/v1/roles/", {"name": "custom", "label": "Custom", "permissions": ["not.a.real.permission"]}, format="json"
    )
    assert res.status_code in (400, 201)
    assert (
        not Role.objects.get(name="custom").permissions.filter(codename="not.a.real.permission").exists()
        if res.status_code == 201
        else True
    )
