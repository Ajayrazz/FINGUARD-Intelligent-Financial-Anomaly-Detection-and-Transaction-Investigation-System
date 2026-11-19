"""Write a RANDOM CSV in PaySim's column format for import benchmarks and demos.

The values are meaningless random data (not PaySim, not real, not for research). It exists so import
throughput can be measured at 100k / 1M / 6.36M rows without needing the real dataset.
"""

import numpy as np
import pandas as pd
from django.core.management.base import BaseCommand

TYPES = np.array(["PAYMENT", "TRANSFER", "CASH_OUT", "CASH_IN", "DEBIT"])
P = [0.34, 0.08, 0.35, 0.22, 0.01]


class Command(BaseCommand):
    help = "Generate a random PaySim-format CSV (mock data)."

    def add_arguments(self, parser):  # noqa: ANN001, ANN201
        parser.add_argument("--rows", type=int, required=True)
        parser.add_argument("--out", required=True)
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--duplicate-rate", type=float, default=0.0, help="Fraction of rows reusing an ID")

    def handle(self, *args, **opts):  # noqa: ANN002, ANN003, ANN201
        rng = np.random.default_rng(opts["seed"])
        rows, out, chunk = opts["rows"], opts["out"], 500_000
        first = True
        for start in range(0, rows, chunk):
            n = min(chunk, rows - start)
            typ = rng.choice(TYPES, size=n, p=P)
            amount = np.round(rng.lognormal(mean=7.5, sigma=1.5, size=n), 2)
            old_o = np.round(amount * rng.uniform(1, 20, size=n), 2)
            fraud = (np.isin(typ, ["TRANSFER", "CASH_OUT"])) & (rng.random(n) < 0.013)
            new_o = np.where(fraud, 0.0, np.round(np.maximum(old_o - amount, 0), 2))
            dest_merchant = typ == "PAYMENT"
            dest_id = rng.integers(10**8, 10**9, size=n)
            df = pd.DataFrame(
                {
                    "step": rng.integers(1, 744, size=n),
                    "type": typ,
                    "amount": amount,
                    "nameOrig": ["C" + str(x) for x in rng.integers(10**8, 10**10, size=n)],
                    "oldbalanceOrg": old_o,
                    "newbalanceOrig": new_o,
                    "nameDest": [("M" if m else "C") + str(x) for m, x in zip(dest_merchant, dest_id, strict=True)],
                    "oldbalanceDest": np.where(dest_merchant, 0.0, np.round(rng.uniform(0, 1e6, size=n), 2)),
                    "newbalanceDest": 0.0,
                    "isFraud": fraud.astype(int),
                    "isFlaggedFraud": 0,
                }
            )
            df.insert(0, "_i", np.arange(start, start + n))
            df = df.drop(columns="_i")
            df.to_csv(out, mode="w" if first else "a", header=first, index=False)
            first = False
        self.stdout.write(self.style.SUCCESS(f"Wrote {rows} mock PaySim-format rows to {out}"))
