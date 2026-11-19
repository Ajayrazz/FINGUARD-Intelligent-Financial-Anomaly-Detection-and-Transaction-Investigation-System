"""Calibration experiment (RQ5): do weights fitted on one part of the data rank better than the default weights?

Uses the stored components of a risk run and the dataset's ground-truth labels. Labels are read here only, for
evaluation; they are never exposed through the API. Weights are searched on the earlier half of the transactions and
reported on the later half. Nothing is activated; `--save-config` stores an inactive 'calibrated' version.
"""

import json
from itertools import product
from pathlib import Path

import numpy as np
from django.core.management.base import BaseCommand, CommandError
from sklearn.metrics import average_precision_score

from apps.risk_engine import services
from apps.risk_engine.models import RiskAssessment, RiskScoreRun
from apps.transactions.models import Transaction
from risk_engine_lib import COMPONENTS


def _scores(S: np.ndarray, M: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Renormalised weighted mean over available components (rows without any available component score -1)."""
    den = (M * w).sum(axis=1)
    out = np.where(den > 0, (np.nan_to_num(S) * M * w).sum(axis=1) / np.where(den > 0, den, 1), -1.0)
    return out


def _precision_at_k(y: np.ndarray, s: np.ndarray, k: int) -> float:
    k = min(k, len(s))
    return float(y[np.argsort(-s, kind="stable")[:k]].mean())


def _alerts_per_tp(y: np.ndarray, s: np.ndarray, recall: float) -> float | None:
    order = np.argsort(-s, kind="stable")
    cum = np.cumsum(y[order])
    target = recall * y.sum()
    idx = np.searchsorted(cum, target)
    return float((idx + 1) / max(cum[min(idx, len(cum) - 1)], 1)) if y.sum() else None


class Command(BaseCommand):
    help = "RQ5 calibration experiment on a scored dataset (labels used for evaluation only)."

    def add_arguments(self, parser):
        parser.add_argument("--run", type=int, required=True, help="RiskScoreRun id")
        parser.add_argument("--out", default="", help="write the JSON report here")
        parser.add_argument("--step", type=float, default=0.1)
        parser.add_argument(
            "--save-config", action="store_true", help="store the best weights as an INACTIVE calibrated config version"
        )
        parser.add_argument("--email", default="", help="user to attribute the saved config to")

    def handle(self, *args, **o):
        run = RiskScoreRun.objects.filter(pk=o["run"], status="succeeded").select_related("config", "dataset").first()
        if run is None:
            raise CommandError("no such finished risk run")
        rows = list(
            RiskAssessment.objects.filter(run=run)
            .order_by("transaction__occurred_at", "transaction_id")
            .values_list("transaction_id", "components")
        )
        ids = [r[0] for r in rows]
        labels = dict(Transaction.objects.filter(pk__in=ids).values_list("id", "ground_truth_label"))
        y = np.array([bool(labels.get(i)) for i in ids], dtype=int)
        S = np.array(
            [[(c[k]["value"] if c[k]["available"] else np.nan) for k in COMPONENTS] for _, c in rows], dtype=float
        )
        M = (~np.isnan(S)).astype(float)
        half = len(y) // 2
        tune, ev = slice(0, half), slice(half, None)
        if y[tune].sum() < 5 or y[ev].sum() < 5:
            raise CommandError("need at least 5 positives in each half")
        informative = [i for i, k in enumerate(COMPONENTS) if M[:, i].mean() >= 0.01 and np.nanstd(S[:, i]) > 0]
        if not informative:
            raise CommandError("no component varies; nothing to calibrate")
        grid = [
            t for t in product(np.arange(0, 1 + 1e-9, o["step"]), repeat=len(informative)) if abs(sum(t) - 1) < 1e-9
        ]
        best_w, best_ap = None, -1.0
        for g in grid:
            w = np.zeros(len(COMPONENTS))
            w[informative] = g
            ap = average_precision_score(y[tune], _scores(S[tune], M[tune], w))
            if ap > best_ap:
                best_w, best_ap = w, ap
        default_w = np.array([run.config.weights[k] for k in COMPONENTS])
        a_only = np.zeros(len(COMPONENTS))
        a_only[0] = 1.0
        report = {"run": run.pk, "dataset": run.dataset.name, "rows": len(y), "positives": {"tune": int(y[tune].sum()), "eval": int(y[ev].sum())},
                  "informative_components": [COMPONENTS[i] for i in informative], "grid_points": len(grid),
                  "tuned_weights": {k: round(float(best_w[i]), 3) for i, k in enumerate(COMPONENTS)}, "evaluation_half": {}}  # fmt: skip
        rng = np.random.default_rng(42)
        for name, w in (
            ("A only (single model score)", a_only),
            ("default weights", default_w),
            ("calibrated weights", best_w),
        ):
            s = _scores(S[ev], M[ev], w)
            yy = y[ev]
            boots = []
            for _ in range(100):
                idx = rng.integers(0, len(yy), len(yy))
                if yy[idx].sum():
                    boots.append(average_precision_score(yy[idx], s[idx]))
            report["evaluation_half"][name] = {
                "pr_auc": float(average_precision_score(yy, s)), "pr_auc_ci95": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
                "precision_at_100": _precision_at_k(yy, s, 100), "precision_at_1000": _precision_at_k(yy, s, 1000),
                "alerts_per_true_positive_at_50pct_recall": _alerts_per_tp(yy, s, 0.5),
            }  # fmt: skip
        report["tuned_pr_auc_on_tuning_half"] = float(best_ap)
        text = json.dumps(report, indent=2)
        self.stdout.write(text)
        if o["out"]:
            Path(o["out"]).write_text(text)
        if o["save_config"]:
            from apps.accounts.models import User

            user = User.objects.filter(email=o["email"]).first() if o["email"] else None
            cfg = services.create_config(user=user, weights=report["tuned_weights"], thresholds=run.config.thresholds, policy=run.config.missing_signal_policy,
                                         min_coverage=run.config.min_coverage, model_version=run.config.model_version, source="calibrated",
                                         notes=f"Calibrated on the first half of run {run.pk}; evaluation in the same report. Not activated.")  # fmt: skip
            self.stdout.write(f"saved inactive config v{cfg.version}")
