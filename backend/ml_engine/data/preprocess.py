"""Cleaning: raw frames -> typed, snake_case frames. Pure functions; the raw frame is never modified."""

from __future__ import annotations

import pandas as pd

PAYSIM_RENAME = {
    "nameOrig": "sender",
    "nameDest": "receiver",
    "oldbalanceOrg": "sender_balance_before",
    "newbalanceOrig": "sender_balance_after",
    "oldbalanceDest": "receiver_balance_before",
    "newbalanceDest": "receiver_balance_after",
    "isFraud": "is_fraud",
    "isFlaggedFraud": "is_flagged_fraud",
}


def clean_paysim(raw: pd.DataFrame, *, drop_duplicates: bool = False) -> tuple[pd.DataFrame, dict[str, int]]:
    """Return (cleaned, stats).

    - `row_id` is the 0-based position in the raw file: a stable key back to the source.
    - Types are tightened (smaller ints, categorical type) with no loss of information.
    - PaySim has no transaction id, so identical rows may be legitimate repeats: duplicates are kept
      unless `drop_duplicates` is set (default False, see docs/19).
    - Nothing is imputed (the raw file has no missing values) and no outliers are removed.
    """
    df = raw.rename(columns=PAYSIM_RENAME).copy()
    df.insert(0, "row_id", range(len(df)))
    n_before = len(df)
    if drop_duplicates:
        df = df.drop_duplicates(subset=[c for c in df.columns if c != "row_id"], keep="first")
    df["step"] = df["step"].astype("int16")
    df["type"] = df["type"].astype("category")
    df["is_fraud"] = df["is_fraud"].astype("int8")
    df["is_flagged_fraud"] = df["is_flagged_fraud"].astype("int8")
    df = df.sort_values(["step", "row_id"], kind="stable").reset_index(drop=True)
    return df, {"rows_in": n_before, "rows_out": len(df), "duplicates_dropped": n_before - len(df)}


def clean_creditcard(raw: pd.DataFrame, *, drop_duplicates: bool = True) -> tuple[pd.DataFrame, dict[str, int]]:
    """Return (cleaned, stats).

    Exact duplicate rows are dropped (keeping the first): a duplicate falling on both sides of a split would
    leak a training example into evaluation. The dropped count is recorded and reported.
    """
    df = raw.copy()
    df.insert(0, "row_id", range(len(df)))
    n_before = len(df)
    if drop_duplicates:
        df = df.drop_duplicates(subset=[c for c in df.columns if c != "row_id"], keep="first")
    df = df.rename(columns={"Time": "time", "Amount": "amount", "Class": "is_fraud"})
    df["is_fraud"] = df["is_fraud"].astype("int8")
    df = df.sort_values(["time", "row_id"], kind="stable").reset_index(drop=True)
    return df, {"rows_in": n_before, "rows_out": len(df), "duplicates_dropped": n_before - len(df)}
