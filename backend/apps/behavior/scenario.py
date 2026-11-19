"""Synthetic demo scenario for behavioral analysis (clearly labelled DEMO; never mixed into research metrics).

A steady customer spends ~INR 800 a few times a week around 10:00 UTC for 60 days, then makes five payments of
INR 40,000 to a new payee within ten minutes. A second customer stays regular throughout.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np

from apps.datasets.models import Dataset
from apps.transactions.models import Account, Transaction

START = datetime(2026, 1, 1, tzinfo=UTC)
BURST_DAY = 61


def build(name: str = "DEMO behavior scenario (synthetic)", seed: int = 7) -> Dataset:
    ds = Dataset.objects.create(
        name=name, source_type=Dataset.SourceType.CUSTOM, is_synthetic=True,
        description="DEMO: synthetic spending history with a planted 5 x 40,000 burst in 10 minutes. Not real data.",
    )  # fmt: skip
    rng = np.random.default_rng(seed)
    merchants = [
        Account.objects.create(dataset=ds, account_ref=f"M-DEMO-{i}", account_type="merchant") for i in range(4)
    ]
    payee = Account.objects.create(dataset=ds, account_ref="NEW-PAYEE-X", account_type="customer")
    steady = Account.objects.create(dataset=ds, account_ref="C-DEMO-STEADY", account_type="customer")
    regular = Account.objects.create(dataset=ds, account_ref="C-DEMO-REGULAR", account_type="customer")
    rows: list[Transaction] = []
    n = 0

    def add(sender: Account, receiver: Account, amount: float, when: datetime) -> None:
        nonlocal n
        n += 1
        rows.append(Transaction(
            dataset=ds, transaction_id=f"DEMO{n:05d}", sender=sender, receiver=receiver,
            amount=Decimal(f"{amount:.2f}"), currency="INR", tx_type="PAYMENT", occurred_at=when,
        ))  # fmt: skip

    for day in range(BURST_DAY):
        base = START + timedelta(days=day, hours=10)
        for who in (steady, regular):
            if day % 7 in (0, 2, 4):
                add(who, merchants[int(rng.integers(0, 4))], 800 + float(rng.normal(0, 60)),
                    base + timedelta(seconds=int(rng.integers(0, 3000))))  # fmt: skip
    burst = START + timedelta(days=BURST_DAY, hours=10)
    for i in range(5):
        add(steady, payee, 40_000.0, burst + timedelta(minutes=2 * i))
    add(regular, merchants[0], 790.0, burst)
    Transaction.objects.bulk_create(rows)
    return ds
