"""Phase 5D: detection runs, hash-verified artifact loading, predictions API (synthetic data, real code path)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from apps.audit.models import AuditLog
from apps.detection import services
from apps.detection.models import DetectionRun, Prediction
from apps.model_registry.models import ModelVersion
from apps.model_registry.services import register_results
from ml_engine.features import paysim as fp

pytestmark = pytest.mark.django_db


@pytest.fixture
def artifacts(settings, tmp_path):
    settings.ML_ARTIFACTS_DIR = tmp_path / "artifacts"
    settings.ML_ARTIFACTS_DIR.mkdir()
    return settings.ML_ARTIFACTS_DIR


@pytest.fixture
def populated(make_dataset, make_tx):
    ds = make_dataset()
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(60):
        make_tx(
            ds, sender=f"C{i}", receiver=f"M{i % 5}", amount=str(50 + i * 40), tx_type="PAYMENT" if i % 3 else "TRANSFER",
            occurred_at=base + timedelta(hours=i), step=i + 1,
            sender_balance_before=Decimal("1000"), sender_balance_after=Decimal("500"),
            receiver_balance_before=Decimal("0"), receiver_balance_after=Decimal("0"),
        )  # fmt: skip
    return ds


def train_and_register(artifacts, features=None, name="lr_test", sha_override=None, algorithm="LogisticRegression"):
    features = features or fp.CORE_FEATURES
    rng = np.random.default_rng(0)
    X = rng.normal(size=(500, len(features)))
    y = (X[:, 0] + rng.normal(size=500) > 1.5).astype(int)
    pipe = Pipeline([("s", StandardScaler()), ("c", LogisticRegression(class_weight="balanced"))]).fit(X, y)
    out = artifacts / name
    out.mkdir(exist_ok=True)
    path = out / "model.joblib"
    joblib.dump(pipe, path)
    from ml_engine.inference import file_sha256

    mv = register_results(
        {
            "run": name, "dataset": "paysim", "algorithm": algorithm, "artifact": str(path),
            "artifact_sha256": sha_override or file_sha256(path), "seed": 1, "raw_sha256": "r" * 64,
            "features": features, "feature_set": "core",
            "metrics": {
                "validation": {"at_validation_threshold": {"threshold": 0.5}},
                "test": {"pr_auc": 0.4, "roc_auc": 0.9, "base_rate": 0.01, "rows": 100, "positives": 1},
                "latency": {"single_ms_median": 0.1},
            },
        }
    )  # fmt: skip
    return mv, pipe


def start_run(api, mv, ds, run_tasks, **extra):
    with run_tasks(execute=True):
        res = api.post("/api/v1/detection/runs/", {"model_version": mv.pk, "dataset": ds.pk, **extra}, format="json")
    return res


def test_run_scores_every_transaction_and_matches_the_research_pipeline(
    artifacts, populated, make_user, api_as, run_tasks
):
    mv, pipe = train_and_register(artifacts)
    api = api_as(make_user("financial_analyst"))
    res = start_run(api, mv, populated, run_tasks)
    assert res.status_code == 202, res.content
    run = DetectionRun.objects.get(pk=res.data["id"])
    assert run.status == "succeeded" and run.rows_scored == 60 and run.threshold == 0.5
    # the stored scores equal what the research code produces from the same rows
    frame = services.build_frame(populated)
    expected = pipe.predict_proba(fp.build_features(frame)[fp.CORE_FEATURES].to_numpy())[:, 1]
    stored = dict(Prediction.objects.filter(run=run).values_list("transaction_id", "score"))
    assert np.allclose([stored[i] for i in frame["id"]], expected)
    assert run.rows_flagged == int((expected >= 0.5).sum())
    assert sum(run.score_summary["histogram"]["counts"]) == 60


def test_predictions_endpoint_is_ordered_filtered_and_hides_ground_truth(
    artifacts, populated, make_user, api_as, run_tasks
):
    populated.transactions.update(ground_truth_label=True)
    mv, _ = train_and_register(artifacts)
    api = api_as(make_user("financial_analyst"))
    run_id = start_run(api, mv, populated, run_tasks, threshold=0.0).data["id"]
    body = api.get(f"/api/v1/detection/runs/{run_id}/predictions/").json()
    scores = [r["score"] for r in body["results"]]
    assert scores == sorted(scores, reverse=True) and body["count"] == 60
    assert not any("ground_truth" in k or "label" in k for r in body["results"] for k in r)
    only = api.get(f"/api/v1/detection/runs/{run_id}/predictions/?flagged=true").json()
    assert only["count"] == 60  # threshold 0.0 flags everything
    hist = api.get(f"/api/v1/transactions/{body['results'][0]['transaction_id']}/predictions/").json()
    assert len(hist) == 1 and hist[0]["run"] == run_id and hist[0]["threshold"] == 0.0


def test_tampered_artifact_fails_the_run_without_loading_it(artifacts, populated, make_user, api_as, run_tasks):
    mv, _ = train_and_register(artifacts)
    (artifacts / "lr_test" / "model.joblib").write_bytes(b"not the registered file")
    api = api_as(make_user("financial_analyst"))
    run = DetectionRun.objects.get(pk=start_run(api, mv, populated, run_tasks).data["id"])
    assert run.status == "failed" and "hash" in run.error_message
    assert not Prediction.objects.filter(run=run).exists()
    assert AuditLog.objects.filter(action="detection.run.failed").exists()


def test_artifact_outside_the_allowed_directory_is_refused(
    artifacts, populated, make_user, api_as, run_tasks, tmp_path
):
    mv, _ = train_and_register(artifacts)
    outside = tmp_path / "elsewhere.joblib"
    outside.write_bytes((artifacts / "lr_test" / "model.joblib").read_bytes())
    ModelVersion.objects.filter(pk=mv.pk).update(artifact_path=str(outside))
    api = api_as(make_user("financial_analyst"))
    run = DetectionRun.objects.get(pk=start_run(api, mv, populated, run_tasks).data["id"])
    assert run.status == "failed" and "outside" in run.error_message


def test_model_with_unavailable_features_or_retired_status_is_rejected(
    artifacts, populated, make_user, api_as, run_tasks
):
    api = api_as(make_user("financial_analyst"))
    ulb, _ = train_and_register(artifacts, features=[f"V{i}" for i in range(1, 5)], name="lr_ulb")
    res = api.post("/api/v1/detection/runs/", {"model_version": ulb.pk, "dataset": populated.pk}, format="json")
    assert res.status_code == 400 and res.json()["error"]["code"] == "detection_not_possible"
    mv, _ = train_and_register(artifacts)
    ModelVersion.objects.filter(pk=mv.pk).update(status="retired")
    assert (
        api.post(
            "/api/v1/detection/runs/", {"model_version": mv.pk, "dataset": populated.pk}, format="json"
        ).status_code
        == 400
    )
    assert not DetectionRun.objects.exists()


def test_balance_model_fails_cleanly_when_balances_are_missing(
    artifacts, make_dataset, make_tx, make_user, api_as, run_tasks
):
    ds = make_dataset()
    for _ in range(5):
        make_tx(ds)  # no balance fields
    mv, _ = train_and_register(artifacts, features=fp.CORE_FEATURES + fp.BALANCE_FEATURES, name="lr_bal")
    api = api_as(make_user("financial_analyst"))
    run = DetectionRun.objects.get(pk=start_run(api, mv, ds, run_tasks).data["id"])
    assert run.status == "failed" and "balance" in run.error_message


def test_missing_step_falls_back_to_hours_since_first_transaction(make_dataset, make_tx):
    ds = make_dataset()
    base = datetime(2026, 1, 1, tzinfo=UTC)
    make_tx(ds, occurred_at=base)
    make_tx(ds, occurred_at=base + timedelta(hours=5, minutes=10))
    assert list(services.build_frame(ds)["step"]) == [1, 6]


def test_scores_use_only_earlier_history_in_the_dataset(artifacts, populated):
    """Adding later transactions never changes the features of earlier ones (platform path, same guarantee as research)."""
    before = fp.build_features(services.build_frame(populated))
    ids_before = services.build_frame(populated)["id"]
    populated.transactions.create(
        transaction_id="LATE", sender=populated.accounts.first(), receiver=populated.accounts.last(), amount=Decimal("1"),
        tx_type="TRANSFER", occurred_at=datetime(2026, 2, 1, tzinfo=UTC), step=5000,
    )  # fmt: skip
    after = fp.build_features(services.build_frame(populated))
    frame_after = services.build_frame(populated)
    keep = frame_after["id"].isin(ids_before).to_numpy()
    pd.testing.assert_frame_equal(before.reset_index(drop=True), after[keep].reset_index(drop=True))


def test_rerunning_a_finished_run_is_a_noop(artifacts, populated, make_user, api_as, run_tasks):
    mv, _ = train_and_register(artifacts)
    api = api_as(make_user("financial_analyst"))
    run_id = start_run(api, mv, populated, run_tasks).data["id"]
    first = list(Prediction.objects.filter(run_id=run_id).values_list("id", flat=True))
    services.execute_run(run_id)
    assert list(Prediction.objects.filter(run_id=run_id).values_list("id", flat=True)) == first


def test_model_version_endpoints_list_headline_metrics_and_flag_scorable(artifacts, make_user, api_as):
    mv, _ = train_and_register(artifacts)
    api = api_as(make_user("auditor"))
    rows = api.get("/api/v1/model-versions/").json()
    assert rows[0]["scorable"] is True and rows[0]["test_metrics"]["pr_auc"] == 0.4 and rows[0]["dataset"] == "paysim"
    detail = api.get(f"/api/v1/model-versions/{mv.pk}/").json()
    assert {e["split_name"] for e in detail["evaluations"]} >= {"validation", "test", "latency"}
    assert "artifact_path" not in detail  # internal filesystem path is not exposed


def test_investigator_can_read_but_not_run(artifacts, populated, make_user, api_as, run_tasks):
    mv, _ = train_and_register(artifacts)
    api = api_as(make_user("fraud_investigator"))
    assert api.get("/api/v1/detection/runs/").status_code == 200
    assert (
        api.post(
            "/api/v1/detection/runs/", {"model_version": mv.pk, "dataset": populated.pk}, format="json"
        ).status_code
        == 403
    )
