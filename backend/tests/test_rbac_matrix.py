"""Generated RBAC verification: every API route x every role (docs/10, Phase 2 acceptance).

1. Completeness: every route under /api/v1 either declares required_permissions or is an allow-listed
   public/auth endpoint. A new endpoint added without a permission declaration fails this test.
2. Enforcement: for each declared (endpoint, codename) and each role, the response is 403 exactly when
   the role lacks the codename, and never 403 when it has it.
"""

import pytest
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.accounts.registry import ROLES

pytestmark = pytest.mark.django_db

PUBLIC_ROUTE_NAMES = {"health", "health-ready", "auth-login", "auth-refresh", "auth-logout"}
AUTHENTICATED_ONLY_NAMES = {"auth-me"}  # any authenticated user, no role permission


def _walk(patterns, prefix=""):
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from _walk(p.url_patterns, prefix + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefix + str(p.pattern), p


def _api_routes():
    for route, pattern in _walk(get_resolver().url_patterns):
        if route.startswith("api/v1/"):
            yield route, pattern


def test_every_route_declares_a_permission_or_is_allowlisted():
    missing = []
    for route, pattern in _api_routes():
        if pattern.name in PUBLIC_ROUTE_NAMES | AUTHENTICATED_ONLY_NAMES:
            continue
        view_cls = getattr(pattern.callback, "cls", None) or getattr(pattern.callback, "view_class", None)
        required = getattr(view_cls, "required_permissions", None)
        if not required:
            missing.append(route)
            continue
        actions = getattr(pattern.callback, "actions", None)
        if actions:
            allowed = set(getattr(view_cls, "http_method_names", []))
            # actions whose HTTP method is disabled on the view (e.g. PUT) are unreachable -> 405
            missing += [f"{route} [{a}]" for m, a in actions.items() if m in allowed and a not in required]
    assert not missing, f"Routes without a permission declaration (default-deny would block them): {missing}"


@pytest.fixture
def population(make_user):
    return {name: make_user(name) for name in ROLES}


def _endpoints(target_pk: int, role_pk: int):
    return [
        ("get", "/api/v1/users/", None, "users.read"),
        ("get", f"/api/v1/users/{target_pk}/", None, "users.read"),
        (
            "post",
            "/api/v1/users/",
            {
                "email": "n@example.com",
                "full_name": "N",
                "role": "auditor",
                "password": "Correct-Horse-Battery-9",
            },
            "users.create",
        ),
        ("patch", f"/api/v1/users/{target_pk}/", {"full_name": "Renamed"}, "users.update"),
        (
            "post",
            f"/api/v1/users/{target_pk}/reset-password/",
            {"new_password": "Another-Strong-Pass-77"},
            "users.update",
        ),
        ("get", "/api/v1/roles/", None, "roles.read"),
        ("get", f"/api/v1/roles/{role_pk}/", None, "roles.read"),
        ("post", "/api/v1/roles/", {"name": "custom", "label": "Custom"}, "roles.create"),
        ("patch", f"/api/v1/roles/{role_pk}/", {"description": "x"}, "roles.update"),
        ("get", "/api/v1/permissions/", None, "roles.read"),
        ("get", "/api/v1/audit/logs/", None, "audit.read"),
    ]


@pytest.mark.parametrize("role_name", list(ROLES))
def test_each_role_gets_403_exactly_when_it_lacks_the_permission(role_name, population, make_user):
    target = make_user("financial_analyst")
    role = Role.objects.get(name="management")
    granted = set(Role.objects.get(name=role_name).permissions.values_list("codename", flat=True))
    user = population[role_name]
    for method, url, body, codename in _endpoints(target.pk, role.pk):
        client = APIClient()
        client.force_authenticate(user=user)
        res = (
            getattr(client, method)(url, body, format="json")
            if body is not None
            else getattr(client, method)(url)
        )
        if codename in granted:
            assert res.status_code != 403, f"{role_name} should reach {method} {url} -> {res.status_code}"
        else:
            assert res.status_code == 403, (
                f"{role_name} must be forbidden {method} {url} -> {res.status_code}"
            )


def test_unauthenticated_requests_get_401_everywhere(population, make_user):
    target = make_user()
    role = Role.objects.get(name="management")
    for method, url, body, _ in _endpoints(target.pk, role.pk):
        res = (
            getattr(APIClient(), method)(url, body, format="json")
            if body is not None
            else getattr(APIClient(), method)(url)
        )
        assert res.status_code == 401, f"{method} {url} -> {res.status_code}"


def test_view_without_declared_permission_is_denied():
    from rest_framework.test import APIRequestFactory

    from apps.accounts.permissions import HasRolePermission

    class V:  # no required_permissions at all
        pass

    request = APIRequestFactory().get("/x")
    request.user = type("U", (), {"is_authenticated": True, "permission_codenames": {"users.read"}})()
    assert HasRolePermission().has_permission(request, V()) is False
