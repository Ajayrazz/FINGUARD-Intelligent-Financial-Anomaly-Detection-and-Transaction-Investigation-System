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
from sklearn.neighbors import LocalOutlierFactor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

Split = tuple[Any, np.ndarray]  # (X as DataFrame/array, y)


@dataclass
class Fitted:
    model: Any
    predict: Callable[[np.ndarray], np.ndarray]  # numpy rows -> anomaly/fraud score (higher = riskier)
    algorithm: str
    task_type: str  # supervised | unsupervised
    hyperparameters: dict[str, Any]
    notes: dict[str, Any] = field(default_factory=dict)  # selection trail, subsampling, timings
    train_eval_cap: int | None = None  # slow scorers: train-split metrics use a seeded sample of this many rows


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


def _fit_scaled_sample(train: Split, n: int, seed: int) -> tuple[StandardScaler, np.ndarray]:
    """Seeded unlabeled sample of train rows, scaled with a scaler fitted on that train sample only."""
    X = train[0].to_numpy()
    rng = np.random.default_rng(seed)
    idx = np.sort(rng.choice(len(X), min(n, len(X)), replace=False))
    scaler = StandardScaler().fit(X[idx])
    return scaler, scaler.transform(X[idx])


class _Scaled:
    """A fitted scaler + estimator scored as 'higher = more anomalous' (picklable, so it can be saved with joblib)."""

    def __init__(self, scaler: StandardScaler, est: Any, sign: float = -1.0) -> None:
        self.scaler, self.est, self.sign = scaler, est, sign

    def score(self, a: np.ndarray) -> np.ndarray:
        z = self.scaler.transform(a)
        fn = self.est.score_samples if hasattr(self.est, "score_samples") else self.est.decision_function
        return self.sign * fn(z)


def fit_lof(train: Split, val: Split, seed: int, *, n_fit: int = 50_000, **kwargs: Any) -> Fitted:
    """Local Outlier Factor in novelty mode, fitted on an unlabeled scaled train sample (O(n^2): subsample)."""
    scaler, Z = _fit_scaled_sample(train, n_fit, seed)
    lof = LocalOutlierFactor(n_neighbors=35, novelty=True, n_jobs=-1).fit(Z)
    wrapped = _Scaled(scaler, lof)
    hp = {
        "n_neighbors": 35,
        "novelty": True,
        "fit_sample_rows": len(Z),
        "scaler": "StandardScaler (train-sample fit)",
        "labels_used_in_fit": False,
    }
    return Fitted(
        wrapped, wrapped.score, "LocalOutlierFactor", "unsupervised", hp, {"tuned": False}, train_eval_cap=200_000
    )


def fit_ocsvm(train: Split, val: Split, seed: int, *, n_fit: int = 20_000, **kwargs: Any) -> Fitted:
    """RBF One-Class SVM on an unlabeled scaled train sample (training is super-linear in rows: subsample)."""
    scaler, Z = _fit_scaled_sample(train, n_fit, seed)
    svm = OneClassSVM(kernel="rbf", gamma="scale", nu=0.01).fit(Z)
    wrapped = _Scaled(scaler, svm)
    hp = {
        "kernel": "rbf",
        "gamma": "scale",
        "nu": 0.01,
        "fit_sample_rows": len(Z),
        "support_vectors": int(svm.support_vectors_.shape[0]),
        "labels_used_in_fit": False,
    }
    return Fitted(wrapped, wrapped.score, "OneClassSVM", "unsupervised", hp, {"tuned": False}, train_eval_cap=200_000)


class AutoencoderModel:
    """Scaler + PyTorch MLP autoencoder; score = per-row mean squared reconstruction error (scaled space)."""

    def __init__(self, scaler: StandardScaler, net: Any) -> None:
        self.scaler, self.net = scaler, net

    def score(self, a: np.ndarray) -> np.ndarray:
        import torch

        z = torch.from_numpy(self.scaler.transform(a).astype("float32"))
        out = []
        with torch.no_grad():
            self.net.eval()
            for i in range(0, len(z), 65_536):
                chunk = z[i : i + 65_536]
                out.append(((self.net(chunk) - chunk) ** 2).mean(dim=1).numpy())
        return np.concatenate(out)


def fit_autoencoder(train: Split, val: Split, seed: int, *, epochs: int = 15, **kwargs: Any) -> Fitted:
    """Autoencoder trained on UNLABELED train rows (labels never used). Early stopping on the validation
    reconstruction loss of the unlabeled validation features (no labels involved)."""
    import torch
    from torch import nn

    torch.manual_seed(seed)
    torch.set_num_threads(8)
    X = train[0].to_numpy()
    scaler = StandardScaler().fit(X)  # train-only fit
    Z = torch.from_numpy(np.clip(scaler.transform(X), -10, 10).astype("float32"))
    Zv = torch.from_numpy(np.clip(scaler.transform(val[0].to_numpy()), -10, 10).astype("float32"))
    d = Z.shape[1]
    hidden, bottleneck = max(d, 16), max(d // 3, 4)
    net = nn.Sequential(
        nn.Linear(d, hidden), nn.ReLU(), nn.Linear(hidden, bottleneck), nn.ReLU(),
        nn.Linear(bottleneck, hidden), nn.ReLU(), nn.Linear(hidden, d),
    )  # fmt: skip
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    gen = torch.Generator().manual_seed(seed)
    batch = 2048
    history, best_state, best_val, patience = [], None, float("inf"), 0
    for epoch in range(epochs):
        net.train()
        perm = torch.randperm(len(Z), generator=gen)
        total = 0.0
        for i in range(0, len(Z), batch):
            xb = Z[perm[i : i + batch]]
            opt.zero_grad()
            loss = ((net(xb) - xb) ** 2).mean()
            loss.backward()
            opt.step()
            total += loss.item() * len(xb)
        net.eval()
        with torch.no_grad():
            val_loss = float(((net(Zv) - Zv) ** 2).mean())
        history.append({"epoch": epoch + 1, "train_loss": total / len(Z), "val_loss": val_loss})
        if val_loss < best_val - 1e-5:
            best_val, patience = val_loss, 0
            best_state = {k: v.clone() for k, v in net.state_dict().items()}
        else:
            patience += 1
            if patience >= 3:
                break
    assert best_state is not None
    net.load_state_dict(best_state)

    clipped = _ClippedScaler(scaler)
    model = AutoencoderModel(clipped, net)  # type: ignore[arg-type]
    hp = {
        "architecture": f"{d}-{hidden}-{bottleneck}-{hidden}-{d} (ReLU)",
        "optimizer": "Adam lr=1e-3",
        "batch": batch,
        "max_epochs": epochs,
        "early_stopping": "patience 3 on unlabeled validation reconstruction loss",
        "input_clip": 10,
        "labels_used_in_fit": False,
    }
    return Fitted(model, model.score, "Autoencoder", "unsupervised", hp, {"history": history, "tuned": False})


class _ClippedScaler:
    """Standardise, then clip to +-10 sigma (heavy-tailed inputs would otherwise dominate the MSE)."""

    def __init__(self, scaler: StandardScaler) -> None:
        self.scaler = scaler

    def transform(self, a: np.ndarray) -> np.ndarray:
        return np.clip(self.scaler.transform(a), -10, 10)


FACTORIES: dict[str, Callable[..., Fitted]] = {
    "lr": fit_lr,
    "rf": fit_rf,
    "xgb": fit_xgb,
    "iforest": fit_iforest,
    "lof": fit_lof,
    "ocsvm": fit_ocsvm,
    "ae": fit_autoencoder,
}
