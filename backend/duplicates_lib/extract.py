"""Field extraction from OCR text. Confidence of a field = mean OCR confidence (0-100) of the line it came from."""

from __future__ import annotations

import re
from typing import Any

from . import normalize

_NUMBER = re.compile(r"(?i)\binvoice\s*(?:no\.?|number|num|#)\s*[:\-#]?\s*([A-Z0-9][A-Z0-9\-/]{2,})")
_DATE_LABEL = re.compile(r"(?i)\b(?:invoice\s+)?date\s*[:\-]?\s*(.+)$")
_TOTAL = re.compile(
    r"(?i)\b(?:grand\s+total|total\s+due|amount\s+due|total\s+amount|total)\b\s*[:\-]?\s*(?:([A-Z]{3}|[$€£₹])\s*)?([\d][\d.,]*)"
)
_SKIP_VENDOR = re.compile(r"(?i)^(tax\s+)?invoice$|^bill\s*to|^page\s|^original|^copy")


def extract_fields(lines: list[tuple[str, float]]) -> dict[str, Any]:
    """`lines` = [(text, mean_confidence)] in reading order. Returns {field: {"value", "confidence"} | None}.
    Unextractable fields are reported as None - never guessed."""
    out: dict[str, Any] = {k: None for k in ("vendor", "invoice_number", "invoice_date", "amount", "currency")}
    for text, conf in lines:
        t = text.strip()
        if t and not _SKIP_VENDOR.match(t) and not re.search(r"(?i)invoice|date|total|bill", t):
            out["vendor"] = {"value": t, "confidence": conf}
            break
    for text, conf in lines:
        m = _NUMBER.search(text)
        if m and out["invoice_number"] is None:
            out["invoice_number"] = {"value": m.group(1).strip("-/"), "confidence": conf}
        d = _DATE_LABEL.search(text)
        if d and out["invoice_date"] is None and not re.search(r"(?i)due\s+date", text):
            parsed = normalize.parse_date(d.group(1).strip())
            if parsed:
                out["invoice_date"] = {"value": parsed.isoformat(), "confidence": conf}
    last = None
    for text, conf in lines:
        for m in _TOTAL.finditer(text):
            amount = normalize.parse_amount(m.group(2))
            if amount is not None:
                last = (m.group(1), amount, conf)
    if last:
        cur = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR"}.get(last[0] or "", last[0])
        out["amount"] = {"value": str(last[1]), "confidence": last[2]}
        if cur:
            out["currency"] = {"value": cur, "confidence": last[2]}
    return out
