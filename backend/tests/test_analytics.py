"""Analytics: the rollup reconciles with the source tables, filters and granularities are consistent, exports are safe."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from django.db.models import Count, Sum

from apps.alerts.models import Alert
from apps.analytics import services
from apps.analytics.models import DailyAggregate
from apps.audit.models import AuditLog
from apps.cases.models import Case
from apps.detection.models import DetectionRun, Prediction
from apps.model_registry.services import register_results
from apps.risk_engine.models import RiskAssessment, RiskConfig, RiskScoreRun
from apps.transactions.models import Transaction

D0 = datetime(2026, 1, 5, 10, tzinfo=UTC)  # a Monday


@pytest.fixture
def world(make_dataset, make_tx):
    """Three days, two types, labelled transactions, a detection run, a risk run, alerts and cases."""
    ds = make_dataset()
    txs = []
    for i, (days, typ, amount, label) in enumerate(
        [(0, "TRANSFER", "100.00", True), (0, "PAYMENT", "50.50", False), (1, "TRANSFER", "200.00", False),
         (1, "TRANSFER", "300.00", True), (8, "PAYMENT", "10.00", False), (9, "CASH_OUT", "999.99", True)]
    ):  # fmt: skip
        txs.append(
            make_tx(
                ds,
                sender=f"C{i % 3}",
                amount=amount,
                tx_type=typ,
                occurred_at=D0 + timedelta(days=days, minutes=i),
                ground_truth_label=label,
            )
        )
    mv = register_results(
        {
            "run": "an_model", "dataset": "paysim", "algorithm": "LogisticRegression", "artifact": "/x/m.joblib", "artifact_sha256": "a" * 64,
            "seed": 1, "raw_sha256": "b" * 64, "features": ["log_amount"],
            "metrics": {"validation": {"at_validation_threshold": {"threshold": 0.5}}, "test": {"pr_auc": 0.7, "roc_auc": 0.9, "recall_at_fpr_1pct": 0.5, "base_rate": 0.01},
                        "latency": {"single_ms_median": 1.2, "single_ms_p95": 2.0, "batch_rows_per_s": 5000.0}},
        }
    )  # fmt: skip
    run = DetectionRun.objects.create(
        model_version=mv,
        dataset=ds,
        threshold=0.5,
        threshold_source="t",
        status="succeeded",
        rows_scored=6,
        rows_flagged=3,
    )
    flags = [True, False, False, True, True, False]  # TP, TN, TN, TP, FP, FN
    Prediction.objects.bulk_create(
        [
            Prediction(run=run, transaction=t, score=0.9 if f else 0.1, flagged=f)
            for t, f in zip(txs, flags, strict=True)
        ]
    )
    cfg = RiskConfig.objects.filter(is_active=True).first() or RiskConfig.objects.create(
        version=1, weights={}, thresholds={}, is_active=True
    )
    rrun = RiskScoreRun.objects.create(
        dataset=ds, config=cfg, status="succeeded", category_counts={"low": 3, "medium": 1, "high": 1, "critical": 1}
    )
    cats = [("low", 10.0), ("low", 12.0), ("medium", 40.0), ("high", 70.0), ("critical", 90.0), ("low", 5.0)]
    RiskAssessment.objects.bulk_create(
        [RiskAssessment(transaction=t, account=t.sender, config=cfg, run=rrun, algorithm_version="1", components={}, overall_score=s, category=c, weight_coverage=1.0, policy="renormalize")
         for t, (c, s) in zip(txs, cats, strict=True)]
    )  # fmt: skip
    for i, (status, outcome) in enumerate(
        [("closed", "false_positive"), ("closed", "true_positive"), ("closed", "false_positive"), ("new", "")]
    ):
        Alert.objects.create(
            alert_type="t", severity="high", status=status, dedup_key=f"k{i}", dataset=ds, reason="r", outcome=outcome
        )
    for i, (status, outcome, hours) in enumerate(
        [("resolved", "false_positive", 10), ("resolved", "confirmed_suspicious", 30), ("new", "", None)]
    ):
        c = Case.objects.create(
            case_ref=f"FG-2026-{i:06d}",
            title="c",
            status=status,
            outcome=outcome,
            resolution_summary="s" if outcome else "",
            dataset=ds,
        )
        if hours:
            Case.objects.filter(pk=c.pk).update(resolved_at=c.opened_at + timedelta(hours=hours))
    return ds, txs


def test_rollup_reconciles_with_direct_counts(world):
    ds, _ = world
    days = services.refresh_daily_aggregates(ds.id)
    direct = Transaction.objects.filter(dataset=ds).aggregate(n=Count("id"), v=Sum("amount"))
    agg = DailyAggregate.objects.filter(dataset=ds)
    assert days == 4 and agg.count() == 4
    assert sum(a.tx_count for a in agg) == direct["n"] == 6
    assert sum(a.tx_value for a in agg) == direct["v"] == Decimal("1660.49")
    assert sum(a.flagged_count for a in agg) == Prediction.objects.filter(run__dataset=ds, flagged=True).count() == 3
    first = agg.get(date=D0.date())
    assert first.tx_count == 2 and first.by_type["TRANSFER"] == {"count": 1, "value": "100.00"}
    assert services.overview(ds.id)["transactions"] == 6
    assert services.overview(None)["flagged"] == 3
    assert services.refresh_daily_aggregates(ds.id) == 4  # idempotent
    assert DailyAggregate.objects.filter(dataset=ds).count() == 4


def test_volume_granularities_all_sum_to_the_same_totals(world):
    ds, _ = world
    for g in ("day", "week", "month"):
        series = services.volume(ds.id, g, None, None)
        assert sum(r["transactions"] for r in series) == 6, g
        assert sum(Decimal(r["value"]) for r in series) == Decimal("1660.49"), g
    weeks = services.volume(ds.id, "week", None, None)
    assert [r["transactions"] for r in weeks] == [4, 2]  # Mon 5th week: days 0-1; next week: days 8-9
    windowed = services.volume(ds.id, "day", D0.date(), D0.date() + timedelta(days=1))
    assert sum(r["transactions"] for r in windowed) == 4


def test_risk_distribution_accounts_and_recent(world):
    ds, _ = world
    services.refresh_daily_aggregates(ds.id)
    d = services.risk_distribution(ds.id)
    assert d["counts"]["low"] == 3 and d["counts"]["critical"] == 1 and d["total"] == 6
    top = services.high_risk_accounts(ds.id)
    assert top[0]["max_score"] == 90.0 and [r["max_score"] for r in top] == sorted(
        (r["max_score"] for r in top), reverse=True
    )
    recent = services.recent_suspicious(ds.id)
    assert {r["category"] for r in recent} == {"high", "critical"}
    assert services.overview(ds.id)["high_risk_transactions"] == 2


def test_false_positive_analysis_two_sources(world):
    ds, _ = world
    f = services.false_positives(ds.id)
    assert f["investigated"]["alerts"] == {"false_positive": 2, "true_positive": 1, "rate": round(2 / 3, 4)}
    assert f["investigated"]["cases"] == {"false_positive": 1, "confirmed_suspicious": 1, "rate": 0.5}
    lab = f["labelled"]
    assert (lab["tp"], lab["fp"], lab["fn"], lab["tn"]) == (2, 1, 1, 2)
    assert (
        lab["precision"] == round(2 / 3, 4)
        and lab["recall"] == round(2 / 3, 4)
        and lab["false_positive_rate"] == round(1 / 3, 4)
    )


def test_investigation_summary_resolution_hours(world):
    ds, _ = world
    s = services.investigations_summary(ds.id, None, None)
    assert s["total"] == 3 and s["by_outcome"]["false_positive"] == 1 and s["resolved"] == 2
    assert s["resolution_hours"]["median"] == 20.0 and s["resolution_hours"]["max"] == 30.0


def test_detection_performance_lists_registered_models(world):
    rows = services.detection_performance()
    assert rows and rows[0]["pr_auc"] == 0.7 and rows[0]["latency_ms_median"] == 1.2


def test_csv_cells_cannot_inject_formulas():
    out = services.to_csv(
        ["a", "=b"], [["=SUM(1,1)", "+1", "-2", "@x", "ok", None], ["\tcmd", "plain", 3, 4, 5, 6]]
    ).decode("utf-8-sig")
    assert "'=SUM(1,1)" in out and "'+1" in out and "'-2" in out and "'@x" in out and "'\tcmd" in out and "'=b" in out
    assert "ok" in out and "'ok" not in out


def test_empty_database_returns_zeroes_not_errors(db):
    assert services.overview(None)["transactions"] == 0
    assert services.volume(None, "day", None, None) == []
    f = services.false_positives(None)
    assert f["investigated"]["alerts"]["rate"] is None and f["labelled"]["precision"] is None


# ------------------------------------------------------------------ API
def test_api_endpoints_and_export(world, make_user, api_as):
    ds, _ = world
    client = api_as(make_user("management"))
    r = client.get("/api/v1/analytics/overview/", {"dataset": ds.id})
    assert r.status_code == 200 and r.json()["transactions"] == 6 and r.json()["refreshed_at"]
    assert client.get("/api/v1/analytics/datasets/").json() == [{"id": ds.id, "name": ds.name}]
    assert client.get("/api/v1/analytics/volume/", {"granularity": "year"}).status_code == 400
    assert client.get("/api/v1/analytics/volume/", {"dataset": "x"}).status_code == 400
    assert client.get("/api/v1/analytics/overview/", {"dataset": 999999}).status_code == 400
    assert client.get("/api/v1/analytics/volume/", {"granularity": "week", "dataset": ds.id}).json()["series"]
    for url in (
        "risk-distribution",
        "accounts/high-risk",
        "recent-suspicious",
        "investigations/summary",
        "false-positives",
        "detection-performance",
    ):
        assert client.get(f"/api/v1/analytics/{url}/", {"dataset": ds.id}).status_code == 200, url
    csv = client.get("/api/v1/analytics/export/", {"report": "volume", "file": "csv", "dataset": ds.id})
    assert csv.status_code == 200 and csv["Content-Type"].startswith("text/csv") and b"Transactions" in csv.content
    pdf = client.get("/api/v1/analytics/export/", {"report": "false-positives", "file": "pdf"})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert client.get("/api/v1/analytics/export/", {"report": "nope"}).status_code == 400
    assert client.get("/api/v1/analytics/export/", {"report": "volume", "file": "xlsx"}).status_code == 400
    assert AuditLog.objects.filter(action="analytics.exported").count() == 2


def test_refresh_requires_its_own_permission(world, make_user, api_as):
    ds, _ = world
    assert api_as(make_user("management")).post("/api/v1/analytics/refresh/", {"dataset": ds.id}).status_code == 403
    analyst = api_as(make_user("financial_analyst"))
    r = analyst.post(f"/api/v1/analytics/refresh/?dataset={ds.id}")
    assert r.status_code == 200 and r.json()["days"] == 4
    assert AuditLog.objects.filter(action="analytics.refreshed").exists()


def test_beat_task_refreshes_every_dataset(world):
    from apps.analytics.tasks import refresh_all

    ds, _ = world
    assert refresh_all() == {ds.id: 4}
