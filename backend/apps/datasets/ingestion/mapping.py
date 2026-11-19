"""Column mapping: source file columns -> canonical transaction fields.

A mapping is {"columns": {source_column: canonical_field}, "options": {...}}. Unmapped source columns are kept
in Transaction.metadata (option `extras_to_metadata`, default true), so no information in the file is lost.
"""

import re
from typing import Any

CANONICAL_FIELDS = [
    "transaction_id", "sender", "receiver", "amount", "occurred_at", "step", "tx_type", "currency",
    "merchant_name", "merchant_category", "status",
    "sender_balance_before", "sender_balance_after", "receiver_balance_before", "receiver_balance_after",
    "ground_truth_label",
]  # fmt: skip
REQUIRED_FIELDS = {"sender", "amount"}
TIME_FIELDS = {"occurred_at", "step"}  # at least one is required

DEFAULT_OPTIONS: dict[str, Any] = {
    "extras_to_metadata": True,
    "default_tx_type": "UNKNOWN",
    "step_epoch": "2026-01-01T00:00:00Z",  # PaySim has no real clock: step N -> epoch + N hours (documented)
    "step_unit": "hours",
    "merchant_prefix": "",
    "customer_prefix": "",
    "encoding": "utf-8-sig",
    "sheet": None,
}

PRESETS: dict[str, dict[str, Any]] = {
    "paysim": {
        "columns": {
            "step": "step",
            "type": "tx_type",
            "amount": "amount",
            "nameOrig": "sender",
            "oldbalanceOrg": "sender_balance_before",
            "newbalanceOrig": "sender_balance_after",
            "nameDest": "receiver",
            "oldbalanceDest": "receiver_balance_before",
            "newbalanceDest": "receiver_balance_after",
            "isFraud": "ground_truth_label",
        },  # isFlaggedFraud is intentionally unmapped -> metadata (excluded from ML features, docs/08)
        "options": {"merchant_prefix": "M", "customer_prefix": "C"},
    }
}

_SYNONYMS: dict[str, list[str]] = {
    "transaction_id": ["transactionid", "txnid", "txid", "id", "transactionref", "reference"],
    "sender": ["sender", "senderaccount", "nameorig", "from", "fromaccount", "source", "originator", "payer"],
    "receiver": ["receiver", "receiveraccount", "namedest", "to", "toaccount", "destination", "beneficiary", "payee"],
    "amount": ["amount", "amt", "value", "transactionamount"],
    "occurred_at": ["timestamp", "occurredat", "datetime", "date", "time", "transactiondate", "createdat"],
    "step": ["step"],
    "tx_type": ["type", "txtype", "transactiontype", "kind"],
    "currency": ["currency", "ccy"],
    "merchant_name": ["merchant", "merchantname"],
    "merchant_category": ["merchantcategory", "category", "mcc"],
    "status": ["status", "state"],
}  # fmt: skip


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def suggest_mapping(columns: list[str]) -> dict[str, Any]:
    """Best-effort mapping for the preview step. Always reviewed/edited by the user before import."""
    preset = PRESETS["paysim"]
    if set(preset["columns"]) <= set(columns):
        return {"columns": dict(preset["columns"]), "options": dict(preset["options"]), "preset": "paysim"}
    chosen: dict[str, str] = {}
    used: set[str] = set()
    for canonical, names in _SYNONYMS.items():
        for col in columns:
            if col not in chosen and canonical not in used and _norm(col) in names:
                chosen[col] = canonical
                used.add(canonical)
                break
    return {"columns": chosen, "options": {}, "preset": None}


def normalise_mapping(raw: dict[str, Any]) -> dict[str, Any]:
    return {"columns": dict(raw.get("columns", {})), "options": {**DEFAULT_OPTIONS, **raw.get("options", {})}}


def validate_mapping(mapping: dict[str, Any], header: list[str]) -> list[str]:
    """Return human-readable problems (empty list = valid)."""
    problems: list[str] = []
    columns: dict[str, str] = mapping["columns"]
    for src, canonical in columns.items():
        if src not in header:
            problems.append(f"Mapped column '{src}' is not in the file.")
        if canonical not in CANONICAL_FIELDS:
            problems.append(f"Unknown target field '{canonical}' for column '{src}'.")
    targets = list(columns.values())
    for field in {t for t in targets if targets.count(t) > 1}:
        problems.append(f"More than one column is mapped to '{field}'.")
    for field in sorted(REQUIRED_FIELDS - set(targets)):
        problems.append(f"Required field '{field}' is not mapped.")
    if not TIME_FIELDS & set(targets):
        problems.append("Map either 'occurred_at' (a timestamp) or 'step' (a time step).")
    if "step" in targets and "occurred_at" not in targets:
        from datetime import datetime

        try:
            datetime.fromisoformat(str(mapping["options"]["step_epoch"]).replace("Z", "+00:00"))
        except ValueError:
            problems.append("option step_epoch must be an ISO-8601 timestamp.")
        if mapping["options"]["step_unit"] not in {"seconds", "minutes", "hours", "days"}:
            problems.append("option step_unit must be seconds, minutes, hours or days.")
    return problems
