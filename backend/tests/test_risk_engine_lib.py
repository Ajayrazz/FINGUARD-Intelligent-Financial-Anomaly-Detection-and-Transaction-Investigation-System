"""Risk engine: normalisation, config validation, and every missing-signal combination under every policy."""

import itertools

import pytest

from risk_engine_lib import COMPONENTS, DEFAULT_THRESHOLDS, DEFAULT_WEIGHTS
from risk_engine_lib import engine as e

W, T = dict(DEFAULT_WEIGHTS), dict(DEFAULT_THRESHOLDS)


def comps(**values):
    """values: component -> score; omitted components are unavailable."""
    return {c: (e.available(values[c]) if c in values else e.unavailable("not computed")) for c in COMPONENTS}


def test_default_config_is_valid_and_bad_configs_are_rejected():
    e.validate_config(W, T, "renormalize", 0.5)
    with pytest.raises(e.ConfigError, match="sum to 1"):
        e.validate_config({**W, "A": 0.5}, T, "renormalize", 0.5)
    with pytest.raises(e.ConfigError, match="exactly"):
        e.validate_config({k: v for k, v in W.items() if k != "H"}, T, "renormalize", 0.5)
    with pytest.raises(e.ConfigError, match=">= 0"):
        e.validate_config({**W, "A": -0.05, "B": 0.30}, T, "renormalize", 0.5)
    for bad in (
        {"medium": 60, "high": 30, "critical": 80},
        {"medium": 30, "high": 60, "critical": 120},
        {"medium": 0, "high": 60, "critical": 80},
        {"medium": 30, "high": 30, "critical": 80},
    ):
        with pytest.raises(e.ConfigError, match="thresholds"):
            e.validate_config(W, bad, "renormalize", 0.5)
    with pytest.raises(e.ConfigError):
        e.validate_config(W, T, "guess", 0.5)
    with pytest.raises(e.ConfigError):
        e.validate_config(W, T, "renormalize", 1.5)


def test_full_signal_formula_matches_the_documented_weights():
    r = e.combine(comps(A=80, B=60, G=40, F=20, D=10, H=0), W, T)
    assert r["overall_score"] == pytest.approx(0.25 * 80 + 0.20 * 60 + 0.20 * 40 + 0.15 * 20 + 0.10 * 10 + 0)  # 44.0
    assert r["weight_coverage"] == 1.0 and r["category"] == "medium" and not r["low_coverage"]
    assert sum(c["contribution"] for c in r["components"].values()) == pytest.approx(r["overall_score"])


@pytest.mark.parametrize("policy", ["renormalize", "neutral_prior", "strict"])
def test_every_missing_signal_combination_is_handled(policy):
    """All 2^6 = 64 availability patterns: no crash, coverage is exact, unavailable is never a silent zero."""
    priors = {c: 10.0 for c in COMPONENTS}
    for mask in itertools.product([True, False], repeat=6):
        present = {c: 70.0 for c, on in zip(COMPONENTS, mask, strict=True) if on}
        r = e.combine(comps(**present), W, T, policy=policy, priors=priors)
        assert r["weight_coverage"] == pytest.approx(sum(W[c] for c in present))
        assert r["low_coverage"] == (r["weight_coverage"] < 0.5)
        n_present = len(present)
        if policy == "strict" and n_present < 6:
            assert r["overall_score"] is None and r["category"] == "unscored"
        elif policy == "renormalize":
            if n_present == 0:
                assert r["overall_score"] is None and r["category"] == "unscored"
            else:
                assert r["overall_score"] == pytest.approx(70.0)  # all present values are 70: renormalised mean is 70
        elif policy == "neutral_prior" and n_present < 6:
            expected = (sum(W[c] * 70 for c in present) + sum(W[c] * 10 for c in COMPONENTS if c not in present)) / 1.0
            assert r["overall_score"] == pytest.approx(expected)
        for c in COMPONENTS:
            comp = r["components"][c]
            if c not in present and r["overall_score"] is not None and policy != "neutral_prior":
                assert comp["contribution"] is None and comp["available"] is False  # excluded, not a zero
            if c in present and r["overall_score"] is not None:
                assert comp["contribution"] is not None


def test_renormalize_does_not_treat_missing_as_zero():
    only_a = e.combine(comps(A=90), W, T)
    assert only_a["overall_score"] == pytest.approx(90.0) and only_a["weight_coverage"] == pytest.approx(0.25)
    zero_b = e.combine(comps(A=90, B=0, G=0, F=0, D=0, H=0), W, T)
    assert zero_b["overall_score"] == pytest.approx(22.5)  # measured zeros DO count, unlike missing signals


def test_low_coverage_cannot_auto_escalate_to_critical():
    r = e.combine(comps(A=100), W, T)  # coverage 0.25 < 0.5, score 100 would be critical
    assert r["low_coverage"] and r["category"] == "high" and r["capped"] is True
    full = e.combine(comps(A=100, B=100, G=100, F=100, D=100, H=100), W, T)
    assert full["category"] == "critical" and full["capped"] is False
    lenient = e.combine(comps(A=100), W, T, min_coverage=0.2)
    assert lenient["category"] == "critical" and lenient["capped"] is False


def test_category_boundaries_are_inclusive_at_the_lower_edge():
    assert [e.categorise(s, T) for s in (0, 29.99, 30, 59.99, 60, 79.99, 80, 100)] == [
        "low",
        "low",
        "medium",
        "medium",
        "high",
        "high",
        "critical",
        "critical",
    ]


def test_zero_weight_component_may_be_missing_even_under_strict():
    w = {**W, "H": 0.0, "A": 0.35}
    r = e.combine(comps(A=50, B=50, G=50, F=50, D=50), w, T, policy="strict")
    assert r["overall_score"] == pytest.approx(50.0)  # H has no weight, so its absence does not block a strict score


def test_model_score_normalisation_is_monotone_with_threshold_at_50():
    thr, low, high = 0.2, 0.0, 0.9
    vals = [e.normalise_model_score(s, thr, low, high) for s in (0.0, 0.1, 0.2, 0.5, 0.9, 5.0)]
    assert vals == sorted(vals) and vals[0] == 0.0 and vals[2] == 50.0 and vals[4] == 100.0 and vals[5] == 100.0
    assert e.normalise_model_score(-1.0, thr, low, high) == 0.0


def test_behaviour_split_counts_burst_once_and_reports_cold_start():
    scored = {"status": "scored", "deviation_score": 83.9, "components": {
        "amount": {"available": True, "score": 100.0}, "burst": {"available": True, "score": 86.0, "detail": {"k": 5}},
        "spend_jump": {"available": True, "score": 80.0}, "new_counterparty": {"available": True, "score": 0.0},
        "hour": {"available": False, "score": None, "reason": "x"}}}  # fmt: skip
    b, f = e.behaviour_components(scored)
    assert f["available"] and f["value"] == 86.0
    assert b["available"] and b["value"] == pytest.approx(0.5 * 100 + 0.5 * (0.30 * 100 + 0.20 * 80 + 0.15 * 0) / 0.65)
    assert "burst" not in b["source"]["components"]
    cold_b, cold_f = e.behaviour_components({"status": "unavailable_cold_start", "components": {}})
    assert not cold_b["available"] and not cold_f["available"] and "cold start" in cold_b["reason"]
    none_b, _ = e.behaviour_components(None)
    assert not none_b["available"]
