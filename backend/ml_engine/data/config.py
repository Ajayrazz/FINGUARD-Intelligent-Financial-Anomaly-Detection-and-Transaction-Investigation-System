"""Paths and dataset-specific constants for Phase 5 experiments."""

import os
from pathlib import Path

DATASETS_DIR = Path(os.environ.get("FINGUARD_DATASETS_DIR", "/datasets"))
RAW_DIR = DATASETS_DIR / "raw"
PROCESSED_DIR = DATASETS_DIR / "processed"

PAYSIM_FILE = "PS_20174392719_1491204439457_log.csv"
CREDITCARD_FILE = "creditcard.csv"

# Raw PaySim schema: column -> pandas dtype kind ("i" integer, "f" float, "O"/"S" text)
PAYSIM_COLUMNS: dict[str, str] = {
    "step": "i",
    "type": "O",
    "amount": "f",
    "nameOrig": "O",
    "oldbalanceOrg": "f",
    "newbalanceOrig": "f",
    "nameDest": "O",
    "oldbalanceDest": "f",
    "newbalanceDest": "f",
    "isFraud": "i",
    "isFlaggedFraud": "i",
}
PAYSIM_TYPES = {"PAYMENT", "TRANSFER", "CASH_OUT", "DEBIT", "CASH_IN"}
PAYSIM_STEP_RANGE = (1, 743)  # hours over ~30 days

CREDITCARD_COLUMNS: dict[str, str] = {
    "Time": "f",
    **{f"V{i}": "f" for i in range(1, 29)},
    "Amount": "f",
    "Class": "i",
}

# Chronological split fractions (train, validation, test), by cumulative row count snapped to a time boundary.
SPLIT_FRACTIONS = (0.70, 0.15, 0.15)
