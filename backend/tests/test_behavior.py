"""Behavioral analysis through the API: scenario, as-of correctness, batch == live, cold start, permissions."""

from datetime import UTC, datetime, timedelta

import pytest

from apps.audit.models import AuditLog
from apps.behavior import scenario
from apps.behavior.models import AccountBehaviorProfile, BehaviorAnalysisResult, BehaviorRun
from apps.transactions.models import Account, Transaction

pytestmark = pytest.mark.django_db


@pytest.fixture
def demo():
    return scenario.build()


@pytest.fixture
def analyst(make_user, api_as):
    return api_as(make_user("financial_analyst"))


def run_behavior(api, dataset, run_tasks):
    with run_tasks(execute=True):
        res = api.post("/api/v1/behavior/runs/", {"dataset": dataset.pk}, format="json")
    assert res.status_code == 202, res.content
    return BehaviorRun.objects.get(pk=res.data["id"])


def test_scenario_burst_is_scored_high_with_component_breakdown(demo, analyst, run_tasks):
    run = run_behavior(analyst, demo, run_tasks)
    assert run.status == "succeeded" and run.rows_total == demo.transactions.count()
    body = analyst.get(f"/api/v1/behavior/runs/{run.pk}/results/").json()
    top = body["results"][:5]
    assert {r["account_ref"] for r in top} == {"C-DEMO-STEADY"}  # the five burst payments rank first
    assert min(r["deviation_score"] for r in top) >= 75 and top[0]["deviation_score"] >= 80
    comps = top[0]["components"]
    assert comps["amount"]["score"] > 95 and comps["burst"]["detail"]["transactions_in_window"] == 5
    assert all(c["available"] for c in comps.values()) and top[0]["coverage"] == 1.0
    regular = [r for r in body["results"] if r["account_ref"] == "C-DEMO-REGULAR" and r["deviation_score"] is not None]
    assert (
        regular and max(r["deviation_score"] for r in regular) < 40
    )  # regular customer stays far below the burst (75+)


def test_cold_start_rows_have_no_score_and_say_so(demo, analyst, run_tasks):
    run = run_behavior(analyst, demo, run_tasks)
    cold = BehaviorAnalysisResult.objects.filter(run=run, status="unavailable_cold_start")
    assert cold.exists() and run.rows_unavailable == cold.count()
    assert not cold.exclude(deviation_score=None).exists()  # unavailable is null, never 0
    assert run.rows_scored + run.rows_unavailable == run.rows_total
    listing = analyst.get(f"/api/v1/behavior/runs/{run.pk}/results/?status=unavailable_cold_start").json()
    assert listing["results"][0]["deviation_score"] is None


def test_batch_results_equal_live_recomputation(demo, analyst, run_tasks):
    run = run_behavior(analyst, demo, run_tasks)
    sample = list(BehaviorAnalysisResult.objects.filter(run=run).order_by("id")[::17][:25])
    sample += list(BehaviorAnalysisResult.objects.filter(run=run, status="scored").order_by("-deviation_score")[:6])
    for stored in sample:
        live = analyst.get(f"/api/v1/transactions/{stored.transaction_id}/behavior/").json()
        assert live["status"] == stored.status and live["history_count"] == stored.history_count
        assert live["deviation_score"] == stored.deviation_score


def test_changing_the_future_never_changes_an_earlier_score(demo, analyst):
    steady = Account.objects.get(dataset=demo, account_ref="C-DEMO-STEADY")
    target = (
        Transaction.objects.filter(sender=steady, occurred_at__lt=scenario.START + timedelta(days=40))
        .order_by("-occurred_at")
        .first()
    )
    before = analyst.get(f"/api/v1/transactions/{target.pk}/behavior/").json()
    Transaction.objects.filter(sender=steady, occurred_at__gt=target.occurred_at).update(amount=1)  # rewrite the future
    Transaction.objects.create(
        dataset=demo, transaction_id="FUT", sender=steady, receiver=None, amount=999999, tx_type="PAYMENT",
        occurred_at=target.occurred_at + timedelta(days=5),
    )  # fmt: skip
    assert analyst.get(f"/api/v1/transactions/{target.pk}/behavior/").json() == before


def test_profile_is_as_of_and_excludes_later_transactions(demo, analyst):
    steady = Account.objects.get(dataset=demo, account_ref="C-DEMO-STEADY")
    as_of = (scenario.START + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    first = analyst.get(f"/api/v1/accounts/{steady.pk}/behavior/profile/?as_of={as_of}").json()
    assert (
        first["sufficient_history"]
        and first["tx_count"] == Transaction.objects.filter(sender=steady, occurred_at__lt=as_of).count()
    )
    assert 700 < first["median_amount"] < 900 and sum(first["hour_histogram"]) == first["tx_count"]
    assert first["merchant_category_dist"] is None and first["direction"] == "out"
    Transaction.objects.create(
        dataset=demo, transaction_id="LATE", sender=steady, receiver=None, amount=500000, tx_type="PAYMENT",
        occurred_at=scenario.START + timedelta(days=50),
    )  # fmt: skip
    assert analyst.get(f"/api/v1/accounts/{steady.pk}/behavior/profile/?as_of={as_of}").json() == first
    later = (scenario.START + timedelta(days=70)).strftime("%Y-%m-%dT%H:%M:%SZ")
    now = analyst.get(f"/api/v1/accounts/{steady.pk}/behavior/profile/?as_of={later}").json()
    assert now["tx_count"] > first["tx_count"] and now["p95_amount"] > first["p95_amount"]


def test_account_without_history_reports_insufficient_history_not_zeros(demo, analyst):
    payee = Account.objects.get(dataset=demo, account_ref="NEW-PAYEE-X")
    p = analyst.get(f"/api/v1/accounts/{payee.pk}/behavior/profile/").json()
    assert p["tx_count"] == 0 and p["sufficient_history"] is False and p["avg_amount"] is None


def test_incoming_direction_profiles_receivers(demo, analyst):
    merchant = Account.objects.get(dataset=demo, account_ref="M-DEMO-0")
    as_of = (scenario.START + timedelta(days=70)).strftime("%Y-%m-%dT%H:%M:%SZ")
    p = analyst.get(f"/api/v1/accounts/{merchant.pk}/behavior/profile/?direction=in&as_of={as_of}").json()
    assert p["direction"] == "in" and p["tx_count"] > 5 and p["unique_counterparties"] == 2


def test_trends_granularity_and_validation(demo, analyst):
    steady = Account.objects.get(dataset=demo, account_ref="C-DEMO-STEADY")
    as_of = (scenario.START + timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
    day = analyst.get(f"/api/v1/accounts/{steady.pk}/behavior/trends/?granularity=day&as_of={as_of}").json()
    month = analyst.get(f"/api/v1/accounts/{steady.pk}/behavior/trends/?granularity=month&as_of={as_of}").json()
    assert sum(p["count"] for p in day["points"]) == sum(p["count"] for p in month["points"]) > 0
    assert analyst.get(f"/api/v1/accounts/{steady.pk}/behavior/trends/?granularity=year").status_code == 400
    assert analyst.get(f"/api/v1/accounts/{steady.pk}/behavior/profile/?as_of=garbage").status_code == 400
    assert analyst.get(f"/api/v1/accounts/{steady.pk}/behavior/profile/?window_days=9999").status_code == 400
    assert analyst.get(f"/api/v1/accounts/{steady.pk}/behavior/profile/?direction=sideways").status_code == 400


def test_run_stores_profile_snapshots_only_for_accounts_with_history(demo, analyst, run_tasks):
    run = run_behavior(analyst, demo, run_tasks)
    assert run.profiles_stored == AccountBehaviorProfile.objects.filter(run=run).count() == 2  # steady + regular
    assert not AccountBehaviorProfile.objects.filter(run=run, account__account_ref="NEW-PAYEE-X").exists()
    assert AuditLog.objects.filter(action="behavior.run.completed").exists()


def test_rerunning_a_finished_run_changes_nothing(demo, analyst, run_tasks):
    from apps.behavior import services

    run = run_behavior(analyst, demo, run_tasks)
    ids = list(BehaviorAnalysisResult.objects.filter(run=run).values_list("id", flat=True)[:20])
    services.execute_run(run.pk)
    assert list(BehaviorAnalysisResult.objects.filter(run=run).values_list("id", flat=True)[:20]) == ids


def test_empty_dataset_is_rejected_and_permissions_are_enforced(make_dataset, demo, make_user, api_as):
    empty = make_dataset()
    analyst = api_as(make_user("financial_analyst"))
    res = analyst.post("/api/v1/behavior/runs/", {"dataset": empty.pk}, format="json")
    assert res.status_code == 400 and res.json()["error"]["code"] == "behavior_not_possible"
    investigator = api_as(make_user("fraud_investigator"))
    assert investigator.get("/api/v1/behavior/runs/").status_code == 200
    assert investigator.post("/api/v1/behavior/runs/", {"dataset": demo.pk}, format="json").status_code == 403
    assert api_as(make_user("management")).get("/api/v1/behavior/runs/").status_code == 403


def test_results_never_expose_ground_truth(demo, analyst, run_tasks):
    demo.transactions.update(ground_truth_label=True)
    run = run_behavior(analyst, demo, run_tasks)
    body = analyst.get(f"/api/v1/behavior/runs/{run.pk}/results/").json()
    assert not any("label" in k or "ground" in k for r in body["results"] for k in r)


def test_ties_in_time_are_ordered_by_id_and_do_not_leak(make_dataset, make_tx, analyst):
    ds = make_dataset()
    base = datetime(2026, 1, 1, 10, tzinfo=UTC)
    txs = [make_tx(ds, sender="C1", receiver="M1", amount="100", occurred_at=base) for _ in range(8)]
    first = analyst.get(f"/api/v1/transactions/{txs[0].pk}/behavior/").json()
    last = analyst.get(f"/api/v1/transactions/{txs[-1].pk}/behavior/").json()
    assert first["history_count"] == 0 and last["history_count"] == 7  # only lower ids count as 'earlier'
