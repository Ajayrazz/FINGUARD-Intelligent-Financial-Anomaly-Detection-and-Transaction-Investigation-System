"""Synthetic invoice generator with controlled duplicates (clearly synthetic; used for OCR/matching evaluation).

Layout (top to bottom): vendor, address, INVOICE, Invoice No, Date, Bill To, one line item, Subtotal, Tax, Total Due.
"""

from __future__ import annotations

import io
import random
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from PIL import Image, ImageDraw, ImageFont

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@dataclass
class Spec:
    vendor: str
    number: str
    when: date
    total: float
    customer: str = "Northwind Traders Ltd"
    item: str = "Consulting services"
    currency: str = "INR"
    date_style: str = "dmy_text"  # dmy_text | iso | slash
    address: str = "14 Market Road, Pune 411001"
    extra: dict[str, Any] = field(default_factory=dict)


def _fmt_date(d: date, style: str) -> str:
    if style == "iso":
        return d.isoformat()
    if style == "slash":
        return f"{d.day:02d}/{d.month:02d}/{d.year}"
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def render(
    spec: Spec, *, rotate: float = 0.0, jpeg_quality: int | None = None, noise: float = 0.0, seed: int = 0
) -> tuple[bytes, str]:
    """Return (file bytes, mime). `rotate` (degrees), `jpeg_quality` and `noise` simulate a re-scan."""
    font = ImageFont.load_default(size=30)
    big = ImageFont.load_default(size=44)
    img = Image.new("RGB", (1240, 900), "white")
    d = ImageDraw.Draw(img)
    subtotal = round(spec.total / 1.18, 2)
    tax = round(spec.total - subtotal, 2)
    rows = [
        (spec.vendor, big), (spec.address, font), ("", font), ("INVOICE", big),
        (f"Invoice No: {spec.number}", font), (f"Date: {_fmt_date(spec.when, spec.date_style)}", font),
        (f"Bill To: {spec.customer}", font), ("", font), (f"{spec.item}   1   {subtotal:,.2f}", font),
        (f"Subtotal {subtotal:,.2f}", font), (f"Tax (18%) {tax:,.2f}", font), (f"Total Due: {spec.currency} {spec.total:,.2f}", big),
    ]  # fmt: skip
    y = 40
    for text, f in rows:
        d.text((60, y), text, fill="black", font=f)
        y += 76 if f is big else 60
    if noise:
        rnd = random.Random(seed)
        px = img.load()
        assert px is not None
        for _ in range(int(noise * img.width * img.height)):
            x, yy = rnd.randrange(img.width), rnd.randrange(img.height)
            v = rnd.randrange(120, 255)
            px[x, yy] = (v, v, v)
    if rotate:
        img = img.rotate(rotate, expand=False, fillcolor="white", resample=Image.Resampling.BICUBIC)
    buf = io.BytesIO()
    if jpeg_quality:
        img.save(buf, "JPEG", quality=jpeg_quality)
        return buf.getvalue(), "image/jpeg"
    img.save(buf, "PNG")
    return buf.getvalue(), "image/png"


def build_set() -> tuple[list[dict[str, Any]], list[tuple[str, str, str | None]]]:
    """Return (documents, expected pairs). Each document: {name, spec, bytes, mime}. Each expected pair is
    (name_a, name_b, class) where class is None when the pair must NOT be reported."""
    acme = Spec("Acme Supplies Pvt Ltd", "INV-2026-0412", date(2026, 3, 12), 1416.00)
    docs: dict[str, tuple[Spec, dict[str, Any]]] = {
        "acme_original": (acme, {}),
        "acme_rescan": (acme, {"rotate": 1.0, "jpeg_quality": 70, "noise": 0.002}),  # same document, scanned again
        "acme_reissue": (Spec("ACME SUPPLY PVT LTD", "INV-2026-0412", date(2026, 3, 14), 1416.00, date_style="iso"), {}),
        "zenith_jan": (Spec("Zenith Cloud Services", "ZCS-0001", date(2026, 1, 1), 499.00, item="Hosting plan"), {}),
        "zenith_feb": (Spec("Zenith Cloud Services", "ZCS-0002", date(2026, 2, 1), 499.00, item="Hosting plan", date_style="slash"), {}),
        "zenith_mar": (Spec("Zenith Cloud Services", "ZCS-0003", date(2026, 3, 1), 499.00, item="Hosting plan"), {}),
        "globex_a": (Spec("Globex Logistics LLC", "GL-88120", date(2026, 4, 2), 8750.00, item="Freight"), {}),
        "globex_b": (Spec("Globex Logistics LLC", "GL-88175", date(2026, 4, 5), 8750.00, item="Freight"), {}),
        "initech": (Spec("Initech Software", "IT-5531", date(2026, 5, 20), 23100.00, item="Licences"), {}),
        "umbrella": (Spec("Umbrella Pharma Corp", "UP-90017", date(2026, 6, 9), 640.50, item="Supplies"), {}),
    }  # fmt: skip
    documents = []
    for name, (spec, opts) in docs.items():
        data, mime = render(spec, **opts)
        documents.append({"name": name, "spec": spec, "bytes": data, "mime": mime})
    expected: list[tuple[str, str, str | None]] = [
        ("acme_original", "acme_rescan", "exact"),
        ("acme_original", "acme_reissue", "strong_similar"),
        ("acme_rescan", "acme_reissue", "strong_similar"),
        ("zenith_jan", "zenith_feb", "legitimate_repeat"),
        ("zenith_feb", "zenith_mar", "legitimate_repeat"),
        ("zenith_jan", "zenith_mar", None),  # 59 days apart: not a recognised billing interval, not reported
        ("globex_a", "globex_b", "potential"),
        ("initech", "umbrella", None),
        ("acme_original", "initech", None),
        ("zenith_jan", "globex_a", None),
    ]
    return documents, expected
