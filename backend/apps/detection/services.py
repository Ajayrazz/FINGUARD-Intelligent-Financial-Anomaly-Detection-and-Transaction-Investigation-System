"""Detection: build features from stored transactions, score them with a registered model, persist predictions."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.datasets.models import Dataset
from apps.model_registry.models import ModelEvaluation, ModelVersion
from apps.transactions.models import Transaction
from ml_engine import inference
from ml_engine.features import paysim as fp

from .models import DetectionRun, Prediction

log = logging.getLogger(__name__)
SUPPORTED_FEATURES = set(fp.CORE_FEATURES) | set(fp.BALANCE_FEATURES)
BATCH = 5000


class DetectionError(Exception):
    """A run cannot be created or executed (message is safe to show to the user)."""


def is_scorable(version: ModelVersion) -> bool:
    """Platform transactions can be scored only by models whose features this system can compute."""
    features = (version.feature_schema or {}).get("features") or []
    return bool(features) and set(features) <= SUPPORTED_FEATURES


def registry_threshold(version: ModelVersion) -> float | None:
    ev = ModelEvaluation.objects.filter(version=version, split_name="validation").first()
    try:
        return float(ev.metrics["at_validation_threshold"]["threshold"]) if ev else None
    except (KeyError, TypeError):
        return None


def create_run(*, version: ModelVersion, dataset: Dataset, user: Any, threshold: float | None = None) -> DetectionRun:
    if version.status == ModelVersion.Status.RETIRED:
        raise DetectionError("This model version is retired.")
    if not is_scorable(version):
        raise DetectionError(
            "This model was trained on features the platform cannot compute from stored transactions "
            "(for example the ULB credit-card model uses anonymised PCA components)."
        )
    default = registry_threshold(version)
    if threshold is None and default is None:
        raise DetectionError("This model version has no validation threshold in the registry; supply one.")
    if not Transaction.objects.filter(dataset=dataset).exists():
        raise DetectionError("The dataset has no transactions.")
    chosen = threshold if threshold is not None else default
    assert chosen is not None
    run = DetectionRun.objects.create(
        model_version=version,
        dataset=dataset,
        threshold=chosen,
        threshold_source="request" if threshold is not None else "registry: max F1 on validation, frozen",
        created_by=user,
    )
    audit.log(
        "detection.run.created", actor=user, resource_type="detection_run", resource_id=run.pk,
        changes={"model_version": str(version), "dataset": dataset.pk, "threshold": run.threshold},
    )  # fmt: skip
    return run


def build_frame(dataset: Dataset) -> pd.DataFrame:
    """Transactions of a dataset as the frame `ml_engine.features.paysim.build_features` expects."""
    qs = Transaction.objects.filter(dataset=dataset)
    if qs.count() > settings.DETECTION_MAX_ROWS:
        raise DetectionError(f"Dataset exceeds the detection limit of {settings.DETECTION_MAX_ROWS:,} rows.")
    rows = qs.values_list(
        "id", "step", "occurred_at", "tx_type", "amount", "sender__account_ref", "receiver__account_ref",
        "sender_balance_before", "sender_balance_after", "receiver_balance_before", "receiver_balance_after",
    )  # fmt: skip
    df = pd.DataFrame.from_records(
        rows,
        columns=[
            "id", "step", "occurred_at", "type", "amount", "sender", "receiver",
            "sender_balance_before", "sender_balance_after", "receiver_balance_before", "receiver_balance_after",
        ],
    )  # fmt: skip
    if df["step"].isna().any():  # no dataset step: use whole hours since the first transaction (documented)
        hours = ((df["occurred_at"] - df["occurred_at"].min()).dt.total_seconds() // 3600).astype("int64") + 1
        df["step"] = df["step"].fillna(hours).astype("int64")
    df["step"] = df["step"].astype("int64")
    df["type"] = df["type"].astype(str).str.upper()
    df["receiver"] = df["receiver"].fillna("").astype(str)
    for col in (
        "amount",
        "sender_balance_before",
        "sender_balance_after",
        "receiver_balance_before",
        "receiver_balance_after",
    ):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    return df.sort_values(["step", "id"], kind="stable").reset_index(drop=True)


def _summarise(scores: np.ndarray, threshold: float) -> dict[str, Any]:
    qs = np.quantile(scores, [0.5, 0.9, 0.99, 0.999])
    counts, edges = np.histogram(scores, bins=20)
    return {
        "min": float(scores.min()), "max": float(scores.max()), "mean": float(scores.mean()),
        "quantiles": {"p50": float(qs[0]), "p90": float(qs[1]), "p99": float(qs[2]), "p99.9": float(qs[3])},
        "histogram": {"counts": counts.tolist(), "edges": [float(e) for e in edges]},
        "threshold": threshold,
    }  # fmt: skip


def execute_run(run_id: int) -> None:
    """Score every transaction of the run's dataset. Idempotent: a finished run is left alone and a rerun of a
    failed/pending run replaces any partial predictions."""
    run = DetectionRun.objects.select_related("model_version__model", "dataset").get(pk=run_id)
    if run.status == DetectionRun.Status.SUCCEEDED:
        return
    run.status, run.started_at, run.error_message = DetectionRun.Status.RUNNING, timezone.now(), ""
    run.save(update_fields=["status", "started_at", "error_message"])
    try:
        version = run.model_version
        model = inference.load_artifact(version.artifact_path, version.artifact_sha256, settings.ML_ARTIFACTS_DIR)
        features = version.feature_schema["features"]
        frame = build_frame(run.dataset)
        if set(features) & set(fp.BALANCE_FEATURES):
            cols = [
                "sender_balance_before",
                "sender_balance_after",
                "receiver_balance_before",
                "receiver_balance_after",
            ]
            if frame[cols].isna().any().any():
                raise DetectionError("This model needs balance fields, which some transactions in the dataset lack.")
        frame = frame.fillna({c: 0.0 for c in frame.columns if c.endswith(("before", "after"))})
        X = fp.build_features(frame)[features].to_numpy()
        scores = inference.score_matrix(model, version.model.algorithm, X)
        if not np.isfinite(scores).all():
            raise DetectionError("The model produced non-finite scores.")
        flagged = scores >= run.threshold
        ids = frame["id"].to_numpy()
        with db_transaction.atomic():
            Prediction.objects.filter(run=run).delete()
            for i in range(0, len(ids), BATCH):
                Prediction.objects.bulk_create(
                    [
                        Prediction(run=run, transaction_id=int(t), score=float(s), flagged=bool(f))
                        for t, s, f in zip(
                            ids[i : i + BATCH], scores[i : i + BATCH], flagged[i : i + BATCH], strict=True
                        )
                    ]
                )
            run.rows_scored, run.rows_flagged = len(ids), int(flagged.sum())
            run.score_summary = _summarise(scores, run.threshold)
            run.status, run.finished_at = DetectionRun.Status.SUCCEEDED, timezone.now()
            run.save()
        audit.log(
            "detection.run.completed", actor=run.created_by, resource_type="detection_run", resource_id=run.pk,
            changes={"rows_scored": run.rows_scored, "rows_flagged": run.rows_flagged},
        )  # fmt: skip
    except Exception as exc:  # noqa: BLE001 - any failure must surface as a failed run, not a lost task
        log.exception("detection run %s failed", run_id)
        message = str(exc) if isinstance(exc, (DetectionError, inference.ArtifactError)) else "Unexpected error."
        run.status, run.error_message, run.finished_at = DetectionRun.Status.FAILED, message[:500], timezone.now()
        run.save(update_fields=["status", "error_message", "finished_at"])
        audit.log(
            "detection.run.failed", actor=run.created_by, resource_type="detection_run", resource_id=run.pk,
            changes={"error": message[:200]},
        )  # fmt: skip
