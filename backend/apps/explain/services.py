"""Generate and store explanations, each tied to the exact model version, prediction and risk assessment it explains."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from django.conf import settings
from django.utils import timezone

from apps.audit import services as audit
from apps.behavior import services as behavior_services
from apps.detection.models import Prediction
from apps.detection.services import build_frame
from apps.duplicates.models import DuplicateCandidate
from apps.graph_engine.models import GraphFinding, GraphSnapshot
from apps.model_registry.models import ModelVersion
from apps.risk_engine.models import RiskAssessment
from apps.transactions.models import Transaction
from ml_engine import explain as mx
from ml_engine import inference
from ml_engine.features import paysim as fp
from risk_engine_lib import COMPONENTS

from . import narrative as nar
from .models import Explanation, ExplanationJob

log = logging.getLogger(__name__)
GENERATOR_VERSION = "x1"
ALL_METHODS = ("shap", "lime", "behavioral", "graph", "risk_breakdown", "summary")
LIME_BACKGROUND_ROWS, LIME_SAMPLES = 500, 2000
COMPONENT_NAMES = {
    "A": "model anomaly",
    "B": "behaviour",
    "G": "graph",
    "F": "frequency",
    "D": "duplicate",
    "H": "history",
}


class ExplanationError(Exception):
    """A request cannot be served (message is safe to show)."""


# ------------------------------------------------------------------------------------ version binding
def latest_prediction(tx: Transaction, model_version: ModelVersion | None = None) -> Prediction | None:
    qs = Prediction.objects.filter(transaction=tx, run__status="succeeded").select_related("run__model_version")
    if model_version is not None:
        qs = qs.filter(run__model_version=model_version)
    return qs.order_by("-run__created_at", "-id").first()


def latest_assessment(tx: Transaction) -> RiskAssessment | None:
    return (
        RiskAssessment.objects.filter(transaction=tx).select_related("config").order_by("-computed_at", "-id").first()
    )


def assert_version_match(prediction: Prediction, model_version: ModelVersion) -> None:
    """An explanation must describe the model that produced the prediction it is attached to."""
    if prediction.run.model_version_id != model_version.pk:
        raise ExplanationError(
            f"Version mismatch: the prediction came from model version {prediction.run.model_version_id}, not {model_version.pk}."
        )


def staleness(exp: Explanation, tx: Transaction | None = None) -> tuple[bool, str]:
    """(current, reason). An explanation is stale when something it was built from has been superseded: the same model
    version was run again, a newer risk assessment exists, or a newer graph analysis exists. A *different* model scoring
    the transaction later does not make it stale (see `other_model_note`)."""
    tx = tx or exp.transaction
    if tx is None:
        return True, ""
    meta = (exp.payload or {}).get("inputs", {})
    if exp.method in ("shap", "lime", "summary") and exp.model_version_id:
        latest = latest_prediction(tx, exp.model_version)
        if latest and latest.pk != exp.prediction_id:
            return (
                False,
                f"The same model version ({exp.model_version}) has been run again since; this explains an older prediction.",
            )
    if exp.method == "risk_breakdown" or (exp.method == "summary" and meta.get("assessment") is not None):
        latest_a = latest_assessment(tx)
        if latest_a and latest_a.pk != (
            exp.assessment_id if exp.method == "risk_breakdown" else meta.get("assessment")
        ):
            return False, "A newer risk assessment exists for this transaction."
    if exp.method in ("graph", "summary"):
        snap = GraphSnapshot.objects.filter(dataset=tx.dataset, status="succeeded").order_by("-created_at").first()
        if snap and meta.get("snapshot") not in (None, snap.pk):
            return False, "A newer graph analysis exists for this dataset."
    return True, ""


def other_model_note(exp: Explanation, tx: Transaction | None = None) -> str:
    """Informational: a later detection run by a different model also scored this transaction."""
    tx = tx or exp.transaction
    if tx is None or exp.method not in ("shap", "lime") or not exp.model_version_id:
        return ""
    latest = latest_prediction(tx)
    if (
        latest
        and latest.run.model_version_id != exp.model_version_id
        and latest.run.created_at > (exp.prediction.run.created_at if exp.prediction else latest.run.created_at)
    ):
        return f"A later run by another model ({latest.run.model_version}) also scored this transaction; this explains {exp.model_version}."
    return ""


# ------------------------------------------------------------------------------------ jobs
def create_job(
    *, tx: Transaction, user: Any, methods: list[str] | None, model_version: ModelVersion | None
) -> ExplanationJob:
    chosen = list(methods or ALL_METHODS)
    bad = [m for m in chosen if m not in ALL_METHODS]
    if bad:
        raise ExplanationError(f"Unknown method(s): {bad}. Choose from {list(ALL_METHODS)}.")
    job = ExplanationJob.objects.create(transaction=tx, model_version=model_version, methods=chosen, created_by=user)
    audit.log(
        "explanation.requested",
        actor=user,
        resource_type="transaction",
        resource_id=tx.pk,
        changes={"methods": chosen, "job": job.pk},
    )
    return job


def create_global_job(*, model_version: ModelVersion, user: Any) -> ExplanationJob:
    job = ExplanationJob.objects.create(
        kind="global", model_version=model_version, methods=["feature_importance"], created_by=user
    )
    audit.log(
        "explanation.requested",
        actor=user,
        resource_type="model_version",
        resource_id=model_version.pk,
        changes={"job": job.pk, "kind": "global"},
    )
    return job


def execute_job(job_id: int) -> None:
    job = ExplanationJob.objects.select_related("transaction__dataset", "model_version").get(pk=job_id)
    if job.status == ExplanationJob.Status.SUCCEEDED:
        return
    job.status, job.error_message = ExplanationJob.Status.RUNNING, ""
    job.save(update_fields=["status", "error_message"])
    try:
        result = _run_global(job) if job.kind == "global" else _run_transaction(job)
        job.result, job.status, job.finished_at = result, ExplanationJob.Status.SUCCEEDED, timezone.now()
        job.save()
        audit.log(
            "explanation.generated",
            actor=job.created_by,
            resource_type="explanation_job",
            resource_id=job.pk,
            changes={"created": result["created"], "skipped": list(result["skipped"])},
        )
    except Exception as exc:  # noqa: BLE001 - surface as a failed job
        log.exception("explanation job %s failed", job_id)
        job.status, job.finished_at = ExplanationJob.Status.FAILED, timezone.now()
        job.error_message = (
            str(exc)[:400] if isinstance(exc, (ExplanationError, inference.ArtifactError)) else "Unexpected error."
        )
        job.save()


# ------------------------------------------------------------------------------------ model context
def _model_context(tx: Transaction, prediction: Prediction) -> dict[str, Any]:
    version = prediction.run.model_version
    model = inference.load_artifact(
        version.artifact_path, version.artifact_sha256, settings.ML_ARTIFACTS_DIR
    )  # hash-verified
    names: list[str] = version.feature_schema["features"]
    frame = build_frame(tx.dataset)
    feats = fp.build_features(frame)[names]
    idx = int(np.flatnonzero((frame["id"] == tx.pk).to_numpy())[0])
    X = feats.to_numpy()
    algorithm = version.model.algorithm
    score_now = float(inference.score_matrix(model, algorithm, X[idx : idx + 1])[0])
    if abs(score_now - prediction.score) > 1e-6 * max(1.0, abs(prediction.score)):
        raise ExplanationError(
            "The stored prediction can no longer be reproduced (the dataset's history changed since the run); re-run detection first."
        )
    rng = np.random.default_rng(tx.pk)
    bg_idx = rng.choice(len(X), size=min(LIME_BACKGROUND_ROWS, len(X)), replace=False)
    return {"version": version, "model": model, "algorithm": algorithm, "names": names, "x": X[idx], "background": X[bg_idx], "score": prediction.score,
            "score_fn": lambda A: inference.score_matrix(model, algorithm, np.asarray(A)), "dataset_rows": len(X)}  # fmt: skip


def _attrib_rows(
    names: list[str], x: np.ndarray, contrib: np.ndarray, extra: dict[str, str] | None = None
) -> list[dict[str, Any]]:
    order = np.argsort(-np.abs(contrib))
    return [{"name": names[i], "label": mx.feature_label(names[i]), "value": float(x[i]), "display": mx.display_value(names[i], float(x[i])),
             "contribution": float(contrib[i]), **({"rule": extra[names[i]]} if extra and names[i] in extra else {})} for i in order]  # fmt: skip


def _save(
    tx: Transaction | None, method: str, payload: dict[str, Any], text: str, job: ExplanationJob, **links: Any
) -> Explanation:
    prediction, version = links.get("prediction"), links.get("model_version")
    if prediction is not None and version is not None:
        assert_version_match(prediction, version)
    return Explanation.objects.create(
        transaction=tx,
        method=method,
        payload=payload,
        narrative=text,
        generator_version=GENERATOR_VERSION,
        job=job,
        created_by=job.created_by,
        **links,
    )


# ------------------------------------------------------------------------------------ the pieces
def _graph_findings(tx: Transaction) -> tuple[GraphSnapshot | None, list[dict[str, Any]]]:
    snap = GraphSnapshot.objects.filter(dataset=tx.dataset, status="succeeded").order_by("-created_at").first()
    if snap is None or snap.as_of <= tx.occurred_at:
        return snap, []
    parties = [tx.sender_id] + ([tx.receiver_id] if tx.receiver_id else [])
    rows = list(GraphFinding.objects.filter(snapshot=snap, account_ids__overlap=parties).order_by("-score"))
    need = {t for f in rows for t in f.transaction_ids}
    times = dict(Transaction.objects.filter(pk__in=need).values_list("id", "occurred_at"))
    out = []
    for f in rows:
        done = max((times[t] for t in f.transaction_ids if t in times), default=snap.as_of)
        if done <= tx.occurred_at:  # only patterns that had completed by this transaction
            out.append({"id": f.pk, "finding_type": f.finding_type, "score": f.score, "account_ids": f.account_ids[:12], "transaction_ids": f.transaction_ids[:12],
                        "evidence": {k: v for k, v in f.evidence.items() if isinstance(v, (int, float, str, bool))}, "completed_at": done.isoformat()})  # fmt: skip
    return snap, out


def _risk_payload(a: RiskAssessment) -> dict[str, Any]:
    comps = {}
    for c in COMPONENTS:
        v = a.components.get(c, {})
        comps[c] = {"name": COMPONENT_NAMES[c], "available": v.get("available", False), "value": v.get("value"), "weight": v.get("weight"),
                    "contribution": v.get("contribution"), "reason": v.get("reason", ""), "imputed": v.get("imputed", False)}  # fmt: skip
    return {"overall_score": a.overall_score, "category": a.category, "weight_coverage": a.weight_coverage, "low_coverage": a.low_coverage, "capped": a.capped,
            "policy": a.policy, "config_version": a.config.version, "algorithm_version": a.algorithm_version, "components": comps}  # fmt: skip


def _timeline(tx: Transaction, extra_ids: set[int]) -> list[dict[str, Any]]:
    recent = list(
        Transaction.objects.filter(sender=tx.sender, occurred_at__lte=tx.occurred_at)
        .select_related("receiver")
        .order_by("-occurred_at", "-id")[:8]
    )
    related = list(
        Transaction.objects.filter(pk__in=extra_ids - {t.pk for t in recent}).select_related("sender", "receiver")[:8]
    )
    rows = []
    for t in sorted({*recent, *related}, key=lambda t: (t.occurred_at, t.pk)):
        rows.append({"transaction_id": t.pk, "external_id": t.transaction_id, "occurred_at": t.occurred_at.isoformat(), "amount": str(t.amount), "tx_type": t.tx_type,
                     "sender": t.sender.account_ref, "receiver": t.receiver.account_ref if t.receiver else None, "is_this_transaction": t.pk == tx.pk})  # fmt: skip
    return rows


def _run_transaction(job: ExplanationJob) -> dict[str, Any]:
    tx = job.transaction
    assert tx is not None
    methods = set(job.methods)
    created: list[str] = []
    skipped: dict[str, str] = {}
    prediction = latest_prediction(tx, job.model_version)
    assessment = latest_assessment(tx)
    parts: dict[str, Any] = {}
    inputs: dict[str, Any] = {
        "prediction": prediction.pk if prediction else None,
        "assessment": assessment.pk if assessment else None,
        "snapshot": None,
    }

    ctx = None
    if methods & {"shap", "lime", "summary"} and prediction is not None:
        try:
            ctx = _model_context(tx, prediction)
        except (ExplanationError, inference.ArtifactError, KeyError) as exc:
            for m in ("shap", "lime"):
                if m in methods:
                    skipped[m] = str(exc) or "model features could not be rebuilt"
            ctx = None
    elif methods & {"shap", "lime"}:
        for m in ("shap", "lime"):
            if m in methods:
                skipped[m] = "no detection prediction exists for this transaction"

    if ctx is not None:
        version, algorithm = ctx["version"], ctx["algorithm"]
        assert prediction is not None
        thr = prediction.run.threshold
        if "shap" in methods or "summary" in methods:
            if algorithm in mx.SHAP_ALGORITHMS:
                values, base, space = mx.shap_attribution(ctx["model"], algorithm, ctx["x"].reshape(1, -1))
                rows = _attrib_rows(ctx["names"], ctx["x"], values[0])
                text = nar.model_narrative(algorithm, ctx["score"], thr, rows, space)
                parts["model"] = text
                if "shap" in methods:
                    payload = {"algorithm": algorithm, "score": ctx["score"], "threshold": thr, "base_value": base, "space": space, "features": rows,
                               "additivity_residual": float(base + values[0].sum()) , "feature_set": version.feature_schema.get("feature_set"),
                               "artifact_sha256": version.artifact_sha256, "background": "none (exact tree/linear SHAP)", "inputs": inputs}  # fmt: skip
                    _save(tx, "shap", payload, text, job, prediction=prediction, model_version=version)
                    created.append("shap")
            elif "shap" in methods:
                skipped["shap"] = f"SHAP is not used for {algorithm}; LIME explains it instead."
        if "lime" in methods or ("summary" in methods and "model" not in parts):
            if "lime" in methods:
                w = mx.lime_attribution(
                    ctx["score_fn"], ctx["background"], ctx["x"], ctx["names"], seed=tx.pk, num_samples=LIME_SAMPLES
                )
                contrib = np.zeros(len(ctx["names"]))
                for f, wt, _ in w:
                    contrib[ctx["names"].index(f)] = wt
                rows = _attrib_rows(ctx["names"], ctx["x"], contrib, {f: r for f, _, r in w})
                rows = [r for r in rows if r["contribution"] != 0.0]
                text = nar.model_narrative(algorithm, ctx["score"], thr, rows, None)
                parts.setdefault("model", text)
                payload = {"algorithm": algorithm, "score": ctx["score"], "threshold": thr, "seed": tx.pk, "num_samples": LIME_SAMPLES, "features": rows,
                           "background": f"{len(ctx['background'])} transactions sampled (seeded) from the same dataset", "feature_set": version.feature_schema.get("feature_set"),
                           "artifact_sha256": version.artifact_sha256, "note": "LIME samples randomly: weights vary a little between runs.", "inputs": inputs}  # fmt: skip
                _save(tx, "lime", payload, text, job, prediction=prediction, model_version=version)
                created.append("lime")

    beh = None
    if methods & {"behavioral", "summary"}:
        beh = behavior_services.live_transaction_behavior(tx)
        text = nar.behaviour_narrative(beh)
        parts["behaviour"] = text
        if "behavioral" in methods:
            payload = {"status": beh["status"], "deviation_score": beh["deviation_score"], "coverage": beh["coverage"], "history_count": beh["history_count"],
                       "components": {k: {"available": v["available"], "score": v.get("score"), "detail": v.get("detail", {}), "reason": v.get("reason", "")} for k, v in beh["components"].items()},
                       "profile_version": beh["profile_version"], "inputs": inputs}  # fmt: skip
            _save(tx, "behavioral", payload, text, job)
            created.append("behavioral")

    snap: GraphSnapshot | None = None
    findings: list[dict[str, Any]] = []
    if methods & {"graph", "summary"}:
        snap, findings = _graph_findings(tx)
        inputs["snapshot"] = snap.pk if snap else None
        text = nar.graph_narrative(findings) if snap else "No graph analysis exists for this dataset."
        parts["graph"] = text
        if "graph" in methods:
            _save(
                tx, "graph", {"snapshot": snap.pk if snap else None, "findings": findings, "inputs": inputs}, text, job
            )
            created.append("graph")

    if "risk_breakdown" in methods or "summary" in methods:
        if assessment is None:
            if "risk_breakdown" in methods:
                skipped["risk_breakdown"] = "this transaction has not been risk scored"
        else:
            rp = _risk_payload(assessment)
            text = nar.risk_narrative(rp)
            parts["risk"] = text
            if "risk_breakdown" in methods:
                _save(tx, "risk_breakdown", {**rp, "inputs": inputs}, text, job, assessment=assessment)
                created.append("risk_breakdown")

    if "summary" in methods:
        cands = list(
            DuplicateCandidate.objects.filter(kind="transaction")
            .filter(record_a_id=tx.pk)
            .union(DuplicateCandidate.objects.filter(kind="transaction", record_b_id=tx.pk))
            .values(
                "id",
                "record_a_id",
                "record_b_id",
                "match_class",
                "similarity_score",
                "review_status",
                "reviewed_by__email",
            )
        )
        live = [c for c in cands if c["match_class"] != "legitimate_repeat"]
        parts["duplicate"] = nar.duplicate_narrative([dict(c) for c in live])
        extra_ids = {t for f in findings for t in f["transaction_ids"]} | {
            i for c in live for i in (c["record_a_id"], c["record_b_id"])
        }
        timeline = _timeline(tx, extra_ids)
        parts["evidence"] = f"{len(timeline)} related transaction(s) are listed in the timeline, including this one."
        reviewed = [c for c in cands if c["review_status"] != "pending"]
        if reviewed:
            c = reviewed[0]
            parts["outcome"] = (
                f"Duplicate candidate #{c['id']} was reviewed by {c['reviewed_by__email']}: {c['review_status'].replace('_', ' ')}."
            )
        sections = nar.summary_sections(parts)
        _save(tx, "summary", {"sections": sections, "timeline": timeline, "disclaimer": nar.DISCLAIMER, "inputs": inputs}, " ".join(s["text"] for s in sections), job,
              prediction=prediction if ctx is not None else None, model_version=ctx["version"] if ctx is not None else None, assessment=assessment)  # fmt: skip
        created.append("summary")
    return {"created": created, "skipped": skipped}


def _run_global(job: ExplanationJob) -> dict[str, Any]:
    version = job.model_version
    assert version is not None
    from apps.detection.services import is_scorable

    if not is_scorable(version):
        raise ExplanationError("This model's features cannot be computed from stored transactions.")
    from apps.detection.models import DetectionRun

    run = DetectionRun.objects.filter(model_version=version, status="succeeded").order_by("-created_at").first()
    if run is None:
        raise ExplanationError("No detection run exists for this model version; run detection on a dataset first.")
    model = inference.load_artifact(version.artifact_path, version.artifact_sha256, settings.ML_ARTIFACTS_DIR)
    names = version.feature_schema["features"]
    X = fp.build_features(build_frame(run.dataset))[names].to_numpy()
    rng = np.random.default_rng(version.pk)
    sample = X[rng.choice(len(X), size=min(1000, len(X)), replace=False)]
    algorithm = version.model.algorithm
    payload: dict[str, Any] = {
        "algorithm": algorithm,
        "dataset": run.dataset.name,
        "rows_used": len(sample),
        "feature_set": version.feature_schema.get("feature_set"),
        "artifact_sha256": version.artifact_sha256,
    }
    if algorithm in mx.SHAP_ALGORITHMS:
        values, _, space = mx.shap_attribution(model, algorithm, sample)
        mean_abs = np.abs(values).mean(axis=0)
        payload.update({"method": "mean |SHAP| over a sample", "space": space,
                        "features": [{"name": names[i], "label": mx.feature_label(names[i]), "importance": float(mean_abs[i])} for i in np.argsort(-mean_abs)]})  # fmt: skip
    else:
        raise ExplanationError(
            f"Global importance is computed with SHAP; {algorithm} is not supported (use per-transaction LIME)."
        )
    if algorithm == "XGBoost":
        payload["intrinsic_gain"] = {n: float(v) for n, v in zip(names, model.feature_importances_, strict=True)}
    elif algorithm == "RandomForest":
        payload["intrinsic_impurity"] = {n: float(v) for n, v in zip(names, model.feature_importances_, strict=True)}
    elif algorithm == "LogisticRegression":
        payload["intrinsic_coefficients_scaled"] = {
            n: float(v) for n, v in zip(names, model.named_steps["clf"].coef_[0], strict=True)
        }
    top = ", ".join(f"{f['label']} ({f['importance']:.3f})" for f in payload["features"][:5])
    text = f"Across {len(sample)} sampled transactions of {run.dataset.name}, the {algorithm} model relies most on: {top}. Importance is the average size of a feature's contribution, not a measure of fraud."
    _save(None, "feature_importance", payload, text, job, model_version=version)
    return {"created": ["feature_importance"], "skipped": {}}
