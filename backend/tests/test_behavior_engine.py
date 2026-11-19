"""Behavioral engine: robust scoring, the 5 x 40,000 in 10 minutes scenario, cold start, no future leakage."""

import numpy as np
import pytest

from apps.behavior import engine

DAY = 86400.0
T0 = 1_767_225_600.0  # 2026-01-01T00:00:00Z


def regular_history(days=60, per_week=3, amount=800.0, hour=10, seed=0):
    """A steady customer: a few ~800 payments per week around 10:00 UTC to a small set of merchants."""
    rng = np.random.default_rng(seed)
    times, amounts, receivers = [], [], []
    for d in range(days):
        if d % 7 in (0, 2, 4)[:per_week]:
            times.append(T0 + d * DAY + hour * 3600 + rng.integers(0, 3000))
            amounts.append(amount + rng.normal(0, 60))
            receivers.append(f"M{rng.integers(0, 4)}")
    return np.array(times), np.array(amounts), receivers


def test_scenario_five_payments_of_40000_in_ten_minutes_scores_high_with_breakdown():
    times, amounts, receivers = regular_history()
    t = T0 + 61 * DAY + 10 * 3600  # day 61, 10:00 (the customer's usual hour)
    hist_t, hist_a, hist_r = list(times), list(amounts), list(receivers)
    results = []
    for i in range(5):
        ti = t + i * 120.0  # one every 2 minutes
        r = engine.score_transaction(ti, 40_000.0, "NEW-PAYEE", np.array(hist_t), np.array(hist_a), hist_r)
        results.append(r)
        hist_t.append(ti), hist_a.append(40_000.0), hist_r.append("NEW-PAYEE")
    first, last = results[0], results[-1]
    assert first["status"] == "scored" and last["status"] == "scored"
    assert first["deviation_score"] >= 70  # a single 40,000 payment against an ~800 baseline is already extreme
    scores = [r["deviation_score"] for r in results]
    assert scores == sorted(scores) and len(set(scores)) == 5  # the burst makes each further payment look worse
    assert min(scores) >= 75 and scores[-1] >= 80  # last payment reaches the 80-100 "Critical" band
    comps = last["components"]
    assert comps["amount"]["score"] > 95 and comps["burst"]["score"] > 80 and comps["spend_jump"]["score"] > 80
    assert comps["burst"]["detail"]["transactions_in_window"] == 5
    assert comps["new_counterparty"]["detail"]["seen_before"] is True  # 4th/5th payment: payee seen in this burst
    assert results[0]["components"]["new_counterparty"]["detail"]["seen_before"] is False
    assert comps["hour"]["score"] < 20  # usual hour: timing is NOT what is unusual
    assert last["coverage"] == 1.0


def test_normal_transaction_scores_low():
    times, amounts, receivers = regular_history()
    t = T0 + 61 * DAY + 10 * 3600
    r = engine.score_transaction(t, 790.0, receivers[0], times, amounts, receivers)
    assert r["status"] == "scored" and r["deviation_score"] < 20


def test_unusual_hour_is_detected_and_only_with_enough_history():
    times, amounts, receivers = regular_history()
    night = T0 + 61 * DAY + 3 * 3600
    r = engine.score_transaction(night, 800.0, receivers[0], times, amounts, receivers)
    assert r["components"]["hour"]["available"] and r["components"]["hour"]["score"] > 40
    short = engine.score_transaction(night, 800.0, "M1", times[:8], amounts[:8], receivers[:8])
    assert (
        short["components"]["hour"]["available"] is False
        and "prior transactions" in short["components"]["hour"]["reason"]
    )


def test_cold_start_is_explicitly_unavailable_not_zero():
    r = engine.score_transaction(T0, 100.0, "M1", np.array([T0 - 10, T0 - 5]), np.array([5.0, 6.0]), ["M1", "M1"])
    assert r["status"] == "unavailable_cold_start" and r["deviation_score"] is None and r["coverage"] == 0.0
    assert all(c["available"] is False and "cold start" in c["reason"] for c in r["components"].values())


def test_identical_historical_amounts_do_not_explode_the_z_score():
    times = T0 + np.arange(10) * DAY
    amounts = np.full(10, 100.0)  # MAD = 0

    def amount_score(a):
        r = engine.score_transaction(T0 + 11 * DAY, a, "M1", times, amounts, ["M1"] * 10)
        assert np.isfinite(r["deviation_score"])
        return r["components"]["amount"]["score"]

    # the scale floor (10% of the median) keeps small departures from a constant amount moderate, not infinite
    assert amount_score(100.0) == 0.0 and amount_score(105.0) < 25 and amount_score(120.0) < 60
    assert amount_score(1000.0) > 95


def test_missing_receiver_and_short_span_mark_components_unavailable():
    times = T0 + np.arange(6) * 3600.0
    r = engine.score_transaction(T0 + 7 * 3600.0, 50.0, None, times, np.full(6, 50.0), [None] * 6)
    assert r["components"]["new_counterparty"]["available"] is False
    assert r["components"]["spend_jump"]["available"] is False
    assert r["coverage"] < 1.0 and r["status"] == "scored"


def test_future_history_is_never_used_by_construction_score_depends_only_on_arguments():
    times, amounts, receivers = regular_history()
    t = T0 + 40 * DAY + 10 * 3600
    keep = times < t
    before = engine.score_transaction(
        t, 5000.0, "M1", times[keep], amounts[keep], [r for r, k in zip(receivers, keep, strict=True) if k]
    )
    # perturb everything after t: the caller passes only prior history, so the result is identical
    mutated = amounts.copy()
    mutated[~keep] *= 100
    after = engine.score_transaction(
        t, 5000.0, "M1", times[keep], mutated[keep], [r for r, k in zip(receivers, keep, strict=True) if k]
    )
    assert before == after


def test_score_is_monotone_in_amount():
    times, amounts, receivers = regular_history()
    t = T0 + 61 * DAY + 10 * 3600
    scores = [
        engine.score_transaction(t, a, "M1", times, amounts, receivers)["deviation_score"]
        for a in (500, 900, 3000, 40000)
    ]
    assert scores == sorted(scores) and scores[-1] > scores[0]


def test_profile_statistics_and_aggregates():
    times, amounts, receivers = regular_history()
    p = engine.build_profile(times, amounts, receivers, [], as_of=T0 + 61 * DAY)
    assert p["sufficient_history"] and p["tx_count"] == len(times)
    assert 700 < p["median_amount"] < 900 and p["p95_amount"] >= p["median_amount"]
    assert sum(p["hour_histogram"]) == len(times) and p["hour_histogram"][10] == len(times)
    assert p["merchant_category_dist"] is None  # no categories supplied => explicitly unavailable
    assert sum(d["count"] for d in p["aggregates"]["daily"]) == len(times)
    assert sum(m["count"] for m in p["aggregates"]["monthly"]) == len(times)
    assert p["unique_counterparties"] <= 4


def test_empty_profile_reports_nulls_not_zeros():
    p = engine.build_profile(np.array([]), np.array([]), [], [], as_of=T0)
    assert p["tx_count"] == 0 and p["avg_amount"] is None and p["sufficient_history"] is False


@pytest.mark.parametrize("g", ["day", "week", "month"])
def test_aggregate_fills_gaps(g):
    t = np.array([T0, T0 + 5 * DAY, T0 + 40 * DAY])
    rows = engine.aggregate(t, np.array([1.0, 2.0, 3.0]), g)
    assert sum(r["count"] for r in rows) == 3 and sum(r["total"] for r in rows) == 6.0
    if g == "day":
        assert len(rows) == 41


def test_profile_reports_merchant_category_distribution_when_present():
    times, amounts, receivers = regular_history(days=21)
    cats = ["grocery" if i % 3 else "fuel" for i in range(len(times))]
    p = engine.build_profile(times, amounts, receivers, cats, as_of=T0 + 22 * DAY)
    assert p["merchant_category_dist"] == {"grocery": cats.count("grocery"), "fuel": cats.count("fuel")}
