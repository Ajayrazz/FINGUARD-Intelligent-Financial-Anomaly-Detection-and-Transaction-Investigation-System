"""Run one model on one dataset/feature set with the shared evaluation harness.

    python -m ml_engine.experiments.runner --dataset paysim --feature-set core --model xgb

Writes the model (joblib) and `results.json` under datasets/artifacts/<run>/. Register with
`python manage.py register_experiment <results.json>`. Thresholds are chosen on validation and frozen for test.
"""

from __future__ import annotations

import argparse
import json
import platform
import time
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn

from ml_engine import evaluation
from ml_engine.data import config
from ml_engine.experiments import models
from ml_engine.experiments.baseline import ARTIFACTS_DIR, load_creditcard, load_paysim, sha256
from ml_engine.features import paysim as paysim_features


def run_name(model: str, dataset: str, feature_set: str) -> str:
    return f"{model}_{dataset}_{feature_set.replace('+', '_')}" if dataset == "paysim" else f"{model}_{dataset}"


def run(dataset: str, feature_set: str, model: str, seed: int, n_boot: int) -> dict[str, Any]:
    t0 = time.time()
    data, columns = load_paysim(feature_set) if dataset == "paysim" else load_creditcard()
    fit_start = time.time()
    fitted = models.FACTORIES[model](
        (data["train"][0], data["train"][1]), (data["validation"][0], data["validation"][1]), seed
    )
    fit_seconds = time.time() - fit_start

    X_train, y_train = data["train"][0].to_numpy(), data["train"][1]
    if (
        fitted.train_eval_cap and len(y_train) > fitted.train_eval_cap
    ):  # slow scorers: sample (seeded) for train metrics
        sel = np.sort(np.random.default_rng(seed).choice(len(y_train), fitted.train_eval_cap, replace=False))
        X_train, y_train = X_train[sel], y_train[sel]
        fitted.notes["train_metrics_on_sample_rows"] = int(fitted.train_eval_cap)
    eval_sets = {
        "train": (X_train, y_train),
        "validation": (data["validation"][0].to_numpy(), data["validation"][1]),
        "test": (data["test"][0].to_numpy(), data["test"][1]),
    }
    scores = {s: fitted.predict(X) for s, (X, _) in eval_sets.items()}
    threshold = evaluation.choose_threshold_max_f1(eval_sets["validation"][1], scores["validation"])  # frozen
    metrics: dict[str, Any] = {}
    for split, (_, y) in eval_sets.items():
        metrics[split] = evaluation.evaluate_scores(
            y, scores[split], threshold, n_boot=n_boot if split != "train" else 0, seed=seed
        )
    if dataset == "paysim":
        mask = data["test"][2].isin(["TRANSFER", "CASH_OUT"]).to_numpy()
        metrics["test_transfer_cashout_only"] = evaluation.evaluate_scores(
            data["test"][1][mask], scores["test"][mask], threshold, n_boot=n_boot, seed=seed
        )
    metrics["latency"] = evaluation.measure_latency(fitted.predict, data["test"][0].to_numpy())

    name = run_name(model, dataset, feature_set)
    out_dir = ARTIFACTS_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = out_dir / "model.joblib"
    joblib.dump(fitted.model, artifact)
    manifest = json.loads((config.PROCESSED_DIR / dataset / "manifest.json").read_text())
    versions = {
        "python": platform.python_version(),
        "scikit-learn": sklearn.__version__,
        "numpy": np.__version__,
        "pandas": pd.__version__,
    }
    if model == "xgb":
        import xgboost

        versions["xgboost"] = xgboost.__version__
    results = {
        "run": name,
        "dataset": dataset,
        "algorithm": fitted.algorithm,
        "task_type": fitted.task_type,
        "artifact_format": f"joblib ({fitted.algorithm})",
        "feature_set": feature_set if dataset == "paysim" else "V1-V28+log_amount",
        "features": columns,
        "hyperparameters": fitted.hyperparameters,
        "model_selection": fitted.notes,
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
        "versions": versions,
    }
    (out_dir / "results.json").write_text(json.dumps(results, indent=2, default=str))
    t = metrics["test"]
    ci = t.get("pr_auc_ci95", [0, 0])
    print(
        f"[{name}] test PR-AUC={t['pr_auc']:.4f} [{ci[0]:.3f},{ci[1]:.3f}] ROC={t['roc_auc']:.4f} "
        f"R@FPR1%={t['recall_at_fpr_1pct']:.3f} val PR-AUC={metrics['validation']['pr_auc']:.4f} "
        f"fit={fit_seconds:.0f}s total={results['total_seconds']:.0f}s",
        flush=True,
    )
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", choices=["paysim", "creditcard"], required=True)
    ap.add_argument("--feature-set", choices=list(paysim_features.FEATURE_SETS), default="core")
    ap.add_argument("--model", choices=list(models.FACTORIES), required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-boot", type=int, default=100)
    a = ap.parse_args(argv)
    run(a.dataset, a.feature_set, a.model, a.seed, a.n_boot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
