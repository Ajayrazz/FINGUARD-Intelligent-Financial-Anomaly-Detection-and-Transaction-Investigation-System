"""Phase 5A: causal features (leakage perturbation), evaluation harness, reproducibility."""

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml_engine import evaluation
from ml_engine.data import preprocess
from ml_engine.features import paysim as fp
from tests.test_ml_data import make_paysim


def cleaned(n: int = 1500, seed: int = 0) -> pd.DataFrame:
    df, _ = preprocess.clean_paysim(make_paysim(n, seed))
    return df


def test_feature_sets_have_expected_columns_and_no_leaky_inputs():
    feats = fp.build_features(cleaned())
    assert list(feats.columns) == fp.CORE_FEATURES + fp.BALANCE_FEATURES
    assert not feats.isna().any().any()
    for banned in ("step", "is_fraud", "is_flagged_fraud", "row_id"):
        assert banned not in feats.columns
    assert set(fp.CORE_FEATURES).isdisjoint(fp.BALANCE_FEATURES)


def test_prior_history_counts_only_strictly_earlier_steps():
    df = pd.DataFrame(
        {
            "step": [1, 1, 2, 3],
            "receiver": ["A", "A", "A", "B"],
            "sender": ["x", "y", "z", "w"],
            "amount": [10.0, 20.0, 5.0, 1.0],
        }
    )
    n, total = fp.prior_history(df, "receiver")
    assert list(n) == [0, 0, 2, 0]  # same-step rows do not see each other
    assert list(total) == [0.0, 0.0, 30.0, 0.0]


def test_future_perturbation_does_not_change_past_features():
    """Altering rows after step T must leave every feature of rows at step <= T unchanged."""
    df = cleaned()
    t = int(df["step"].quantile(0.6))
    base = fp.build_features(df)
    perturbed = df.copy()
    future = perturbed["step"] > t
    perturbed.loc[future, "amount"] *= 50
    perturbed.loc[future, "receiver"] = "C_new"
    perturbed.loc[future, "sender_balance_after"] += 999
    new = fp.build_features(perturbed)
    past = (df["step"] <= t).to_numpy()
    pd.testing.assert_frame_equal(base[past], new[past])
    assert not base[~past].equals(new[~past])  # and the perturbation is visible where it should be


def test_features_independent_of_row_order():
    df = cleaned()
    shuffled = df.sample(frac=1, random_state=3)
    a = fp.build_features(df)
    b = fp.build_features(shuffled).loc[a.index]
    pd.testing.assert_frame_equal(a, b)


def test_metrics_on_known_scores():
    y = np.array([0, 0, 0, 0, 1, 1])
    perfect = np.array([0.1, 0.2, 0.3, 0.4, 0.8, 0.9])
    m = evaluation.evaluate_scores(y, perfect, 0.5, n_boot=0, ks=(2,))
    assert m["pr_auc"] == pytest.approx(1.0) and m["roc_auc"] == pytest.approx(1.0)
    assert m["precision_at_2"] == 1.0 and m["recall_at_fpr_1pct"] == 1.0
    t = m["at_validation_threshold"]
    assert (t["tp"], t["fp"], t["fn"], t["tn"]) == (2, 0, 0, 4) and t["f1"] == 1.0
    worst = evaluation.evaluate_scores(y, -perfect, 0.5, n_boot=0, ks=())
    assert worst["roc_auc"] == pytest.approx(0.0)


def test_threshold_chosen_on_validation_is_frozen_for_test():
    rng = np.random.default_rng(0)
    yv = np.r_[np.zeros(500), np.ones(20)].astype(int)
    sv = np.r_[rng.normal(0, 1, 500), rng.normal(2, 1, 20)]
    thr = evaluation.choose_threshold_max_f1(yv, sv)
    yt = np.r_[np.zeros(500), np.ones(20)].astype(int)
    st = np.r_[rng.normal(0, 1, 500), rng.normal(2, 1, 20)]
    out = evaluation.evaluate_scores(yt, st, thr, n_boot=0, ks=())
    assert out["at_validation_threshold"]["threshold"] == thr  # test metrics never re-tune it


def test_bootstrap_ci_is_reproducible_and_brackets_estimate():
    rng = np.random.default_rng(1)
    y = (rng.random(2000) < 0.05).astype(int)
    s = y * 1.0 + rng.normal(0, 1, 2000)
    from sklearn.metrics import average_precision_score as ap

    a = evaluation.bootstrap_ci(y, s, ap, 50, seed=7)
    assert a == evaluation.bootstrap_ci(y, s, ap, 50, seed=7)
    assert a[0] <= ap(y, s) <= a[1]


def fit_score(X, y, seed):
    pipe = Pipeline([("s", StandardScaler()), ("c", LogisticRegression(class_weight="balanced", random_state=seed))])
    return pipe.fit(X, y).predict_proba(X)[:, 1]


def test_training_is_reproducible_with_same_seed():
    df = cleaned(3000)
    X = fp.build_features(df)[fp.CORE_FEATURES].to_numpy()
    y = df["is_fraud"].to_numpy()
    assert np.array_equal(fit_score(X, y, 42), fit_score(X, y, 42))


def test_latency_measurement_returns_positive_numbers():
    X = np.random.default_rng(0).normal(size=(2000, 5))
    lat = evaluation.measure_latency(lambda a: a.sum(axis=1), X, single_repeats=20, batch_rows=1000)
    assert lat["single_ms_median"] > 0 and lat["batch_rows_per_s"] > 0
