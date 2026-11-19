"""Write experiment results (from ml_engine) into the model registry."""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from .models import MLModel, ModelEvaluation, ModelVersion

REQUIRED = ("run", "dataset", "algorithm", "artifact", "artifact_sha256", "metrics", "seed", "raw_sha256")


def register_results(results: dict[str, Any], *, code_commit: str = "") -> ModelVersion:
    """Idempotently record one experiment. The version id embeds the artifact hash, so re-running identical
    training yields the same version (evaluations are refreshed); a changed artifact makes a new version."""
    missing = [k for k in REQUIRED if k not in results]
    if missing:
        raise ValueError(f"results are missing keys: {missing}")
    version = f"{results['dataset']}-s{results['seed']}-{results['artifact_sha256'][:8]}"
    with transaction.atomic():
        model, _ = MLModel.objects.get_or_create(
            name=results["run"],
            defaults={
                "task_type": results.get("task_type", MLModel.TaskType.SUPERVISED),
                "algorithm": results["algorithm"],
            },
        )
        mv, _ = ModelVersion.objects.update_or_create(
            model=model,
            version=version,
            defaults={
                "artifact_path": results["artifact"],
                "artifact_sha256": results["artifact_sha256"],
                "artifact_format": results.get("artifact_format", "joblib (sklearn Pipeline)"),
                "feature_schema": {"feature_set": results.get("feature_set"), "features": results.get("features", [])},
                "hyperparameters": {
                    **results.get("hyperparameters", {}),
                    "_model_selection": results.get("model_selection", {}),
                },
                "training_data_sha256": results["raw_sha256"],
                "split_strategy": results.get("split", {}),
                "random_seed": results["seed"],
                "library_versions": results.get("versions", {}),
                "code_commit": code_commit[:40],
                "trained_at": timezone.now(),
            },
        )
        mv.evaluations.all().delete()
        for split_name, metrics in results["metrics"].items():
            if split_name == "latency":
                continue
            ModelEvaluation.objects.create(version=mv, split_name=split_name, metrics=metrics)
        ModelEvaluation.objects.create(
            version=mv, split_name="latency", metrics=results["metrics"].get("latency", {}), notes="CPU, measured"
        )
    return mv
