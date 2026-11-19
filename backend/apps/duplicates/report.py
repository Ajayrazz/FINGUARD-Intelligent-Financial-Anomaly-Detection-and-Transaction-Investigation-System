"""PDF investigation report for one duplicate candidate (ReportLab)."""

from __future__ import annotations

import io
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import DuplicateCandidate
from .serializers import record_detail


def _kv(rows: list[list[str]], widths: list[float]) -> Table:
    t = Table(rows, colWidths=widths)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke), ("FONTSIZE", (0, 0), (-1, -1), 8)]))  # fmt: skip
    return t


def _flatten(prefix: str, value: Any, out: list[list[str]]) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            _flatten(f"{prefix}.{k}" if prefix else str(k), v, out)
    else:
        out.append([prefix, str(value)])


def build_report(cand: DuplicateCandidate) -> bytes:
    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm,
                            title=f"Duplicate candidate {cand.pk}")  # fmt: skip
    story: list[Any] = [Paragraph(f"FinGuard - duplicate investigation report #{cand.pk}", styles["Title"]),
                        Paragraph(f"{cand.get_kind_display()} candidate - class <b>{cand.match_class}</b> - similarity score "
                                  f"<b>{cand.similarity_score:.1f}</b> / 100", styles["Normal"]), Spacer(1, 6 * mm)]  # fmt: skip
    story.append(Paragraph("Records compared", styles["Heading2"]))
    a, b = (
        record_detail(cand.record_a_type, cand.record_a_id) or {},
        record_detail(cand.record_b_type, cand.record_b_id) or {},
    )
    keys = [k for k in dict.fromkeys([*a, *b]) if k not in ("type",)]
    story.append(
        _kv(
            [["Field", "Record A", "Record B"], *[[k, str(a.get(k, "-")), str(b.get(k, "-"))] for k in keys]],
            [38 * mm, 70 * mm, 70 * mm],
        )
    )
    story += [Spacer(1, 5 * mm), Paragraph("Evidence", styles["Heading2"])]
    rows: list[list[str]] = []
    _flatten("", cand.evidence, rows)
    story.append(_kv([["Signal", "Value"], *rows], [70 * mm, 108 * mm]))
    story += [Spacer(1, 5 * mm), Paragraph("Review", styles["Heading2"])]
    who = cand.reviewed_by.email if cand.reviewed_by else "-"
    story.append(_kv([["Status", "Reviewed by", "Reviewed at", "Notes"],
                      [cand.review_status, who, cand.reviewed_at.isoformat() if cand.reviewed_at else "-", cand.notes or "-"]],
                     [38 * mm, 45 * mm, 40 * mm, 55 * mm]))  # fmt: skip
    story += [Spacer(1, 6 * mm), Paragraph(
        "The similarity score and class are automated evidence to prioritise human review. They are not proof that records are "
        "duplicates; only the recorded review decision is a determination.", styles["Italic"])]  # fmt: skip
    doc.build(story)
    return buf.getvalue()
