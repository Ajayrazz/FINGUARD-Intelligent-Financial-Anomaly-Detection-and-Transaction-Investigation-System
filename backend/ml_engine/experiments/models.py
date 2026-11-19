"""Model factories for Phase 5. Each `fit_*` returns a `Fitted` and uses only train (and, for selection /
early stopping, validation) data — never test. Class imbalance handling touches the training data only."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

Split = tuple[Any, np.ndarray]  # (X as DataFrame/array, y)


@dataclass
class Fitted:
    model: Any
    predict: Callable[[np.ndarray], np.ndarray]  # numpy rows -> anomaly/fraud score (higher = riskier)
    algorithm: str
    task_type: str  # supervised | unsupervised
    hyperparameters: dict[str, Any]
    notes: dict[str, Any] = field(default_factory=dict)  # selection trail, subsampling, timings


def fit_lr(train: Split, val: Split, seed: int, **kwargs: Any) -> Fitted:
    X, y = train
    pipe = Pipeline(
        [
            ("scale", StandardScaler()),  # fitted on train only
            ("clf", LogisticRegression(C=1.0, class_weight="balanced", max_iter=300, random_state=seed)),
        ]
    )
    pipe.fit(X.to_numpy(), y)
    hp = {"C": 1.0, "class_weight": "balanced", "max_iter": 300, "scaler": "StandardScaler (train-fit)"}
    return Fitted(pipe, lambda a: pipe.predict_proba(a)[:, 1], "LogisticRegression", "supervised", hp)


def undersample_negatives(y: np.ndarray, max_negatives: int, seed: int) -> np.ndarray:
    """Indices of all positives plus a seeded random sample of negatives (train data only)."""
    rng = np.random.default_rng(seed)
    pos = np.flatnonzero(y == 1)
    neg = np.flatnonzero(y == 0)
    if len(neg) > max_negatives:
        neg = rng.choice(neg, max_negatives, replace=False)
    return np.sort(np.concatenate([pos, neg]))


def fit_rf(train: Split, val: Split, seed: int, *, max_negatives: int = 400_000, **kwargs: Any) -> Fitted:
    """Random Forest on all train positives + sampled negatives; `min_samples_leaf` picked on validation PR-AUC."""
    X, y = train
    idx = undersample_negatives(y, max_negatives, seed)
    Xs, ys = X.to_numpy()[idx], y[idx]
    Xv, yv = val[0].to_numpy(), val[1]
    trials = []
    best: tuple[float, Any, int] | None = None
    for leaf in (1, 5, 20):
        t0 = time.time()
        rf = RandomForestClassifier(
            n_estimators=100,
            min_samples_leaf=leaf,
            max_features="sqrt",
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=seed,
        ).fit(Xs, ys)
        pr = float(average_precision_score(yv, rf.predict_proba(Xv)[:, 1]))
        trials.append({"min_samples_leaf": leaf, "val_pr_auc": pr, "fit_seconds": time.time() - t0})
        if best is None or pr > best[0]:
            best = (pr, rf, leaf)
    assert best is not None
    _, rf, leaf = best
    hp = {
        "n_estimators": 100,
        "min_samples_leaf": leaf,
        "max_features": "sqrt",
        "class_weight": "balanced_subsample",
        "train_negatives_sampled": int((ys == 0).sum()),
    }
    notes = {
        "search": "min_samples_leaf in {1,5,20}, selected by validation PR-AUC",
        "trials": trials,
        "train_rows_used": len(idx),
    }
    return Fitted(rf, lambda a: rf.predict_proba(a)[:, 1], "RandomForest", "supervised", hp, notes)


def fit_xgb(train: Split, val: Split, seed: int, **kwargs: Any) -> Fitted:
    """XGBoost (hist) on the full train split; small grid, early stopping on validation."""
    from xgboost import XGBClassifier

    X, y = train[0].to_numpy(), train[1]
    Xv, yv = val[0].to_numpy(), val[1]
    ratio = float((y == 0).sum() / max((y == 1).sum(), 1))
    trials = []
    best: tuple[float, Any, dict[str, Any]] | None = None
    for depth in (4, 6, 8):
        for spw_name, spw in (("1", 1.0), ("sqrt_ratio", float(np.sqrt(ratio)))):
            t0 = time.time()
            clf = XGBClassifier(
                n_estimators=500,
                learning_rate=0.1,
                max_depth=depth,
                scale_pos_weight=spw,
                subsample=0.8,
                colsample_bytree=0.8,
                tree_method="hist",
                eval_metric="aucpr",
                early_stopping_rounds=30,
                n_jobs=8,
                random_state=seed,
            )
            clf.fit(X, y, eval_set=[(Xv, yv)], verbose=False)
            pr = float(average_precision_score(yv, clf.predict_proba(Xv)[:, 1]))
            params = {"max_depth": depth, "scale_pos_weight": spw_name, "best_iteration": int(clf.best_iteration)}
            trials.append({**params, "val_pr_auc": pr, "fit_seconds": time.time() - t0})
            if best is None or pr > best[0]:
                best = (pr, clf, params)
    assert best is not None
    _, clf, params = best
    hp = {"learning_rate": 0.1, "subsample": 0.8, "colsample_bytree": 0.8, "tree_method": "hist", **params}
    notes = {
        "search": (
            "max_depth {4,6,8} x scale_pos_weight {1, sqrt(neg/pos)}; "
            "early stopping (30) on validation aucpr; selected by validation PR-AUC"
        ),
        "trials": trials,
    }
    return Fitted(clf, lambda a: clf.predict_proba(a)[:, 1], "XGBoost", "supervised", hp, notes)


def fit_iforest(train: Split, val: Split, seed: int, **kwargs: Any) -> Fitted:
    """Isolation Forest fitted WITHOUT labels. Labels are used only later, to pick the alert threshold on validation."""
    X = train[0].to_numpy()
    iso = IsolationForest(n_estimators=200, max_samples=1024, contamination="auto", n_jobs=-1, random_state=seed).fit(X)
    hp = {"n_estimators": 200, "max_samples": 1024, "contamination": "auto", "labels_used_in_fit": False}
    return Fitted(iso, lambda a: -iso.score_samples(a), "IsolationForest", "unsupervised", hp)


FACTORIES: dict[str, Callable[..., Fitted]] = {"lr": fit_lr, "rf": fit_rf, "xgb": fit_xgb, "iforest": fit_iforest}
