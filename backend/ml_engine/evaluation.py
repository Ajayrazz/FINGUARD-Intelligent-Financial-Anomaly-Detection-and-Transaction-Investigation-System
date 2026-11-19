"""Evaluation harness shared by every model: threshold-free and thresholded metrics, bootstrap CIs, latency.

Thresholds are chosen on the validation split and frozen before the test split is scored (leakage item 5).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import numpy as np
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score, roc_curve


def recall_at_fpr(y: np.ndarray, score: np.ndarray, fpr_target: float) -> float:
    fpr, tpr, _ = roc_curve(y, score)
    return float(tpr[fpr <= fpr_target].max())


def precision_at_k(y: np.ndarray, score: np.ndarray, k: int) -> float:
    top = np.argpartition(-score, min(k, len(score) - 1))[:k]
    return float(y[top].mean())


def choose_threshold_max_f1(y: np.ndarray, score: np.ndarray) -> float:
    """Threshold maximising F1 on the given (validation) data."""
    p, r, t = precision_recall_curve(y, score)
    f1 = 2 * p[:-1] * r[:-1] / np.maximum(p[:-1] + r[:-1], 1e-12)
    return float(t[int(np.argmax(f1))])


def threshold_metrics(y: np.ndarray, score: np.ndarray, threshold: float) -> dict[str, float | int]:
    pred = score >= threshold
    tp = int((pred & (y == 1)).sum())
    fp = int((pred & (y == 0)).sum())
    fn = int((~pred & (y == 1)).sum())
    tn = int((~pred & (y == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "threshold": float(threshold),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,
        "alerts": tp + fp,
    }


def bootstrap_ci(
    y: np.ndarray, score: np.ndarray, metric: Callable[[np.ndarray, np.ndarray], float], n_boot: int, seed: int
) -> tuple[float, float]:
    """95% percentile CI of `metric` over bootstrap resamples (fixed seed => reproducible)."""
    rng = np.random.default_rng(seed)
    n = len(y)
    vals = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        if y[idx].sum() == 0:
            continue
        vals.append(metric(y[idx], score[idx]))
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return float(lo), float(hi)


def evaluate_scores(
    y: np.ndarray,
    score: np.ndarray,
    threshold: float,
    *,
    n_boot: int = 100,
    seed: int = 0,
    ks: tuple[int, ...] = (100, 1000),
) -> dict[str, Any]:
    """All metrics for one split. `threshold` must come from validation."""
    out: dict[str, Any] = {
        "rows": int(len(y)),
        "positives": int(y.sum()),
        "base_rate": float(y.mean()),
        "pr_auc": float(average_precision_score(y, score)),
        "roc_auc": float(roc_auc_score(y, score)),
        "recall_at_fpr_0.1pct": recall_at_fpr(y, score, 0.001),
        "recall_at_fpr_1pct": recall_at_fpr(y, score, 0.01),
        "at_validation_threshold": threshold_metrics(y, score, threshold),
    }
    for k in ks:
        if k < len(y):
            out[f"precision_at_{k}"] = precision_at_k(y, score, k)
    if n_boot:
        lo, hi = bootstrap_ci(y, score, average_precision_score, n_boot, seed)
        out["pr_auc_ci95"] = [lo, hi]
    return out


def measure_latency(
    predict: Callable[[np.ndarray], np.ndarray], X: np.ndarray, *, single_repeats: int = 300, batch_rows: int = 100_000
) -> dict[str, float]:
    """Single-transaction latency (ms, median/p95) and batch throughput (rows/s). Measured, not estimated."""
    single = []
    for i in range(single_repeats):
        row = X[i % len(X) : i % len(X) + 1]
        t0 = time.perf_counter()
        predict(row)
        single.append((time.perf_counter() - t0) * 1000)
    batch = X[:batch_rows]
    t0 = time.perf_counter()
    predict(batch)
    elapsed = time.perf_counter() - t0
    return {
        "single_ms_median": float(np.median(single)),
        "single_ms_p95": float(np.percentile(single, 95)),
        "batch_rows_per_s": float(len(batch) / elapsed),
    }
