"""Model explanations: SHAP (tree/linear models), LIME (any model), and the checks used to evaluate them.

No Django imports. `values` are attributions per feature for one or many rows; for SHAP they sum (with the base value)
to the model output in `space` ("log-odds" for XGBoost and logistic regression, "probability" for random forests).
"""

from __future__ import annotations

from typing import Any

import numpy as np

SHAP_ALGORITHMS = ("LogisticRegression", "RandomForest", "XGBoost")

FEATURE_LABELS = {
    "log_amount": "transaction amount",
    "receiver_is_merchant": "receiver is a merchant account",
    "receiver_prior_tx_count": "earlier transactions received by this receiver",
    "receiver_prior_amount_log": "total earlier amount received by this receiver",
    "sender_prior_tx_count": "earlier transactions made by this sender",
    "sender_balance_before_log": "sender balance before",
    "sender_balance_after_log": "sender balance after",
    "receiver_balance_before_log": "receiver balance before",
    "receiver_balance_after_log": "receiver balance after",
    "sender_error": "sender balance change not matching the amount",
    "receiver_error": "receiver balance change not matching the amount",
    "sender_drained": "sender account emptied by the transaction",
    "amount_to_sender_balance": "amount relative to the sender's balance",
    "receiver_zero_both": "receiver balance zero before and after",
}


def feature_label(name: str) -> str:
    if name.startswith("type_"):
        return f"transaction type is {name[5:].replace('_', ' ')}"
    return FEATURE_LABELS.get(name, name.replace("_", " "))


def display_value(name: str, value: float) -> str:
    """Human-readable value (log features are shown on the original scale)."""
    if name in (
        "log_amount",
        "receiver_prior_amount_log",
        "sender_balance_before_log",
        "sender_balance_after_log",
        "receiver_balance_before_log",
        "receiver_balance_after_log",
    ):
        return f"{np.expm1(value):,.2f}"
    if name in ("receiver_prior_tx_count", "sender_prior_tx_count"):
        return f"{np.expm1(value):.0f}"
    if name.startswith("type_") or name in ("receiver_is_merchant", "sender_drained", "receiver_zero_both"):
        return "yes" if value >= 0.5 else "no"
    return f"{value:.3g}"


# ---------------------------------------------------------------------------------------------- SHAP
def shap_attribution(model: Any, algorithm: str, X: np.ndarray) -> tuple[np.ndarray, float, str]:
    """Exact SHAP values for tree models and a linear model. Returns (values [n, d], base value, output space)."""
    import shap

    if algorithm == "XGBoost":
        ex = shap.TreeExplainer(model)
        return np.asarray(ex.shap_values(X), dtype="float64"), float(np.ravel(ex.expected_value)[0]), "log-odds"
    if algorithm == "RandomForest":
        ex = shap.TreeExplainer(model)
        vals = ex.shap_values(X, check_additivity=False)
        arr = np.asarray(vals)
        arr = arr[1] if isinstance(vals, list) else (arr[..., 1] if arr.ndim == 3 else arr)
        return arr.astype("float64"), float(np.ravel(ex.expected_value)[-1]), "probability"
    if (
        algorithm == "LogisticRegression"
    ):  # Pipeline(scaler, clf): attribute in the scaled space, baseline = training mean
        scaler, clf = model.named_steps["scale"], model.named_steps["clf"]
        Z = scaler.transform(X)
        ex = shap.LinearExplainer(clf, np.zeros((1, Z.shape[1])))
        return np.asarray(ex.shap_values(Z), dtype="float64"), float(np.ravel(ex.expected_value)[0]), "log-odds"
    raise ValueError(f"SHAP is not used for {algorithm}")


def top_features(values: np.ndarray, names: list[str], k: int = 5) -> list[tuple[str, float]]:
    order = np.argsort(-np.abs(values))[:k]
    return [(names[i], float(values[i])) for i in order]


# ---------------------------------------------------------------------------------------------- LIME
def lime_attribution(
    score_fn, background: np.ndarray, x: np.ndarray, names: list[str], *, seed: int, num_samples: int = 2000, k: int = 8
) -> list[tuple[str, float, str]]:  # noqa: ANN001
    """Local linear surrogate (LIME) of `score_fn` around x. Returns [(feature, weight, rule)] by |weight|.
    LIME samples randomly, so results vary with the seed; callers report stability."""
    from lime.lime_tabular import LimeTabularExplainer

    explainer = LimeTabularExplainer(
        background, feature_names=names, mode="regression", discretize_continuous=True, random_state=seed
    )
    exp = explainer.explain_instance(x, score_fn, num_features=k, num_samples=num_samples)
    rules = dict(zip([names[i] for i, _ in exp.local_exp[1]], [r for r, _ in exp.as_list(label=1)], strict=False))
    weights = {names[i]: w for i, w in exp.local_exp[1]}
    return [(f, float(w), rules.get(f, "")) for f, w in sorted(weights.items(), key=lambda kv: -abs(kv[1]))]


# ---------------------------------------------------------------------------------------------- evaluation
def topk_jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if sa | sb else 1.0


def deletion_drop(
    score_fn, X: np.ndarray, attributions: np.ndarray, baseline: np.ndarray, k: int, rng: np.random.Generator
) -> tuple[float, float]:  # noqa: ANN001
    """Fidelity (deletion test): replace each row's k most-attributed features by the baseline and measure the mean
    score drop; compare with replacing k random features. A faithful explanation drops the score more than random."""
    base_scores = score_fn(X)
    top, rand = X.copy(), X.copy()
    for i in range(len(X)):
        idx = np.argsort(-np.abs(attributions[i]))[:k]
        top[i, idx] = baseline[idx]
        ridx = rng.choice(X.shape[1], size=k, replace=False)
        rand[i, ridx] = baseline[ridx]
    return float(np.mean(base_scores - score_fn(top))), float(np.mean(base_scores - score_fn(rand)))
