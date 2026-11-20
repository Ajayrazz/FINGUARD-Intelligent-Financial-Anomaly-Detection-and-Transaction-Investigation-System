"""Measure API latency on the current database (NFR-02): p50/p95/max per endpoint over N calls, in-process.

Run:  python manage.py benchmark_api [--runs 30] [--json out.json]
The numbers describe THIS machine and THIS data; they are recorded in docs/17 with the dataset sizes.
"""

import json
import statistics
import time

from django.core.management.base import BaseCommand
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.cases.models import Case
from apps.datasets.models import Dataset
from apps.graph_engine.models import GraphSnapshot
from apps.transactions.models import Account, Transaction


class Command(BaseCommand):
    help = "Time the main API endpoints on the current database."

    def add_arguments(self, parser):  # noqa: ANN001, ANN201
        parser.add_argument("--runs", type=int, default=30)
        parser.add_argument("--json", default="")

    def handle(self, *args, **opts):  # noqa: ANN002, ANN003, ANN201
        user = User.objects.filter(role__name="super_admin", is_active=True).first()
        if user is None:
            self.stderr.write("No active super admin to benchmark as.")
            return
        client = APIClient(HTTP_HOST="localhost")
        client.force_authenticate(user=user)
        biggest = Dataset.objects.order_by("-row_count").first()
        ds = biggest.id if biggest else 0
        tx = Transaction.objects.filter(dataset_id=ds).order_by("id").first()
        acct = Account.objects.filter(dataset_id=ds).order_by("id").first()
        case = Case.objects.order_by("id").first()
        snap = GraphSnapshot.objects.filter(status="succeeded").order_by("-id").first()
        total = Transaction.objects.count()
        paths = {
            "transactions list (page 1)": f"/api/v1/transactions/?dataset={ds}",
            "transactions list (sorted by amount)": f"/api/v1/transactions/?dataset={ds}&ordering=-amount",
            "transactions list (filter type+amount)": f"/api/v1/transactions/?dataset={ds}&tx_type=TRANSFER&min_amount=100000",
            "transactions list (deep page 5000)": f"/api/v1/transactions/?dataset={ds}&page=5000",
            "transaction detail": f"/api/v1/transactions/{tx.id}/" if tx else None,
            "account detail": f"/api/v1/accounts/{acct.id}/" if acct else None,
            "alerts list": "/api/v1/alerts/?open=true",
            "alerts summary": "/api/v1/alerts/summary/",
            "cases list": "/api/v1/cases/",
            "case detail": f"/api/v1/cases/{case.id}/" if case else None,
            "analytics overview": "/api/v1/analytics/overview/",
            "analytics volume (day)": "/api/v1/analytics/volume/?granularity=day",
            "analytics risk distribution": "/api/v1/analytics/risk-distribution/",
            "analytics high-risk accounts": "/api/v1/analytics/accounts/high-risk/",
            "analytics false positives": "/api/v1/analytics/false-positives/",
            "analytics detection performance": "/api/v1/analytics/detection-performance/",
            "model versions": "/api/v1/model-versions/",
            "risk assessments": "/api/v1/risk/assessments/",
            "graph findings": f"/api/v1/graph/findings/?snapshot={snap.id}" if snap else None,
        }
        results = {}
        self.stdout.write(
            f"dataset {ds} ({biggest.row_count if biggest else 0:,} rows); {total:,} transactions in total; {opts['runs']} runs each"
        )
        for name, path in paths.items():
            if path is None:
                continue
            client.get(path)  # warm-up (plan cache, ORM)
            times = []
            status = 0
            for _ in range(opts["runs"]):
                t0 = time.perf_counter()
                res = client.get(path)
                times.append((time.perf_counter() - t0) * 1000)
                status = res.status_code
            times.sort()
            row = {
                "p50_ms": round(statistics.median(times), 1),
                "p95_ms": round(times[max(0, int(len(times) * 0.95) - 1)], 1),
                "max_ms": round(times[-1], 1),
                "status": status,
            }
            results[name] = row
            self.stdout.write(
                f"{name:42s} p50 {row['p50_ms']:8.1f}  p95 {row['p95_ms']:8.1f}  max {row['max_ms']:8.1f} ms  [{status}]"
            )
        if opts["json"]:
            with open(opts["json"], "w") as f:
                json.dump(
                    {
                        "transactions_total": total,
                        "dataset_rows": biggest.row_count if biggest else 0,
                        "results": results,
                    },
                    f,
                    indent=2,
                )
