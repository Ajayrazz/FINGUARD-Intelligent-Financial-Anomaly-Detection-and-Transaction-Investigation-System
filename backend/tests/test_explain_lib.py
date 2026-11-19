"""Explanation library: SHAP additivity on trained models, LIME determinism, labels, deletion test, narratives."""

import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from apps.explain import narrative as nar
from ml_engine import explain as mx

NAMES = ["log_amount", "receiver_is_merchant", "type_TRANSFER", "sender_prior_tx_count"]


@pytest.fixture(scope="module")
def data():
    rng = np.random.default_rng(0)
    X = np.column_stack(
        [rng.normal(8, 2, 800), rng.integers(0, 2, 800), rng.integers(0, 2, 800), rng.integers(0, 4, 800).astype(float)]
    )
    y = ((X[:, 0] > 9.5) & (X[:, 2] == 1) | (rng.random(800) < 0.03)).astype(int)
    return X, y


def sigmoid(z):
    return 1 / (1 + np.exp(-z))


def test_shap_is_additive_for_xgboost_random_forest_and_logistic_regression(data):
    X, y = data
    xgb = XGBClassifier(n_estimators=30, max_depth=3, random_state=0).fit(X, y)
    rf = RandomForestClassifier(n_estimators=30, max_depth=5, random_state=0).fit(X, y)
    lr = Pipeline([("scale", StandardScaler()), ("clf", LogisticRegression(max_iter=300))]).fit(X, y)
    rows = X[:25]
    v, base, space = mx.shap_attribution(xgb, "XGBoost", rows)
    assert space == "log-odds" and v.shape == (25, 4)
    assert np.allclose(
        sigmoid(base + v.sum(axis=1)), xgb.predict_proba(rows)[:, 1], atol=1e-4
    )  # base + contributions = the score
    v, base, space = mx.shap_attribution(rf, "RandomForest", rows)
    assert space == "probability" and np.allclose(base + v.sum(axis=1), rf.predict_proba(rows)[:, 1], atol=1e-3)
    v, base, space = mx.shap_attribution(lr, "LogisticRegression", rows)
    assert space == "log-odds" and np.allclose(sigmoid(base + v.sum(axis=1)), lr.predict_proba(rows)[:, 1], atol=1e-4)
    with pytest.raises(ValueError):
        mx.shap_attribution(object(), "IsolationForest", rows)


def test_shap_attributes_the_planted_driver_most(data):
    X, y = data
    xgb = XGBClassifier(n_estimators=40, max_depth=3, random_state=0).fit(X, y)
    target = X[(X[:, 0] > 10.5) & (X[:, 2] == 1)][:1]
    v, _, _ = mx.shap_attribution(xgb, "XGBoost", target)
    assert mx.top_features(v[0], NAMES, 2)[0][0] in ("log_amount", "type_TRANSFER")
    assert [n for n, _ in mx.top_features(v[0], NAMES, 4)][-1] != "log_amount"


def test_lime_is_deterministic_for_a_seed_and_varies_across_seeds(data):
    X, y = data
    xgb = XGBClassifier(n_estimators=30, max_depth=3, random_state=0).fit(X, y)
    fn = lambda A: xgb.predict_proba(np.asarray(A))[:, 1]  # noqa: E731
    a = mx.lime_attribution(fn, X, X[3], NAMES, seed=1, num_samples=500)
    b = mx.lime_attribution(fn, X, X[3], NAMES, seed=1, num_samples=500)
    c = mx.lime_attribution(fn, X, X[3], NAMES, seed=2, num_samples=500)
    assert a == b and [w for _, w, _ in a] != [w for _, w, _ in c]
    assert {f for f, _, _ in a} <= set(NAMES) and all(isinstance(rule, str) for _, _, rule in a)


def test_labels_display_values_and_jaccard():
    assert (
        mx.feature_label("type_CASH_OUT") == "transaction type is CASH OUT"
        and mx.feature_label("log_amount") == "transaction amount"
    )
    assert mx.feature_label("weird_new_feature") == "weird new feature"
    assert (
        mx.display_value("log_amount", float(np.log1p(1234.5))) == "1,234.50"
        and mx.display_value("receiver_is_merchant", 1.0) == "yes"
    )
    assert mx.display_value("sender_prior_tx_count", float(np.log1p(3))) == "3"
    assert mx.topk_jaccard(["a", "b", "c"], ["a", "b", "d"]) == pytest.approx(0.5) and mx.topk_jaccard([], []) == 1.0


def test_deletion_test_separates_a_faithful_attribution_from_a_random_one(data):
    X, y = data
    xgb = XGBClassifier(n_estimators=40, max_depth=3, random_state=0).fit(X, y)
    rows = X[(X[:, 0] > 10.5) & (X[:, 2] == 1)][:30]
    fn = lambda A: xgb.predict_proba(A)[:, 1]  # noqa: E731
    v, _, _ = mx.shap_attribution(xgb, "XGBoost", rows)
    top_drop, rand_drop = mx.deletion_drop(fn, rows, v, np.median(X, axis=0), k=1, rng=np.random.default_rng(0))
    assert top_drop > rand_drop >= -0.05 and top_drop > 0.05  # removing what SHAP says matters hurts the score the most
    reversed_ranking = 1.0 / (np.abs(v) + 1e-9)  # the least important feature first
    wrong, _ = mx.deletion_drop(fn, rows, reversed_ranking, np.median(X, axis=0), k=1, rng=np.random.default_rng(0))
    assert wrong < 0.1 * top_drop


def test_narratives_are_deterministic_use_neutral_language_and_state_limits():
    attrib = [
        {"label": "transaction amount", "display": "40,000.00", "contribution": 1.2},
        {"label": "receiver is a merchant account", "display": "no", "contribution": -0.4},
    ]
    t = nar.model_narrative("XGBoost", 0.91, 0.2, attrib, "log-odds")
    assert t == nar.model_narrative("XGBoost", 0.91, 0.2, attrib, "log-odds") and "above" not in t.split("score of")[0]
    assert "raised the score most" in t and "lowered it most" in t and "not a conclusion" in t
    cold = {"status": "unavailable_cold_start", "history_count": 1, "components": {}}
    assert "only 1 earlier transaction" in nar.behaviour_narrative(cold)
    assert "No network pattern" in nar.graph_narrative(
        []
    ) and "No similar earlier transaction" in nar.duplicate_narrative([])
    risk = {"overall_score": 71.2, "category": "high", "weight_coverage": 0.55, "capped": True,
            "components": {"A": {"name": "model anomaly", "contribution": 40.0}, "B": {"name": "behaviour", "contribution": None}}}  # fmt: skip
    rt = nar.risk_narrative(risk)
    assert "model anomaly 40.0 points" in rt and "Not available and excluded: behaviour" in rt and "held at High" in rt
    sections = nar.summary_sections({})
    assert [s["title"] for s in sections] == ["Prediction", "Indicator", "Evidence", "Assessment", "Outcome"]
    everything = " ".join([t, rt, nar.DISCLAIMER, *[s["text"] for s in sections]]).lower()
    for banned in ("fraudster", "criminal", "guilty", "committed fraud", "is fraud"):
        assert banned not in everything
    assert "not proof" in nar.DISCLAIMER
