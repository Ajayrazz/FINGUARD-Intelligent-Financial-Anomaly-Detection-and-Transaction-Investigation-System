from decimal import Decimal

import pytest
from django.db import DatabaseError, IntegrityError, transaction

from apps.audit.models import AuditLog
from apps.transactions.models import Transaction, TransactionEvent

pytestmark = pytest.mark.django_db
URL = "/api/v1/transactions/"


# ------------------------------------------------------------------ model constraints
def test_negative_amount_rejected(make_dataset, make_tx):
    with pytest.raises(IntegrityError), transaction.atomic():
        make_tx(make_dataset(), amount="-1.00")


def test_transaction_id_unique_per_dataset_but_reusable_across_datasets(make_dataset, make_tx):
    a, b = make_dataset(), make_dataset()
    make_tx(a, transaction_id="X1")
    make_tx(b, transaction_id="X1")  # different dataset: allowed
    with pytest.raises(IntegrityError), transaction.atomic():
        make_tx(a, transaction_id="X1")


def test_transaction_events_are_append_only(make_dataset, make_tx):
    tx = make_tx(make_dataset())
    ev = TransactionEvent.objects.create(transaction=tx, event_type="imported")
    with pytest.raises(DatabaseError), transaction.atomic():
        TransactionEvent.objects.filter(pk=ev.pk).update(event_type="tampered")
    with pytest.raises(DatabaseError), transaction.atomic():
        ev.delete()


# ------------------------------------------------------------------ list / search / filter / sort
@pytest.fixture
def seeded(make_dataset, make_tx):
    ds = make_dataset()
    make_tx(ds, "C1", "C2", "50.00", tx_type="PAYMENT", transaction_id="A1")
    make_tx(ds, "C1", "C3", "500.00", tx_type="TRANSFER", transaction_id="A2")
    make_tx(ds, "C2", "C3", "5000.00", tx_type="CASH_OUT", transaction_id="A3", status="failed")
    other = make_dataset()
    make_tx(other, "C1", "C2", "7.00", transaction_id="B1")
    return ds, other


def ids(res):
    return [r["transaction_id"] for r in res.data["results"]]


def test_list_is_newest_first_and_hides_ground_truth(seeded, make_user, api_as):
    ds, _ = seeded
    res = api_as(make_user("financial_analyst")).get(f"{URL}?dataset={ds.pk}")
    assert ids(res) == ["A3", "A2", "A1"]
    assert res.data["count"] == 3
    assert "ground_truth_label" not in res.data["results"][0]


def test_dataset_filter_isolates_datasets(seeded, make_user, api_as):
    _, other = seeded
    assert ids(api_as(make_user("auditor")).get(f"{URL}?dataset={other.pk}")) == ["B1"]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("tx_type=PAYMENT", ["A1"]),
        ("status=failed", ["A3"]),
        ("amount_min=100&amount_max=1000", ["A2"]),
        ("sender=C2", ["A3"]),
        ("receiver=C3", ["A3", "A2"]),
        ("q=A2", ["A2"]),  # transaction id
        ("q=C2", ["A3", "A1"]),  # account ref matches sender or receiver
        ("q=nothing", []),
    ],
)
def test_filters_and_search(seeded, make_user, api_as, query, expected):
    ds, _ = seeded
    assert ids(api_as(make_user("financial_analyst")).get(f"{URL}?dataset={ds.pk}&{query}")) == expected


def test_date_range_filter(make_dataset, make_tx, make_user, api_as):
    from datetime import UTC, datetime

    ds = make_dataset()
    make_tx(ds, transaction_id="OLD", occurred_at=datetime(2026, 1, 1, tzinfo=UTC))
    make_tx(ds, transaction_id="NEW", occurred_at=datetime(2026, 3, 1, tzinfo=UTC))
    res = api_as(make_user()).get(f"{URL}?dataset={ds.pk}&occurred_after=2026-02-01T00:00:00Z")
    assert ids(res) == ["NEW"]


def test_sorting(seeded, make_user, api_as):
    ds, _ = seeded
    client = api_as(make_user())
    assert ids(client.get(f"{URL}?dataset={ds.pk}&ordering=amount")) == ["A1", "A2", "A3"]
    assert ids(client.get(f"{URL}?dataset={ds.pk}&ordering=-amount")) == ["A3", "A2", "A1"]


def test_page_number_pagination(make_dataset, make_tx, make_user, api_as):
    ds = make_dataset()
    for _ in range(7):
        make_tx(ds)
    client = api_as(make_user())
    p1 = client.get(f"{URL}?dataset={ds.pk}&page_size=3")
    assert p1.data["count"] == 7 and len(p1.data["results"]) == 3 and p1.data["next"]
    assert len(client.get(f"{URL}?dataset={ds.pk}&page_size=3&page=3").data["results"]) == 1
    assert client.get(f"{URL}?dataset={ds.pk}&page_size=1000").data["results"].__len__() == 7  # capped at 100


def test_keyset_pagination_walks_everything_exactly_once_even_with_ties(make_dataset, make_tx, make_user, api_as):
    from datetime import UTC, datetime

    ds = make_dataset()
    same_time = datetime(2026, 1, 1, tzinfo=UTC)
    for _ in range(11):  # identical timestamps: stresses tie handling
        make_tx(ds, occurred_at=same_time)
    client = api_as(make_user())
    url, seen = f"{URL}?dataset={ds.pk}&page_size=3&cursor=", []
    while url:
        res = client.get(url.replace("http://testserver", ""))
        assert res.status_code == 200
        assert "count" not in res.data  # keyset mode has no COUNT(*)
        seen += [r["id"] for r in res.data["results"]]
        url = res.data["next"]
    assert len(seen) == 11 and len(set(seen)) == 11


# ------------------------------------------------------------------ detail / related / events
def test_detail_includes_accounts_and_not_label(seeded, make_user, api_as):
    ds, _ = seeded
    tx = Transaction.objects.get(dataset=ds, transaction_id="A2")
    Transaction.objects.filter(pk=tx.pk).update(ground_truth_label=True)
    res = api_as(make_user("fraud_investigator")).get(f"{URL}{tx.pk}/")
    assert res.status_code == 200
    assert res.data["sender"]["account_ref"] == "C1" and res.data["receiver"]["account_ref"] == "C3"
    assert res.data["dataset_name"] == ds.name and "ground_truth_label" not in res.data


def test_related_returns_same_pair_both_directions_only(make_dataset, make_tx, make_user, api_as):
    ds = make_dataset()
    main = make_tx(ds, "C1", "C2", transaction_id="MAIN")
    make_tx(ds, "C1", "C2", transaction_id="SAME")
    make_tx(ds, "C2", "C1", transaction_id="REVERSE")
    make_tx(ds, "C1", "C9", transaction_id="OTHER")
    res = api_as(make_user()).get(f"{URL}{main.pk}/related/")
    assert sorted(r["transaction_id"] for r in res.data) == ["REVERSE", "SAME"]


def test_related_for_transaction_without_receiver_is_empty(make_dataset, make_tx, make_user, api_as):
    tx = make_tx(make_dataset(), receiver=None)
    assert api_as(make_user()).get(f"{URL}{tx.pk}/related/").data == []


# ------------------------------------------------------------------ status change
def test_status_change_writes_event_and_audit(make_dataset, make_tx, make_user, api_as):
    analyst = make_user("financial_analyst")
    tx = make_tx(make_dataset())
    res = api_as(analyst).patch(
        f"{URL}{tx.pk}/status/", {"status": "reversed", "reason": "customer dispute"}, format="json"
    )
    assert res.status_code == 200 and res.data["status"] == "reversed"
    ev = TransactionEvent.objects.get(transaction=tx)
    assert ev.event_type == "status_changed" and ev.actor == analyst
    assert ev.payload == {"from": "completed", "to": "reversed", "reason": "customer dispute"}
    assert AuditLog.objects.filter(action="transaction.status_changed", resource_id=str(tx.pk)).exists()
    events = api_as(analyst).get(f"{URL}{tx.pk}/events/")
    assert [e["event_type"] for e in events.data] == ["status_changed"]


def test_status_change_validation(make_dataset, make_tx, make_user, api_as):
    client = api_as(make_user("financial_analyst"))
    tx = make_tx(make_dataset())
    assert client.patch(f"{URL}{tx.pk}/status/", {"status": "bogus"}, format="json").status_code == 400
    assert client.patch(f"{URL}{tx.pk}/status/", {"status": "completed"}, format="json").status_code == 400  # no-op
    assert not TransactionEvent.objects.filter(transaction=tx).exists()


def test_investigator_and_auditor_cannot_change_status(make_dataset, make_tx, make_user, api_as):
    tx = make_tx(make_dataset())
    for role in ("fraud_investigator", "auditor", "management"):
        res = api_as(make_user(role)).patch(f"{URL}{tx.pk}/status/", {"status": "failed"}, format="json")
        assert res.status_code == 403, role
    assert Transaction.objects.get(pk=tx.pk).status == "completed"


def test_management_has_no_row_level_transaction_access(make_user, api_as):
    assert api_as(make_user("management")).get(URL).status_code == 403


# ------------------------------------------------------------------ accounts
def test_account_detail_totals_and_transactions_by_direction(make_dataset, make_tx, make_user, api_as):
    ds = make_dataset()
    make_tx(ds, "C1", "C2", "100.00")
    make_tx(ds, "C1", "C3", "50.00")
    make_tx(ds, "C3", "C1", "25.00")
    client = api_as(make_user())
    acct = client.get("/api/v1/accounts/?q=C1").data["results"][0]
    detail = client.get(f"/api/v1/accounts/{acct['id']}/").data
    assert (detail["sent_count"], Decimal(detail["sent_total"])) == (2, Decimal("150.00"))
    assert (detail["received_count"], Decimal(detail["received_total"])) == (1, Decimal("25.00"))
    out = client.get(f"/api/v1/accounts/{acct['id']}/transactions/?direction=out")
    inc = client.get(f"/api/v1/accounts/{acct['id']}/transactions/?direction=in")
    both = client.get(f"/api/v1/accounts/{acct['id']}/transactions/")
    assert (out.data["count"], inc.data["count"], both.data["count"]) == (2, 1, 3)
    assert client.get(f"/api/v1/accounts/{acct['id']}/transactions/?direction=sideways").status_code == 400


def test_same_account_ref_in_two_datasets_are_distinct_accounts(make_dataset, make_account, make_user, api_as):
    a, b = make_dataset(), make_dataset()
    make_account(a, "C1")
    make_account(b, "C1")
    res = api_as(make_user()).get(f"/api/v1/accounts/?q=C1&dataset={a.pk}")
    assert res.data["count"] == 1


# ------------------------------------------------------------------ datasets
def test_dataset_create_list_and_audit(make_user, api_as):
    analyst = make_user("financial_analyst")
    res = api_as(analyst).post("/api/v1/datasets/", {"name": "My upload", "source_type": "custom"}, format="json")
    assert res.status_code == 201 and res.data["row_count"] == 0
    assert any(d["name"] == "My upload" for d in api_as(analyst).get("/api/v1/datasets/").data)
    assert AuditLog.objects.filter(action="dataset.created").exists()
    dup = api_as(analyst).post("/api/v1/datasets/", {"name": "My upload"}, format="json")
    assert dup.status_code == 400


def test_investigator_can_read_but_not_create_datasets(make_user, api_as):
    client = api_as(make_user("fraud_investigator"))
    assert client.get("/api/v1/datasets/").status_code == 200
    assert client.post("/api/v1/datasets/", {"name": "x"}, format="json").status_code == 403
