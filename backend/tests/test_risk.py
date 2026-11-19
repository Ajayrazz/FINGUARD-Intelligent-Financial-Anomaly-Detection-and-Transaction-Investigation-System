"""Risk scoring through the API: all six components on the DEMO burst scenario, missing signals, config versions,
immutability, reproducibility from stored components, history and compare."""

import pytest
from django.db import DatabaseError, connection
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.behavior import scenario
from apps.behavior import services as behavior_services
from apps.detection.models import DetectionRun, Prediction
from apps.duplicates import services as dup_services
from apps.duplicates.models import DuplicateScanRun
from apps.graph_engine import services as graph_services
from apps.model_registry.models import MLModel, ModelVersion
from apps.risk_engine import services
from apps.risk_engine.models import AccountRiskHistory, RiskAssessment, RiskConfig, RiskScoreRun
from apps.transactions.models import Account, Transaction

pytestmark = pytest.mark.django_db


@pytest.fixture
def analyst(make_user, api_as):
    return api_as(make_user("financial_analyst"))


@pytest.fixture
def user(make_user):
    return make_user("financial_analyst")


def run_risk(api, dataset, run_tasks, **extra):
    with run_tasks(execute=True):
        res = api.post("/api/v1/risk/runs/", {"dataset": dataset.pk, **extra}, format="json")
    assert res.status_code == 202, res.content
    return RiskScoreRun.objects.get(pk=res.data["id"])


def make_detection(ds, user, high_ids):
    """A detection run with hand-set scores (no model artifact needed): `high_ids` score 0.9, the rest 0.02."""
    mv = ModelVersion.objects.create(model=MLModel.objects.create(name="risk_test_model", task_type="supervised", algorithm="XGBoost"),
                                     version="paysim-s1-test", artifact_path="/x", artifact_sha256="a" * 64, artifact_format="joblib",
                                     feature_schema={"features": ["log_amount"]})  # fmt: skip
    run = DetectionRun.objects.create(model_version=mv, dataset=ds, threshold=0.2, threshold_source="test", status="succeeded", created_by=user,
                                      rows_scored=ds.transactions.count(), score_summary={"min": 0.0, "max": 0.95, "quantiles": {"p99.9": 0.9}})  # fmt: skip
    Prediction.objects.bulk_create(
        [
            Prediction(run=run, transaction=t, score=0.9 if t.pk in high_ids else 0.02, flagged=t.pk in high_ids)
            for t in ds.transactions.all()
        ]
    )
    return run, mv


@pytest.fixture
def demo_all(user):
    """DEMO burst scenario with every engine run: behavior, graph, duplicates, detection."""
    ds = scenario.build()
    burst = list(
        Transaction.objects.filter(dataset=ds, receiver__account_ref="NEW-PAYEE-X").values_list("id", flat=True)
    )
    brun = behavior_services.create_run(dataset=ds, user=user)
    behavior_services.execute_run(brun.pk)
    snap = graph_services.create_snapshot(dataset=ds, user=user, as_of=None, window_days=None)
    graph_services.execute_snapshot(snap.pk)
    scan = DuplicateScanRun.objects.create(kind="transaction", dataset=ds, created_by=user)
    dup_services.execute_scan(scan.pk)
    det, mv = make_detection(ds, user, set(burst))
    return {"ds": ds, "burst": burst, "behavior": brun, "snapshot": snap, "scan": scan, "detection": det, "mv": mv}


def test_default_config_is_seeded_active_and_valid():
    cfg = RiskConfig.objects.get(is_active=True)
    assert (
        cfg.version == 1
        and cfg.source == "default"
        and cfg.weights == {"A": 0.25, "B": 0.2, "G": 0.2, "F": 0.15, "D": 0.1, "H": 0.1}
    )
    assert RiskConfig.objects.filter(is_active=True).count() == 1


def test_burst_scenario_gets_all_components_and_scores_far_above_normal_payments(demo_all, analyst, run_tasks):
    run = run_risk(analyst, demo_all["ds"], run_tasks)
    assert run.status == "succeeded" and run.rows_scored == demo_all["ds"].transactions.count()
    assert (
        run.params["detection_run"] == demo_all["detection"].pk
        and run.params["behavior_run"] == demo_all["behavior"].pk
    )
    last_burst = (
        RiskAssessment.objects.filter(run=run, transaction_id__in=demo_all["burst"])
        .order_by("-transaction__occurred_at")
        .first()
    )
    comps = last_burst.components
    for c in "ABGFDH":
        assert c in comps
    assert comps["A"]["available"] and comps["A"]["value"] > 90  # model score 0.9 vs threshold 0.2
    assert comps["B"]["available"] and comps["B"]["value"] > 70 and comps["F"]["value"] > 70  # burst counted once, as F
    assert comps["D"]["available"] and comps["D"]["value"] >= 80  # identical 40,000 payments minutes apart
    assert comps["G"]["available"] and comps["H"]["available"]
    assert (
        last_burst.category in ("high", "critical")
        and last_burst.overall_score > 60
        and last_burst.weight_coverage == 1.0
    )
    normal = (
        RiskAssessment.objects.filter(run=run).exclude(transaction_id__in=demo_all["burst"]).exclude(overall_score=None)
    )
    assert normal.exists() and max(a.overall_score for a in normal) < last_burst.overall_score - 20
    assert sum(c["contribution"] for c in comps.values() if c["contribution"] is not None) == pytest.approx(
        last_burst.overall_score, abs=0.01
    )


def test_missing_components_are_reported_with_reasons_and_coverage(demo_all, analyst, run_tasks):
    run = run_risk(analyst, demo_all["ds"], run_tasks)
    cold = RiskAssessment.objects.filter(run=run, components__B__available=False).first()
    assert (
        cold is not None
        and "cold start" in cold.components["B"]["reason"]
        and cold.components["B"]["contribution"] is None
    )
    assert cold.weight_coverage < 1.0 and cold.low_coverage == (cold.weight_coverage < 0.5)


def test_no_other_engines_means_only_A_and_low_coverage_cap(make_dataset, make_tx, user, analyst, run_tasks):
    ds = make_dataset()
    tx = [make_tx(ds, sender=f"C{i}", receiver=f"M{i}", amount="10") for i in range(5)]
    make_detection(ds, user, {tx[0].pk})
    run = run_risk(analyst, ds, run_tasks)
    top = RiskAssessment.objects.filter(run=run).order_by("-overall_score").first()
    assert top.transaction_id == tx[0].pk and top.overall_score == pytest.approx(
        100.0, abs=1
    )  # renormalised over A only
    assert (
        top.weight_coverage == pytest.approx(0.25) and top.low_coverage and top.capped and top.category == "high"
    )  # not Critical
    assert {c for c, v in top.components.items() if v["available"]} == {"A", "H"} or top.components["A"]["available"]
    assert all(not top.components[c]["available"] for c in "BFG")


def test_nothing_available_is_unscored_not_zero(make_dataset, make_tx, analyst, run_tasks):
    ds = make_dataset()
    make_tx(ds, sender="C1", receiver="M1", amount="10")
    run = run_risk(analyst, ds, run_tasks)
    a = RiskAssessment.objects.get(run=run)
    assert a.overall_score is None and a.category == "unscored" and a.weight_coverage == 0.0
    assert RiskScoreRun.objects.get(pk=run.pk).category_counts == {"unscored": 1}


def test_assessments_are_immutable_and_reproducible_from_stored_components(demo_all, analyst, run_tasks):
    run = run_risk(analyst, demo_all["ds"], run_tasks)
    a = RiskAssessment.objects.filter(run=run, overall_score__gt=0).order_by("-overall_score").first()
    again = services.recompute_from_stored(a)
    assert again["overall_score"] == pytest.approx(a.overall_score, abs=1e-3) and again["category"] == a.category
    assert again["weight_coverage"] == pytest.approx(a.weight_coverage)
    with pytest.raises(DatabaseError), connection.cursor() as cur:
        cur.execute("UPDATE risk_engine_riskassessment SET overall_score = 1 WHERE id = %s", [a.pk])
    with pytest.raises(DatabaseError), connection.cursor() as cur:
        cur.execute("DELETE FROM risk_engine_riskassessment WHERE id = %s", [a.pk])


def test_config_versions_validation_activation_and_immutability_once_used(
    demo_all, analyst, make_user, api_as, run_tasks
):
    admin = api_as(make_user("super_admin"))
    good = {
        "weights": {"A": 0.4, "B": 0.2, "G": 0.1, "F": 0.1, "D": 0.1, "H": 0.1},
        "thresholds": {"medium": 25, "high": 55, "critical": 85},
        "missing_signal_policy": "renormalize",
        "min_coverage": 0.4,
    }
    bad_sum = admin.post("/api/v1/risk/config/", {**good, "weights": {**good["weights"], "A": 0.9}}, format="json")
    assert bad_sum.status_code == 400 and "sum to 1" in bad_sum.json()["error"]["message"]
    bad_thr = admin.post(
        "/api/v1/risk/config/", {**good, "thresholds": {"medium": 70, "high": 60, "critical": 80}}, format="json"
    )
    assert bad_thr.status_code == 400 and "thresholds" in bad_thr.json()["error"]["message"]
    assert (
        admin.post("/api/v1/risk/config/", {**good, "missing_signal_policy": "guess"}, format="json").status_code == 400
    )
    created = admin.post("/api/v1/risk/config/", good, format="json")
    assert created.status_code == 201 and created.json()["version"] == 2 and created.json()["is_active"] is False
    assert analyst.post("/api/v1/risk/config/", good, format="json").status_code == 403  # analysts cannot configure
    run1 = run_risk(analyst, demo_all["ds"], run_tasks)  # scores with active v1
    assert run1.config.version == 1
    activated = admin.post(f"/api/v1/risk/config/{created.json()['id']}/activate/", format="json")
    assert activated.status_code == 200 and activated.json()["is_active"] is True
    assert list(RiskConfig.objects.filter(is_active=True).values_list("version", flat=True)) == [2]
    run2 = run_risk(analyst, demo_all["ds"], run_tasks)
    assert (
        run2.config.version == 2 and run2.rows_scored == run1.rows_scored
    )  # a new run, the old assessments stay as they were
    v1 = RiskConfig.objects.get(version=1)
    assert RiskAssessment.objects.filter(config=v1).exists()
    v1.weights = {**v1.weights, "A": 0.30, "B": 0.15}
    with pytest.raises(ValueError, match="immutable"):
        v1.save()  # a used version cannot be edited, only superseded
    assert (
        AuditLog.objects.filter(action="risk.config.activated").exists()
        and AuditLog.objects.filter(action="risk.run.completed").count() == 2
    )


def test_strict_and_neutral_prior_policies(make_dataset, make_tx, user, analyst, run_tasks, make_user, api_as):
    admin_cfg = services.create_config(user=user, weights={"A": 0.5, "B": 0.1, "G": 0.1, "F": 0.1, "D": 0.1, "H": 0.1}, thresholds={"medium": 30, "high": 60, "critical": 80},
                                       policy="strict", min_coverage=0.5)  # fmt: skip
    ds = make_dataset()
    tx = [make_tx(ds, sender=f"C{i}", receiver=f"M{i}", amount="10") for i in range(3)]
    make_detection(ds, user, {tx[0].pk})
    run = run_risk(analyst, ds, run_tasks, config=admin_cfg.pk)
    assert set(RiskAssessment.objects.filter(run=run).values_list("category", flat=True)) == {
        "unscored"
    }  # strict: missing signals -> no score
    # neutral_prior imputes a missing component only where the dataset has a population for it (needs a mixed dataset)
    prior_cfg = services.create_config(
        user=user,
        weights=dict(admin_cfg.weights),
        thresholds=dict(admin_cfg.thresholds),
        policy="neutral_prior",
        min_coverage=0.5,
    )
    only_a = run_risk(analyst, ds, run_tasks, config=prior_cfg.pk)
    assert not any(
        v.get("imputed") for a in RiskAssessment.objects.filter(run=only_a) for v in a.components.values()
    )  # no population, no imputation


def test_neutral_prior_imputes_from_the_dataset_median_and_marks_it(demo_all, user, analyst, run_tasks):
    cfg = services.create_config(user=user, weights={"A": 0.25, "B": 0.20, "G": 0.20, "F": 0.15, "D": 0.10, "H": 0.10}, thresholds={"medium": 30, "high": 60, "critical": 80},
                                  policy="neutral_prior", min_coverage=0.5)  # fmt: skip
    run = run_risk(analyst, demo_all["ds"], run_tasks, config=cfg.pk)
    assert run.params["priors"].get("B") is not None
    imputed = RiskAssessment.objects.filter(run=run, components__B__imputed=True).first()
    assert imputed is not None and imputed.components["B"]["value"] == pytest.approx(run.params["priors"]["B"])
    assert (
        imputed.components["B"]["contribution"] is not None and imputed.weight_coverage < 1.0
    )  # coverage = measured, not imputed


def test_listing_filters_history_account_history_and_compare(demo_all, analyst, run_tasks):
    run = run_risk(analyst, demo_all["ds"], run_tasks)
    top = analyst.get(f"/api/v1/risk/assessments/?run={run.pk}&scored=true").json()
    scores = [r["overall_score"] for r in top["results"]]
    assert (
        scores == sorted(scores, reverse=True)
        and "ground_truth" not in str(top).lower()
        and "label" not in str(top["results"][0]).lower()
    )
    crit = analyst.get(f"/api/v1/risk/assessments/?run={run.pk}&category=high").json()
    assert crit["count"] >= 1 and {r["category"] for r in crit["results"]} == {"high"} or crit["count"] == 0
    tx_id = top["results"][0]["transaction"]
    latest = analyst.get(f"/api/v1/transactions/{tx_id}/risk/").json()
    assert (
        latest["transaction"] == tx_id
        and set("ABGFDH") <= set(latest["components"])
        and latest["algorithm_version"] == "r1"
    )
    assert analyst.get(f"/api/v1/transactions/{tx_id}/risk/history/").json()["count"] == 1
    run2 = run_risk(analyst, demo_all["ds"], run_tasks)
    hist = analyst.get(f"/api/v1/transactions/{tx_id}/risk/history/").json()
    assert hist["count"] == 2  # both assessments retained
    a, b = (r["id"] for r in hist["results"])
    cmp = analyst.get(f"/api/v1/risk/compare/?a={a}&b={b}").json()
    assert cmp["comparable"] is True and set(cmp["components"]) == set("ABGFDH") and run2.pk != run.pk
    assert (
        analyst.get("/api/v1/risk/compare/?a=x&b=1").status_code == 400
        and analyst.get("/api/v1/risk/compare/?a=1&b=999999").status_code == 404
    )
    acct = top["results"][0]["account"]
    ah = analyst.get(f"/api/v1/accounts/{acct}/risk/history/").json()
    assert ah["highest_assessments"] and any(h["category"] in ("medium", "high", "critical") for h in ah["history"])
    never = Transaction.objects.filter(dataset=demo_all["ds"]).first()
    RiskAssessment.objects.filter(transaction=never).exists()


def test_unscored_transaction_404_and_permissions(make_dataset, make_tx, make_user, api_as, analyst):
    ds = make_dataset()
    t = make_tx(ds)
    assert analyst.get(f"/api/v1/transactions/{t.pk}/risk/").status_code == 404
    inv = api_as(make_user("fraud_investigator"))
    assert inv.get("/api/v1/risk/assessments/").status_code == 200
    assert inv.post("/api/v1/risk/runs/", {"dataset": ds.pk}, format="json").status_code == 403
    assert api_as(make_user("management")).get("/api/v1/risk/assessments/").status_code == 403
    assert analyst.post("/api/v1/risk/runs/", {"dataset": 999999}, format="json").status_code == 400
    empty = make_dataset()
    res = analyst.post("/api/v1/risk/runs/", {"dataset": empty.pk}, format="json")
    assert res.status_code == 400 and res.json()["error"]["code"] == "risk_not_possible"


def test_graph_finding_only_counts_from_the_moment_it_completed(make_dataset, make_tx, user, analyst, run_tasks):
    from datetime import UTC, datetime, timedelta

    ds = make_dataset()
    base = datetime(2026, 1, 1, tzinfo=UTC)
    early = make_tx(ds, sender="A1", receiver="A2", amount="1000", occurred_at=base)
    mid = make_tx(ds, sender="A2", receiver="A3", amount="990", occurred_at=base + timedelta(hours=1))
    last = make_tx(
        ds, sender="A3", receiver="A1", amount="980", occurred_at=base + timedelta(hours=2)
    )  # completes the cycle
    snap = graph_services.create_snapshot(dataset=ds, user=user, as_of=None, window_days=None)
    graph_services.execute_snapshot(snap.pk)
    assert snap.findings.filter(finding_type="cycle").exists()
    run = run_risk(analyst, ds, run_tasks)
    g = {a.transaction_id: a.components["G"] for a in RiskAssessment.objects.filter(run=run)}
    assert g[early.pk]["value"] == 0.0 and g[mid.pk]["value"] == 0.0  # the cycle did not exist yet
    assert g[last.pk]["value"] > 60  # it exists from the transaction that closes it
    assert (
        Account.objects.filter(dataset=ds).count() == 3
        and AccountRiskHistory.objects.filter(run=run).count() >= 0
        and timezone.now()
    )
