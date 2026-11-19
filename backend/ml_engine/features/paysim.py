"""PaySim feature engineering. Every feature uses only the row itself and data from STRICTLY EARLIER steps.

Feature sets (leakage register item 3 — balance fields are evaluated separately):
- `core`:    type, amount, merchant receiver flag, causal receiver/sender history. No balance fields.
- `balance`: the balance-derived features (sender/receiver balances, accounting errors, drained flags).
`step` itself is deliberately NOT a feature (simulator artefact, see docs/19).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TYPES = ["CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"]

CORE_FEATURES = [
    *[f"type_{t}" for t in TYPES],
    "log_amount",
    "receiver_is_merchant",
    "receiver_prior_tx_count",
    "receiver_prior_amount_log",
    "sender_prior_tx_count",
]
BALANCE_FEATURES = [
    "sender_balance_before_log",
    "sender_balance_after_log",
    "receiver_balance_before_log",
    "receiver_balance_after_log",
    "sender_error",
    "receiver_error",
    "sender_drained",
    "amount_to_sender_balance",
    "receiver_zero_both",
]
FEATURE_SETS = {"core": CORE_FEATURES, "core+balance": CORE_FEATURES + BALANCE_FEATURES}


def _signed_log(x: pd.Series) -> pd.Series:
    return np.sign(x) * np.log1p(np.abs(x))


def prior_history(df: pd.DataFrame, key: str) -> tuple[pd.Series, pd.Series]:
    """Per row: number of transactions and total amount for `key` in steps strictly before the row's step."""
    g = df.groupby([key, "step"], sort=True, observed=True)["amount"].agg(n="size", total="sum").reset_index()
    g["prior_n"] = g.groupby(key, sort=False)["n"].cumsum() - g["n"]
    g["prior_total"] = g.groupby(key, sort=False)["total"].cumsum() - g["total"]
    merged = df[[key, "step"]].merge(g[[key, "step", "prior_n", "prior_total"]], on=[key, "step"], how="left")
    return merged["prior_n"].set_axis(df.index), merged["prior_total"].set_axis(df.index)


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Return a feature frame aligned with `df` (cleaned PaySim, any row order). Pure function."""
    out = pd.DataFrame(index=df.index)
    for t in TYPES:
        out[f"type_{t}"] = (df["type"].astype(str) == t).astype("int8")
    out["log_amount"] = np.log1p(df["amount"])
    out["receiver_is_merchant"] = df["receiver"].str.startswith("M").astype("int8")
    r_n, r_total = prior_history(df, "receiver")
    s_n, _ = prior_history(df, "sender")
    out["receiver_prior_tx_count"] = np.log1p(r_n)
    out["receiver_prior_amount_log"] = np.log1p(r_total)
    out["sender_prior_tx_count"] = np.log1p(s_n)

    sb, sa = df["sender_balance_before"], df["sender_balance_after"]
    rb, ra = df["receiver_balance_before"], df["receiver_balance_after"]
    out["sender_balance_before_log"] = np.log1p(sb)
    out["sender_balance_after_log"] = np.log1p(sa)
    out["receiver_balance_before_log"] = np.log1p(rb)
    out["receiver_balance_after_log"] = np.log1p(ra)
    out["sender_error"] = _signed_log(sb - df["amount"] - sa)
    out["receiver_error"] = _signed_log(rb + df["amount"] - ra)
    out["sender_drained"] = ((sa == 0) & (sb > 0)).astype("int8")
    out["amount_to_sender_balance"] = np.minimum(df["amount"] / (sb + 1.0), 10.0)
    out["receiver_zero_both"] = ((rb == 0) & (ra == 0)).astype("int8")
    return out.astype("float32")
