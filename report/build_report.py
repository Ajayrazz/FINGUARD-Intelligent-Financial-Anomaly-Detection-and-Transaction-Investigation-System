"""Builds Project_Report_Final.docx and Project_Report_Final.pdf from the content modules.

    python report/build_report.py            # needs: python-docx, pypdf, reportlab; node + Playwright (e2e/node_modules)

DOCX: python-docx (real Word headings, a TOC field that Word refreshes on open, header/footer with PAGE fields).
PDF : the same blocks rendered to HTML, printed by headless Chromium, then headers/footers and page numbers are
      stamped on and the table of contents is filled in with page numbers found by a first pass.
"""

from __future__ import annotations

import html
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from content_a import (  # noqa: E402
    A,
    COURSE_CODE,
    COURSE_NAME,
    DOC_TITLE,
    PREPARED_FOR,
    PROJECT,
    PROJECT_FULL,
    STUDENTS,
    TERM,
)
from content_b import B  # noqa: E402
from content_c import C  # noqa: E402

BLOCKS = A + B + C
OUT_DOCX = os.path.join(HERE, "Project_Report_Final.docx")
OUT_PDF = os.path.join(HERE, "Project_Report_Final.pdf")
TMP_HTML = os.path.join(HERE, "_report.html")


CACHE = os.path.join(HERE, "_cache")


def asset(name: str) -> str:
    """Path of a figure; screenshots are re-encoded as JPEG so the DOCX and PDF stay small."""
    if not name.startswith("screens/"):
        return os.path.join(HERE, "figures", name)
    from PIL import Image

    os.makedirs(CACHE, exist_ok=True)
    out = os.path.join(CACHE, os.path.basename(name).rsplit(".", 1)[0] + ".jpg")
    if not os.path.exists(out):
        im = Image.open(os.path.join(HERE, name)).convert("RGB")
        im.thumbnail((1300, 1300))
        im.save(out, "JPEG", quality=86, optimize=True)
    return out


def toc_entries():
    return [(b[1], b[2]) for b in BLOCKS if b[0] == "h" and b[1] <= 3]


def captions(prefix: str):
    out = []
    for b in BLOCKS:
        if b[0] == "fig" and b[2].startswith(prefix):
            out.append(b[2])
        if b[0] == "table" and b[1].startswith(prefix):
            out.append(b[1])
    return out


INLINE = re.compile(r"(\*\*.+?\*\*|`.+?`)")


def runs(text: str):
    """Yield (text, bold, code, italic) pieces from the light inline markup."""
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            yield part[2:-2], True, False
        elif part.startswith("`") and part.endswith("`"):
            yield part[1:-1], False, True
        else:
            yield part, False, False


# =================================================================================================== DOCX
def build_docx(pages: dict[str, str]) -> None:
    from docx import Document
    from docx.enum.section import WD_SECTION
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT, WD_TAB_LEADER
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.27), Inches(11.69)  # A4
    for s in (sec,):
        s.left_margin = s.right_margin = Inches(1.0)
        s.top_margin, s.bottom_margin = Inches(1.0), Inches(0.9)

    st = doc.styles
    st["Normal"].font.name = "Times New Roman"
    st["Normal"].font.size = Pt(11)
    st["Normal"]._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    st["Normal"].paragraph_format.space_after = Pt(6)
    st["Normal"].paragraph_format.line_spacing = 1.12
    for name, size, before, after in (("Heading 1", 17, 18, 8), ("Heading 2", 13.5, 14, 5), ("Heading 3", 12, 10, 4), ("Heading 4", 11, 8, 3)):
        h = st[name]
        h.font.name = "Times New Roman"
        h.font.size = Pt(size)
        h.font.bold = True
        h.font.italic = name == "Heading 4"
        h.font.color.rgb = RGBColor(0, 0, 0)
        h._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
        h._element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
        h._element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")
        h.paragraph_format.space_before = Pt(before)
        h.paragraph_format.space_after = Pt(after)
        h.paragraph_format.keep_with_next = True

    def add_runs(par, text, size=None, color=None):
        for t, bold, code in runs(text):
            r = par.add_run(t)
            r.bold = bold or None
            if code:
                r.font.name = "Courier New"
                r.font.size = Pt(9.5 if size is None else size - 1)
            elif size:
                r.font.size = Pt(size)
            if color:
                r.font.color.rgb = color

    def fld(par, instr):
        for kind, txt in (("begin", None), (None, instr), ("separate", None), ("text", "1"), ("end", None)):
            r = par.add_run()
            if kind in ("begin", "separate", "end"):
                e = OxmlElement("w:fldChar")
                e.set(qn("w:fldCharType"), kind)
                r._r.append(e)
            elif kind is None:
                e = OxmlElement("w:instrText")
                e.set(qn("xml:space"), "preserve")
                e.text = txt
                r._r.append(e)
            else:
                r.text = txt

    def set_pgnum(section, fmt, start):
        sp = section._sectPr
        for old in sp.findall(qn("w:pgNumType")):
            sp.remove(old)
        e = OxmlElement("w:pgNumType")
        e.set(qn("w:fmt"), fmt)
        e.set(qn("w:start"), str(start))
        sp.append(e)

    def header_footer(section, on: bool):
        section.header.is_linked_to_previous = False
        section.footer.is_linked_to_previous = False
        for p in list(section.header.paragraphs) + list(section.footer.paragraphs):
            for r in list(p.runs):
                r._r.getparent().remove(r._r)
        if not on:
            return
        hp = section.header.paragraphs[0]
        hp.paragraph_format.left_indent = Inches(0)
        hr = hp.add_run(PROJECT)
        hr.font.size = Pt(10)
        fp = section.footer.paragraphs[0]
        fp.paragraph_format.tab_stops.add_tab_stop(Inches(6.27), WD_TAB_ALIGNMENT.RIGHT)
        r = fp.add_run("Software Requirements Specification\tPage ")
        r.font.size = Pt(10)
        fld(fp, " PAGE ")
        for rr in fp.runs[1:]:
            rr.font.size = Pt(10)

    # ------------------------------------------------------------------ cover
    header_footer(sec, False)

    def centered(text, size, bold=True, before=0, after=0):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(before)
        p.paragraph_format.space_after = Pt(after)
        r = p.add_run(text)
        r.bold = bold
        r.font.size = Pt(size)
        return p

    centered("", 11, before=80)
    centered(PROJECT, 28, before=40, after=6)
    centered(PROJECT_FULL, 12.5, bold=False, after=30)
    centered(DOC_TITLE, 20, before=20, after=26)
    centered(COURSE_CODE, 15)
    centered(COURSE_NAME, 15, after=26)
    for name, reg in STUDENTS:
        centered(name, 15, before=2)
        centered("Registration number: " + reg, 13, bold=False, after=10)
    centered("", 11, before=50)
    centered("Prepared for", 12, bold=False, before=0)
    centered(PREPARED_FOR, 12, bold=False)
    centered(TERM, 12, bold=False)

    # ------------------------------------------------------------------ front matter section
    fm = doc.add_section(WD_SECTION.NEW_PAGE)
    set_pgnum(fm, "lowerRoman", 1)
    header_footer(fm, True)

    p = doc.add_paragraph()
    r = p.add_run("Table of Contents")
    r.bold = True
    r.font.size = Pt(17)
    p.paragraph_format.space_after = Pt(10)

    entries = toc_entries()

    def toc_par(level, text, page, first=False, last=False):
        par = doc.add_paragraph()
        pf = par.paragraph_format
        pf.left_indent = Inches(0.0 if level == 1 else 0.25 if level == 2 else 0.5)
        pf.space_after = Pt(1 if level > 1 else 2)
        pf.space_before = Pt(5 if level == 1 else 0)
        pf.tab_stops.add_tab_stop(Inches(6.27), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        if first:
            for kind, txt in (("begin", None), (None, ' TOC \\o "1-3" \\h \\z \\u '), ("separate", None)):
                rr = par.add_run()
                if kind:
                    e = OxmlElement("w:fldChar")
                    e.set(qn("w:fldCharType"), kind)
                    rr._r.append(e)
                else:
                    e = OxmlElement("w:instrText")
                    e.set(qn("xml:space"), "preserve")
                    e.text = txt
                    rr._r.append(e)
        run = par.add_run(f"{text}\t{page}")
        run.bold = level == 1
        run.font.size = Pt(10.5 if level == 1 else 10)
        if last:
            rr = par.add_run()
            e = OxmlElement("w:fldChar")
            e.set(qn("w:fldCharType"), "end")
            rr._r.append(e)

    for i, (lvl, text) in enumerate(entries):
        toc_par(lvl, text, pages.get(text, ""), first=i == 0, last=i == len(entries) - 1)

    def list_of(title, prefix):
        p = doc.add_paragraph()
        p.add_run().add_break(WD_BREAK.PAGE)
        r = p.add_run(title)
        r.bold = True
        r.font.size = Pt(17)
        for cap in captions(prefix):
            par = doc.add_paragraph()
            par.paragraph_format.space_after = Pt(1)
            par.paragraph_format.tab_stops.add_tab_stop(Inches(6.27), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
            rr = par.add_run(f"{cap}\t{pages.get(cap, '')}")
            rr.font.size = Pt(10)

    list_of("List of Figures", "Figure")
    list_of("List of Tables", "Table")

    # ------------------------------------------------------------------ body section
    body = doc.add_section(WD_SECTION.NEW_PAGE)
    set_pgnum(body, "decimal", 1)
    header_footer(body, True)

    def shade(cell, color):
        tcPr = cell._tc.get_or_add_tcPr()
        e = OxmlElement("w:shd")
        e.set(qn("w:val"), "clear")
        e.set(qn("w:color"), "auto")
        e.set(qn("w:fill"), color)
        tcPr.append(e)

    first_h1 = True
    for b in BLOCKS:
        kind = b[0]
        if kind == "h":
            lvl, text = b[1], b[2]
            if lvl == 1 and not first_h1:
                doc.add_page_break()
            if lvl == 1:
                first_h1 = False
            doc.add_heading(text, level=lvl)
        elif kind == "p":
            par = doc.add_paragraph()
            add_runs(par, b[1])
        elif kind in ("bul", "num"):
            for it in b[1]:
                par = doc.add_paragraph(style="List Bullet" if kind == "bul" else "List Number")
                par.paragraph_format.space_after = Pt(2)
                add_runs(par, it)
        elif kind == "note":
            par = doc.add_paragraph()
            add_runs(par, b[1])
        elif kind == "fig":
            path = asset(b[1])
            par = doc.add_paragraph()
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            par.paragraph_format.keep_with_next = True
            par.paragraph_format.space_before = Pt(6)
            par.add_run().add_picture(path, width=Inches(min(b[3], 6.27)))
            cap = doc.add_paragraph()
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            rr = cap.add_run(b[2])
            rr.italic = True
            rr.font.size = Pt(9.5)
            cap.paragraph_format.space_after = Pt(10)
        elif kind == "table":
            _, cap, headers, rows, widths = b
            cp = doc.add_paragraph()
            cp.paragraph_format.keep_with_next = True
            cp.paragraph_format.space_before = Pt(8)
            rr = cp.add_run(cap)
            rr.bold = True
            rr.font.size = Pt(10)
            t = doc.add_table(rows=1, cols=len(headers))
            t.style = "Table Grid"
            t.alignment = WD_TABLE_ALIGNMENT.CENTER
            t.autofit = False
            total = 6.27
            ws = [total * w / sum(widths) for w in widths]
            for i, h in enumerate(headers):
                c = t.rows[0].cells[i]
                c.width = Inches(ws[i])
                shade(c, "D9E2F3")
                c.paragraphs[0].paragraph_format.space_after = Pt(1)
                x = c.paragraphs[0].add_run(h)
                x.bold = True
                x.font.size = Pt(9)
            trPr = t.rows[0]._tr.get_or_add_trPr()
            th = OxmlElement("w:tblHeader")
            th.set(qn("w:val"), "true")
            trPr.append(th)
            for row in rows:
                cells = t.add_row().cells
                for i, v in enumerate(row):
                    cells[i].width = Inches(ws[i])
                    par = cells[i].paragraphs[0]
                    par.paragraph_format.space_after = Pt(1)
                    par.paragraph_format.line_spacing = 1.0
                    add_runs(par, str(v), size=9)
                    for rn in par.runs:
                        if rn.font.size is None:
                            rn.font.size = Pt(9)
                cant = OxmlElement("w:cantSplit")
                cant.set(qn("w:val"), "true")
                t.rows[-1]._tr.get_or_add_trPr().append(cant)
            doc.add_paragraph().paragraph_format.space_after = Pt(2)

    # Word refreshes fields (the table of contents) when the file is opened
    settings = doc.settings.element
    uf = OxmlElement("w:updateFields")
    uf.set(qn("w:val"), "true")
    compat = settings.find(qn("w:compat"))
    if compat is not None:
        compat.addprevious(uf)  # schema order: updateFields comes before compat
    else:
        settings.append(uf)
    doc.core_properties.title = f"{PROJECT}: {DOC_TITLE}"
    doc.core_properties.author = ", ".join(n for n, _ in STUDENTS)
    doc.core_properties.subject = PROJECT_FULL
    doc.save(OUT_DOCX)
    print("wrote", OUT_DOCX)


# =================================================================================================== HTML / PDF
CSS = """
@page { size: A4; margin: 24mm 22mm 24mm 22mm; }
html { font-family: 'Times New Roman', Times, serif; font-size: 11pt; color: #000; }
body { margin: 0; line-height: 1.38; }
h1 { font-size: 17pt; margin: 0 0 10pt; page-break-before: always; page-break-after: avoid; }
h1.first { page-break-before: auto; }
h2 { font-size: 13.5pt; margin: 16pt 0 5pt; page-break-after: avoid; }
h3 { font-size: 12pt; margin: 12pt 0 4pt; page-break-after: avoid; }
h4 { font-size: 11pt; font-style: italic; margin: 9pt 0 3pt; page-break-after: avoid; }
p { margin: 0 0 6pt; text-align: justify; }
ul, ol { margin: 0 0 6pt 0; padding-left: 20pt; }
li { margin-bottom: 2pt; text-align: justify; }
code { font-family: 'Courier New', monospace; font-size: 9.5pt; }
figure { margin: 8pt 0 10pt; text-align: center; page-break-inside: avoid; }
figure img { max-width: 100%; height: auto; border: 0.5pt solid #999; }
figure.diagram img { border: 0; }
figcaption { font-size: 9.5pt; font-style: italic; margin-top: 3pt; }
.tcap { font-weight: bold; font-size: 10pt; margin: 10pt 0 3pt; page-break-after: avoid; }
table { border-collapse: collapse; width: 100%; font-size: 9pt; margin-bottom: 8pt; }
th, td { border: 0.6pt solid #444; padding: 2.5pt 4pt; vertical-align: top; text-align: left; }
th { background: #d9e2f3; }
tr { page-break-inside: avoid; }
thead { display: table-header-group; }
.cover { text-align: center; page-break-after: always; }
.cover .proj { font-size: 28pt; font-weight: bold; margin-top: 30mm; }
.cover .full { font-size: 12.5pt; margin: 6pt 18mm 18mm; }
.cover .title { font-size: 20pt; font-weight: bold; margin-bottom: 16mm; }
.cover .big { font-size: 15pt; font-weight: bold; }
.cover .reg { font-size: 13pt; margin-bottom: 6pt; }
.cover .foot { margin-top: 30mm; font-size: 12pt; }
.toc { page-break-after: always; }
.toc h1 { page-break-before: auto; }
.toc .e { display: flex; align-items: baseline; font-size: 10.5pt; line-height: 1.3; }
.toc .e .t { white-space: nowrap; }
.toc .e .d { flex: 1; border-bottom: 1pt dotted #555; margin: 0 3pt; transform: translateY(-2pt); }
.toc .l1 { font-weight: bold; margin-top: 5pt; }
.toc .l2 { padding-left: 14pt; }
.toc .l3 { padding-left: 28pt; font-size: 10pt; }
.lof { page-break-before: always; }
.lof h1 { page-break-before: auto; }
.mark { font-size: 1px; color: #fff; line-height: 1px; height: 1px; }
"""


def inline_html(text: str) -> str:
    out = []
    for t, bold, code in runs(text):
        e = html.escape(t)
        out.append(f"<b>{e}</b>" if bold else f"<code>{e}</code>" if code else e)
    return "".join(out)


def build_html(pages: dict[str, str]) -> str:
    h = ["<!doctype html><html><head><meta charset='utf-8'><style>", CSS, "</style></head><body>"]
    # cover
    h.append("<div class='cover'>")
    h.append(f"<div class='proj'>{html.escape(PROJECT)}</div><div class='full'>{html.escape(PROJECT_FULL)}</div>")
    h.append(f"<div class='title'>{html.escape(DOC_TITLE)}</div>")
    h.append(f"<div class='big'>{html.escape(COURSE_CODE)}</div><div class='big' style='margin-bottom:14mm'>{html.escape(COURSE_NAME)}</div>")
    for n, r in STUDENTS:
        h.append(f"<div class='big'>{html.escape(n)}</div><div class='reg'>Registration number: {r}</div>")
    h.append(f"<div class='foot'>Prepared for<br>{html.escape(PREPARED_FOR)}<br>{html.escape(TERM)}</div></div>")

    def toc_rows(items):
        rows = []
        for lvl, text, page in items:
            rows.append(f"<div class='e l{lvl}'><span class='t'>{html.escape(text)}</span><span class='d'></span><span>{page}</span></div>")
        return "".join(rows)

    h.append("<div class='toc'><h1>Table of Contents</h1>")
    h.append(toc_rows([(lvl, t, pages.get(t, "00")) for lvl, t in toc_entries()]))
    h.append("</div>")
    for title, prefix in (("List of Figures", "Figure"), ("List of Tables", "Table")):
        h.append(f"<div class='lof'><h1>{title}</h1>")
        h.append(toc_rows([(3, c, pages.get(c, "00")) for c in captions(prefix)]))
        h.append("</div>")

    first = True
    for b in BLOCKS:
        k = b[0]
        if k == "h":
            lvl, text = b[1], b[2]
            if lvl == 1:
                mark = "<div class='mark'>BODYSTARTMARK</div>" if first else ""
                h.append(f"{mark}<h1 class='{'first' if first else ''}'>{html.escape(text)}</h1>")
                first = False
            else:
                h.append(f"<h{lvl}>{html.escape(text)}</h{lvl}>")
        elif k == "p":
            h.append(f"<p>{inline_html(b[1])}</p>")
        elif k in ("bul", "num"):
            tag = "ul" if k == "bul" else "ol"
            h.append(f"<{tag}>" + "".join(f"<li>{inline_html(i)}</li>" for i in b[1]) + f"</{tag}>")
        elif k == "fig":
            path = asset(b[1])
            cls = "diagram" if not b[1].startswith("screens/") else ""
            wpct = min(100, int(b[3] / 6.27 * 100))
            h.append(f"<figure class='{cls}'><img src='file://{path}' style='width:{wpct}%'><figcaption>{html.escape(b[2])}</figcaption></figure>")
        elif k == "table":
            _, cap, headers, rows, widths = b
            h.append(f"<div class='tcap'>{html.escape(cap)}</div><table><colgroup>" + "".join(f"<col style='width:{w}%'>" for w in widths) + "</colgroup><thead><tr>")
            h.append("".join(f"<th>{html.escape(x)}</th>" for x in headers) + "</tr></thead><tbody>")
            for row in rows:
                h.append("<tr>" + "".join(f"<td>{inline_html(str(v))}</td>" for v in row) + "</tr>")
            h.append("</tbody></table>")
    h.append("</body></html>")
    return "".join(h)


def render_pdf(html_text: str, out_pdf: str) -> None:
    with open(TMP_HTML, "w", encoding="utf-8") as f:
        f.write(html_text)
    subprocess.run(["node", os.path.join(HERE, "html_to_pdf.mjs"), TMP_HTML, out_pdf], check=True)


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def find_pages(pdf_path: str):
    """Return (body_start_index, {heading/caption text: label}) using the text of a first-pass PDF."""
    from pypdf import PdfReader

    rd = PdfReader(pdf_path)
    texts = [norm(p.extract_text() or "") for p in rd.pages]
    start = next(i for i, t in enumerate(texts) if "bodystartmark" in t)
    labels: dict[str, str] = {}
    cursor = start
    for lvl, text in toc_entries():
        key = norm(text)
        for i in range(cursor, len(texts)):
            if key in texts[i]:
                labels[text] = str(i - start + 1)
                cursor = i
                break
    for prefix in ("Figure", "Table"):
        cursor = start
        for cap in captions(prefix):
            key = norm(cap[:60])
            for i in range(cursor, len(texts)):
                if key in texts[i]:
                    labels[cap] = str(i - start + 1)
                    cursor = i
                    break
    return start, labels, len(texts)


def roman(n: int) -> str:
    vals = [(10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out


def stamp(pdf_in: str, pdf_out: str, start: int) -> None:
    from pypdf import PdfReader, PdfWriter
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    wr = PdfWriter(clone_from=pdf_in)
    w, h = A4
    for i, page in enumerate(wr.pages):
        if i == 0:  # no header or footer on the cover
            continue
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        label = roman(i) if i < start else str(i - start + 1)
        c.setFont("Times-Roman", 10)
        c.drawString(22 * 2.835, h - 14 * 2.835, PROJECT)
        c.drawString(22 * 2.835, 12 * 2.835, "Software Requirements Specification")
        c.drawRightString(w - 22 * 2.835, 12 * 2.835, f"Page {label}")
        c.setLineWidth(0.4)
        c.line(22 * 2.835, 17 * 2.835, w - 22 * 2.835, 17 * 2.835)
        c.save()
        buf.seek(0)
        page.merge_page(PdfReader(buf).pages[0])
    for pg in wr.pages:
        pg.compress_content_streams()
    wr.compress_identical_objects(remove_duplicates=True, remove_unreferenced=True)
    wr.add_metadata({"/Title": f"{PROJECT}: {DOC_TITLE}", "/Author": ", ".join(n for n, _ in STUDENTS)})
    with open(pdf_out, "wb") as f:
        wr.write(f)


def main() -> None:
    # pass 1: render with placeholder page numbers to learn where everything lands
    tmp1 = os.path.join(HERE, "_pass1.pdf")
    render_pdf(build_html({}), tmp1)
    start, labels, n1 = find_pages(tmp1)
    # pass 2: real numbers (same layout: the placeholders have the same height)
    tmp2 = os.path.join(HERE, "_pass2.pdf")
    render_pdf(build_html(labels), tmp2)
    start2, labels2, n2 = find_pages(tmp2)
    assert start2 == start, "front matter length changed between passes"
    stamp(tmp2, OUT_PDF, start2)
    print("wrote", OUT_PDF, f"({n2} pages, body starts on physical page {start2 + 1})")
    build_docx(labels2)
    for f in (tmp1, tmp2, TMP_HTML):
        try:
            os.remove(f)
        except OSError:
            pass
    import shutil

    shutil.rmtree(CACHE, ignore_errors=True)
    missing = [t for _, t in toc_entries() if t not in labels2]
    print("headings without a page number:", len(missing), missing[:5])


if __name__ == "__main__":
    main()
