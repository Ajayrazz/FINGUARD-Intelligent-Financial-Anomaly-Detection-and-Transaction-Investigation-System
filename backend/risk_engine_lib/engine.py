"""Component normalisation, combination under a missing-signal policy, and categories."""

from __future__ import annotations

import math
from typing import Any

from . import ALGORITHM_VERSION, COMPONENTS, DEFAULT_MIN_COVERAGE, POLICIES

Component = dict[str, Any]  # {"available": bool, "value": float | None, "reason": str, "source": dict}


def unavailable(reason: str, source: dict[str, Any] | None = None) -> Component:
    return {"available": False, "value": None, "reason": reason, "source": source or {}}


def available(value: float, source: dict[str, Any] | None = None) -> Component:
    return {"available": True, "value": float(min(max(value, 0.0), 100.0)), "reason": "", "source": source or {}}


# ------------------------------------------------------------------------------------ validation
class ConfigError(ValueError):
    """Weights or thresholds are invalid."""


def validate_config(weights: dict[str, float], thresholds: dict[str, float], policy: str, min_coverage: float) -> None:
    if set(weights) != set(COMPONENTS):
        raise ConfigError(f"weights must define exactly {list(COMPONENTS)}")
    if any(not isinstance(w, int | float) or w < 0 or not math.isfinite(w) for w in weights.values()):
        raise ConfigError("weights must be finite numbers >= 0")
    if abs(sum(weights.values()) - 1.0) > 1e-6:
        raise ConfigError(f"weights must sum to 1 (they sum to {sum(weights.values()):.6f})")
    if set(thresholds) != {"medium", "high", "critical"}:
        raise ConfigError("thresholds must define medium, high and critical")
    if not (0 < thresholds["medium"] < thresholds["high"] < thresholds["critical"] <= 100):
        raise ConfigError("thresholds must satisfy 0 < medium < high < critical <= 100")
    if policy not in POLICIES:
        raise ConfigError(f"missing_signal_policy must be one of {list(POLICIES)}")
    if not 0.0 <= min_coverage <= 1.0:
        raise ConfigError("min_coverage must be between 0 and 1")


# ------------------------------------------------------------------------------------ normalisation
def normalise_model_score(score: float, threshold: float, low: float, high: float) -> float:
    """Map a raw model score to 0-100 with the model's own alert threshold at 50.

    `low` = minimum seen, `high` = a high quantile (99.9th) of the run's scores. Piecewise linear and monotone, so
    the ranking of transactions is exactly the model's ranking; only the scale is shared across models."""
    if score < threshold:
        span = max(threshold - low, 1e-12)
        return 50.0 * max(score - low, 0.0) / span
    span = max(high - threshold, 1e-12)
    return 50.0 + 50.0 * min((score - threshold) / span, 1.0)


def behaviour_components(
    result: dict[str, Any] | None, cfg_weights: dict[str, float] | None = None
) -> tuple[Component, Component]:
    """Split the stored behavioural components into B (amount, spend_jump, new_counterparty, hour) and F (burst).
    B is recombined with the behaviour engine's own rule (0.5 max + 0.5 weighted mean) *without* burst, so burst is
    counted once, as F."""
    if not result or result.get("status") != "scored":
        reason = (
            "no behavioural analysis for this transaction"
            if not result
            else "cold start: not enough earlier transactions"
        )
        return unavailable(reason), unavailable(reason)
    comps = result["components"]
    w = cfg_weights or {"amount": 0.30, "spend_jump": 0.20, "new_counterparty": 0.15, "hour": 0.10}
    avail = [k for k in w if comps.get(k, {}).get("available")]
    burst = comps.get("burst", {})
    f = (
        available(burst["score"], {"detail": burst.get("detail", {})})
        if burst.get("available")
        else unavailable("burst signal unavailable")
    )
    if not avail:
        return unavailable("no behavioural signal available"), f
    scores = {k: comps[k]["score"] for k in avail}
    wsum = sum(w[k] for k in avail)
    b = 0.5 * max(scores.values()) + 0.5 * sum(w[k] * scores[k] for k in avail) / wsum
    return available(b, {"components": scores, "deviation_score_with_burst": result.get("deviation_score")}), f


# ------------------------------------------------------------------------------------ combination
def categorise(score: float, thresholds: dict[str, float]) -> str:
    if score >= thresholds["critical"]:
        return "critical"
    if score >= thresholds["high"]:
        return "high"
    if score >= thresholds["medium"]:
        return "medium"
    return "low"


def combine(
    components: dict[str, Component],
    weights: dict[str, float],
    thresholds: dict[str, float],
    *,
    policy: str = "renormalize",
    priors: dict[str, float] | None = None,
    min_coverage: float = DEFAULT_MIN_COVERAGE,
) -> dict[str, Any]:
    """Combine components. Returns {overall_score|None, category, weight_coverage, low_coverage, capped, policy,
    components (with weight and contribution), algorithm_version}.

    renormalize  : R = sum(w_i S_i) / sum(w_i) over available components; coverage = sum(w_i available) / sum(w_i)
    neutral_prior: missing components take their prior (population median); coverage still reports what was measured
    strict       : any missing component (with weight > 0) -> no score
    Low coverage (< min_coverage) never auto-escalates to Critical: the category is capped at High and `capped` set."""
    if policy not in POLICIES:
        raise ConfigError(f"unknown policy {policy}")
    priors = priors or {}
    total_w = sum(weights.values()) or 1.0
    measured_w = sum(weights[c] for c in COMPONENTS if components[c]["available"])
    coverage = measured_w / total_w
    out: dict[str, Any] = {
        "algorithm_version": ALGORITHM_VERSION, "policy": policy, "weight_coverage": round(coverage, 6),
        "low_coverage": coverage < min_coverage, "capped": False, "overall_score": None, "category": "unscored",
        "components": {},
    }  # fmt: skip
    used: dict[str, float] = {}
    for c in COMPONENTS:
        comp = components[c]
        if comp["available"]:
            used[c] = comp["value"]
        elif policy == "neutral_prior" and c in priors:
            used[c] = float(priors[c])
    missing_needed = [c for c in COMPONENTS if weights[c] > 0 and not components[c]["available"]]
    if policy == "strict" and missing_needed:
        refuse = True
    else:
        refuse = False
    denom = sum(weights[c] for c in used)
    if refuse or denom <= 0:
        for c in COMPONENTS:
            out["components"][c] = {**components[c], "weight": weights[c], "contribution": None, "imputed": False}
        return out
    score = sum(weights[c] * used[c] for c in used) / denom
    category = categorise(score, thresholds)
    if out["low_coverage"] and category == "critical":
        category, out["capped"] = "high", True
    out["overall_score"], out["category"] = round(score, 4), category
    for c in COMPONENTS:
        imputed = c in used and not components[c]["available"]
        out["components"][c] = {
            **components[c], "weight": weights[c], "imputed": imputed,
            "contribution": round(weights[c] * used[c] / denom, 4) if c in used else None,
        }  # fmt: skip
        if imputed:
            out["components"][c]["value"] = used[c]
    return out
