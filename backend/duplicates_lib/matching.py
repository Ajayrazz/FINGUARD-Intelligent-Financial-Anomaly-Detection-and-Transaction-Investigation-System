"""Similarity of two invoices and detection of repeated payments. Scores are evidence, not proof."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd
from rapidfuzz import fuzz

from . import CONFIG

EXACT, STRONG, POTENTIAL, LEGIT = "exact", "strong_similar", "potential", "legitimate_repeat"


def _recurring(days: int, cfg: dict[str, Any]) -> bool:
    ranges = cfg["recurring_days"]
    return any(ranges[i] <= days <= ranges[i + 1] for i in range(0, len(ranges), 2))


def compare_invoices(a: dict[str, Any], b: dict[str, Any], cfg: dict[str, Any] = CONFIG) -> dict[str, Any] | None:
    """Each invoice: vendor_normalized, invoice_number_normalized, amount (Decimal|None), invoice_date (date|None),
    phash (int|None). Returns {match_class, score, evidence} or None when the pair is unrelated."""
    ev: dict[str, Any] = {}
    same_number = (
        bool(a["invoice_number_normalized"]) and a["invoice_number_normalized"] == b["invoice_number_normalized"]
    )
    num_sim = (
        100.0
        if same_number
        else fuzz.ratio(a["invoice_number_normalized"], b["invoice_number_normalized"])
        if a["invoice_number_normalized"] and b["invoice_number_normalized"]
        else 0.0
    )
    ven_sim = (
        fuzz.token_set_ratio(a["vendor_normalized"], b["vendor_normalized"])
        if a["vendor_normalized"] and b["vendor_normalized"]
        else 0.0
    )
    ev["number"] = {
        "a": a["invoice_number_normalized"],
        "b": b["invoice_number_normalized"],
        "same": same_number,
        "similarity": num_sim,
    }
    ev["vendor"] = {"a": a["vendor_normalized"], "b": b["vendor_normalized"], "similarity": ven_sim}

    amt_a, amt_b = a.get("amount"), b.get("amount")
    amount_equal = amount_close = False
    if amt_a is not None and amt_b is not None:
        amount_equal = amt_a == amt_b
        denom = max(abs(amt_a), abs(amt_b), Decimal("0.01"))
        rel = float(abs(amt_a - amt_b) / denom)
        amount_close = rel <= cfg["amount_rel_tol"]
        ev["amount"] = {"a": str(amt_a), "b": str(amt_b), "equal": amount_equal, "relative_difference": rel}
    else:
        ev["amount"] = {"available": False}
    d_a, d_b = a.get("invoice_date"), b.get("invoice_date")
    days: int | None = None
    if isinstance(d_a, date) and isinstance(d_b, date):
        days = abs((d_a - d_b).days)
        ev["date"] = {"a": d_a.isoformat(), "b": d_b.isoformat(), "days_apart": days}
    else:
        ev["date"] = {"available": False}
    dist = None
    if a.get("phash") is not None and b.get("phash") is not None:
        dist = bin(int(a["phash"]) ^ int(b["phash"])).count("1")
        ev["image"] = {"hamming_distance": dist, "close": dist <= cfg["phash_close"]}
    else:
        ev["image"] = {"available": False}

    # score: weighted similarity over the signals that are available (missing signals are not counted as 0)
    parts = {
        "number": num_sim / 100.0 if ev["number"]["a"] and ev["number"]["b"] else None,
        "vendor": ven_sim / 100.0 if ev["vendor"]["a"] and ev["vendor"]["b"] else None,
        "amount": (1.0 if amount_equal else 0.8 if amount_close else 0.0) if "equal" in ev["amount"] else None,
        "date": (max(0.0, 1.0 - days / 30.0) if days is not None else None),
        "image": (max(0.0, 1.0 - dist / 32.0) if dist is not None else None),
    }
    w = cfg["weights"]
    avail = [k for k, v in parts.items() if v is not None]
    if not avail:
        return None
    score = 100.0 * sum(w[k] * parts[k] for k in avail) / sum(w[k] for k in avail)
    ev["signals_available"] = avail

    same_vendor = ven_sim >= cfg["vendor_strong"]
    similar_vendor = ven_sim >= cfg["vendor_potential"]
    near_date = days is not None and days <= cfg["date_window_days"]
    both_numbers = bool(a["invoice_number_normalized"] and b["invoice_number_normalized"])
    # different numbers AND far-apart dates: two separate invoices that merely share a template
    contradicted = both_numbers and not same_number and days is not None and days > cfg["date_window_days"]
    image_close = dist is not None and dist <= cfg["phash_close"]
    if same_number and same_vendor and amount_equal and (days is None or days == 0):
        cls = EXACT
    elif same_number and similar_vendor and (amount_close or amount_equal or "equal" not in ev["amount"]):
        cls = STRONG  # same invoice number, small variation in vendor name and/or date
    elif same_vendor and amount_equal and not same_number and days is not None and _recurring(days, cfg):
        cls = LEGIT  # same vendor + amount, different invoice number, at a regular billing interval
    elif num_sim >= 85 and similar_vendor and amount_close:
        cls = STRONG  # invoice number differs by a character or two (OCR error or re-keying)
    elif similar_vendor and amount_close and near_date and not same_number:
        cls = POTENTIAL  # same vendor and amount, close dates, different numbers
    elif image_close and similar_vendor and amount_close and not contradicted:
        cls = POTENTIAL  # looks alike, same vendor and amount, and no evidence against (templated invoices alone are not enough)
    else:
        return None
    ev["class_reason"] = cls
    return {"match_class": cls, "score": round(score, 2), "evidence": ev}


def find_repeated_payments(df: pd.DataFrame, cfg: dict[str, Any] = CONFIG) -> list[dict[str, Any]]:
    """Pairs of consecutive transactions with the same sender, receiver, amount and type.

    df columns: tx_id, sender, receiver, amount, tx_type, t (epoch seconds). Within `payment_window_s` they are
    candidates (strong inside `payment_strong_s`). Beyond the window, a series of >= 3 with regular intervals
    (CV <= recurring_cv, gaps <= 35 days) is reported as a legitimate repeat so reviewers can see why it is not
    suspicious."""
    keys = ["sender", "receiver", "amount", "tx_type"]
    d = df.dropna(subset=["receiver"])
    d = d[d.duplicated(subset=keys, keep=False)].sort_values("t", kind="stable")  # only groups that repeat at all
    out: list[dict[str, Any]] = []
    for key, g in d.groupby(keys, sort=False):
        if len(g) < 2:
            continue
        t, ids = g["t"].to_numpy(), g["tx_id"].to_numpy()
        gaps = np.diff(t)
        regular = (
            len(g) >= 3
            and gaps.mean() > 0
            and gaps.std() / gaps.mean() <= cfg["recurring_cv"]
            and gaps.max() <= cfg["recurring_max_gap_s"]
            and gaps.min() > cfg["payment_window_s"]
        )
        for i, gap in enumerate(gaps):
            ev = {
                "sender": key[0],
                "receiver": key[1],
                "amount": float(key[2]),
                "tx_type": key[3],
                "gap_seconds": float(gap),
                "series_length": int(len(g)),
            }
            if regular:
                out.append(
                    {
                        "a": int(ids[i]),
                        "b": int(ids[i + 1]),
                        "match_class": LEGIT,
                        "score": 20.0,
                        "evidence": {**ev, "regular_interval": True},
                    }
                )
            elif gap <= cfg["payment_strong_s"]:
                out.append(
                    {
                        "a": int(ids[i]),
                        "b": int(ids[i + 1]),
                        "match_class": STRONG,
                        "score": round(80.0 + 20.0 * (1 - gap / cfg["payment_strong_s"]), 2),
                        "evidence": ev,
                    }
                )
            elif gap <= cfg["payment_window_s"]:
                out.append(
                    {
                        "a": int(ids[i]),
                        "b": int(ids[i + 1]),
                        "match_class": POTENTIAL,
                        "score": round(50.0 + 30.0 * (1 - gap / cfg["payment_window_s"]), 2),
                        "evidence": ev,
                    }
                )
        if len(out) >= cfg["max_candidates"]:
            break
    return out
