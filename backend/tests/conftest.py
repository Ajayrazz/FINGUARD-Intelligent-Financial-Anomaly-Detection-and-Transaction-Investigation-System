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


@pytest.fixture
def make_dataset(db):
    from apps.datasets.models import Dataset

    counter = {"n": 0}

    def _make(name: str | None = None, **extra) -> Dataset:
        counter["n"] += 1
        return Dataset.objects.create(name=name or f"MOCK test {counter['n']}", **extra)

    return _make


@pytest.fixture
def make_account(db):
    from apps.transactions.models import Account

    def _make(dataset, ref: str, account_type: str = "customer") -> Account:
        return Account.objects.get_or_create(
            dataset=dataset, account_ref=ref, defaults={"account_type": account_type}
        )[0]

    return _make


@pytest.fixture
def make_tx(db, make_account):
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal

    from apps.transactions.models import Transaction

    counter = {"n": 0}

    def _make(
        dataset, sender: str = "C1", receiver: str | None = "C2", amount="100.00", **extra
    ) -> Transaction:
        counter["n"] += 1
        n = counter["n"]
        return Transaction.objects.create(
            dataset=dataset,
            transaction_id=extra.pop("transaction_id", f"T{n:06d}"),
            sender=make_account(dataset, sender),
            receiver=make_account(dataset, receiver) if receiver else None,
            amount=Decimal(str(amount)),
            tx_type=extra.pop("tx_type", "TRANSFER"),
            occurred_at=extra.pop("occurred_at", datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=n)),
            **extra,
        )

    return _make
