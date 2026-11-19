"""Alert rules (Module 6). Each rule reads *stored results* of the other engines and yields candidates; deduplication
and persistence happen in services. A candidate carries a snapshot of the evidence it was based on."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from django.db.models import Count

from apps.behavior.models import BehaviorAnalysisResult, BehaviorRun
from apps.datasets.models import Dataset
from apps.duplicates.models import DuplicateCandidate
from apps.graph_engine.models import GraphFinding, GraphSnapshot
from apps.risk_engine.models import RiskAssessment, RiskScoreRun
from apps.transactions.models import Transaction

from .models import SEVERITIES, SEVERITY_RANK

TYPE_LABEL = {
    "high_risk": "High-risk transaction",
    "multiple_transactions": "Burst of transactions",
    "unusual_activity": "Unusual account activity",
    "suspicious_beneficiary": "Suspicious beneficiary",
    "failed_transactions": "Repeated transaction failures",
    "high_value": "High-value transfer",
    "rapid_fund_movement": "Rapid movement of funds",
    "behavior_change": "Account behaviour change",
    "duplicate_record": "Possible duplicate record",
}

DEFAULT_POLICY: dict[str, Any] = {
    "high_risk": {"enabled": True, "min_category": "high"},
    "multiple_transactions": {"enabled": True, "min_transactions": 3, "critical_at": 5},
    "unusual_activity": {"enabled": True, "min_score": 70},
    "suspicious_beneficiary": {"enabled": True, "min_score": 50},
    "failed_transactions": {"enabled": True, "min_count": 3},
    "high_value": {"enabled": True, "amount": 1_000_000, "critical_multiple": 5},
    "rapid_fund_movement": {"enabled": True, "min_score": 40},
    "behavior_change": {"enabled": True, "min_score": 60},
    "duplicate_record": {"enabled": True, "min_class": "strong_similar"},
    "dedup_bucket_hours": 24,
    "email": {"min_severity": "high", "recipients": []},
    "auto_evaluate": True,
    "max_alerts_per_rule": 500,
    "auto_case": {
        "enabled": True,
        "min_severity": "critical",
    },  # open a case automatically for alerts at/above this severity
}
RULE_KEYS = [k for k, v in DEFAULT_POLICY.items() if isinstance(v, dict) and "enabled" in v]  # includes auto_case


class PolicyError(ValueError):
    """The alert policy is invalid."""


def validate_policy(p: dict[str, Any]) -> None:
    for key, default in DEFAULT_POLICY.items():
        if key not in p:
            raise PolicyError(f"missing setting: {key}")
        if isinstance(default, dict):
            if not isinstance(p[key], dict) or set(p[key]) != set(default):
                raise PolicyError(f"{key} must define exactly {sorted(default)}")
    for key in RULE_KEYS:
        if not isinstance(p[key]["enabled"], bool):
            raise PolicyError(f"{key}.enabled must be true or false")
    if p["high_risk"]["min_category"] not in ("medium", "high", "critical"):
        raise PolicyError("high_risk.min_category must be medium, high or critical")
    if p["duplicate_record"]["min_class"] not in ("exact", "strong_similar", "potential"):
        raise PolicyError("duplicate_record.min_class must be exact, strong_similar or potential")
    if p["email"]["min_severity"] not in SEVERITIES:
        raise PolicyError("email.min_severity must be low, medium, high or critical")
    if not isinstance(p["email"]["recipients"], list) or any("@" not in str(r) for r in p["email"]["recipients"]):
        raise PolicyError("email.recipients must be a list of email addresses")
    numeric = [("multiple_transactions", "min_transactions"), ("multiple_transactions", "critical_at"), ("unusual_activity", "min_score"),
               ("suspicious_beneficiary", "min_score"), ("failed_transactions", "min_count"), ("high_value", "amount"), ("high_value", "critical_multiple"),
               ("rapid_fund_movement", "min_score"), ("behavior_change", "min_score")]  # fmt: skip
    for key, sub in numeric:
        v = p[key][sub]
        if not isinstance(v, int | float) or isinstance(v, bool) or v <= 0:
            raise PolicyError(f"{key}.{sub} must be a positive number")
    if p["multiple_transactions"]["critical_at"] < p["multiple_transactions"]["min_transactions"]:
        raise PolicyError("multiple_transactions.critical_at must be at least min_transactions")
    if (
        not isinstance(p["dedup_bucket_hours"], int | float)
        or p["dedup_bucket_hours"] <= 0
        or p["dedup_bucket_hours"] > 24 * 30
    ):
        raise PolicyError("dedup_bucket_hours must be between 0 and 720")
    if p["auto_case"]["min_severity"] not in SEVERITIES:
        raise PolicyError("auto_case.min_severity must be low, medium, high or critical")
    if not isinstance(p["auto_evaluate"], bool):
        raise PolicyError("auto_evaluate must be true or false")
    cap = p["max_alerts_per_rule"]
    if not isinstance(cap, int) or isinstance(cap, bool) or not 1 <= cap <= 100000:
        raise PolicyError("max_alerts_per_rule must be a whole number between 1 and 100000")


@dataclass
class Candidate:
    alert_type: str
    severity: str
    dedup_key: str
    reason: str
    evidence: dict[str, Any]
    transaction_id: int | None = None
    account_id: int | None = None
    assessment_id: int | None = None
    signals: list[str] = field(default_factory=list)
    priority: float = 0.0  # used only to choose which candidates survive the per-rule cap


def _bucket(epoch: float, hours: float) -> int:
    return int(epoch // (hours * 3600))


def _sev_from_score(score: float, lo: float) -> str:
    return "critical" if score >= 90 else "high" if score >= 80 else "medium" if score >= lo else "low"


def rule_high_risk(ds: Dataset, p: dict[str, Any]) -> list[Candidate]:
    run = RiskScoreRun.objects.filter(dataset=ds, status="succeeded").order_by("-created_at").first()
    if run is None:
        return []
    wanted = (
        ["critical"]
        if p["high_risk"]["min_category"] == "critical"
        else ["high", "critical"]
        if p["high_risk"]["min_category"] == "high"
        else ["medium", "high", "critical"]
    )
    out = []
    for a in RiskAssessment.objects.filter(run=run, category__in=wanted).select_related("transaction"):
        comps = {
            c: {"value": v.get("value"), "contribution": v.get("contribution"), "available": v.get("available")}
            for c, v in a.components.items()
        }
        out.append(Candidate("high_risk", "critical" if a.category == "critical" else "high" if a.category == "high" else "medium", f"high_risk:tx:{a.transaction_id}",
                             f"Risk score {a.overall_score:.1f} ({a.category}) for transaction {a.transaction.transaction_id}, built from {a.weight_coverage * 100:.0f}% of the signal weight.",
                             {"overall_score": a.overall_score, "category": a.category, "weight_coverage": a.weight_coverage, "capped": a.capped, "components": comps,
                              "risk_run": run.pk, "config_version": a.config.version if hasattr(a, "config") else None}, a.transaction_id, a.account_id, a.pk, ["risk"]))  # fmt: skip
    return out


def _behavior_results(ds: Dataset):  # noqa: ANN202
    run = BehaviorRun.objects.filter(dataset=ds, status="succeeded").order_by("-created_at").first()
    if run is None:
        return None, BehaviorAnalysisResult.objects.none()
    # time order: events are processed as they happened, so a burst raises its alert's severity as it grows
    qs = BehaviorAnalysisResult.objects.filter(run=run, status="scored").select_related("transaction", "account")
    return run, qs.order_by("transaction__occurred_at", "transaction_id")


def rule_multiple_transactions(ds: Dataset, p: dict[str, Any]) -> list[Candidate]:
    cfg = p["multiple_transactions"]
    run, qs = _behavior_results(ds)
    out = []
    for r in qs.filter(components__burst__detail__transactions_in_window__gte=cfg["min_transactions"]):
        d = r.components["burst"]["detail"]
        k = d["transactions_in_window"]
        bucket = _bucket(r.transaction.occurred_at.timestamp(), p["dedup_bucket_hours"])
        out.append(Candidate("multiple_transactions", "critical" if k >= cfg["critical_at"] else "high", f"multiple_transactions:acct:{r.account_id}:{bucket}",
                             f"{k} transactions by {r.account.account_ref} within {d['window_minutes']} minutes.", {"transactions_in_window": k, "window_minutes": d["window_minutes"],
                             "behavior_run": run.pk if run else None, "latest_transaction": r.transaction.transaction_id}, r.transaction_id, r.account_id, None, ["burst"]))  # fmt: skip
    return out


def rule_unusual_activity(ds: Dataset, p: dict[str, Any]) -> list[Candidate]:
    cfg = p["unusual_activity"]
    run, qs = _behavior_results(ds)
    out = []
    for r in qs.filter(deviation_score__gte=cfg["min_score"]):
        top = sorted(((k, v["score"]) for k, v in r.components.items() if v.get("available")), key=lambda kv: -kv[1])[
            :3
        ]
        out.append(Candidate("unusual_activity", _sev_from_score(r.deviation_score, cfg["min_score"]), f"unusual_activity:tx:{r.transaction_id}",
                             f"Behavioural deviation {r.deviation_score:.1f}/100 from {r.account.account_ref}'s own history.", {"deviation_score": r.deviation_score, "coverage": r.coverage,
                             "history_count": r.history_count, "top_signals": top, "behavior_run": run.pk if run else None}, r.transaction_id, r.account_id, None, ["behavior"]))  # fmt: skip
    return out


def rule_behavior_change(ds: Dataset, p: dict[str, Any]) -> list[Candidate]:
    cfg = p["behavior_change"]
    run, qs = _behavior_results(ds)
    out = []
    for r in qs.filter(components__spend_jump__score__gte=cfg["min_score"]):
        c = r.components["spend_jump"]
        bucket = _bucket(r.transaction.occurred_at.timestamp(), p["dedup_bucket_hours"])
        out.append(Candidate("behavior_change", _sev_from_score(c["score"], cfg["min_score"]), f"behavior_change:acct:{r.account_id}:{bucket}",
                             f"Spending of {r.account.account_ref} over the last 7 days is {c['detail']['ratio']:.1f} times its usual weekly spend.", {"spend_jump": c["detail"], "score": c["score"],
                             "behavior_run": run.pk if run else None}, r.transaction_id, r.account_id, None, ["spend_jump"]))  # fmt: skip
    return out


def _snapshot(ds: Dataset):  # noqa: ANN202
    return GraphSnapshot.objects.filter(dataset=ds, status="succeeded").order_by("-created_at").first()


def rule_suspicious_beneficiary(ds: Dataset, p: dict[str, Any]) -> list[Candidate]:
    cfg = p["suspicious_beneficiary"]
    snap = _snapshot(ds)
    if snap is None:
        return []
    out = []
    for f in GraphFinding.objects.filter(
        snapshot=snap, finding_type__in=["shared_beneficiary", "fan_in"], score__gte=cfg["min_score"]
    ):
        bens = f.evidence.get("beneficiaries") if f.finding_type == "shared_beneficiary" else [f.account_ids[0]]
        for b in (bens or [])[:5]:
            out.append(Candidate("suspicious_beneficiary", _sev_from_score(f.score, cfg["min_score"]), f"suspicious_beneficiary:acct:{b}:{f.finding_type}",
                                 f"Account {b} is a beneficiary in a {f.finding_type.replace('_', ' ')} pattern (score {f.score:.0f}/100).",
                                 {"finding": f.pk, "finding_type": f.finding_type, "score": f.score, "evidence": {k: v for k, v in f.evidence.items() if isinstance(v, int | float | str | bool)},
                                  "snapshot": snap.pk}, f.transaction_ids[0] if f.transaction_ids else None, int(b), None, ["graph"]))  # fmt: skip
    return out


def rule_rapid_fund_movement(ds: Dataset, p: dict[str, Any]) -> list[Candidate]:
    cfg = p["rapid_fund_movement"]
    snap = _snapshot(ds)
    if snap is None:
        return []
    return [
        Candidate("rapid_fund_movement", _sev_from_score(f.score, cfg["min_score"]), f"rapid_fund_movement:chain:{'-'.join(str(a) for a in f.account_ids)}",
                  f"Funds moved through {len(f.account_ids)} accounts within hours ({f.evidence.get('hops', '?')} hops, {f.evidence.get('amount_retention', 0) * 100:.0f}% passed on).",
                  {"finding": f.pk, "score": f.score, "evidence": {k: v for k, v in f.evidence.items() if isinstance(v, int | float | str | bool)}, "account_ids": f.account_ids, "snapshot": snap.pk},
                  f.transaction_ids[-1] if f.transaction_ids else None, f.account_ids[0], None, ["graph"])
        for f in GraphFinding.objects.filter(snapshot=snap, finding_type="chain", score__gte=cfg["min_score"])
    ]  # fmt: skip


def rule_failed_transactions(ds: Dataset, p: dict[str, Any]) -> list[Candidate]:
    """Only evaluated when the dataset has status data (some transaction is not 'completed')."""
    cfg = p["failed_transactions"]
    qs = Transaction.objects.filter(dataset=ds, status="failed")
    if not qs.exists():
        return []
    out = []
    for row in qs.values("sender_id").annotate(n=Count("id")).filter(n__gte=cfg["min_count"]):
        last = qs.filter(sender_id=row["sender_id"]).order_by("-occurred_at").first()
        assert last is not None
        bucket = _bucket(last.occurred_at.timestamp(), p["dedup_bucket_hours"])
        out.append(Candidate("failed_transactions", "high" if row["n"] >= 2 * cfg["min_count"] else "medium", f"failed_transactions:acct:{row['sender_id']}:{bucket}",
                             f"{row['n']} failed transactions from {last.sender.account_ref}.", {"failed_count": row["n"]}, last.pk, row["sender_id"], None, ["status"]))  # fmt: skip
    return out


def rule_high_value(ds: Dataset, p: dict[str, Any]) -> list[Candidate]:
    cfg = p["high_value"]
    out = []
    for t in Transaction.objects.filter(dataset=ds, amount__gte=cfg["amount"]).select_related("sender"):
        severity = "high" if float(t.amount) >= cfg["amount"] * cfg["critical_multiple"] else "medium"
        out.append(Candidate("high_value", severity, f"high_value:tx:{t.pk}", f"Transaction {t.transaction_id} of {t.amount} is at or above the high-value threshold {cfg['amount']:,.0f}.",
                             {"amount": str(t.amount), "threshold": cfg["amount"], "tx_type": t.tx_type}, t.pk, t.sender_id, None, ["amount"]))  # fmt: skip
    return out


def rule_duplicate_record(ds: Dataset, p: dict[str, Any]) -> list[Candidate]:
    cfg = p["duplicate_record"]
    ok = {
        "exact": ["exact"],
        "strong_similar": ["exact", "strong_similar"],
        "potential": ["exact", "strong_similar", "potential"],
    }[cfg["min_class"]]
    out = []
    tx_ids = (
        set(Transaction.objects.filter(dataset=ds).values_list("id", flat=True))
        if DuplicateCandidate.objects.filter(kind="transaction").exists()
        else set()
    )
    for c in DuplicateCandidate.objects.filter(match_class__in=ok).exclude(
        review_status__in=["not_duplicate", "legitimate_repeat"]
    ):
        if c.kind == "transaction" and not ({c.record_a_id, c.record_b_id} & tx_ids):
            continue  # the pair belongs to other datasets
        confirmed = c.review_status == "confirmed_duplicate"
        out.append(Candidate("duplicate_record", "high" if confirmed or c.match_class == "exact" else "medium", f"duplicate_record:{c.kind}:{c.pk}",
                             f"{'Confirmed duplicate' if confirmed else 'Possible duplicate'} ({c.match_class.replace('_', ' ')}, similarity {c.similarity_score:.0f}/100).",
                             {"candidate": c.pk, "kind": c.kind, "match_class": c.match_class, "similarity_score": c.similarity_score, "review_status": c.review_status,
                              "record_a": c.record_a_id, "record_b": c.record_b_id}, max(c.record_a_id, c.record_b_id) if c.kind == "transaction" else None, None, None, ["duplicate"]))  # fmt: skip
    return out


RULES = {
    "high_risk": rule_high_risk, "multiple_transactions": rule_multiple_transactions, "unusual_activity": rule_unusual_activity,
    "suspicious_beneficiary": rule_suspicious_beneficiary, "failed_transactions": rule_failed_transactions, "high_value": rule_high_value,
    "rapid_fund_movement": rule_rapid_fund_movement, "behavior_change": rule_behavior_change, "duplicate_record": rule_duplicate_record,
}  # fmt: skip


def _priority(c: Candidate) -> float:
    e = c.evidence
    key = {"high_risk": "overall_score", "multiple_transactions": "transactions_in_window", "unusual_activity": "deviation_score", "behavior_change": "score",
           "suspicious_beneficiary": "score", "rapid_fund_movement": "score", "failed_transactions": "failed_count", "high_value": "amount",
           "duplicate_record": "similarity_score"}[c.alert_type]  # fmt: skip
    try:
        return float(e.get(key, 0.0))
    except (TypeError, ValueError):
        return 0.0


def evaluate(ds: Dataset, policy: dict[str, Any]) -> tuple[list[Candidate], dict[str, int]]:
    """Run every enabled rule. Each rule keeps at most `max_alerts_per_rule` candidates (highest severity, then
    priority first) so a loose threshold cannot flood the queue; what was cut is returned as `suppressed`."""
    cap = int(policy.get("max_alerts_per_rule", DEFAULT_POLICY["max_alerts_per_rule"]))
    out: list[Candidate] = []
    suppressed: dict[str, int] = {}
    for key, fn in RULES.items():
        if not policy[key]["enabled"]:
            continue
        found = [copy.deepcopy(c) for c in fn(ds, policy)]
        for c in found:
            c.priority = _priority(c)
        if len(found) > cap:
            ranked = sorted(found, key=lambda c: (-SEVERITY_RANK[c.severity], -c.priority, c.dedup_key))[:cap]
            suppressed[key] = len(found) - cap
            found = sorted(ranked, key=lambda c: found.index(c))  # keep the original (time) order for the survivors
        out += found
    return out, suppressed
