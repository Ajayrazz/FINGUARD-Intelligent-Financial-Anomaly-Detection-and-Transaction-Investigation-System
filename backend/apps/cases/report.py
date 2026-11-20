"""PDF case report (ReportLab): summary, outcome, timeline, alerts, transactions, notes, evidence hashes, disclaimer."""

from __future__ import annotations

import io
from typing import Any
from xml.sax.saxutils import escape as esc  # user text must never be parsed as ReportLab markup

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import Case


def _table(rows: list[list[str]], widths: list[float]) -> Table:
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return t


def build_report(case: Case) -> bytes:
    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"Case report {case.case_ref}",
    )
    P = lambda text, style="Normal": Paragraph(text, styles[style])  # noqa: E731
    story: list[Any] = [
        P(f"FinGuard - case report {case.case_ref}", "Title"),
        P(f"<b>{esc(case.title)}</b>"),
        Spacer(1, 3 * mm),
    ]
    state = (
        "CLOSED"
        if case.status == "closed"
        else f"IN PROGRESS ({case.status.replace('_', ' ')}) - this is an interim report"
    )
    story.append(_table([["Status", "Priority", "Opened", "Assignee", "Outcome"],
                         [state, case.priority, f"{case.opened_at:%Y-%m-%d}", case.assignee.email if case.assignee else "-", case.outcome.replace("_", " ") or "none yet"]],
                        [50 * mm, 22 * mm, 25 * mm, 50 * mm, 33 * mm]))  # fmt: skip
    if case.description:
        story += [Spacer(1, 3 * mm), P(esc(case.description))]
    if case.resolution_summary:
        who = case.resolved_by.email if case.resolved_by else "-"
        story += [
            Spacer(1, 4 * mm),
            P("Resolution", "Heading2"),
            P(esc(case.resolution_summary)),
            P(
                f"Resolved by {esc(who)} on {case.resolved_at:%Y-%m-%d %H:%M} UTC. The outcome is the investigator's determination.",
                "Italic",
            ),
        ]
    story += [Spacer(1, 4 * mm), P("Alerts", "Heading2")]
    story.append(
        _table(
            [
                ["#", "Type", "Severity", "Reason"],
                *[
                    [
                        str(link.alert_id),
                        link.alert.alert_type.replace("_", " "),
                        link.alert.severity,
                        link.alert.reason[:110],
                    ]
                    for link in case.case_alerts.select_related("alert")
                ],
            ]
            or [["-"]],
            [12 * mm, 40 * mm, 22 * mm, 106 * mm],
        )
    )
    story += [Spacer(1, 4 * mm), P("Transactions in the case", "Heading2")]
    rows = [["Transaction", "Time (UTC)", "Type", "Amount", "From", "To"]]
    for link in case.case_transactions.select_related("transaction__sender", "transaction__receiver"):
        t = link.transaction
        rows.append(
            [
                t.transaction_id,
                f"{t.occurred_at:%Y-%m-%d %H:%M}",
                t.tx_type,
                str(t.amount),
                t.sender.account_ref,
                t.receiver.account_ref if t.receiver else "-",
            ]
        )
    story.append(_table(rows, [34 * mm, 32 * mm, 22 * mm, 28 * mm, 30 * mm, 30 * mm]))
    story += [Spacer(1, 4 * mm), P("Notes and comments (latest text)", "Heading2")]
    for n in case.notes.select_related("author"):
        last = n.revisions.order_by("-revision").first()
        story.append(
            P(
                f"<b>{esc(n.kind)}</b> by {esc(n.author.email)}, {n.created_at:%Y-%m-%d %H:%M}{' (edited)' if n.revisions.count() > 1 else ''}: {esc(last.body) if last else ''}"
            )
        )
    story += [Spacer(1, 4 * mm), P("Evidence (recorded hashes)", "Heading2")]
    story.append(
        _table(
            [
                ["File", "Type", "Size", "SHA-256"],
                *[[e.original_name[:40], e.mime, str(e.size), e.sha256] for e in case.evidence.all()],
            ]
            or [["-"]],
            [45 * mm, 25 * mm, 18 * mm, 92 * mm],
        )
    )
    story += [Spacer(1, 4 * mm), P("Timeline", "Heading2")]
    story.append(
        _table(
            [
                ["Time (UTC)", "Event", "By", "Change"],
                *[
                    [
                        f"{e.created_at:%Y-%m-%d %H:%M}",
                        e.event_type.replace("_", " "),
                        e.actor.email if e.actor else "system",
                        (f"{e.from_status} -> {e.to_status}" if e.to_status else ""),
                    ]
                    for e in case.events.select_related("actor")
                ],
            ],
            [34 * mm, 45 * mm, 55 * mm, 46 * mm],
        )
    )
    story += [
        Spacer(1, 6 * mm),
        P(
            "This report records the work done on a case. Scores, alerts and model outputs it mentions are automated indicators for prioritising review, not proof of wrongdoing; only the recorded investigator outcome is a determination.",
            "Italic",
        ),
    ]
    doc.build(story)
    return buf.getvalue()
