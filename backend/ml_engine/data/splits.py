"""Chronological train/validation/test splitting and leakage checks."""

from __future__ import annotations

from typing import Any

import pandas as pd


class LeakageError(Exception):
    """A split violates a time-ordering or disjointness requirement."""


def chronological_split(
    df: pd.DataFrame,
    time_col: str,
    fractions: tuple[float, float, float] = (0.70, 0.15, 0.15),
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """Split by time so that train < validation < test strictly.

    Boundaries are chosen on cumulative row share and snapped to a distinct time value, so rows that share a
    timestamp (e.g. a PaySim hour) never straddle two splits. Returns (splits, boundaries).
    """
    if abs(sum(fractions) - 1.0) > 1e-9:
        raise ValueError("fractions must sum to 1")
    counts = df.groupby(time_col, sort=True).size()
    cumulative = counts.cumsum() / len(df)
    t_train_end = cumulative[cumulative >= fractions[0]].index[0]
    t_val_end = cumulative[cumulative >= fractions[0] + fractions[1]].index[0]
    t = df[time_col]
    splits = {
        "train": df[t <= t_train_end],
        "validation": df[(t > t_train_end) & (t <= t_val_end)],
        "test": df[t > t_val_end],
    }
    boundaries = {
        "time_col": time_col,
        "train_end": _scalar(t_train_end),
        "validation_end": _scalar(t_val_end),
        "requested_fractions": list(fractions),
        "actual_fractions": [len(v) / len(df) for v in splits.values()],
    }
    return splits, boundaries


def _scalar(v: Any) -> Any:
    return v.item() if hasattr(v, "item") else v


def verify_split(splits: dict[str, pd.DataFrame], time_col: str, label_col: str, *, total_rows: int) -> dict[str, Any]:
    """Raise LeakageError on any violation; return per-split summary. Checks:
    complete + disjoint (by row_id), strict time ordering, labels present in every split."""
    train, val, test = splits["train"], splits["validation"], splits["test"]
    ids = [set(s["row_id"]) for s in (train, val, test)]
    if sum(len(i) for i in ids) != total_rows:
        raise LeakageError("splits do not cover every row exactly once")
    if (ids[0] & ids[1]) or (ids[0] & ids[2]) or (ids[1] & ids[2]):
        raise LeakageError("splits share rows")
    if not train[time_col].max() < val[time_col].min():
        raise LeakageError("train overlaps validation in time")
    if not val[time_col].max() < test[time_col].min():
        raise LeakageError("validation overlaps test in time")
    summary: dict[str, Any] = {}
    for name, part in splits.items():
        positives = int(part[label_col].sum())
        if positives == 0:
            raise LeakageError(f"{name} split has no positive examples")
        summary[name] = {
            "rows": len(part),
            "positives": positives,
            "positive_rate": positives / len(part),
            "time_min": _scalar(part[time_col].min()),
            "time_max": _scalar(part[time_col].max()),
        }
    return summary


def account_overlap(splits: dict[str, pd.DataFrame], col: str) -> dict[str, float]:
    """Share of later-split accounts already seen in earlier splits (cold-start vs seen accounts)."""
    train_ids = set(splits["train"][col])
    seen_before_val = train_ids
    seen_before_test = train_ids | set(splits["validation"][col])
    val_ids = splits["validation"][col]
    test_ids = splits["test"][col]
    return {
        "validation_rows_with_account_seen_in_train": float(val_ids.isin(seen_before_val).mean()),
        "test_rows_with_account_seen_before": float(test_ids.isin(seen_before_test).mean()),
    }
