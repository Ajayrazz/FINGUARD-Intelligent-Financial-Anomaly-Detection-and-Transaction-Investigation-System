"""Behavioral profiling and deviation scoring. Pure functions (numpy/pandas only, no Django, no I/O).

Everything is *as-of*: callers pass only the history that precedes the transaction in (occurred_at, id) order, so
the score of a transaction can never depend on its future (docs/08 leakage item 2; perturbation-tested).
Times are UTC epoch seconds. Unavailable signals are reported explicitly with a reason, never as 0.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

CONFIG: dict[str, Any] = {
    "version": "b1",
    "window_days": 90,  # baseline window
    "max_history": 500,  # scoring uses at most the most recent N prior transactions in the window
    "min_history": 5,  # fewer prior transactions => cold start, no score
    "min_history_hour": 20,  # hour-of-day rarity needs a real histogram
    "min_span_days_jump": 14,  # spend-jump needs a baseline of at least two weeks
    "burst_minutes": 10,
    "tau": {"amount": 3.0, "burst": 2.0, "hour": 2.0, "spend_jump": 2.0},
    "new_counterparty_score": 50.0,
    "weights": {"amount": 0.30, "burst": 0.25, "spend_jump": 0.20, "new_counterparty": 0.15, "hour": 0.10},
    "blend_max": 0.5,  # overall = blend*max(component) + (1-blend)*weighted mean of available components
}
COMPONENTS = list(CONFIG["weights"])


def _to_score(z: float, tau: float) -> float:
    """Monotone map of a non-negative deviation to 0-100: 100*(1-exp(-z/tau))."""
    return float(100.0 * (1.0 - math.exp(-max(z, 0.0) / tau)))


def _unavailable(reason: str) -> dict[str, Any]:
    return {"available": False, "score": None, "reason": reason}


def score_transaction(
    t: float, amount: float, receiver: str | None, times: np.ndarray, amounts: np.ndarray, receivers: list[str | None],
    cfg: dict[str, Any] = CONFIG,
) -> dict[str, Any]:  # fmt: skip
    """Deviation of one transaction (time `t`, `amount`, `receiver`) from the account's prior history.

    `times` (sorted ascending), `amounts` and `receivers` describe prior transactions only.
    """
    n = len(times)
    if n < cfg["min_history"]:
        reason = f"cold start: {n} prior transactions, {cfg['min_history']} needed"
        return {
            "status": "unavailable_cold_start", "deviation_score": None, "coverage": 0.0, "history_count": n,
            "components": {c: _unavailable(reason) for c in COMPONENTS},
        }  # fmt: skip
    comps: dict[str, dict[str, Any]] = {}
    tau = cfg["tau"]

    median = float(np.median(amounts))
    mad = float(np.median(np.abs(amounts - median)))
    scale = max(1.4826 * mad, 0.1 * median, 1.0)  # floor stops MAD=0 (identical amounts) from exploding the z-score
    z_amount = max((amount - median) / scale, 0.0)
    comps["amount"] = {
        "available": True, "score": _to_score(z_amount, tau["amount"]), "value": z_amount,
        "detail": {"amount": amount, "median": median, "mad": mad},
    }  # fmt: skip

    window = cfg["burst_minutes"] * 60.0
    k = 1 + int((times > t - window).sum())  # this transaction plus prior ones inside the burst window
    expected = n * window / max(t - float(times[0]), window)  # typical prior transactions per window
    z_burst = max(k - 1, 0) / math.sqrt(1.0 + expected)
    comps["burst"] = {
        "available": True, "score": _to_score(z_burst, tau["burst"]), "value": z_burst,
        "detail": {"transactions_in_window": k, "window_minutes": cfg["burst_minutes"], "expected_in_window": expected},
    }  # fmt: skip

    if n >= cfg["min_history_hour"]:
        hours = ((times % 86400) // 3600).astype(int)
        counts = np.bincount(hours, minlength=24)
        h = int((t % 86400) // 3600)
        surprisal = -math.log2((counts[h] + 1) / (n + 24))
        z_hour = max(surprisal - math.log2(24), 0.0)  # bits of surprise beyond a uniform hour
        comps["hour"] = {
            "available": True, "score": _to_score(z_hour, tau["hour"]), "value": z_hour,
            "detail": {"hour_utc": h, "prior_in_hour": int(counts[h])},
        }  # fmt: skip
    else:
        comps["hour"] = _unavailable(f"needs {cfg['min_history_hour']} prior transactions for an hour-of-day profile")

    if receiver is None:
        comps["new_counterparty"] = _unavailable("transaction has no receiver")
    else:
        is_new = receiver not in set(receivers)
        comps["new_counterparty"] = {
            "available": True, "score": cfg["new_counterparty_score"] if is_new else 0.0, "value": float(is_new),
            "detail": {"receiver": receiver, "seen_before": not is_new},
        }  # fmt: skip

    span_days = (t - float(times[0])) / 86400.0
    if span_days < cfg["min_span_days_jump"]:
        comps["spend_jump"] = _unavailable(f"history spans {span_days:.1f} days, {cfg['min_span_days_jump']} needed")
    else:
        last7 = amount + float(amounts[times > t - 7 * 86400.0].sum())
        weekly_baseline = float(amounts.sum()) / (span_days / 7.0)
        ratio = last7 / max(weekly_baseline, 1.0)
        z_jump = math.log2(max(ratio, 1.0))
        comps["spend_jump"] = {
            "available": True, "score": _to_score(z_jump, tau["spend_jump"]), "value": z_jump,
            "detail": {"last_7d_total": last7, "baseline_weekly_total": weekly_baseline, "ratio": ratio},
        }  # fmt: skip

    w = cfg["weights"]
    avail = [c for c, v in comps.items() if v["available"]]
    wsum = sum(w[c] for c in avail)
    wmean = sum(w[c] * comps[c]["score"] for c in avail) / wsum
    top = max(comps[c]["score"] for c in avail)
    overall = cfg["blend_max"] * top + (1 - cfg["blend_max"]) * wmean
    return {
        "status": "scored", "deviation_score": round(overall, 2), "coverage": round(wsum / sum(w.values()), 3),
        "history_count": n, "components": comps,
    }  # fmt: skip


def aggregate(times: np.ndarray, amounts: np.ndarray, granularity: str) -> list[dict[str, Any]]:
    """Counts and totals per UTC day/week(Monday)/month, with empty periods filled so charts have no gaps."""
    if len(times) == 0:
        return []
    idx = pd.to_datetime(times, unit="s", utc=True).tz_localize(None)
    s = pd.Series(amounts, index=idx)
    freq = {"day": "D", "week": "W-MON", "month": "MS"}[granularity]
    if granularity == "week":
        g = s.resample("W-MON", label="left", closed="left").agg(["size", "sum"])
    else:
        g = s.resample(freq).agg(["size", "sum"])
    fmt = "%Y-%m" if granularity == "month" else "%Y-%m-%d"
    return [
        {"period": p.strftime(fmt), "count": int(r["size"]), "total": float(r["sum"])} for p, r in g.iterrows()
    ]  # fmt: skip


def build_profile(
    times: np.ndarray, amounts: np.ndarray, counterparties: list[str | None], categories: list[str],
    as_of: float, cfg: dict[str, Any] = CONFIG,
) -> dict[str, Any]:  # fmt: skip
    """Descriptive profile of the transactions in the window ending at `as_of` (inputs are already filtered)."""
    n = len(times)
    out: dict[str, Any] = {
        "profile_version": cfg["version"],
        "tx_count": n,
        "sufficient_history": n >= cfg["min_history"],
    }
    if n == 0:
        return {**out, "avg_amount": None, "median_amount": None, "std_amount": None, "p95_amount": None,
                "mad_amount": None, "tx_per_day": 0.0, "unique_counterparties": 0, "hour_histogram": [0] * 24,
                "merchant_category_dist": None, "aggregates": {"daily": [], "weekly": [], "monthly": []},
                "recent_7d": {"count": 0, "total": 0.0, "avg": None}}  # fmt: skip
    median = float(np.median(amounts))
    span_days = max((as_of - float(times[0])) / 86400.0, 1.0)
    cats = [c for c in categories if c]
    recent = amounts[times > as_of - 7 * 86400.0]
    return {
        **out,
        "avg_amount": float(amounts.mean()), "median_amount": median,
        "std_amount": float(amounts.std(ddof=1)) if n > 1 else 0.0,
        "p95_amount": float(np.percentile(amounts, 95)),
        "mad_amount": float(np.median(np.abs(amounts - median))),
        "tx_per_day": n / span_days,
        "unique_counterparties": len({c for c in counterparties if c}),
        "hour_histogram": np.bincount(((times % 86400) // 3600).astype(int), minlength=24).tolist(),
        "merchant_category_dist": (pd.Series(cats).value_counts().to_dict() if cats else None),  # None = not available
        "aggregates": {
            "daily": aggregate(times, amounts, "day")[-90:],
            "weekly": aggregate(times, amounts, "week")[-26:],
            "monthly": aggregate(times, amounts, "month")[-24:],
        },
        "recent_7d": {
            "count": int(len(recent)), "total": float(recent.sum()),
            "avg": float(recent.mean()) if len(recent) else None,
        },
    }  # fmt: skip
