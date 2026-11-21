# Project report (SRS format)

`Project_Report_Final.docx` (editable) and `Project_Report_Final.pdf` follow the supplied *Project Report Format* (IEEE-style
Software Requirements Specification): cover, table of contents, 1 Introduction, 2 General Description, 3 Specific
Requirements (3.1, 3.2, 3.5, 3.7, 3.9), 4 Analysis Models, A Appendices. Lists of figures and tables were added after the
table of contents.

## What still has to be filled in (marked in square brackets in the report)
Course code, course name, academic term, institution and department, supervisor, submission date, and the signed declaration,
certificate and acknowledgement (Appendix A.1; the template has no such pages, so only placeholders are provided).

## How the files are produced
| Step | Command | Output |
|---|---|---|
| Screenshots of the running app (dev stack on :5173) | `FG_REFRESH=<refresh token> FG_TX=<tx id> FG_ACC=<account id> node report/capture_screens.mjs` | `report/screens/*.png` (mailbox addresses are replaced by example.com) |
| Diagrams | `python report/make_diagrams.py` (matplotlib) | `report/figures/*.png` |
| Report | `python report/build_report.py` (python-docx, pypdf, reportlab, Pillow; Chromium through `e2e/node_modules`) | the DOCX and PDF |

Content lives in `content_a.py` (sections 1-2), `content_b.py` (3.1-3.2) and `content_c.py` (3.5-4 and appendices).
Every statement was checked against the code or the project documents (docs 00-24); numbers come from the documented runs.

## Notes
* The PDF is rendered from the same content by headless Chromium, with headers, footers and page numbers added afterwards
  (front matter in Roman numerals, body from 1). The DOCX uses a Word table-of-contents field and asks Word to refresh it on
  opening; page numbers cached in it come from the PDF and may shift by a page until Word updates them (click *Yes*).
* A refresh token is needed only to take the screenshots; none is stored in the repository.
