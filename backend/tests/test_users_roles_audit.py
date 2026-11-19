import pytest
from django.db import DatabaseError, connection

from apps.accounts.models import Role, User
from apps.audit import services as audit
from apps.audit.models import AuditLog

from .conftest import STRONG_PASSWORD

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------- users
def test_admin_creates_user_and_it_is_audited(make_user, api_as):
    admin = make_user("super_admin")
    res = api_as(admin).post(
        "/api/v1/users/",
        {
            "email": "New.Person@Example.com",
            "full_name": "New Person",
            "role": "auditor",
            "password": STRONG_PASSWORD,
        },
        format="json",
    )
    assert res.status_code == 201, res.data
    assert res.data["email"] == "new.person@example.com"
    assert "password" not in res.data
    entry = AuditLog.objects.get(action="user.created")
    assert entry.actor == admin and "password" not in str(entry.changes).lower().replace("***", "")


@pytest.mark.parametrize("pw", ["short1A!", "password12345", "1234567890123"])
def test_weak_passwords_rejected(make_user, api_as, pw):
    res = api_as(make_user("super_admin")).post(
        "/api/v1/users/",
        {"email": "a@example.com", "full_name": "A", "role": "auditor", "password": pw},
        format="json",
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "validation_error"


def test_duplicate_email_rejected_case_insensitively(make_user, api_as):
    existing = make_user("auditor", email="dup@example.com")
    res = api_as(make_user("super_admin")).post(
        "/api/v1/users/",
        {"email": existing.email.upper(), "full_name": "X", "role": "auditor", "password": STRONG_PASSWORD},
        format="json",
    )
    assert res.status_code == 400


def test_cannot_demote_or_deactivate_last_super_admin(make_user, api_as):
    only_admin = make_user("super_admin")
    client = api_as(only_admin)
    assert (
        client.patch(f"/api/v1/users/{only_admin.pk}/", {"is_active": False}, format="json").status_code
        == 400
    )
    assert (
        client.patch(f"/api/v1/users/{only_admin.pk}/", {"role": "auditor"}, format="json").status_code == 400
    )
    second = make_user("super_admin")
    assert client.patch(f"/api/v1/users/{second.pk}/", {"is_active": False}, format="json").status_code == 200


def test_users_cannot_be_deleted(make_user, api_as):
    admin, other = make_user("super_admin"), make_user()
    assert api_as(admin).delete(f"/api/v1/users/{other.pk}/").status_code in (403, 405)
    assert User.objects.filter(pk=other.pk).exists()


def test_reset_password_changes_credentials_and_unlocks(make_user, api_as):
    admin, victim = make_user("super_admin"), make_user()
    res = api_as(admin).post(
        f"/api/v1/users/{victim.pk}/reset-password/",
        {"new_password": "Another-Strong-Pass-77"},
        format="json",
    )
    assert res.status_code == 204
    victim.refresh_from_db()
    assert victim.check_password("Another-Strong-Pass-77")
    assert AuditLog.objects.filter(action="user.password_reset").exists()


def test_user_list_supports_search_and_filter(make_user, api_as):
    admin = make_user("super_admin")
    make_user("auditor", email="zed@example.com", full_name="Zed Zebra")
    res = api_as(admin).get("/api/v1/users/?search=zebra")
    assert [u["email"] for u in res.data["results"]] == ["zed@example.com"]
    assert api_as(admin).get("/api/v1/users/?role__name=super_admin").data["count"] == 1


# ---------------------------------------------------------------- roles
def test_role_permission_edit_takes_effect_immediately(make_user, api_as):
    admin, analyst = make_user("super_admin"), make_user("financial_analyst")
    assert api_as(analyst).get("/api/v1/audit/logs/").status_code == 403
    role = Role.objects.get(name="financial_analyst")
    res = api_as(admin).patch(f"/api/v1/roles/{role.pk}/", {"permissions": ["audit.read"]}, format="json")
    assert res.status_code == 200
    assert (
        api_as(User.objects.get(pk=analyst.pk)).get("/api/v1/audit/logs/").status_code == 200
    )  # fresh load, as per request
    assert AuditLog.objects.filter(action="role.updated").exists()


def test_super_admin_role_is_immutable(make_user, api_as):
    admin = make_user("super_admin")
    role = Role.objects.get(name="super_admin")
    assert (
        api_as(admin).patch(f"/api/v1/roles/{role.pk}/", {"permissions": []}, format="json").status_code
        == 400
    )


def test_seeding_preserves_admin_edits_and_is_idempotent(make_user):
    from apps.accounts.seed import seed_roles

    role = Role.objects.get(name="auditor")
    role.permissions.clear()
    seed_roles()
    assert role.permissions.count() == 0  # admin's removal not re-granted
    assert Role.objects.get(name="super_admin").permissions.count() == len(
        __import__("apps.accounts.registry", fromlist=["PERMISSIONS"]).PERMISSIONS
    )


# ---------------------------------------------------------------- audit
def test_audit_log_is_append_only_at_database_level(make_user):
    entry = audit.log("test.event", actor_email="t@example.com")
    with pytest.raises(DatabaseError), connection.cursor() as cur:
        cur.execute("UPDATE audit_auditlog SET action = 'tampered' WHERE id = %s", [entry.pk])


def test_audit_log_cannot_be_deleted_at_database_level(make_user):
    entry = audit.log("test.event", actor_email="t@example.com")
    with pytest.raises(DatabaseError):
        entry.delete()


def test_audit_redacts_secrets():
    entry = audit.log("x", changes={"password": "hunter2", "nested": {"api_token": "abc"}, "ok": 1})
    assert entry.changes == {"password": "***", "nested": {"api_token": "***"}, "ok": 1}


def test_audit_endpoint_filters_and_is_read_only(make_user, api_as):
    auditor = make_user("auditor")
    audit.log("a.one", actor_email="x@example.com", resource_type="thing")
    audit.log("b.two", actor_email="y@example.com")
    client = api_as(auditor)
    assert client.get("/api/v1/audit/logs/?action=a.one").data["count"] == 1
    assert client.get("/api/v1/audit/logs/?actor_email=y@").data["count"] == 1
    assert client.post("/api/v1/audit/logs/", {}, format="json").status_code in (403, 405)
    assert client.delete("/api/v1/audit/logs/1/").status_code in (403, 405)


def test_request_id_header_present_and_validated(client):
    res = client.get("/api/v1/health/", HTTP_X_REQUEST_ID="abc-123")
    assert res["X-Request-ID"] == "abc-123"
    assert client.get("/api/v1/health/", HTTP_X_REQUEST_ID="bad id\nx")["X-Request-ID"] != "bad id\nx"
