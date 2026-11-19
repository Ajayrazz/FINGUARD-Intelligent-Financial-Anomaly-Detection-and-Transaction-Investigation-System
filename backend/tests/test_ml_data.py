"""Phase 5A data pipeline: validation, cleaning, chronological splits, leakage checks (synthetic data)."""

import numpy as np
import pandas as pd
import pytest

from ml_engine.data import config, preprocess, splits, validation


def make_paysim(n: int = 2000, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    step = np.sort(rng.integers(1, 744, n))
    amount = rng.gamma(2.0, 5000.0, n).round(2)
    fraud = (rng.random(n) < 0.02).astype(int)
    fraud[[0, n // 2, n - 1]] = 1  # ensure positives in every split
    return pd.DataFrame(
        {
            "step": step,
            "type": rng.choice(sorted(config.PAYSIM_TYPES), n),
            "amount": amount,
            "nameOrig": [f"C{i % 300}" for i in range(n)],
            "oldbalanceOrg": amount + 100.0,
            "newbalanceOrig": np.full(n, 100.0),
            "nameDest": [f"M{i % 50}" for i in range(n)],
            "oldbalanceDest": np.zeros(n),
            "newbalanceDest": np.zeros(n),
            "isFraud": fraud,
            "isFlaggedFraud": np.zeros(n, dtype=int),
        }
    )


def make_creditcard(n: int = 1000, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    data = {"Time": np.sort(rng.uniform(0, 172800, n))}
    data.update({f"V{i}": rng.normal(size=n) for i in range(1, 29)})
    data["Amount"] = rng.gamma(2.0, 40.0, n)
    cls = (rng.random(n) < 0.02).astype(int)
    cls[[0, n // 2, n - 1]] = 1
    data["Class"] = cls
    return pd.DataFrame(data)


def test_validate_accepts_good_paysim_and_creditcard():
    validation.validate_paysim(make_paysim()).raise_if_failed()
    validation.validate_creditcard(make_creditcard()).raise_if_failed()


@pytest.mark.parametrize(
    "mutate, fragment",
    [
        (lambda d: d.drop(columns=["amount"]), "missing columns"),
        (lambda d: d.assign(step=0), "step outside"),
        (lambda d: d.assign(type="REFUND"), "unknown transaction types"),
        (lambda d: d.assign(amount=-1.0), "negative amounts"),
        (lambda d: d.assign(isFraud=2), "not binary"),
        (lambda d: d.assign(amount=d["amount"].astype(str)), "expected float"),
    ],
)
def test_validate_paysim_rejects_bad_data(mutate, fragment):
    res = validation.validate_paysim(mutate(make_paysim()))
    assert any(fragment in e for e in res.errors)
    with pytest.raises(validation.DataValidationError):
        res.raise_if_failed()


def test_validate_creditcard_rejects_bad_data():
    assert validation.validate_creditcard(make_creditcard().assign(Class=3)).errors
    assert validation.validate_creditcard(make_creditcard().drop(columns=["V3"])).errors


def test_cleaning_does_not_mutate_raw_and_keeps_row_ids():
    raw = make_paysim()
    snapshot = raw.copy(deep=True)
    cleaned, stats = preprocess.clean_paysim(raw)
    pd.testing.assert_frame_equal(raw, snapshot)  # raw frame untouched
    assert stats["rows_out"] == len(raw) and stats["duplicates_dropped"] == 0
    assert set(cleaned["row_id"]) == set(range(len(raw)))
    assert {"sender", "receiver", "is_fraud", "sender_balance_before"} <= set(cleaned.columns)
    assert cleaned["step"].dtype == "int16"
    assert cleaned["is_fraud"].sum() == raw["isFraud"].sum()


def test_creditcard_duplicates_dropped_and_counted():
    raw = make_creditcard()
    raw = pd.concat([raw, raw.iloc[[5, 6, 7]]], ignore_index=True)
    cleaned, stats = preprocess.clean_creditcard(raw)
    assert stats["duplicates_dropped"] == 3 and len(cleaned) == len(raw) - 3
    kept, _ = preprocess.clean_creditcard(raw, drop_duplicates=False)
    assert len(kept) == len(raw)


def test_split_is_chronological_complete_and_disjoint():
    cleaned, _ = preprocess.clean_paysim(make_paysim())
    parts, b = splits.chronological_split(cleaned, "step")
    summary = splits.verify_split(parts, "step", "is_fraud", total_rows=len(cleaned))
    assert parts["train"]["step"].max() < parts["validation"]["step"].min()
    assert parts["validation"]["step"].max() < parts["test"]["step"].min()
    assert sum(s["rows"] for s in summary.values()) == len(cleaned)
    assert b["train_end"] < b["validation_end"]
    # ratios are close to requested despite snapping to whole steps
    assert abs(b["actual_fractions"][0] - 0.70) < 0.05


def test_same_timestamp_rows_never_straddle_a_boundary():
    df = pd.DataFrame({"row_id": range(100), "step": [i // 10 for i in range(100)], "is_fraud": [1, 0] * 50})
    parts, _ = splits.chronological_split(df, "step")
    for a, c in (("train", "validation"), ("validation", "test")):
        assert set(parts[a]["step"]).isdisjoint(parts[c]["step"])


def test_verify_split_detects_leakage():
    cleaned, _ = preprocess.clean_paysim(make_paysim())
    parts, _ = splits.chronological_split(cleaned, "step")
    leaky = {**parts, "test": pd.concat([parts["test"], parts["train"].iloc[:5]])}  # train rows in test
    with pytest.raises(splits.LeakageError):
        splits.verify_split(leaky, "step", "is_fraud", total_rows=len(cleaned))
    no_pos = {**parts, "test": parts["test"].assign(is_fraud=0)}
    with pytest.raises(splits.LeakageError, match="no positive"):
        splits.verify_split(no_pos, "step", "is_fraud", total_rows=len(cleaned))


def test_split_is_deterministic():
    cleaned, _ = preprocess.clean_paysim(make_paysim())
    a, _ = splits.chronological_split(cleaned, "step")
    b, _ = splits.chronological_split(cleaned.sample(frac=1, random_state=1).sort_values(["step", "row_id"]), "step")
    for k in a:
        assert list(a[k]["row_id"]) == list(b[k]["row_id"])


def test_perturbing_future_rows_does_not_change_past_split():
    """Leakage perturbation: altering test-window rows must not move train/validation boundaries' membership."""
    cleaned, _ = preprocess.clean_paysim(make_paysim())
    parts, b = splits.chronological_split(cleaned, "step")
    perturbed = cleaned.copy()
    perturbed.loc[perturbed["step"] > b["validation_end"], "amount"] *= 1000
    parts2, _ = splits.chronological_split(perturbed, "step")
    pd.testing.assert_frame_equal(parts["train"].reset_index(drop=True), parts2["train"].reset_index(drop=True))


def test_account_overlap_reports_seen_share():
    cleaned, _ = preprocess.clean_paysim(make_paysim())
    parts, _ = splits.chronological_split(cleaned, "step")
    ov = splits.account_overlap(parts, "sender")
    assert 0.0 <= ov["test_rows_with_account_seen_before"] <= 1.0


def test_profile_paysim_reports_key_facts():
    prof = validation.profile_paysim(make_paysim())
    assert prof["rows"] == 2000 and prof["class_distribution"]["positives"] >= 3
    assert prof["exact_duplicate_rows"] == 0
