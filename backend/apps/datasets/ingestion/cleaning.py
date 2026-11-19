"""Vectorised cleaning/validation of one chunk of raw rows.

Everything arrives as strings. Each row gets at most one error (first failing check, in the documented order).
Missing-value policy:
  * sender, amount, and a time reference are mandatory -> row rejected;
  * transaction_id blank -> generated; tx_type blank -> option default ("UNKNOWN"); status blank -> completed;
  * every other optional field blank -> NULL (never silently 0).
Amounts are rounded to 2 decimals (the column is NUMERIC(18,2)).
"""

import json
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from apps.transactions.models import Transaction

from .mapping import CANONICAL_FIELDS

STATUSES = {c for c, _ in Transaction.Status.choices}
TRUE = {"1", "true", "t", "yes", "y"}
FALSE = {"0", "false", "f", "no", "n"}
MAX_AMOUNT = 10**16
BALANCES = [
    "sender_balance_before",
    "sender_balance_after",
    "receiver_balance_before",
    "receiver_balance_after",
]
STEP_UNITS = {"seconds": "s", "minutes": "m", "hours": "h", "days": "D"}


@dataclass
class RowError:
    row_number: int
    code: str
    message: str
    raw: dict[str, Any] = field(default_factory=dict)


def _blank(s: pd.Series) -> pd.Series:
    return s.isna() | (s.astype(str).str.strip() == "")


def clean_chunk(
    df: pd.DataFrame,
    mapping: dict[str, Any],
    first_row_number: int,
    id_prefix: str,
    max_raw_errors: int = 0,
) -> tuple[pd.DataFrame, list[RowError]]:
    """Return (valid rows with canonical columns + `metadata` JSON string + `row_number`, errors)."""
    columns: dict[str, str] = mapping["columns"]
    opts: dict[str, Any] = mapping["options"]
    raw = df.reset_index(drop=True)
    raw = raw.astype(object).where(raw.notna(), "")
    n = len(raw)
    row_numbers = pd.Series(range(first_row_number, first_row_number + n))

    d = pd.DataFrame(index=raw.index)
    for src, canonical in columns.items():
        d[canonical] = raw[src].astype(str).str.strip()
    for f in CANONICAL_FIELDS:
        if f not in d:
            d[f] = ""

    code = pd.Series([""] * n, dtype=object)
    msg = pd.Series([""] * n, dtype=object)

    def flag(mask: pd.Series, c: str, m: str) -> None:
        nonlocal code, msg
        hit = mask & (code == "")
        code = code.mask(hit, c)
        msg = msg.mask(hit, m)

    # --- sender
    flag(d["sender"] == "", "missing_sender", "Sender account is missing")
    flag(d["sender"].str.len() > 64, "invalid_sender", "Sender account is longer than 64 characters")
    flag(d["receiver"].str.len() > 64, "invalid_receiver", "Receiver account is longer than 64 characters")

    # --- transaction id
    flag(
        d["transaction_id"].str.len() > 64,
        "invalid_transaction_id",
        "Transaction ID is longer than 64 characters",
    )
    generated = d["transaction_id"] == ""
    d.loc[generated, "transaction_id"] = [f"{id_prefix}-{r}" for r in row_numbers[generated]]

    # --- amount
    amount = pd.to_numeric(d["amount"].str.replace(",", "", regex=False), errors="coerce")
    flag(d["amount"] == "", "missing_amount", "Amount is missing")
    flag(amount.isna(), "invalid_amount", "Amount is not a number")
    flag(amount < 0, "negative_amount", "Amount is negative")
    flag(amount.abs() >= MAX_AMOUNT, "invalid_amount", "Amount is too large")
    d["amount"] = amount.round(2)

    # --- time
    if "occurred_at" in columns.values():
        parsed = pd.to_datetime(d["occurred_at"].replace("", pd.NA), utc=True, errors="coerce", format="mixed")
        flag(d["occurred_at"] == "", "missing_timestamp", "Timestamp is missing")
        flag(parsed.isna(), "invalid_timestamp", "Timestamp could not be parsed")
        d["occurred_at"] = parsed
        step = pd.to_numeric(d["step"], errors="coerce")
        d["step"] = step
    else:
        step = pd.to_numeric(d["step"], errors="coerce")
        flag(d["step"] == "", "missing_step", "Step is missing")
        flag(
            step.isna() | (step < 0) | (step != step.round()),
            "invalid_step",
            "Step is not a non-negative integer",
        )
        epoch = pd.Timestamp(str(opts["step_epoch"]).replace("Z", "+00:00"))
        unit = STEP_UNITS[opts["step_unit"]]
        d["occurred_at"] = epoch + pd.to_timedelta(step.fillna(0).astype("int64"), unit=unit)
        d["step"] = step

    # --- type / status / currency / merchant
    tx_type = d["tx_type"].str.upper()
    d["tx_type"] = tx_type.mask(tx_type == "", str(opts["default_tx_type"]).upper())
    flag(d["tx_type"].str.len() > 32, "invalid_tx_type", "Transaction type is longer than 32 characters")
    status = d["status"].str.lower()
    d["status"] = status.mask(status == "", "completed")
    flag(~d["status"].isin(STATUSES), "invalid_status", f"Status must be one of {sorted(STATUSES)}")
    d["currency"] = d["currency"].str.upper()
    flag(d["currency"].str.len() > 3, "invalid_currency", "Currency must be a 3-letter code")
    flag(
        d["merchant_name"].str.len() > 120,
        "invalid_merchant_name",
        "Merchant name is longer than 120 characters",
    )
    flag(
        d["merchant_category"].str.len() > 60,
        "invalid_merchant_category",
        "Merchant category is longer than 60 characters",
    )

    # --- optional numerics: blank -> NULL, junk -> error
    for f in BALANCES:
        num = pd.to_numeric(d[f].str.replace(",", "", regex=False), errors="coerce")
        flag((d[f] != "") & num.isna(), f"invalid_{f}", f"{f.replace('_', ' ').capitalize()} is not a number")
        d[f] = num.round(2)

    # --- label
    label = d["ground_truth_label"].str.lower()
    flag(
        (label != "") & ~label.isin(TRUE | FALSE),
        "invalid_label",
        "Label must be 0/1/true/false/yes/no",
    )
    d["ground_truth_label"] = label.map(lambda v: True if v in TRUE else (False if v in FALSE else None))

    # --- metadata from unmapped columns
    mapped = set(columns)
    extras = [c for c in raw.columns if c not in mapped] if opts.get("extras_to_metadata", True) else []
    if extras:
        extra_df = raw[extras].astype(str)
        d["metadata"] = [json.dumps({k: v for k, v in rec.items() if v != ""}) for rec in extra_df.to_dict("records")]
    else:
        d["metadata"] = "{}"

    d["row_number"] = row_numbers
    bad = code != ""
    errors: list[RowError] = []
    for i in d.index[bad]:
        raw_row = {k: str(v) for k, v in raw.loc[i].items()} if len(errors) < max_raw_errors else {}
        errors.append(RowError(int(row_numbers[i]), str(code[i]), str(msg[i]), raw_row))
    return d[~bad].reset_index(drop=True), errors
