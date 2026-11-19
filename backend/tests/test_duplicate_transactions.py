"""Transaction duplicate scans through the API: repeated payments, cross-dataset ids, import-flagged rows."""

from datetime import UTC, datetime, timedelta

import pytest

from apps.duplicates.models import DuplicateCandidate, DuplicateScanRun

pytestmark = pytest.mark.django_db
T0 = datetime(2026, 1, 1, 10, tzinfo=UTC)


@pytest.fixture
def analyst(make_user, api_as):
    return api_as(make_user("financial_analyst"))


def scan(api, run_tasks, **body):
    with run_tasks(execute=True):
        res = api.post("/api/v1/duplicates/scan/", {"kind": "transaction", **body}, format="json")
    assert res.status_code == 202, res.content
    return DuplicateScanRun.objects.get(pk=res.data["id"])


def test_repeated_payment_series_and_singles(make_dataset, make_tx, analyst, run_tasks):
    ds = make_dataset()
    a = make_tx(ds, sender="C1", receiver="M1", amount="40000", occurred_at=T0)
    b = make_tx(ds, sender="C1", receiver="M1", amount="40000", occurred_at=T0 + timedelta(minutes=10))  # strong
    c = make_tx(ds, sender="C2", receiver="M1", amount="500", occurred_at=T0)
    d = make_tx(ds, sender="C2", receiver="M1", amount="500", occurred_at=T0 + timedelta(hours=9))  # potential
    rent = [
        make_tx(ds, sender="C3", receiver="L1", amount="9000", occurred_at=T0 + timedelta(days=30 * k))
        for k in range(4)
    ]  # legit
    make_tx(ds, sender="C4", receiver="M1", amount="40000", occurred_at=T0)  # different sender: not a repeat
    run = scan(analyst, run_tasks, dataset=ds.pk)
    assert run.status == "succeeded" and run.candidates_found == 2 + 3
    by_pair = {(x.record_a_id, x.record_b_id): x for x in DuplicateCandidate.objects.filter(kind="transaction")}
    assert by_pair[(a.pk, b.pk)].match_class == "strong_similar" and by_pair[(a.pk, b.pk)].similarity_score > 90
    assert by_pair[(c.pk, d.pk)].match_class == "potential"
    assert {by_pair[(rent[i].pk, rent[i + 1].pk)].match_class for i in range(3)} == {"legitimate_repeat"}
    assert all(x.review_status == "pending" for x in by_pair.values())


def test_scan_is_idempotent_and_keeps_human_decisions(make_dataset, make_tx, analyst, run_tasks):
    ds = make_dataset()
    make_tx(ds, sender="C1", receiver="M1", amount="40000", occurred_at=T0)
    make_tx(ds, sender="C1", receiver="M1", amount="40000", occurred_at=T0 + timedelta(minutes=5))
    scan(analyst, run_tasks, dataset=ds.pk)
    cand = DuplicateCandidate.objects.get()
    analyst.post(
        f"/api/v1/duplicates/candidates/{cand.pk}/review/",
        {"decision": "legitimate_repeat", "notes": "two instalments"},
        format="json",
    )
    second = scan(analyst, run_tasks, dataset=ds.pk)
    assert second.candidates_found == 0 and DuplicateCandidate.objects.count() == 1
    cand.refresh_from_db()
    assert cand.review_status == "legitimate_repeat" and cand.notes == "two instalments"


def test_same_external_id_in_two_datasets_and_import_flagged_rows_are_exact(make_dataset, make_tx, analyst, run_tasks):
    d1, d2 = make_dataset(), make_dataset()
    x1 = make_tx(d1, transaction_id="PAY-777", sender="C1", receiver="M1", amount="10")
    x2 = make_tx(d2, transaction_id="PAY-777", sender="C9", receiver="M9", amount="99")
    orig = make_tx(
        d1, transaction_id="ORD-1", sender="C5", receiver="M5", amount="30", occurred_at=T0 + timedelta(days=5)
    )
    flagged = make_tx(d1, transaction_id="ORD-1~dup2", sender="C5", receiver="M5", amount="31", occurred_at=T0 + timedelta(days=9),
                      metadata={"flagged_duplicate_of": "ORD-1", "flagged_in_import": 3})  # fmt: skip
    scan(analyst, run_tasks)
    exact = {(c.record_a_id, c.record_b_id) for c in DuplicateCandidate.objects.filter(match_class="exact")}
    assert (x1.pk, x2.pk) in exact and (orig.pk, flagged.pk) in exact
    assert all(c.similarity_score == 100.0 for c in DuplicateCandidate.objects.filter(match_class="exact"))


def test_unrelated_transactions_produce_no_candidates_and_permissions(
    make_dataset, make_tx, make_user, api_as, analyst, run_tasks
):
    ds = make_dataset()
    for i in range(20):
        make_tx(ds, sender=f"C{i}", receiver=f"M{i}", amount=str(100 + i))
    assert scan(analyst, run_tasks, dataset=ds.pk).candidates_found == 0
    assert (
        api_as(make_user("fraud_investigator"))
        .post("/api/v1/duplicates/scan/", {"kind": "transaction"}, format="json")
        .status_code
        == 403
    )
    assert analyst.post("/api/v1/duplicates/scan/", {"kind": "bogus"}, format="json").status_code == 400
    assert (
        analyst.post("/api/v1/duplicates/scan/", {"kind": "transaction", "dataset": 999999}, format="json").status_code
        == 400
    )
    assert analyst.get("/api/v1/duplicates/scans/").json()["count"] >= 1
