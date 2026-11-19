"""Duplicate library: normalisation, field extraction from OCR text, invoice similarity classes, repeated payments."""

from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from duplicates_lib import matching, normalize
from duplicates_lib.extract import extract_fields

H = 3600.0


def test_normalisation_of_vendor_number_amount_date():
    assert (
        normalize.normalize_vendor("Acme Supplies Pvt. Ltd.")
        == normalize.normalize_vendor("ACME SUPPLIES PRIVATE LIMITED")
        == "acme supplies"
    )
    assert normalize.normalize_vendor("Ltd.") == "ltd"  # never normalises to an empty string
    assert (
        normalize.normalize_invoice_number("inv-2026-0412")
        == normalize.normalize_invoice_number("INV 2026 412")
        == "INV2026412"
    )
    assert normalize.parse_amount("1,416.00") == Decimal("1416.00") and normalize.parse_amount("1.416,00") == Decimal(
        "1416.00"
    )
    assert normalize.parse_amount("INR 25,000") == Decimal("25000.00") and normalize.parse_amount("abc") is None
    assert (
        normalize.parse_date("12 Mar 2026")
        == date(2026, 3, 12)
        == normalize.parse_date("2026-03-12")
        == normalize.parse_date("12/03/2026")
    )
    assert normalize.parse_date("March 12, 2026") == date(2026, 3, 12) and normalize.parse_date("31/02/2026") is None


def test_field_extraction_from_ocr_lines_and_missing_fields_stay_none():
    lines = [("Acme Supplies Pvt Ltd", 96.0), ("14 Market Road", 90.0), ("INVOICE", 99.0), ("Invoice No: INV-2026-0412", 91.5),
             ("Date: 12 Mar 2026", 95.0), ("Bill To: Northwind", 93.0), ("Subtotal 1,200.00", 90.0), ("Total Due: INR 1,416.00", 88.0)]  # fmt: skip
    f = extract_fields(lines)
    assert f["vendor"]["value"] == "Acme Supplies Pvt Ltd" and f["invoice_number"]["value"] == "INV-2026-0412"
    assert (
        f["invoice_date"]["value"] == "2026-03-12"
        and f["amount"]["value"] == "1416.00"
        and f["currency"]["value"] == "INR"
    )
    assert f["amount"]["confidence"] == 88.0
    empty = extract_fields([("hello", 50.0)])
    assert empty["invoice_number"] is None and empty["amount"] is None and empty["invoice_date"] is None


def inv(vendor="acme supplies", number="INV2026412", amount="1416.00", d=date(2026, 3, 12), phash=None):
    return {
        "vendor_normalized": vendor,
        "invoice_number_normalized": number,
        "amount": Decimal(amount) if amount else None,
        "invoice_date": d,
        "phash": phash,
    }


def test_invoice_classes():
    assert matching.compare_invoices(inv(), inv())["match_class"] == "exact"
    strong = matching.compare_invoices(inv(), inv(vendor="acme supply", d=date(2026, 3, 14)))
    assert strong["match_class"] == "strong_similar" and strong["score"] > 80
    ocr_slip = matching.compare_invoices(inv(), inv(number="INV2026412X"))  # one extra character
    assert ocr_slip["match_class"] == "strong_similar"
    monthly = matching.compare_invoices(
        inv("zenith cloud", "ZCS1", "499.00", date(2026, 1, 1)), inv("zenith cloud", "ZCS2", "499.00", date(2026, 2, 1))
    )
    assert monthly["match_class"] == "legitimate_repeat"
    potential = matching.compare_invoices(
        inv("globex", "GL88120", "8750", date(2026, 4, 2)), inv("globex", "GL88175", "8750", date(2026, 4, 5))
    )
    assert potential["match_class"] == "potential"
    assert (
        matching.compare_invoices(
            inv("globex", "GL88120", "8750"), inv("initech", "IT5531", "23100", date(2026, 5, 20))
        )
        is None
    )


def test_score_ignores_missing_signals_instead_of_counting_them_as_zero():
    full = matching.compare_invoices(inv(), inv())
    sparse = matching.compare_invoices(inv(amount=None, d=None), inv(amount=None, d=None))
    assert sparse is not None and sparse["match_class"] == "strong_similar"  # no amount/date to confirm: never "exact"
    assert sparse["evidence"]["signals_available"] == ["number", "vendor"] and sparse["score"] == pytest.approx(
        full["score"], abs=1.0
    )


def test_image_hash_is_supporting_evidence_not_proof():
    close = {"phash": 0xFFFF}
    # same vendor+amount, looks alike, dates close, different numbers -> potential
    near = matching.compare_invoices(
        inv("a corp", "X1", "100", date(2026, 1, 1), **close),
        inv("a corp", "Y9", "100", date(2026, 1, 3), phash=0xFFFE),
    )
    assert near["match_class"] == "potential" and near["evidence"]["image"]["close"] is True
    # identical template two months apart with different numbers: separate invoices, not reported
    templated = matching.compare_invoices(
        inv("a corp", "X1", "100", date(2026, 1, 1), **close),
        inv("a corp", "Y9", "100", date(2026, 3, 5), phash=0xFFFE),
    )
    assert templated is None
    # no numbers/dates to contradict the look-alike -> still worth a human look
    sparse = matching.compare_invoices(
        inv("a corp", "", "100", None, **close), inv("a corp", "", "100", None, phash=0xFFFE)
    )
    assert sparse is not None and sparse["match_class"] == "potential"
    # a look-alike alone (different vendor and amount) is nothing
    assert (
        matching.compare_invoices(
            inv("a corp", "X1", "100", date(2026, 1, 1), **close),
            inv("zzz", "Y9", "900", date(2026, 1, 2), phash=0xFFFE),
        )
        is None
    )


def pays(rows):
    return pd.DataFrame({"tx_id": range(1, len(rows) + 1), "sender": [r[0] for r in rows], "receiver": [r[1] for r in rows],
                         "amount": [r[2] for r in rows], "tx_type": "PAYMENT", "t": [r[3] for r in rows]})  # fmt: skip


def test_repeated_payments_strong_potential_and_legitimate_series():
    strong = matching.find_repeated_payments(pays([(1, 2, 40000.0, 0), (1, 2, 40000.0, 600)]))
    assert [c["match_class"] for c in strong] == ["strong_similar"] and strong[0]["score"] > 90
    potential = matching.find_repeated_payments(pays([(1, 2, 500.0, 0), (1, 2, 500.0, 6 * H)]))
    assert [c["match_class"] for c in potential] == ["potential"]
    far = matching.find_repeated_payments(pays([(1, 2, 500.0, 0), (1, 2, 500.0, 3 * 86400.0)]))
    assert far == []  # three days apart, no series: not reported
    rent = matching.find_repeated_payments(pays([(1, 2, 9000.0, k * 30 * 86400.0) for k in range(4)]))
    assert (
        {c["match_class"] for c in rent} == {"legitimate_repeat"}
        and len(rent) == 3
        and all(c["score"] < 30 for c in rent)
    )


def test_different_amount_receiver_or_type_is_never_a_repeat():
    assert matching.find_repeated_payments(pays([(1, 2, 100.0, 0), (1, 2, 101.0, 60), (1, 3, 100.0, 120)])) == []
    df = pays([(1, 2, 100.0, 0), (1, 2, 100.0, 60)])
    df.loc[1, "tx_type"] = "TRANSFER"
    assert matching.find_repeated_payments(df) == []
