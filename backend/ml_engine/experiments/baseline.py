"""Phase 5A baseline: class-weighted logistic regression on chronological splits.

    python -m ml_engine.experiments.baseline --dataset paysim --feature-set core
    python -m ml_engine.experiments.baseline --dataset creditcard

Writes the fitted pipeline (joblib) and `results.json` under datasets/artifacts/<run>/; register them in the
model registry with `python manage.py register_experiment <results.json>`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml_engine import evaluation
from ml_engine.data import config
from ml_engine.features import paysim as paysim_features

ARTIFACTS_DIR = config.DATASETS_DIR / "artifacts"
SPLITS = ("train", "validation", "test")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_paysim(feature_set: str) -> tuple[dict[str, tuple[pd.DataFrame, np.ndarray, pd.Series]], list[str]]:
    """Return {split: (X, y, type)}. Features are computed on the full time-ordered frame, each using only the past."""
    base = config.PROCESSED_DIR / "paysim"
    frames = []
    for s in SPLITS:
        f = pd.read_parquet(base / f"{s}.parquet")
        f["split"] = s
        frames.append(f)
    full = pd.concat(frames, ignore_index=True)
    del frames
    full = full.sort_values(["step", "row_id"], kind="stable").reset_index(drop=True)
    feats = paysim_features.build_features(full)
    columns = paysim_features.FEATURE_SETS[feature_set]
    out = {}
    for s in SPLITS:
        mask = (full["split"] == s).to_numpy()
        out[s] = (feats.loc[mask, columns], full.loc[mask, "is_fraud"].to_numpy(), full.loc[mask, "type"].astype(str))
    return out, columns


def load_creditcard() -> tuple[dict[str, tuple[pd.DataFrame, np.ndarray, pd.Series]], list[str]]:
    base = config.PROCESSED_DIR / "creditcard"
    columns = [*(f"V{i}" for i in range(1, 29)), "log_amount"]
    out = {}
    for s in SPLITS:
        f = pd.read_parquet(base / f"{s}.parquet")
        f["log_amount"] = np.log1p(f["amount"])  # `time` is not a feature (48 h window, chronological split)
        out[s] = (f[columns].astype("float32"), f["is_fraud"].to_numpy(), pd.Series("all", index=f.index))
    return out, columns


def run(dataset: str, feature_set: str, seed: int, n_boot: int, C: float) -> dict[str, Any]:
    t0 = time.time()
    data, columns = load_paysim(feature_set) if dataset == "paysim" else load_creditcard()
    X_tr, y_tr, _ = data["train"]

    pipe = Pipeline(  # scaler is fitted inside the pipeline => on train only (leakage item 4)
        [
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(C=C, class_weight="balanced", max_iter=300, random_state=seed)),
        ]
    )
    fit_start = time.time()
    pipe.fit(X_tr.to_numpy(), y_tr)
    fit_seconds = time.time() - fit_start

    def score(split: str) -> np.ndarray:
        return pipe.predict_proba(data[split][0].to_numpy())[:, 1]

    val_score = score("validation")
    threshold = evaluation.choose_threshold_max_f1(data["validation"][1], val_score)  # frozen from here on
    metrics: dict[str, Any] = {}
    for split in ("train", "validation", "test"):
        y = data[split][1]
        s = score(split)
        metrics[split] = evaluation.evaluate_scores(
            y, s, threshold, n_boot=n_boot if split != "train" else 0, seed=seed
        )
    # diagnostic: PaySim fraud only exists in TRANSFER/CASH_OUT, so also score the test rows of those types
    if dataset == "paysim":
        mask = data["test"][2].isin(["TRANSFER", "CASH_OUT"]).to_numpy()
        metrics["test_transfer_cashout_only"] = evaluation.evaluate_scores(
            data["test"][1][mask], score("test")[mask], threshold, n_boot=n_boot, seed=seed
        )
    metrics["latency"] = evaluation.measure_latency(lambda a: pipe.predict_proba(a), data["test"][0].to_numpy())

    run_name = f"lr_{dataset}_{feature_set.replace('+', '_')}" if dataset == "paysim" else f"lr_{dataset}"
    out_dir = ARTIFACTS_DIR / run_name
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = out_dir / "model.joblib"
    joblib.dump(pipe, artifact)
    manifest = json.loads((config.PROCESSED_DIR / dataset / "manifest.json").read_text())
    results = {
        "run": run_name,
        "dataset": dataset,
        "algorithm": "LogisticRegression",
        "feature_set": feature_set if dataset == "paysim" else "V1-V28+log_amount",
        "features": columns,
        "hyperparameters": {
            "C": C,
            "class_weight": "balanced",
            "max_iter": 300,
            "scaler": "StandardScaler (train-fit)",
        },
        "seed": seed,
        "n_boot": n_boot,
        "threshold_policy": "max F1 on validation, frozen for test",
        "split": manifest["split"],
        "raw_sha256": manifest["raw"]["sha256"],
        "artifact": str(artifact),
        "artifact_sha256": sha256(artifact),
        "metrics": metrics,
        "fit_seconds": fit_seconds,
        "total_seconds": time.time() - t0,
        "versions": {
            "python": platform.python_version(),
            "scikit-learn": sklearn.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
    }
    (out_dir / "results.json").write_text(json.dumps(results, indent=2, default=str))
    t = metrics["test"]
    print(
        f"[{run_name}] test PR-AUC={t['pr_auc']:.4f} {t.get('pr_auc_ci95')} ROC={t['roc_auc']:.4f} "
        f"R@FPR1%={t['recall_at_fpr_1pct']:.3f} val PR-AUC={metrics['validation']['pr_auc']:.4f} "
        f"({results['total_seconds']:.0f}s)",
        flush=True,
    )
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", choices=["paysim", "creditcard"], required=True)
    ap.add_argument("--feature-set", choices=list(paysim_features.FEATURE_SETS), default="core")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-boot", type=int, default=100)
    ap.add_argument("-C", type=float, default=1.0, help="inverse L2 regularisation strength")
    a = ap.parse_args(argv)
    run(a.dataset, a.feature_set, a.seed, a.n_boot, a.C)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
