"""Normalisation of vendor names, invoice numbers, amounts and dates extracted from invoices."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

_LEGAL = {
    "pvt",
    "private",
    "ltd",
    "limited",
    "llc",
    "inc",
    "incorporated",
    "corp",
    "corporation",
    "co",
    "company",
    "plc",
    "gmbh",
    "llp",
    "sa",
    "pty",
}
_MONTHS = {
    m: i
    for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)
}


def normalize_vendor(name: str) -> str:
    """Lower-case, strip punctuation and legal-form words: 'Acme Supplies Pvt. Ltd.' -> 'acme supplies'."""
    words = re.sub(r"[^a-z0-9 ]+", " ", (name or "").lower().replace("&", " and ")).split()
    kept = [w for w in words if w not in _LEGAL]
    return " ".join(kept or words)


def normalize_invoice_number(number: str) -> str:
    """Upper-case alphanumerics with separators dropped and leading zeros of each numeric run removed:
    'inv-2026-0412' -> 'INV2026412', 'ZCS-0001' -> 'ZCS1'."""
    parts = re.split(r"[^A-Z0-9]+", (number or "").upper())
    return "".join(re.sub(r"(?<![0-9])0+(?=[0-9])", "", p) for p in parts if p)


def parse_amount(text: str) -> Decimal | None:
    """'1,416.00' -> 1416.00; '1.416,00' (European) -> 1416.00; returns None when it is not a number."""
    t = re.sub(r"[^\d.,]", "", text or "")
    if not t or not re.search(r"\d", t):
        return None
    if "," in t and "." in t:
        if t.rfind(",") > t.rfind("."):  # 1.416,00
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif "," in t:
        head, _, tail = t.rpartition(",")
        t = head.replace(",", "") + "." + tail if len(tail) in (1, 2) else t.replace(",", "")
    try:
        return Decimal(t).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def parse_date(text: str) -> date | None:
    """Accepts '2026-03-12', '12/03/2026' (day first), '12 Mar 2026', 'Mar 12, 2026'. None when unparseable."""
    t = (text or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            pass
    m = re.match(r"(\d{1,2})\s+([A-Za-z]{3})[a-z]*\.?,?\s+(\d{4})$", t)
    if m and m.group(2).lower() in _MONTHS:
        return _safe_date(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))
    m = re.match(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})$", t)
    if m and m.group(1).lower() in _MONTHS:
        return _safe_date(int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2)))
    return None


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None
