"""PDF explanation report for one transaction (ReportLab): versions, summary sections, attributions, breakdown, disclaimers."""

from __future__ import annotations

import io
from typing import Any
from xml.sax.saxutils import escape as esc  # imported text must never be parsed as ReportLab markup

from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.transactions.models import Transaction

from . import narrative
from .models import Explanation
from .services import staleness


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


def _bars(features: list[dict[str, Any]], title: str) -> Drawing:
    top = features[:8][::-1]
    d = Drawing(170 * mm, 55 * mm)
    ch = HorizontalBarChart()
    ch.x, ch.y, ch.width, ch.height = 55 * mm, 5 * mm, 105 * mm, 45 * mm
    ch.data = [[f["contribution"] for f in top]]
    ch.categoryAxis.categoryNames = [f["label"][:34] for f in top]
    ch.categoryAxis.labels.fontSize = 6
    ch.valueAxis.labels.fontSize = 6
    ch.bars[0].fillColor = colors.HexColor("#475569")
    d.add(ch)
    return d


def build_report(tx: Transaction, explanations: list[Explanation]) -> bytes:
    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"Explanation report - {tx.transaction_id}",
    )
    by = {e.method: e for e in explanations}
    story: list[Any] = [
        Paragraph("FinGuard - transaction explanation report", styles["Title"]),
        Paragraph(f"Transaction <b>{esc(tx.transaction_id)}</b> - {esc(tx.tx_type)} - amount {tx.amount} - {tx.occurred_at:%Y-%m-%d %H:%M} UTC", styles["Normal"]),
        Spacer(1, 3 * mm), Paragraph(narrative.DISCLAIMER, styles["Italic"]), Spacer(1, 4 * mm),
    ]  # fmt: skip
    rows = [["Explanation", "Model version", "Generator", "Generated", "Status"]]
    for e in explanations:
        cur, why = staleness(e, tx)
        rows.append(
            [
                e.method,
                str(e.model_version) if e.model_version else "-",
                e.generator_version,
                f"{e.generated_at:%Y-%m-%d %H:%M}",
                "current" if cur else f"STALE: {why}",
            ]
        )
    story += [
        Paragraph("Versions and freshness", styles["Heading2"]),
        _table(rows, [28 * mm, 52 * mm, 18 * mm, 28 * mm, 54 * mm]),
    ]
    if any(not staleness(e, tx)[0] for e in explanations):
        story += [
            Spacer(1, 2 * mm),
            Paragraph(
                "<b>Warning:</b> at least one explanation is out of date; regenerate it before relying on this report.",
                styles["Normal"],
            ),
        ]
    if "summary" in by:
        story += [Spacer(1, 4 * mm), Paragraph("Investigation summary", styles["Heading2"])]
        for s in by["summary"].payload["sections"]:
            story += [Paragraph(f"<b>{esc(s['title'])}.</b> {esc(s['text'])}", styles["Normal"]), Spacer(1, 1.5 * mm)]
    for method, title in (("shap", "Model explanation (SHAP)"), ("lime", "Model explanation (LIME)")):
        if method in by:
            p = by[method].payload
            story += [
                Spacer(1, 4 * mm),
                Paragraph(title, styles["Heading2"]),
                Paragraph(esc(by[method].narrative), styles["Normal"]),
                _bars(p["features"], title),
            ]
            story.append(
                _table(
                    [
                        ["Feature", "Value", "Contribution"],
                        *[[f["label"][:48], f["display"], f"{f['contribution']:+.4f}"] for f in p["features"][:10]],
                    ],
                    [90 * mm, 40 * mm, 40 * mm],
                )
            )
            if method == "lime":
                story.append(Paragraph(esc(p["note"]), styles["Italic"]))
    if "risk_breakdown" in by:
        p = by["risk_breakdown"].payload
        story += [
            Spacer(1, 4 * mm),
            Paragraph("Risk breakdown", styles["Heading2"]),
            Paragraph(esc(by["risk_breakdown"].narrative), styles["Normal"]),
        ]
        story.append(_table([["Signal", "Value", "Weight", "Contribution", "Note"], *[[c["name"], "n/a" if c["value"] is None else f"{c['value']:.0f}", f"{(c['weight'] or 0) * 100:.0f}%",
                                                                                      "excluded" if c["contribution"] is None else f"{c['contribution']:.1f}", c["reason"][:40]] for c in p["components"].values()]],
                             [32 * mm, 20 * mm, 20 * mm, 25 * mm, 80 * mm]))  # fmt: skip
    for method, title in (("behavioral", "Behavioural deviation"), ("graph", "Network patterns")):
        if method in by:
            story += [
                Spacer(1, 4 * mm),
                Paragraph(title, styles["Heading2"]),
                Paragraph(esc(by[method].narrative), styles["Normal"]),
            ]
    if "summary" in by and by["summary"].payload.get("timeline"):
        story += [Spacer(1, 4 * mm), Paragraph("Timeline", styles["Heading2"]),
                  _table([["Time (UTC)", "Transaction", "Amount", "From", "To"], *[[t["occurred_at"][:16].replace("T", " "), t["external_id"] + (" *" if t["is_this_transaction"] else ""), t["amount"], t["sender"], t["receiver"] or "-"] for t in by["summary"].payload["timeline"]]],
                         [35 * mm, 40 * mm, 28 * mm, 35 * mm, 35 * mm])]  # fmt: skip
    story += [
        Spacer(1, 6 * mm),
        Paragraph(
            "* marks this transaction. Contributions explain a model's score, not the truth of any allegation.",
            styles["Italic"],
        ),
    ]
    doc.build(story)
    return buf.getvalue()
