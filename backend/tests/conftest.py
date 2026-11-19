import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import Role, User

STRONG_PASSWORD = "Correct-Horse-Battery-9"


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def make_user(db):
    counter = {"n": 0}

    def _make(role: str = "financial_analyst", password: str = STRONG_PASSWORD, **extra) -> User:
        counter["n"] += 1
        return User.objects.create_user(
            email=extra.pop("email", f"{role}{counter['n']}@example.com"),
            password=password,
            role=Role.objects.get(name=role),
            full_name=extra.pop("full_name", f"{role} {counter['n']}"),
            **extra,
        )

    return _make


@pytest.fixture
def api_as(db):
    def _client(user: User) -> APIClient:
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    return _client
