"""Explanations through the API on a real (small) trained model: versions, additivity, staleness, PDF, permissions."""

import math

import joblib
import numpy as np
import pytest
from django.db import IntegrityError
from django.db import transaction as dbtx
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from xgboost import XGBClassifier

from apps.audit.models import AuditLog
from apps.behavior import scenario
from apps.behavior import services as behavior_services
from apps.detection import services as det_services
from apps.detection.models import DetectionRun, Prediction
from apps.duplicates import services as dup_services
from apps.duplicates.models import DuplicateScanRun
from apps.explain import services
from apps.explain.models import Explanation
from apps.graph_engine import services as graph_services
from apps.model_registry.services import register_results
from apps.risk_engine import services as risk_services
from apps.transactions.models import Transaction
from ml_engine import inference
from ml_engine.features import paysim as fp

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(make_user):
    return make_user("financial_analyst")


@pytest.fixture
def analyst(user, api_as):
    return api_as(user)


@pytest.fixture
def artifacts(settings, tmp_path):
    settings.ML_ARTIFACTS_DIR = tmp_path / "artifacts"
    settings.ML_ARTIFACTS_DIR.mkdir()
    return settings.ML_ARTIFACTS_DIR


def register_model(artifacts, ds, algorithm, name):
    """Train a real model on the dataset's features, save + register it (hash-verified loading), return the version."""
    frame = det_services.build_frame(ds)
    X = fp.build_features(frame)[fp.CORE_FEATURES].to_numpy()
    burst = set(
        Transaction.objects.filter(dataset=ds, receiver__account_ref="NEW-PAYEE-X").values_list("id", flat=True)
    )
    y = frame["id"].isin(burst).to_numpy().astype(int)
    if algorithm == "XGBoost":
        model = XGBClassifier(n_estimators=30, max_depth=3, random_state=0).fit(X, y)
    elif algorithm == "RandomForest":
        model = RandomForestClassifier(n_estimators=30, max_depth=5, random_state=0).fit(X, y)
    else:
        model = IsolationForest(n_estimators=50, random_state=0).fit(X)
    out = artifacts / name
    out.mkdir(exist_ok=True)
    path = out / "model.joblib"
    joblib.dump(model, path)
    mv = register_results({
        "run": name, "dataset": "paysim", "algorithm": algorithm, "artifact": str(path), "artifact_sha256": inference.file_sha256(path), "seed": 0,
        "raw_sha256": "r" * 64, "features": fp.CORE_FEATURES, "feature_set": "core",
        "metrics": {"validation": {"at_validation_threshold": {"threshold": 0.5 if algorithm != "IsolationForest" else 0.0}}, "latency": {}},
        "task_type": "unsupervised" if algorithm == "IsolationForest" else "supervised",
    })  # fmt: skip
    return mv


def detect(ds, user, mv):
    run = det_services.create_run(version=mv, dataset=ds, user=user)
    det_services.execute_run(run.pk)
    run.refresh_from_db()
    assert run.status == "succeeded", run.error_message
    return run


@pytest.fixture
def world(artifacts, user):
    ds = scenario.build()
    mv = register_model(artifacts, ds, "XGBoost", "xgb_explain")
    det = detect(ds, user, mv)
    brun = behavior_services.create_run(dataset=ds, user=user)
    behavior_services.execute_run(brun.pk)
    snap = graph_services.create_snapshot(dataset=ds, user=user, as_of=None, window_days=None)
    graph_services.execute_snapshot(snap.pk)
    scan = DuplicateScanRun.objects.create(kind="transaction", dataset=ds, created_by=user)
    dup_services.execute_scan(scan.pk)
    rrun = risk_services.start_run(dataset=ds, user=user)
    risk_services.execute_run(rrun.pk)
    burst = Transaction.objects.filter(dataset=ds, receiver__account_ref="NEW-PAYEE-X").order_by("occurred_at", "id")
    return {"ds": ds, "mv": mv, "det": det, "tx": burst.last(), "burst": burst}


def explain(api, tx, run_tasks, **body):
    with run_tasks(execute=True):
        res = api.post(f"/api/v1/transactions/{tx.pk}/explanations/", body, format="json")
    assert res.status_code == 202, res.content
    return api.get(f"/api/v1/explanation-jobs/{res.data['id']}/").json()


def by_method(api, tx):
    return {e["method"]: e for e in api.get(f"/api/v1/transactions/{tx.pk}/explanations/").json()}


def test_all_methods_are_generated_and_tied_to_the_exact_versions(world, analyst, run_tasks):
    tx = world["tx"]
    job = explain(analyst, tx, run_tasks)
    assert job["status"] == "succeeded" and set(job["result"]["created"]) == {
        "shap",
        "lime",
        "behavioral",
        "graph",
        "risk_breakdown",
        "summary",
    }
    ex = by_method(analyst, tx)
    pred = Prediction.objects.get(transaction=tx, run=world["det"])
    for m in ("shap", "lime"):
        assert ex[m]["model_version"] == world["mv"].pk and ex[m]["prediction"] == pred.pk and ex[m]["current"] is True
        assert (
            ex[m]["generator_version"] == services.GENERATOR_VERSION
            and ex[m]["payload"]["artifact_sha256"] == world["mv"].artifact_sha256
        )
    assert ex["risk_breakdown"]["assessment"] is not None and ex["summary"]["assessment"] is not None
    assert "not proof" in ex["shap"]["disclaimer"]
    assert "ground_truth" not in str(ex).lower()


def test_shap_contributions_reproduce_the_stored_model_score(world, analyst, run_tasks):
    tx = world["tx"]
    explain(analyst, tx, run_tasks, methods=["shap"])
    p = by_method(analyst, tx)["shap"]["payload"]
    pred = Prediction.objects.get(transaction=tx, run=world["det"])
    assert p["score"] == pytest.approx(pred.score) and 1 / (1 + math.exp(-p["additivity_residual"])) == pytest.approx(
        pred.score, abs=1e-4
    )
    assert sum(f["contribution"] for f in p["features"]) + p["base_value"] == pytest.approx(
        p["additivity_residual"], abs=1e-4
    )
    mags = [abs(f["contribution"]) for f in p["features"]]
    assert mags == sorted(mags, reverse=True) and all(f["label"] and f["display"] for f in p["features"])


def test_lime_is_reproducible_and_labelled_as_random(world, analyst, run_tasks):
    tx = world["tx"]
    explain(analyst, tx, run_tasks, methods=["lime"])
    explain(analyst, tx, run_tasks, methods=["lime"])
    runs = list(Explanation.objects.filter(transaction=tx, method="lime").order_by("id"))
    assert (
        runs[0].payload["features"] == runs[1].payload["features"]
    )  # seeded by the transaction: same result every time
    assert "vary a little" in runs[0].payload["note"] and "sampled" in runs[0].payload["background"]


def test_summary_has_the_five_sections_a_timeline_and_the_non_proof_text(world, analyst, run_tasks):
    tx = world["tx"]
    explain(analyst, tx, run_tasks)
    s = by_method(analyst, tx)["summary"]["payload"]
    assert [x["title"] for x in s["sections"]] == ["Prediction", "Indicator", "Evidence", "Assessment", "Outcome"]
    assert (
        any(t["is_this_transaction"] for t in s["timeline"])
        and len(s["timeline"]) >= 2
        and "not proof" in s["disclaimer"]
    )
    text = " ".join(x["text"] for x in s["sections"])
    assert (
        "score of" in text
        and "risk score is" in text
        and "No analyst outcome" in text
        and "5 transactions" in text.replace("5 transactions", "5 transactions")
    )


def test_missing_inputs_are_skipped_with_reasons_not_invented(make_dataset, make_tx, analyst, run_tasks):
    ds = make_dataset()
    t = make_tx(ds, sender="C1", receiver="M1", amount="10")
    job = explain(analyst, t, run_tasks)
    assert set(job["result"]["skipped"]) == {"shap", "lime", "risk_breakdown"}
    assert (
        "no detection prediction" in job["result"]["skipped"]["shap"]
        and "not been risk scored" in job["result"]["skipped"]["risk_breakdown"]
    )
    ex = by_method(analyst, t)
    assert "No model prediction is available" in ex["summary"]["payload"]["sections"][0]["text"]
    assert (
        "only 0 earlier transaction" in ex["behavioral"]["narrative"]
        and "No graph analysis exists" in ex["graph"]["narrative"]
    )


def test_unsupported_algorithm_is_explained_with_lime_and_says_why_shap_is_skipped(
    artifacts, user, analyst, run_tasks, world
):
    mv = register_model(artifacts, world["ds"], "IsolationForest", "iforest_explain")
    detect(world["ds"], user, mv)
    job = explain(analyst, world["tx"], run_tasks, methods=["shap", "lime"], model_version=mv.pk)
    assert "SHAP is not used for IsolationForest" in job["result"]["skipped"]["shap"] and job["result"]["created"] == [
        "lime"
    ]
    lime = Explanation.objects.filter(transaction=world["tx"], method="lime").order_by("-id").first()
    assert lime.model_version_id == mv.pk and lime.prediction.run.model_version_id == mv.pk


def test_explanation_cannot_be_attached_to_a_prediction_of_another_model_version(artifacts, user, world):
    other = register_model(artifacts, world["ds"], "RandomForest", "rf_explain")
    pred = Prediction.objects.get(transaction=world["tx"], run=world["det"])
    with pytest.raises(services.ExplanationError, match="Version mismatch"):
        services.assert_version_match(pred, other)
    with (
        pytest.raises(IntegrityError),
        dbtx.atomic(),
    ):  # the database refuses a model explanation without prediction + version
        Explanation.objects.create(transaction=world["tx"], method="shap", payload={}, generator_version="x1")
    with pytest.raises(IntegrityError), dbtx.atomic():
        Explanation.objects.create(transaction=world["tx"], method="risk_breakdown", payload={}, generator_version="x1")


def test_rerunning_the_same_model_makes_the_explanation_stale_a_different_model_only_adds_a_note(
    artifacts, world, user, analyst, run_tasks
):
    tx = world["tx"]
    explain(analyst, tx, run_tasks)
    assert by_method(analyst, tx)["shap"]["current"] is True
    rf = register_model(artifacts, world["ds"], "RandomForest", "rf_explain")
    detect(world["ds"], user, rf)  # another model scores the transaction later
    ex = by_method(analyst, tx)
    assert (
        ex["shap"]["current"] is True and "another model" in ex["shap"]["note"] and "rf_explain" in ex["shap"]["note"]
    )
    assert ex["shap"]["model_version"] == world["mv"].pk  # still says which model it describes
    newer = detect(world["ds"], user, world["mv"])  # the same model version is run again
    stale = by_method(analyst, tx)
    assert (
        stale["shap"]["current"] is False
        and "run again" in stale["shap"]["stale_reason"]
        and stale["summary"]["current"] is False
    )
    explain(analyst, tx, run_tasks, methods=["shap"], model_version=world["mv"].pk)
    fresh = by_method(analyst, tx)["shap"]
    assert fresh["current"] is True and fresh["prediction"] == Prediction.objects.get(transaction=tx, run=newer).pk
    allx = analyst.get(f"/api/v1/transactions/{tx.pk}/explanations/?all=true").json()
    assert sum(e["method"] == "shap" for e in allx) == 2  # history kept


def test_a_new_risk_assessment_makes_the_risk_explanation_stale(world, user, analyst, run_tasks):
    tx = world["tx"]
    explain(analyst, tx, run_tasks, methods=["risk_breakdown"])
    r2 = risk_services.start_run(dataset=world["ds"], user=user)
    risk_services.execute_run(r2.pk)
    e = by_method(analyst, tx)["risk_breakdown"]
    assert e["current"] is False and "newer risk assessment" in e["stale_reason"]


def test_job_fails_clearly_when_the_prediction_can_no_longer_be_reproduced(world, user, analyst, run_tasks, make_tx):
    tx = world["tx"]
    # a new earlier transaction to the same receiver changes this transaction's history features after the run
    make_tx(
        world["ds"],
        sender="C-OTHER",
        receiver="NEW-PAYEE-X",
        amount="5",
        occurred_at=tx.occurred_at.replace(year=2025),
        step=1,
    )
    job = explain(analyst, tx, run_tasks, methods=["shap"])
    assert job["status"] == "succeeded" and "can no longer be reproduced" in job["result"]["skipped"]["shap"]


def test_tampered_artifact_is_refused(world, analyst, run_tasks):
    import pathlib

    pathlib.Path(world["mv"].artifact_path).write_bytes(b"swapped")
    job = explain(analyst, world["tx"], run_tasks, methods=["shap"])
    assert "hash does not match" in job["result"]["skipped"]["shap"]


def test_pdf_report_contains_versions_disclaimer_and_a_stale_warning(world, user, analyst, run_tasks, artifacts):
    tx = world["tx"]
    assert analyst.get(f"/api/v1/transactions/{tx.pk}/explanations/report/").status_code == 404
    explain(analyst, tx, run_tasks)
    res = analyst.get(f"/api/v1/transactions/{tx.pk}/explanations/report/")
    assert (
        res.status_code == 200
        and res["Content-Type"] == "application/pdf"
        and res.content.startswith(b"%PDF")
        and len(res.content) > 3000
    )
    detect(world["ds"], user, world["mv"])  # the same model is run again
    import io

    import pypdfium2 as pdfium

    page_text = (
        pdfium.PdfDocument(io.BytesIO(analyst.get(f"/api/v1/transactions/{tx.pk}/explanations/report/").content))[0]
        .get_textpage()
        .get_text_range()
    )
    assert "not proof of wrongdoing" in page_text and "STALE" in page_text and "xgb_explain" in page_text


def test_global_feature_importance_for_a_model_version(world, analyst, run_tasks):
    with run_tasks(execute=True):
        res = analyst.post(f"/api/v1/model-versions/{world['mv'].pk}/importance/", {}, format="json")
    assert res.status_code == 202
    e = analyst.get(f"/api/v1/model-versions/{world['mv'].pk}/importance/").json()
    imp = [f["importance"] for f in e["payload"]["features"]]
    assert (
        imp == sorted(imp, reverse=True)
        and e["model_version"] == world["mv"].pk
        and "intrinsic_gain" in e["payload"]
        and e["transaction"] is None
    )
    assert "not a measure of fraud" in e["narrative"]


def test_permissions_audit_and_validation(world, analyst, make_user, api_as, run_tasks):
    tx = world["tx"]
    explain(analyst, tx, run_tasks, methods=["summary"])
    aud = api_as(make_user("auditor"))
    assert aud.get(f"/api/v1/transactions/{tx.pk}/explanations/").status_code == 200
    assert aud.post(f"/api/v1/transactions/{tx.pk}/explanations/", {}, format="json").status_code == 403
    assert api_as(make_user("management")).get(f"/api/v1/transactions/{tx.pk}/explanations/").status_code == 403
    assert (
        analyst.post(f"/api/v1/transactions/{tx.pk}/explanations/", {"methods": ["magic"]}, format="json").status_code
        == 400
    )
    assert (
        analyst.post(
            f"/api/v1/transactions/{tx.pk}/explanations/", {"model_version": 999999}, format="json"
        ).status_code
        == 400
    )
    assert (
        AuditLog.objects.filter(action="explanation.requested").exists()
        and AuditLog.objects.filter(action="explanation.generated").exists()
    )
    assert np.isclose(1, 1) and DetectionRun.objects.count() >= 1
