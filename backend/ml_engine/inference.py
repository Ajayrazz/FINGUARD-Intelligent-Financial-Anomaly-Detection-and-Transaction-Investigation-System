"""Load a registered artifact (hash-verified) and score a feature matrix. No Django imports."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import joblib
import numpy as np

# These classes are pickled inside artifacts; importing them makes joblib.load work in any process.
from ml_engine.experiments import models as _models  # noqa: F401


class ArtifactError(Exception):
    """The artifact is missing, outside the allowed directory, or does not match its registered hash."""


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_artifact(path: str | Path, expected_sha256: str, allowed_dir: Path) -> Any:
    """Pickle executes code on load, so only files inside `allowed_dir` whose SHA-256 equals the registered
    hash are ever deserialised."""
    p = Path(path).resolve()
    root = allowed_dir.resolve()
    if root not in p.parents:
        raise ArtifactError("artifact path is outside the model artifact directory")
    if not p.is_file():
        raise ArtifactError("artifact file not found")
    if file_sha256(p) != expected_sha256:
        raise ArtifactError("artifact hash does not match the registry (file changed since registration)")
    return joblib.load(p)


def score_matrix(model: Any, algorithm: str, X: np.ndarray) -> np.ndarray:
    """Return one score per row; higher always means more suspicious."""
    if algorithm in ("LogisticRegression", "RandomForest", "XGBoost"):
        return np.asarray(model.predict_proba(X)[:, 1], dtype="float64")
    if algorithm == "IsolationForest":
        return np.asarray(-model.score_samples(X), dtype="float64")
    if algorithm in ("LocalOutlierFactor", "OneClassSVM", "Autoencoder"):
        return np.asarray(model.score(X), dtype="float64")
    raise ArtifactError(f"unsupported algorithm: {algorithm}")
