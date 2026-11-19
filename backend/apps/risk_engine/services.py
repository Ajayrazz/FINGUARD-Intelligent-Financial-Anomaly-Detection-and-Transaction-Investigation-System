"""Risk scoring: configuration versions, and batch scoring that assembles A, B, G, F, D, H for every transaction.

Every input is used *as of the transaction*: graph findings only once they had completed, history events only if they
happened earlier, and the stored components make each assessment reproducible without re-reading the sources.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from statistics import median
from typing import Any

import pandas as pd
from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.behavior.models import BehaviorAnalysisResult, BehaviorRun
from apps.datasets.models import Dataset
from apps.detection.models import DetectionRun, Prediction
from apps.duplicates.models import DuplicateCandidate, DuplicateScanRun
from apps.graph_engine.models import GraphFinding, GraphSnapshot
from apps.model_registry.models import ModelVersion
from apps.transactions.models import Transaction
from risk_engine_lib import ALGORITHM_VERSION, COMPONENTS, DEFAULT_THRESHOLDS, DEFAULT_WEIGHTS
from risk_engine_lib import engine as eng

from .models import AccountRiskHistory, RiskAssessment, RiskConfig, RiskScoreRun

log = logging.getLogger(__name__)
BATCH = 5000


class RiskError(Exception):
    """A request cannot be served (message is safe to show)."""


# ------------------------------------------------------------------------------------ configuration
def create_config(
    *, user: Any, weights: dict[str, float], thresholds: dict[str, float], policy: str, min_coverage: float,
    model_version: ModelVersion | None = None, notes: str = "", source: str = RiskConfig.Source.MANUAL,
) -> RiskConfig:  # fmt: skip
    """New immutable version (inactive). Validation failures raise RiskError with the reason."""
    try:
        eng.validate_config(weights, thresholds, policy, min_coverage)
    except eng.ConfigError as exc:
        raise RiskError(str(exc)) from exc
    with db_transaction.atomic():
        version = (RiskConfig.objects.order_by("-version").values_list("version", flat=True).first() or 0) + 1
        cfg = RiskConfig.objects.create(
            version=version, weights={k: float(weights[k]) for k in COMPONENTS}, thresholds={k: float(v) for k, v in thresholds.items()},
            missing_signal_policy=policy, min_coverage=float(min_coverage), model_version=model_version, notes=notes[:2000],
            source=source, created_by=user,
        )  # fmt: skip
    audit.log("risk.config.created", actor=user, resource_type="risk_config", resource_id=cfg.pk,
              changes={"version": version, "weights": cfg.weights, "thresholds": cfg.thresholds, "policy": policy, "source": source})  # fmt: skip
    return cfg


def activate_config(cfg: RiskConfig, user: Any) -> RiskConfig:
    with db_transaction.atomic():
        previous = RiskConfig.objects.filter(is_active=True).exclude(pk=cfg.pk).first()
        RiskConfig.objects.filter(is_active=True).exclude(pk=cfg.pk).update(is_active=False)
        RiskConfig.objects.filter(pk=cfg.pk).update(is_active=True)
    audit.log("risk.config.activated", actor=user, resource_type="risk_config", resource_id=cfg.pk,
              changes={"version": cfg.version, "previous_version": previous.version if previous else None})  # fmt: skip
    cfg.refresh_from_db()
    return cfg


def active_config() -> RiskConfig:
    cfg = RiskConfig.objects.filter(is_active=True).first()
    if cfg is None:
        raise RiskError("No active risk configuration.")
    return cfg


def default_config_values() -> dict[str, Any]:
    return {
        "weights": dict(DEFAULT_WEIGHTS),
        "thresholds": dict(DEFAULT_THRESHOLDS),
        "policy": "renormalize",
        "min_coverage": 0.5,
    }


# ------------------------------------------------------------------------------------ runs
def start_run(*, dataset: Dataset, user: Any, config: RiskConfig | None = None) -> RiskScoreRun:
    if not Transaction.objects.filter(dataset=dataset).exists():
        raise RiskError("The dataset has no transactions.")
    cfg = config or active_config()
    run = RiskScoreRun.objects.create(dataset=dataset, config=cfg, created_by=user)
    audit.log("risk.run.created", actor=user, resource_type="risk_run", resource_id=run.pk,
              changes={"dataset": dataset.pk, "config_version": cfg.version})  # fmt: skip
    return run


def _latest(qs):  # noqa: ANN001, ANN202
    return qs.order_by("-created_at", "-id").first()


def _to_epoch(series: pd.Series) -> pd.Series:
    return (pd.to_datetime(series, utc=True) - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds()


def execute_run(run_id: int) -> None:
    run = RiskScoreRun.objects.select_related("dataset", "config", "config__model_version").get(pk=run_id)
    if run.status == RiskScoreRun.Status.SUCCEEDED:
        return
    run.status, run.error_message = RiskScoreRun.Status.RUNNING, ""
    run.save(update_fields=["status", "error_message"])
    try:
        _score_dataset(run)
        audit.log("risk.run.completed", actor=run.created_by, resource_type="risk_run", resource_id=run.pk,
                  changes={"rows_scored": run.rows_scored, "categories": run.category_counts})  # fmt: skip
    except Exception as exc:  # noqa: BLE001 - surface as a failed run
        log.exception("risk run %s failed", run_id)
        run.status, run.finished_at = RiskScoreRun.Status.FAILED, timezone.now()
        run.error_message = str(exc)[:300] if isinstance(exc, RiskError) else "Unexpected error."
        run.save()
        audit.log(
            "risk.run.failed",
            actor=run.created_by,
            resource_type="risk_run",
            resource_id=run.pk,
            changes={"error": run.error_message},
        )


def _score_dataset(run: RiskScoreRun) -> None:
    cfg, ds = run.config, run.dataset
    weights, thresholds = cfg.weights, cfg.thresholds
    qs = Transaction.objects.filter(dataset=ds)
    n = qs.count()
    if n > settings.RISK_MAX_ROWS:
        raise RiskError(f"Dataset exceeds the risk-scoring limit of {settings.RISK_MAX_ROWS:,} transactions.")
    df = pd.DataFrame.from_records(
        qs.values_list("id", "sender_id", "receiver_id", "occurred_at"),
        columns=["id", "sender", "receiver", "occurred_at"],
    )
    df["t"] = _to_epoch(df["occurred_at"])
    tx_t: dict[int, float] = dict(zip(df["id"], df["t"], strict=True))

    # ---- A: the model score of the configured (or latest) detection run, scaled with the model's threshold at 50
    det_qs = DetectionRun.objects.filter(dataset=ds, status="succeeded")
    if cfg.model_version_id:
        det_qs = det_qs.filter(model_version_id=cfg.model_version_id)
    det = _latest(det_qs)
    a_scores: dict[int, float] = {}
    a_norm: tuple[float, float, float] | None = None
    if det is not None:
        summ = det.score_summary or {}
        a_norm = (
            det.threshold,
            float(summ.get("min", 0.0)),
            float(summ.get("quantiles", {}).get("p99.9", summ.get("max", 1.0))),
        )
        a_scores = dict(Prediction.objects.filter(run=det).values_list("transaction_id", "score"))
    # ---- B and F: the behavioural analysis
    beh = _latest(BehaviorRun.objects.filter(dataset=ds, status="succeeded"))
    beh_results: dict[int, dict[str, Any]] = {}
    if beh is not None:
        for tid, st, comps, dev in BehaviorAnalysisResult.objects.filter(run=beh).values_list(
            "transaction_id", "status", "components", "deviation_score"
        ):
            beh_results[tid] = {"status": st, "components": comps, "deviation_score": dev}
    # ---- G: graph findings, each visible only from the moment it completed
    snap = _latest(GraphSnapshot.objects.filter(dataset=ds, status="succeeded"))
    g_events: dict[int, list[tuple[float, float, int]]] = defaultdict(
        list
    )  # account -> [(visible_from, score, finding_id)]
    if snap is not None:
        findings = list(
            GraphFinding.objects.filter(snapshot=snap).values_list("id", "account_ids", "transaction_ids", "score")
        )
        need = {t for _, _, tids, _ in findings for t in tids}
        times = (
            dict(
                zip(
                    *[
                        list(x)
                        for x in zip(
                            *Transaction.objects.filter(pk__in=need).values_list("id", "occurred_at"), strict=True
                        )
                    ],
                    strict=True,
                )
            )
            if need
            else {}
        )
        for fid, accounts, tids, score in findings:
            visible = max((times[t].timestamp() for t in tids if t in times), default=snap.as_of.timestamp())
            for a in accounts:
                g_events[a].append((visible, score, fid))
    # ---- D: the later transaction of a non-dismissed duplicate pair carries the duplicate score
    scan = DuplicateScanRun.objects.filter(kind="transaction", status="succeeded").filter(dataset__in=[ds, None]).exists() or DuplicateScanRun.objects.filter(
        kind="transaction", status="succeeded", dataset__isnull=True).exists()  # fmt: skip
    d_values: dict[int, tuple[float, int]] = {}
    h_events: dict[int, list[float]] = defaultdict(list)  # account -> times of human-confirmed duplicate events
    pair_ids: set[int] = set()
    cands = list(DuplicateCandidate.objects.filter(kind="transaction").exclude(match_class="legitimate_repeat")
                 .exclude(review_status__in=["not_duplicate", "legitimate_repeat"]).values_list("id", "record_a_id", "record_b_id", "similarity_score", "review_status"))  # fmt: skip
    for _, a_id, b_id, *_ in cands:
        pair_ids.update((a_id, b_id))
    extra = dict(Transaction.objects.filter(pk__in=pair_ids - set(tx_t)).values_list("id", "occurred_at"))
    other_t = {k: v.timestamp() for k, v in extra.items()}
    for cid, a_id, b_id, sim, review in cands:
        ta, tb = tx_t.get(a_id, other_t.get(a_id)), tx_t.get(b_id, other_t.get(b_id))
        if ta is None or tb is None:
            continue
        later = b_id if (tb, b_id) >= (ta, a_id) else a_id
        value = 100.0 if review == "confirmed_duplicate" else float(sim)
        if later not in d_values or value > d_values[later][0]:
            d_values[later] = (value, cid)
        if review == "confirmed_duplicate" and later in tx_t:
            row = df[df["id"] == later].iloc[0]
            for acct in (row["sender"], row["receiver"]):
                if pd.notna(acct):
                    h_events[int(acct)].append(tx_t[later])
    # first transaction time per account (history exists only after it)
    first_t: dict[int, float] = {}
    for col in ("sender", "receiver"):
        for acct, t0 in df.dropna(subset=[col]).groupby(col)["t"].min().items():
            first_t[int(acct)] = min(first_t.get(int(acct), t0), t0)

    # ---- assemble components per transaction
    def components_for(tid: int, sender: int, receiver: float | None, t: float) -> dict[str, eng.Component]:
        comps: dict[str, eng.Component] = {}
        if det is None or a_norm is None:
            comps["A"] = eng.unavailable("no detection run for this dataset")
        elif tid not in a_scores:
            comps["A"] = eng.unavailable("transaction was not scored by the detection run")
        else:
            comps["A"] = eng.available(
                eng.normalise_model_score(a_scores[tid], *a_norm),
                {"detection_run": det.pk, "raw_score": a_scores[tid], "threshold": det.threshold},
            )
        comps["B"], comps["F"] = eng.behaviour_components(beh_results.get(tid) if beh is not None else None)
        if beh is None:
            comps["B"] = comps["F"] = eng.unavailable("no behavioural analysis for this dataset")
        if snap is None:
            comps["G"] = eng.unavailable("no graph analysis for this dataset")
        elif snap.as_of.timestamp() <= t:
            comps["G"] = eng.unavailable("the graph snapshot does not cover this transaction")
        else:
            parties = [sender] + ([int(receiver)] if receiver is not None and not math.isnan(receiver) else [])
            vis = [(s, f) for a in parties for (v, s, f) in g_events.get(a, []) if v <= t]
            comps["G"] = eng.available(
                max((s for s, _ in vis), default=0.0),
                {"snapshot": snap.pk, "finding": max(vis)[1] if vis else None, "visible_findings": len(vis)},
            )
        if not scan:
            comps["D"] = eng.unavailable("no completed duplicate scan")
        elif tid in d_values:
            comps["D"] = eng.available(d_values[tid][0], {"candidate": d_values[tid][1]})
        else:
            comps["D"] = eng.available(0.0, {"candidate": None})
        parties_f = [a for a in (sender, receiver) if a is not None and not (isinstance(a, float) and math.isnan(a))]
        if not any(first_t.get(int(a), t) < t for a in parties_f):
            comps["H"] = eng.unavailable("no earlier transactions for either account")
        else:
            k = sum(1 for a in parties_f for ev in h_events.get(int(a), []) if ev < t)
            comps["H"] = eng.available(100.0 * (1 - math.exp(-k / 2.0)), {"confirmed_duplicates_before": k})
        return comps

    rows = list(zip(df["id"], df["sender"], df["receiver"], df["t"], strict=True))
    priors: dict[str, float] = {}
    if cfg.missing_signal_policy == "neutral_prior":  # population median of each component over this dataset
        vals: dict[str, list[float]] = {c: [] for c in COMPONENTS}
        for tid, s, r, t in rows[:: max(1, len(rows) // 50000)]:
            for c, comp in components_for(int(tid), int(s), r, float(t)).items():
                if comp["available"]:
                    vals[c].append(comp["value"])
        priors = {c: float(median(v)) for c, v in vals.items() if v}
    run.params = {"detection_run": det.pk if det else None, "behavior_run": beh.pk if beh else None, "graph_snapshot": snap.pk if snap else None,
                  "duplicate_scan_available": bool(scan), "priors": priors, "algorithm_version": ALGORITHM_VERSION}  # fmt: skip

    counts: dict[str, int] = defaultdict(int)
    cov_buckets: dict[str, int] = defaultdict(int)
    best: dict[int, tuple[float, str, int]] = {}
    batch: list[RiskAssessment] = []
    with db_transaction.atomic():
        for tid, s, r, t in rows:
            tid, s = int(tid), int(s)
            res = eng.combine(
                components_for(tid, s, r, float(t)),
                weights,
                thresholds,
                policy=cfg.missing_signal_policy,
                priors=priors,
                min_coverage=cfg.min_coverage,
            )
            counts[res["category"]] += 1
            cov_buckets[f"{res['weight_coverage']:.2f}"] += 1
            if res["overall_score"] is not None and (s not in best or res["overall_score"] > best[s][0]):
                best[s] = (res["overall_score"], res["category"], best.get(s, (0, "", 0))[2])
            if s in best:
                best[s] = (best[s][0], best[s][1], best[s][2] + 1)
            batch.append(RiskAssessment(
                transaction_id=tid, account_id=s, config=cfg, run=run, algorithm_version=ALGORITHM_VERSION, components=res["components"],
                overall_score=res["overall_score"], category=res["category"], weight_coverage=res["weight_coverage"],
                low_coverage=res["low_coverage"], capped=res["capped"], policy=res["policy"],
                detection_run=det, behavior_run=beh, graph_snapshot=snap,
            ))  # fmt: skip
            if len(batch) >= BATCH:
                RiskAssessment.objects.bulk_create(batch)
                batch = []
        if batch:
            RiskAssessment.objects.bulk_create(batch)
        now = timezone.now()
        AccountRiskHistory.objects.filter(run=run).delete()
        AccountRiskHistory.objects.bulk_create([
            AccountRiskHistory(account_id=a, run=run, as_of=now, score=sc, category=cat, assessment_count=cnt)
            for a, (sc, cat, cnt) in best.items() if cat in ("medium", "high", "critical")
        ], batch_size=2000)  # fmt: skip
        run.rows_total = run.rows_scored = len(rows)
        run.category_counts, run.coverage_summary = dict(counts), dict(sorted(cov_buckets.items()))
        run.status, run.finished_at = RiskScoreRun.Status.SUCCEEDED, timezone.now()
        run.save()


def recompute_from_stored(assessment: RiskAssessment) -> dict[str, Any]:
    """Reproduce an assessment from its stored components and its configuration (no source data needed)."""
    cfg = assessment.config
    stored = {
        c: {
            "available": v["available"],
            "value": v.get("value"),
            "reason": v.get("reason", ""),
            "source": v.get("source", {}),
        }
        for c, v in assessment.components.items()
    }
    for c, v in assessment.components.items():
        if v.get("imputed"):
            stored[c] = eng.unavailable(v.get("reason", ""))
    priors = {c: v["value"] for c, v in assessment.components.items() if v.get("imputed")}
    return eng.combine(
        stored,
        cfg.weights,
        cfg.thresholds,
        policy=cfg.missing_signal_policy,
        priors=priors,
        min_coverage=cfg.min_coverage,
    )
