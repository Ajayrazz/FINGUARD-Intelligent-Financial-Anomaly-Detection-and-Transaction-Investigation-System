"""Analytics selectors and the daily rollup. Read-only over the other apps (docs/05: analytics sits at the top).

Every number is computed from stored rows; nothing here is estimated. Definitions are documented per function and in
docs/07. Labels (`ground_truth_label`) feed only the research-metrics block of `false_positives`, never a prediction.
"""

from __future__ import annotations

import csv
import io
import statistics
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.db import transaction as db_transaction
from django.db.models import Count, Max, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone

from apps.alerts.models import Alert
from apps.cases.models import Case
from apps.datasets.models import Dataset
from apps.detection.models import DetectionRun, Prediction
from apps.model_registry.models import ModelVersion
from apps.risk_engine.models import RiskAssessment, RiskScoreRun
from apps.transactions.models import Transaction

from .models import DailyAggregate

CATEGORIES = ("low", "medium", "high", "critical", "unscored")
GRANULARITIES = {"day": None, "week": TruncWeek, "month": TruncMonth}


# --------------------------------------------------------------------------- helpers
def _latest_run(model, dataset_id: int):  # noqa: ANN001, ANN202
    return model.objects.filter(dataset_id=dataset_id, status="succeeded").order_by("-created_at", "-id").first()


def _datasets(dataset_id: int | None) -> list[int]:
    if dataset_id:
        return [dataset_id]
    return list(Dataset.objects.values_list("id", flat=True))


def _aggregates(dataset_id: int | None, date_from: date | None = None, date_to: date | None = None):  # noqa: ANN202
    qs = DailyAggregate.objects.all()
    if dataset_id:
        qs = qs.filter(dataset_id=dataset_id)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return qs


# --------------------------------------------------------------------------- rollup
def refresh_daily_aggregates(dataset_id: int) -> int:
    """Rebuild the rollup rows of one dataset from the source tables. Returns the number of days written."""
    tx = Transaction.objects.filter(dataset_id=dataset_id)
    per_day = {
        r["day"]: r
        for r in tx.annotate(day=TruncDate("occurred_at")).values("day").annotate(n=Count("id"), v=Sum("amount"))
    }
    by_type: dict[date, dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in (
        tx.annotate(day=TruncDate("occurred_at")).values("day", "tx_type").annotate(n=Count("id"), v=Sum("amount"))
    ):
        by_type[r["day"]][r["tx_type"]] = {"count": r["n"], "value": str(r["v"] or Decimal(0))}

    flagged: dict[date, int] = {}
    drun = _latest_run(DetectionRun, dataset_id)
    if drun:
        for f in (
            Prediction.objects.filter(run=drun, flagged=True)
            .annotate(day=TruncDate("transaction__occurred_at"))
            .values("day")
            .annotate(n=Count("id"))
        ):
            flagged[f["day"]] = f["n"]

    risk: dict[date, dict[str, int]] = defaultdict(dict)
    rrun = _latest_run(RiskScoreRun, dataset_id)
    if rrun:
        for c in (
            RiskAssessment.objects.filter(run=rrun)
            .annotate(day=TruncDate("transaction__occurred_at"))
            .values("day", "category")
            .annotate(n=Count("id"))
        ):
            risk[c["day"]][c["category"]] = c["n"]

    with db_transaction.atomic():
        DailyAggregate.objects.filter(dataset_id=dataset_id).delete()
        DailyAggregate.objects.bulk_create(
            [
                DailyAggregate(
                    dataset_id=dataset_id,
                    date=day,
                    tx_count=row["n"],
                    tx_value=row["v"] or Decimal(0),
                    flagged_count=flagged.get(day, 0),
                    by_risk_category=risk.get(day, {}),
                    by_type=by_type.get(day, {}),
                )
                for day, row in per_day.items()
            ],
            batch_size=1000,
        )
    return len(per_day)


def refresh_all() -> dict[int, int]:
    return {ds_id: refresh_daily_aggregates(ds_id) for ds_id in Dataset.objects.values_list("id", flat=True)}


def ensure_fresh(dataset_id: int | None) -> None:
    """First use of a dataset: build its rollup lazily so a new dataset never shows an empty dashboard."""
    for ds_id in _datasets(dataset_id):
        if (
            not DailyAggregate.objects.filter(dataset_id=ds_id).exists()
            and Transaction.objects.filter(dataset_id=ds_id).exists()
        ):
            refresh_daily_aggregates(ds_id)


# --------------------------------------------------------------------------- selectors
def overview(dataset_id: int | None) -> dict[str, Any]:
    ensure_fresh(dataset_id)
    agg = _aggregates(dataset_id).aggregate(
        n=Sum("tx_count"), v=Sum("tx_value"), f=Sum("flagged_count"), at=Max("refreshed_at")
    )
    risk = risk_distribution(dataset_id)["counts"]
    ds_ids = _datasets(dataset_id)
    return {
        "transactions": agg["n"] or 0,
        "value": str(agg["v"] or Decimal(0)),
        "flagged": agg["f"] or 0,
        "high_risk_transactions": risk.get("high", 0) + risk.get("critical", 0),
        "open_alerts": Alert.objects.filter(
            ~Q(status="closed"), **({"dataset_id__in": ds_ids} if dataset_id else {})
        ).count(),
        "open_cases": Case.objects.filter(
            ~Q(status="closed"), **({"dataset_id__in": ds_ids} if dataset_id else {})
        ).count(),
        "datasets": len(ds_ids),
        "refreshed_at": agg["at"],
    }


def volume(
    dataset_id: int | None, granularity: str, date_from: date | None, date_to: date | None
) -> list[dict[str, Any]]:
    """Transactions, value and flagged count per period (sum of the daily rollup)."""
    ensure_fresh(dataset_id)
    qs = _aggregates(dataset_id, date_from, date_to)
    trunc = GRANULARITIES[granularity]
    key = trunc("date") if trunc else TruncDate("date")
    rows = (
        qs.annotate(period=key)
        .values("period")
        .annotate(n=Sum("tx_count"), v=Sum("tx_value"), f=Sum("flagged_count"))
        .order_by("period")
    )
    return [
        {
            "period": r["period"].isoformat() if hasattr(r["period"], "isoformat") else str(r["period"]),
            "transactions": r["n"],
            "value": str(r["v"]),
            "flagged": r["f"],
        }
        for r in rows
    ]


def risk_distribution(dataset_id: int | None) -> dict[str, Any]:
    """Category counts of the latest succeeded risk run of each dataset in scope (summed across datasets)."""
    counts: dict[str, int] = dict.fromkeys(CATEGORIES, 0)
    runs = []
    for ds_id in _datasets(dataset_id):
        run = _latest_run(RiskScoreRun, ds_id)
        if run:
            runs.append(run.id)
            for k, v in (run.category_counts or {}).items():
                counts[k] = counts.get(k, 0) + int(v)
    return {"counts": counts, "total": sum(counts.values()), "runs": runs}


def high_risk_accounts(dataset_id: int | None, limit: int = 10) -> list[dict[str, Any]]:
    run_ids = risk_distribution(dataset_id)["runs"]
    rows = (
        RiskAssessment.objects.filter(run_id__in=run_ids, overall_score__isnull=False)
        .values("account_id", "account__account_ref", "account__dataset_id")
        .annotate(
            max_score=Max("overall_score"),
            assessments=Count("id"),
            flagged=Count("id", filter=Q(category__in=["high", "critical"])),
        )
        .order_by("-max_score", "account_id")[:limit]
    )
    return [
        {
            "account": r["account_id"],
            "account_ref": r["account__account_ref"],
            "dataset": r["account__dataset_id"],
            "max_score": round(r["max_score"], 1),
            "assessments": r["assessments"],
            "high_or_critical": r["flagged"],
        }
        for r in rows
    ]


def recent_suspicious(dataset_id: int | None, limit: int = 10) -> list[dict[str, Any]]:
    run_ids = risk_distribution(dataset_id)["runs"]
    rows = (
        RiskAssessment.objects.filter(run_id__in=run_ids, category__in=["high", "critical"])
        .select_related("transaction", "account")
        .order_by("-transaction__occurred_at", "-overall_score")[:limit]
    )
    return [
        {
            "transaction": a.transaction_id,
            "external_id": a.transaction.transaction_id,
            "account_ref": a.account.account_ref,
            "amount": str(a.transaction.amount),
            "occurred_at": a.transaction.occurred_at,
            "score": round(a.overall_score or 0, 1),
            "category": a.category,
        }
        for a in rows
    ]


def investigations_summary(dataset_id: int | None, date_from: date | None, date_to: date | None) -> dict[str, Any]:
    """Case counts by status / priority / outcome and resolution time (opened to resolved, hours)."""
    cases = Case.objects.all()
    if dataset_id:
        cases = cases.filter(dataset_id=dataset_id)
    if date_from:
        cases = cases.filter(opened_at__date__gte=date_from)
    if date_to:
        cases = cases.filter(opened_at__date__lte=date_to)

    def _count(field: str) -> dict[str, int]:
        return {r[field] or "none": r["n"] for r in cases.values(field).annotate(n=Count("id"))}

    pairs = cases.filter(resolved_at__isnull=False).values_list("opened_at", "resolved_at")[:200_000]
    hours = [(resolved - opened).total_seconds() / 3600 for opened, resolved in pairs if resolved is not None]
    return {
        "total": cases.count(),
        "by_status": _count("status"),
        "by_priority": _count("priority"),
        "by_outcome": _count("outcome"),
        "resolved": len(hours),
        "resolution_hours": {
            "mean": round(statistics.fmean(hours), 2) if hours else None,
            "median": round(statistics.median(hours), 2) if hours else None,
            "max": round(max(hours), 2) if hours else None,
        },
    }


def false_positives(dataset_id: int | None) -> dict[str, Any]:
    """False-positive analysis from two independent sources.

    * `investigated`: what investigators decided. Alerts closed as false_positive / true_positive and cases resolved
      as false_positive / confirmed_suspicious. Rate = false positives / (false + confirmed) among decided items.
    * `labelled` (research only): latest detection run per dataset vs `ground_truth_label` where labels exist.
      TP/FP/FN/TN, precision, recall and false-positive rate. Labels are evaluation data, not model output.
    """
    ds_ids = _datasets(dataset_id)
    alerts = Alert.objects.filter(status="closed", **({"dataset_id__in": ds_ids} if dataset_id else {}))
    a_fp = alerts.filter(outcome="false_positive").count()
    a_tp = alerts.filter(outcome="true_positive").count()
    cases = Case.objects.filter(**({"dataset_id__in": ds_ids} if dataset_id else {}))
    c_fp = cases.filter(outcome="false_positive").count()
    c_tp = cases.filter(outcome="confirmed_suspicious").count()

    def _rate(fp: int, tp: int) -> float | None:
        return round(fp / (fp + tp), 4) if (fp + tp) else None

    tp = fp = fn = tn = 0
    runs = []
    for ds_id in ds_ids:
        run = _latest_run(DetectionRun, ds_id)
        if not run:
            continue
        labelled = Prediction.objects.filter(run=run, transaction__ground_truth_label__isnull=False)
        if not labelled.exists():
            continue
        runs.append(run.id)
        c = labelled.aggregate(
            tp=Count("id", filter=Q(flagged=True, transaction__ground_truth_label=True)),
            fp=Count("id", filter=Q(flagged=True, transaction__ground_truth_label=False)),
            fn=Count("id", filter=Q(flagged=False, transaction__ground_truth_label=True)),
            tn=Count("id", filter=Q(flagged=False, transaction__ground_truth_label=False)),
        )
        tp, fp, fn, tn = tp + c["tp"], fp + c["fp"], fn + c["fn"], tn + c["tn"]
    return {
        "investigated": {
            "alerts": {"false_positive": a_fp, "true_positive": a_tp, "rate": _rate(a_fp, a_tp)},
            "cases": {"false_positive": c_fp, "confirmed_suspicious": c_tp, "rate": _rate(c_fp, c_tp)},
        },
        "labelled": {
            "runs": runs,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(tp / (tp + fp), 4) if (tp + fp) else None,
            "recall": round(tp / (tp + fn), 4) if (tp + fn) else None,
            "false_positive_rate": round(fp / (fp + tn), 4) if (fp + tn) else None,
        },
    }  # fmt: skip


def detection_performance() -> list[dict[str, Any]]:
    """Offline test-split quality and measured latency per registered model version (best PR-AUC first)."""
    out = []
    for mv in ModelVersion.objects.select_related("model").prefetch_related("evaluations"):
        ev = {e.split_name: e.metrics for e in mv.evaluations.all()}
        test, lat = ev.get("test") or {}, ev.get("latency") or {}
        if not test:
            continue
        out.append(
            {
                "id": mv.id, "model": mv.model.name, "algorithm": mv.model.algorithm, "dataset": mv.version.split("-")[0],  # noqa: E501
                "pr_auc": test.get("pr_auc"), "roc_auc": test.get("roc_auc"), "recall_at_fpr_1pct": test.get("recall_at_fpr_1pct"),  # noqa: E501
                "base_rate": test.get("base_rate"), "latency_ms_median": lat.get("single_ms_median"),
                "latency_ms_p95": lat.get("single_ms_p95"), "throughput_rows_per_s": lat.get("batch_rows_per_s"),
            }
        )  # fmt: skip
    return sorted(out, key=lambda r: -(r["pr_auc"] or 0))


# --------------------------------------------------------------------------- exports
_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value: Any) -> str:
    """CSV/spreadsheet formula injection guard (OWASP): a text cell that starts with = + - @ is neutralised."""
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(_FORMULA) else text


def to_csv(headers: list[str], rows: list[list[Any]]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([safe_cell(h) for h in headers])
    for row in rows:
        w.writerow([safe_cell(c) for c in row])
    return buf.getvalue().encode("utf-8-sig")


def to_pdf(title: str, subtitle: str, headers: list[str], rows: list[list[Any]]) -> bytes:
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=title,
    )
    cell = styles["BodyText"]
    cell.fontSize = 7.5
    data = [[Paragraph(f"<b>{escape(str(h))}</b>", cell) for h in headers]] + [
        [Paragraph(escape("" if c is None else str(c)), cell) for c in r] for r in rows[:2000]
    ]
    t = Table(data, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story = [
        Paragraph(escape(title), styles["Title"]),
        Paragraph(escape(subtitle), styles["Normal"]),
        Spacer(1, 4 * mm),
        t,
        Spacer(1, 4 * mm),
    ]
    story.append(
        Paragraph(
            "Generated by FinGuard from stored data. Scores and flags are automated indicators for prioritising review, not proof of wrongdoing.",  # noqa: E501
            styles["Italic"],
        )
    )
    doc.build(story)
    return buf.getvalue()


def report_table(
    report: str, dataset_id: int | None, granularity: str, date_from: date | None, date_to: date | None
) -> tuple[str, list[str], list[list[Any]]]:
    if report == "volume":
        data = volume(dataset_id, granularity, date_from, date_to)
        return (
            "Transaction volume",
            ["Period", "Transactions", "Value", "Flagged"],
            [[r["period"], r["transactions"], r["value"], r["flagged"]] for r in data],
        )
    if report == "risk-distribution":
        d = risk_distribution(dataset_id)
        return "Risk distribution", ["Category", "Transactions"], [[k, v] for k, v in d["counts"].items()]
    if report == "high-risk-accounts":
        return (
            "Highest-risk accounts",
            ["Account", "Highest score", "Assessments", "High or critical"],
            [
                [r["account_ref"], r["max_score"], r["assessments"], r["high_or_critical"]]
                for r in high_risk_accounts(dataset_id, 100)
            ],
        )
    if report == "false-positives":
        f = false_positives(dataset_id)
        rows = [
            ["Alerts closed as false positive", f["investigated"]["alerts"]["false_positive"]],
            ["Alerts closed as true positive", f["investigated"]["alerts"]["true_positive"]],
            ["Alert false-positive rate", f["investigated"]["alerts"]["rate"]],
            ["Cases resolved as false positive", f["investigated"]["cases"]["false_positive"]],
            ["Cases confirmed suspicious", f["investigated"]["cases"]["confirmed_suspicious"]],
            ["Case false-positive rate", f["investigated"]["cases"]["rate"]],
        ]
        rows += [[f"Labelled research: {k}", v] for k, v in f["labelled"].items() if k != "runs"]
        return "False-positive analysis", ["Measure", "Value"], rows
    if report == "investigations":
        s = investigations_summary(dataset_id, date_from, date_to)
        rows = (
            [["Total cases", s["total"]]]
            + [[f"Status: {k}", v] for k, v in s["by_status"].items()]
            + [[f"Outcome: {k}", v] for k, v in s["by_outcome"].items()]
            + [[f"Resolution hours ({k})", v] for k, v in s["resolution_hours"].items()]
        )
        return "Investigation summary", ["Measure", "Value"], rows
    if report == "recent-suspicious":
        return (
            "Recent suspicious transactions",
            ["Transaction", "Account", "Amount", "Time", "Score", "Category"],
            [
                [r["external_id"], r["account_ref"], r["amount"], r["occurred_at"], r["score"], r["category"]]
                for r in recent_suspicious(dataset_id, 200)
            ],
        )
    raise ValueError(report)


REPORTS = (
    "volume",
    "risk-distribution",
    "high-risk-accounts",
    "false-positives",
    "investigations",
    "recent-suspicious",
)


def now() -> datetime:
    return timezone.now()
