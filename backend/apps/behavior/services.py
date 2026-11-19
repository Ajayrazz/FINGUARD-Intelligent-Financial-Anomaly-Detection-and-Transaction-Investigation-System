"""Behavioral analysis on stored transactions: live profiles/trends/transaction deviation and batch runs.

Behavior = an account's *outgoing* transactions (its spending). History is ordered by (occurred_at, id) and a
transaction only ever sees entries strictly before it in that order.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from django.conf import settings
from django.db import transaction as db_transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit import services as audit
from apps.datasets.models import Dataset
from apps.transactions.models import Account, Transaction

from . import engine
from .models import AccountBehaviorProfile, BehaviorAnalysisResult, BehaviorRun

log = logging.getLogger(__name__)
CFG = engine.CONFIG
BATCH = 5000


class BehaviorError(Exception):
    """A request cannot be served (message is safe to show)."""


def _epoch(dt: datetime) -> float:
    return dt.timestamp()


def _side(account: Account, direction: str) -> Q:
    if direction == "in":
        return Q(receiver=account)
    return Q(sender=account)


def load_history(account: Account, before: datetime, before_id: int | None, window_days: int, direction: str = "out",
                 cap: int | None = None) -> dict[str, Any]:  # fmt: skip
    """Transactions of `account` strictly before (before, before_id) within the window, oldest first.
    `before_id=None` means everything with occurred_at < before (profile as-of a point in time)."""
    lo = before - timedelta(days=window_days)
    qs = Transaction.objects.filter(_side(account, direction), occurred_at__gte=lo)
    if before_id is None:
        qs = qs.filter(occurred_at__lt=before)
    else:
        qs = qs.filter(Q(occurred_at__lt=before) | Q(occurred_at=before, id__lt=before_id))
    qs = qs.order_by("-occurred_at", "-id")
    if cap:
        qs = qs[:cap]
    rows = list(
        qs.values_list("occurred_at", "amount", "receiver__account_ref", "sender__account_ref", "merchant_category")
    )
    rows.reverse()
    counterpart = [r[2] if direction == "out" else r[3] for r in rows]
    return {
        "times": np.array([_epoch(r[0]) for r in rows], dtype="float64"),
        "amounts": np.array([float(r[1]) for r in rows], dtype="float64"),
        "counterparties": counterpart,
        "categories": [r[4] for r in rows],
    }


def live_profile(account: Account, as_of: datetime, window_days: int, direction: str = "out") -> dict[str, Any]:
    h = load_history(account, as_of, None, window_days, direction)
    profile = engine.build_profile(h["times"], h["amounts"], h["counterparties"], h["categories"], _epoch(as_of), CFG)
    return {"account": account.pk, "account_ref": account.account_ref, "as_of": as_of, "window_days": window_days,
            "direction": direction, **profile}  # fmt: skip


def live_trends(
    account: Account, as_of: datetime, window_days: int, granularity: str, direction: str = "out"
) -> dict[str, Any]:
    if granularity not in ("day", "week", "month"):
        raise BehaviorError("granularity must be day, week or month")
    h = load_history(account, as_of, None, window_days, direction)
    return {
        "account": account.pk, "as_of": as_of, "window_days": window_days, "granularity": granularity,
        "direction": direction, "points": engine.aggregate(h["times"], h["amounts"], granularity),
    }  # fmt: skip


def live_transaction_behavior(tx: Transaction) -> dict[str, Any]:
    """Deviation of one transaction from its sender's history as of the transaction (recomputed, not stored)."""
    h = load_history(tx.sender, tx.occurred_at, tx.pk, CFG["window_days"], "out", cap=CFG["max_history"])
    receiver = tx.receiver.account_ref if tx.receiver else None
    res = engine.score_transaction(
        _epoch(tx.occurred_at), float(tx.amount), receiver, h["times"], h["amounts"], h["counterparties"], CFG
    )
    return {"transaction": tx.pk, "account": tx.sender_id, "profile_version": CFG["version"], **res}


def create_run(*, dataset: Dataset, user: Any) -> BehaviorRun:
    if not Transaction.objects.filter(dataset=dataset).exists():
        raise BehaviorError("The dataset has no transactions.")
    run = BehaviorRun.objects.create(dataset=dataset, params=CFG, created_by=user)
    audit.log("behavior.run.created", actor=user, resource_type="behavior_run", resource_id=run.pk,
              changes={"dataset": dataset.pk, "profile_version": CFG["version"]})  # fmt: skip
    return run


def execute_run(run_id: int) -> None:
    """Score every transaction against its sender's prior history. Idempotent: finished runs are skipped,
    a rerun of a failed/pending run replaces partial results."""
    run = BehaviorRun.objects.select_related("dataset").get(pk=run_id)
    if run.status == BehaviorRun.Status.SUCCEEDED:
        return
    run.status, run.started_at, run.error_message = BehaviorRun.Status.RUNNING, timezone.now(), ""
    run.save(update_fields=["status", "started_at", "error_message"])
    try:
        qs = Transaction.objects.filter(dataset=run.dataset)
        total = qs.count()
        if total > settings.BEHAVIOR_MAX_ROWS:
            raise BehaviorError(f"Dataset exceeds the behavior-run limit of {settings.BEHAVIOR_MAX_ROWS:,} rows.")
        df = pd.DataFrame.from_records(
            qs.values_list("id", "sender_id", "receiver__account_ref", "occurred_at", "amount"),
            columns=["id", "sender", "receiver", "occurred_at", "amount"],
        )
        df["t"] = (
            pd.to_datetime(df["occurred_at"], utc=True) - pd.Timestamp("1970-01-01", tz="UTC")
        ).dt.total_seconds()
        df["amount"] = df["amount"].astype(float)
        df = df.sort_values(["sender", "t", "id"], kind="stable").reset_index(drop=True)

        window = CFG["window_days"] * 86400.0
        cap, min_h = CFG["max_history"], CFG["min_history"]
        results: list[BehaviorAnalysisResult] = []
        profile_inputs: list[tuple[int, np.ndarray, np.ndarray, list]] = []
        scored = unavailable = 0
        with db_transaction.atomic():
            BehaviorAnalysisResult.objects.filter(run=run).delete()
            AccountBehaviorProfile.objects.filter(run=run).delete()
            for sender, g in df.groupby("sender", sort=False):
                t_arr, a_arr, ids = g["t"].to_numpy(), g["amount"].to_numpy(), g["id"].to_numpy()
                recv = g["receiver"].tolist()
                for i in range(len(g)):
                    lo = max(int(np.searchsorted(t_arr, t_arr[i] - window, side="left")), i - cap, 0)
                    # entries with the same timestamp but a later id are excluded: history = indices < i
                    if i - lo < min_h:
                        res = {"status": "unavailable_cold_start", "deviation_score": None, "coverage": 0.0,
                               "history_count": i - lo, "components": {}}  # fmt: skip
                    else:
                        res = engine.score_transaction(
                            float(t_arr[i]), float(a_arr[i]), recv[i], t_arr[lo:i], a_arr[lo:i], recv[lo:i], CFG
                        )
                    if res["status"] == "scored":
                        scored += 1
                    else:
                        unavailable += 1
                    results.append(
                        BehaviorAnalysisResult(
                            run=run,
                            transaction_id=int(ids[i]),
                            account_id=int(sender),
                            deviation_score=res["deviation_score"],
                            coverage=res["coverage"],
                            components=res["components"] if res["status"] == "scored" else {},
                            status=res["status"],
                            history_count=res["history_count"],
                        )
                    )
                    if len(results) >= BATCH:
                        BehaviorAnalysisResult.objects.bulk_create(results)
                        results = []
                if len(g) >= min_h:
                    profile_inputs.append((int(sender), t_arr, a_arr, recv))
            if results:
                BehaviorAnalysisResult.objects.bulk_create(results)
            profiles = []
            for account_id, t_arr, a_arr, recv in profile_inputs:
                as_of = float(t_arr[-1]) + 1.0
                keep = t_arr > as_of - window
                p = engine.build_profile(
                    t_arr[keep], a_arr[keep], [r for r, k in zip(recv, keep, strict=True) if k], [], as_of, CFG
                )
                profiles.append(
                    AccountBehaviorProfile(
                        run=run,
                        account_id=account_id,
                        as_of=datetime.fromtimestamp(as_of, UTC),
                        window_days=CFG["window_days"],
                        tx_count=p["tx_count"],
                        avg_amount=p["avg_amount"],
                        median_amount=p["median_amount"],
                        std_amount=p["std_amount"],
                        p95_amount=p["p95_amount"],
                        aggregates=p["aggregates"],
                        hour_histogram=p["hour_histogram"],
                        merchant_category_dist=p["merchant_category_dist"],
                        unique_counterparties=p["unique_counterparties"],
                        tx_per_day=p["tx_per_day"],
                        profile_version=CFG["version"],
                    )
                )
            AccountBehaviorProfile.objects.bulk_create(profiles, batch_size=1000)
            run.rows_total, run.rows_scored, run.rows_unavailable = total, scored, unavailable
            run.profiles_stored = len(profiles)
            run.status, run.finished_at = BehaviorRun.Status.SUCCEEDED, timezone.now()
            run.save()
        audit.log("behavior.run.completed", actor=run.created_by, resource_type="behavior_run", resource_id=run.pk,
                  changes={"rows_total": total, "rows_scored": scored, "rows_unavailable": unavailable})  # fmt: skip
    except Exception as exc:  # noqa: BLE001 - any failure must surface as a failed run
        log.exception("behavior run %s failed", run_id)
        msg = str(exc) if isinstance(exc, BehaviorError) else "Unexpected error."
        run.status, run.error_message, run.finished_at = BehaviorRun.Status.FAILED, msg[:500], timezone.now()
        run.save(update_fields=["status", "error_message", "finished_at"])
        audit.log("behavior.run.failed", actor=run.created_by, resource_type="behavior_run", resource_id=run.pk,
                  changes={"error": msg[:200]})  # fmt: skip
