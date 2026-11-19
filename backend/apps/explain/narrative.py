"""Deterministic, template-based narratives (no language model). Wording follows the UI rules: "flagged for review",
"risk indicators", "model score" - never an accusation. Every text states what the evidence is and is not."""

from __future__ import annotations

from typing import Any

DISCLAIMER = (
    "This explanation describes why a model, a rule or a risk score prioritised this transaction for review. "
    "It is automated evidence, not proof of wrongdoing; only an investigator's recorded decision is a determination."
)


def _money(x: Any) -> str:
    try:
        return f"{float(x):,.2f}"
    except (TypeError, ValueError):
        return str(x)


def model_narrative(
    algorithm: str, score: float, threshold: float, attributions: list[dict[str, Any]], space: str | None
) -> str:
    side = "at or above" if score >= threshold else "below"
    up = [a for a in attributions if a["contribution"] > 0][:3]
    down = [a for a in attributions if a["contribution"] < 0][:3]
    parts = [
        f"The {algorithm} model gave this transaction a score of {score:.3f}, {side} its alert threshold of {threshold:.3f}."
    ]
    if up:
        parts.append(
            "Factors that raised the score most: " + "; ".join(f"{a['label']} ({a['display']})" for a in up) + "."
        )
    if down:
        parts.append("Factors that lowered it most: " + "; ".join(f"{a['label']} ({a['display']})" for a in down) + ".")
    if space:
        parts.append(f"Contributions are in {space} units.")
    parts.append("The score is a ranking aid for review, not a conclusion.")
    return " ".join(parts)


def behaviour_narrative(b: dict[str, Any]) -> str:
    if b["status"] != "scored":
        return f"No behavioural deviation could be computed: the sender has only {b['history_count']} earlier transaction(s) in the window, too few for a baseline."
    c = b["components"]
    lines = [
        f"Compared with the sender's own earlier behaviour this transaction deviates by {b['deviation_score']:.1f} out of 100 (based on {b['history_count']} earlier transactions)."
    ]
    if c.get("amount", {}).get("available") and c["amount"]["score"] >= 30:
        d = c["amount"]["detail"]
        lines.append(f"The amount {_money(d['amount'])} is well above the sender's typical {_money(d['median'])}.")
    if c.get("burst", {}).get("available") and c["burst"]["detail"]["transactions_in_window"] >= 2:
        d = c["burst"]["detail"]
        lines.append(
            f"It is one of {d['transactions_in_window']} transactions by this sender within {d['window_minutes']} minutes."
        )
    if c.get("spend_jump", {}).get("available") and c["spend_jump"]["score"] >= 30:
        lines.append(
            f"Spending over the last 7 days is {c['spend_jump']['detail']['ratio']:.1f} times the sender's usual weekly spend."
        )
    if c.get("new_counterparty", {}).get("available") and not c["new_counterparty"]["detail"]["seen_before"]:
        lines.append("This is the first payment from this sender to this receiver.")
    if c.get("hour", {}).get("available") and c["hour"]["score"] >= 30:
        lines.append(f"The hour ({c['hour']['detail']['hour_utc']}:00 UTC) is unusual for this sender.")
    unavailable = [k for k, v in c.items() if not v.get("available")]
    if unavailable:
        lines.append("Not available: " + ", ".join(sorted(unavailable)) + ".")
    return " ".join(lines)


_FINDING_TEXT = {
    "cycle": "money moved in a circle between these accounts",
    "chain": "funds were passed on through several accounts within a short time",
    "fan_in": "many different senders paid the same account within a day",
    "fan_out": "one account paid many different receivers within a day",
    "shared_beneficiary": "several senders paid the same group of beneficiaries",
    "dense_cluster": "these accounts form a tightly interconnected group",
}


def graph_narrative(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "No network pattern involving the sender or receiver had completed by the time of this transaction."
    parts = [f"{len(findings)} network pattern(s) involving the sender or receiver had completed by this transaction:"]
    for f in findings[:5]:
        parts.append(f"{_FINDING_TEXT.get(f['finding_type'], f['finding_type'])} (pattern score {f['score']:.0f}/100)")
    return " ".join([parts[0], "; ".join(parts[1:]) + "."])


def risk_narrative(r: dict[str, Any]) -> str:
    if r["overall_score"] is None:
        return "No risk score could be computed: no signal was available (or the strict policy refused to score with missing signals)."
    comps = sorted(
        (c for c in r["components"].values() if c["contribution"] is not None), key=lambda c: -c["contribution"]
    )
    top = "; ".join(f"{c['name']} {c['contribution']:.1f} points" for c in comps[:3])
    text = f"The risk score is {r['overall_score']:.1f} out of 100 ({r['category']}), built from {r['weight_coverage'] * 100:.0f}% of the possible signal weight. Largest contributions: {top}."
    missing = [c["name"] for c in r["components"].values() if c["contribution"] is None]
    if missing:
        text += " Not available and excluded: " + ", ".join(missing) + "."
    if r.get("capped"):
        text += " The score would be Critical but is held at High because too few signals were available; an analyst should review it."
    return text


def duplicate_narrative(cands: list[dict[str, Any]]) -> str:
    if not cands:
        return "No similar earlier transaction was found."
    c = cands[0]
    return f"This transaction resembles another one ({c['match_class'].replace('_', ' ')}, similarity {c['similarity_score']:.0f}/100); review status: {c['review_status'].replace('_', ' ')}."


def summary_sections(parts: dict[str, Any]) -> list[dict[str, str]]:
    """The five fixed sections of an investigation summary: Prediction / Indicator / Evidence / Assessment / Outcome."""

    def pick(key: str, default: str) -> str:
        return parts.get(key) or default

    outcome = pick("outcome", "No analyst outcome has been recorded yet.")
    return [
        {"title": "Prediction", "text": pick("model", "No model prediction is available for this transaction.")},
        {
            "title": "Indicator",
            "text": " ".join(x for x in (parts.get("behaviour"), parts.get("graph"), parts.get("duplicate")) if x)
            or "No risk indicators are available.",
        },
        {"title": "Evidence", "text": pick("evidence", "No supporting transactions to list.")},
        {"title": "Assessment", "text": pick("risk", "This transaction has not received a risk score.")},
        {"title": "Outcome", "text": outcome},
    ]
