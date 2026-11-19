"""Synthetic DEMO graph scenario with planted patterns (never mixed into research metrics)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np

from apps.datasets.models import Dataset
from apps.transactions.models import Account, Transaction

START = datetime(2026, 1, 1, tzinfo=UTC)


def build(name: str = "DEMO graph scenario (synthetic)", seed: int = 11) -> Dataset:
    """Background of ~400 random payments plus: a 3-account cycle (A1>A2>A3>A1), a rapid 4-hop chain
    (B1>B2>B3>B4>B5), a fan-in of 8 senders to one account (F0) and 3 senders paying the same 2 beneficiaries."""
    ds = Dataset.objects.create(
        name=name,
        source_type=Dataset.SourceType.CUSTOM,
        is_synthetic=True,
        description="DEMO: synthetic payments with planted cycle, rapid chain, fan-in and shared beneficiaries.",
    )
    rng = np.random.default_rng(seed)
    acc: dict[str, Account] = {}

    def a(ref: str, kind: str = "customer") -> Account:
        if ref not in acc:
            acc[ref] = Account.objects.create(dataset=ds, account_ref=ref, account_type=kind)
        return acc[ref]

    rows: list[Transaction] = []
    n = 0

    def tx(s: str, r: str, amount: float, when: datetime, kind: str = "TRANSFER") -> None:
        nonlocal n
        n += 1
        rows.append(
            Transaction(
                dataset=ds,
                transaction_id=f"G{n:05d}",
                sender=a(s),
                receiver=a(r, "merchant" if r.startswith("M") else "customer"),
                amount=Decimal(f"{amount:.2f}"),
                currency="INR",
                tx_type=kind,
                occurred_at=when,
            )
        )

    for _ in range(400):  # background: customers pay merchants / each other, no structure
        s, r = int(rng.integers(0, 120)), int(rng.integers(0, 40))
        tx(
            f"C{s:03d}",
            f"M{r:03d}",
            float(rng.integers(50, 3000)),
            START + timedelta(minutes=int(rng.integers(0, 20 * 24 * 60))),
            "PAYMENT",
        )
    t = START + timedelta(days=10)
    tx("A1", "A2", 50_000, t)
    tx("A2", "A3", 49_500, t + timedelta(hours=2))
    tx("A3", "A1", 49_000, t + timedelta(hours=5))
    t = START + timedelta(days=12)
    for i, (src, dst) in enumerate([("B1", "B2"), ("B2", "B3"), ("B3", "B4"), ("B4", "B5")]):
        tx(src, dst, 90_000 - i * 1_000, t + timedelta(minutes=10 * i))
    t = START + timedelta(days=14)
    for i in range(8):
        tx(f"FS{i}", "F0", 2_000, t + timedelta(minutes=15 * i))
    t = START + timedelta(days=16)
    for sender in ("S1", "S2", "S3"):
        for j, receiver in enumerate(("X1", "X2")):
            tx(sender, receiver, 7_500, t + timedelta(hours=j))
    Transaction.objects.bulk_create(rows)
    return ds
