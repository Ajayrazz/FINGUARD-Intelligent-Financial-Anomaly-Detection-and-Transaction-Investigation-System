"""Duplicate detection and invoice OCR library (no Django, no database).

Similarity scores are evidence for a human reviewer, not proof of duplication (docs/08).
"""

CONFIG = {
    "version": "d1",
    # invoice similarity weights (sum to 1)
    "weights": {"number": 0.35, "vendor": 0.20, "amount": 0.25, "date": 0.10, "image": 0.10},
    "vendor_strong": 90.0,  # rapidfuzz token-set ratio considered "same vendor, small variation"
    "vendor_potential": 80.0,
    "amount_rel_tol": 0.01,  # 1% counts as "about the same amount"
    "date_window_days": 7,
    "phash_close": 8,  # Hamming distance on a 64-bit pHash
    "recurring_days": (
        6,
        8,
        13,
        15,
        27,
        33,
        88,
        94,
        360,
        370,
    ),  # ~weekly, bi-weekly, monthly, quarterly, yearly (min,max pairs)
    # repeated payments
    "payment_strong_s": 3600.0,
    "payment_window_s": 86400.0,
    "recurring_cv": 0.10,  # regular interval: coefficient of variation of gaps
    "recurring_max_gap_s": 35 * 86400.0,
    "max_candidates": 20000,
}
