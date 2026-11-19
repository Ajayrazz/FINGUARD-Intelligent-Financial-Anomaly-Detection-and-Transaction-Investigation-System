"""Schema validation and profiling of the raw datasets. Read-only: never mutates the input frame."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from . import config


class DataValidationError(Exception):
    """Raised when a dataset violates a hard requirement (wrong schema, impossible values)."""


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)  # hard failures: pipeline stops
    warnings: list[str] = field(default_factory=list)  # data quirks worth documenting

    def raise_if_failed(self) -> None:
        if self.errors:
            raise DataValidationError("; ".join(self.errors))


def check_schema(df: pd.DataFrame, expected: dict[str, str]) -> list[str]:
    """Return schema problems: missing/unexpected columns and dtype-kind mismatches."""
    problems: list[str] = []
    missing = [c for c in expected if c not in df.columns]
    extra = [c for c in df.columns if c not in expected]
    if missing:
        problems.append(f"missing columns: {missing}")
    if extra:
        problems.append(f"unexpected columns: {extra}")
    for col, kind in expected.items():
        if col not in df.columns:
            continue
        actual = df[col].dtype
        if kind == "i" and not pd.api.types.is_integer_dtype(actual):
            problems.append(f"{col}: expected integer, got {actual}")
        elif kind == "f" and not pd.api.types.is_float_dtype(actual):
            problems.append(f"{col}: expected float, got {actual}")
        elif kind == "O" and not (pd.api.types.is_object_dtype(actual) or pd.api.types.is_string_dtype(actual)):
            problems.append(f"{col}: expected text, got {actual}")
    return problems


def _class_distribution(labels: pd.Series) -> dict[str, Any]:
    counts = labels.value_counts().to_dict()
    positives = int(counts.get(1, 0))
    total = int(len(labels))
    return {
        "total": total,
        "positives": positives,
        "negatives": total - positives,
        "positive_rate": positives / total if total else 0.0,
        "imbalance_ratio": (total - positives) / positives if positives else None,
    }


def validate_paysim(df: pd.DataFrame) -> ValidationResult:
    res = ValidationResult()
    res.errors += check_schema(df, config.PAYSIM_COLUMNS)
    if res.errors:
        return res
    lo, hi = config.PAYSIM_STEP_RANGE
    if not df["step"].between(lo, hi).all():
        res.errors.append(f"step outside [{lo}, {hi}]")
    unknown = set(df["type"].unique()) - config.PAYSIM_TYPES
    if unknown:
        res.errors.append(f"unknown transaction types: {sorted(unknown)}")
    if (df["amount"] < 0).any():
        res.errors.append("negative amounts present")
    for col in ("isFraud", "isFlaggedFraud"):
        if not set(df[col].unique()) <= {0, 1}:
            res.errors.append(f"{col} is not binary")
    if df.isna().any().any():
        res.warnings.append("missing values present")
    if (df["amount"] == 0).any():
        res.warnings.append(f"{int((df['amount'] == 0).sum())} transactions have amount 0")
    return res


def validate_creditcard(df: pd.DataFrame) -> ValidationResult:
    res = ValidationResult()
    res.errors += check_schema(df, config.CREDITCARD_COLUMNS)
    if res.errors:
        return res
    if (df["Time"] < 0).any():
        res.errors.append("negative Time")
    if (df["Amount"] < 0).any():
        res.errors.append("negative Amount")
    if not set(df["Class"].unique()) <= {0, 1}:
        res.errors.append("Class is not binary")
    if df.isna().any().any():
        res.warnings.append("missing values present")
    return res


def profile_paysim(df: pd.DataFrame) -> dict[str, Any]:
    """Descriptive statistics used in the dataset report (no transformation)."""
    fraud = df[df["isFraud"] == 1]
    by_type = (
        df.groupby("type")["isFraud"].agg(rows="size", frauds="sum").assign(rate=lambda t: t["frauds"] / t["rows"])
    )
    amount_q = df["amount"].quantile([0.5, 0.9, 0.99, 0.999]).to_dict()
    dup_all = int(df.duplicated().sum())
    orig_counts = df["nameOrig"].value_counts()
    dest_counts = df["nameDest"].value_counts()
    # accounting identity: for the sender, old - amount == new
    orig_ok = ((df["oldbalanceOrg"] - df["amount"]).round(2) == df["newbalanceOrig"].round(2)).mean()
    return {
        "rows": int(len(df)),
        "columns": list(df.columns),
        "missing_per_column": {c: int(v) for c, v in df.isna().sum().items()},
        "exact_duplicate_rows": dup_all,
        "class_distribution": _class_distribution(df["isFraud"]),
        "fraud_by_type": {k: {kk: float(vv) for kk, vv in v.items()} for k, v in by_type.to_dict("index").items()},
        "fraud_types": sorted(fraud["type"].unique().tolist()),
        "is_flagged_fraud": {
            "flagged": int(df["isFlaggedFraud"].sum()),
            "flagged_and_fraud": int(((df["isFlaggedFraud"] == 1) & (df["isFraud"] == 1)).sum()),
            "fraud_not_flagged": int(((df["isFlaggedFraud"] == 0) & (df["isFraud"] == 1)).sum()),
        },
        "step": {"min": int(df["step"].min()), "max": int(df["step"].max()), "distinct": int(df["step"].nunique())},
        "amount": {
            "min": float(df["amount"].min()),
            "max": float(df["amount"].max()),
            "mean": float(df["amount"].mean()),
            "zero_count": int((df["amount"] == 0).sum()),
            "quantiles": {str(k): float(v) for k, v in amount_q.items()},
            "fraud_mean": float(fraud["amount"].mean()),
        },
        "accounts": {
            "distinct_senders": int(orig_counts.size),
            "distinct_receivers": int(dest_counts.size),
            "senders_with_single_tx": int((orig_counts == 1).sum()),
            "max_tx_per_sender": int(orig_counts.max()),
            "merchant_receivers": int(dest_counts.index.str.startswith("M").sum()),
        },
        "balance_checks": {
            "sender_identity_holds_share": float(orig_ok),
            "fraud_sender_drained_share": float((fraud["newbalanceOrig"] == 0).mean()),
            "legit_sender_drained_share": float((df.loc[df["isFraud"] == 0, "newbalanceOrig"] == 0).mean()),
            "zero_old_and_new_dest_share": float(((df["oldbalanceDest"] == 0) & (df["newbalanceDest"] == 0)).mean()),
        },
    }


def profile_creditcard(df: pd.DataFrame) -> dict[str, Any]:
    dup = df.duplicated()
    fraud = df[df["Class"] == 1]
    return {
        "rows": int(len(df)),
        "columns": list(df.columns),
        "missing_per_column": {c: int(v) for c, v in df.isna().sum().items() if v},
        "exact_duplicate_rows": int(dup.sum()),
        "duplicate_fraud_rows": int(df[dup]["Class"].sum()),
        "class_distribution": _class_distribution(df["Class"]),
        "time": {
            "min": float(df["Time"].min()),
            "max": float(df["Time"].max()),
            "span_hours": float(df["Time"].max() / 3600),
        },
        "amount": {
            "min": float(df["Amount"].min()),
            "max": float(df["Amount"].max()),
            "mean": float(df["Amount"].mean()),
            "zero_count": int((df["Amount"] == 0).sum()),
            "fraud_mean": float(fraud["Amount"].mean()),
            "legit_mean": float(df.loc[df["Class"] == 0, "Amount"].mean()),
        },
    }
