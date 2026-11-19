"""Phase 5B: model factories obey the leakage rules and are deterministic (small synthetic data)."""

import numpy as np
import pandas as pd
import pytest

from ml_engine.experiments import models


def synth(n=3000, seed=0):
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < 0.03).astype(int)
    y[:5] = 1
    X = pd.DataFrame(rng.normal(size=(n, 6)), columns=list("abcdef"))
    X["a"] += y * 2.5
    return X, y


def split():
    return synth(3000, 0), synth(1500, 1)


def test_undersample_keeps_all_positives_and_is_seeded():
    y = np.r_[np.ones(10), np.zeros(1000)].astype(int)
    a = models.undersample_negatives(y, 100, seed=1)
    assert y[a].sum() == 10 and (y[a] == 0).sum() == 100
    assert np.array_equal(a, models.undersample_negatives(y, 100, seed=1))
    assert not np.array_equal(a, models.undersample_negatives(y, 100, seed=2))
    assert len(models.undersample_negatives(y, 5000, seed=1)) == len(y)  # nothing to drop


@pytest.mark.parametrize("name", ["lr", "rf", "xgb", "iforest", "lof", "ocsvm", "ae"])
def test_every_model_scores_rows_and_separates_signal(name):
    train, val = split()
    f = models.FACTORIES[name](train, val, 42)
    scores = f.predict(val[0].to_numpy())
    assert scores.shape == (len(val[1]),) and np.isfinite(scores).all()
    from sklearn.metrics import roc_auc_score

    assert roc_auc_score(val[1], scores) > 0.7  # the planted signal is found
    assert f.task_type == ("supervised" if name in ("lr", "rf", "xgb") else "unsupervised")


@pytest.mark.parametrize("name", ["rf", "xgb", "iforest", "lof", "ocsvm", "ae"])
def test_models_are_deterministic_for_a_seed(name):
    train, val = split()
    a = models.FACTORIES[name](train, val, 7).predict(val[0].to_numpy())
    b = models.FACTORIES[name](train, val, 7).predict(val[0].to_numpy())
    assert np.allclose(a, b)


@pytest.mark.parametrize("name", ["iforest", "lof", "ocsvm", "ae"])
def test_unsupervised_models_never_see_labels(name):
    train, val = split()
    flipped = (train[0], 1 - train[1])  # labels destroyed; an unsupervised fit must not change
    flipped_val = (val[0], 1 - val[1])
    a = models.FACTORIES[name](train, val, 3).predict(val[0].to_numpy())
    b = models.FACTORIES[name](flipped, flipped_val, 3).predict(val[0].to_numpy())
    assert np.allclose(a, b)


def test_autoencoder_scores_anomalies_higher_and_records_history():
    rng = np.random.default_rng(0)
    normal = pd.DataFrame(rng.normal(size=(4000, 6)), columns=list("abcdef"))
    f = models.fit_autoencoder((normal, np.zeros(4000, int)), (normal.iloc[:1000], np.zeros(1000, int)), 0, epochs=5)
    far = normal.iloc[:200] + 8.0
    assert f.predict(far.to_numpy()).mean() > 5 * f.predict(normal.iloc[:200].to_numpy()).mean()
    assert f.notes["history"][0]["epoch"] == 1


def test_selection_uses_validation_not_test_and_records_trials():
    train, val = split()
    f = models.fit_rf(train, val, 1)
    assert len(f.notes["trials"]) == 3 and f.hyperparameters["min_samples_leaf"] in (1, 5, 20)
    best = max(f.notes["trials"], key=lambda t: t["val_pr_auc"])
    assert best["min_samples_leaf"] == f.hyperparameters["min_samples_leaf"]
