"""Draws every diagram used in the project report (white background, print friendly).

Run:  python report/make_diagrams.py   (needs matplotlib)
Facts drawn here come from the code base: backend/apps/*/models.py (46 models), apps/cases/models.py (TRANSITIONS),
apps/accounts/registry.py (roles), docker-compose*.yml (services), risk_engine_lib/__init__.py (components).
"""

from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Ellipse, FancyBboxPatch, Polygon  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT, exist_ok=True)

INK = "#1f2937"
BLUE = "#dbeafe"
BLUE_E = "#2563eb"
VIOLET = "#ede9fe"
VIOLET_E = "#6d28d9"
GREEN = "#dcfce7"
GREEN_E = "#15803d"
AMBER = "#fef3c7"
AMBER_E = "#b45309"
RED = "#fee2e2"
RED_E = "#b91c1c"
GREY = "#f3f4f6"
GREY_E = "#6b7280"


def canvas(w: float, h: float, scale: float = 0.62):
    fig, ax = plt.subplots(figsize=(w * scale, h * scale))
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def save(fig, name: str) -> None:
    fig.savefig(os.path.join(OUT, name + ".png"), dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", name)


def box(ax, cx, cy, w, h, text, fc=BLUE, ec=BLUE_E, fs=9, bold=False, lw=1.3, round_=0.12, color=INK, ls="-"):
    p = FancyBboxPatch((cx - w / 2, cy - h / 2), w, h, boxstyle=f"round,pad=0,rounding_size={round_}", fc=fc, ec=ec, lw=lw, ls=ls)
    ax.add_patch(p)
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs, color=color, fontweight="bold" if bold else "normal", linespacing=1.25)
    return (cx, cy, w, h)


def arrow(ax, p1, p2, label=None, ls="-", color=INK, lw=1.2, fs=7.5, off=(0, 0.15), style="-|>", rad=0.0, lab_pos=0.5, ha="center"):
    ax.annotate("", xy=p2, xytext=p1, arrowprops=dict(arrowstyle=style, color=color, lw=lw, ls=ls, connectionstyle=f"arc3,rad={rad}", shrinkA=0, shrinkB=0))
    if label:
        x = p1[0] + (p2[0] - p1[0]) * lab_pos + off[0]
        y = p1[1] + (p2[1] - p1[1]) * lab_pos + off[1]
        ax.text(x, y, label, ha=ha, va="center", fontsize=fs, color=color, bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.9))


def actor(ax, x, y, label, fs=8.5):
    ax.add_patch(plt.Circle((x, y + 0.62), 0.17, fc="white", ec=INK, lw=1.3))
    ax.plot([x, x], [y + 0.45, y - 0.05], color=INK, lw=1.3)
    ax.plot([x - 0.3, x + 0.3], [y + 0.3, y + 0.3], color=INK, lw=1.3)
    ax.plot([x, x - 0.25], [y - 0.05, y - 0.5], color=INK, lw=1.3)
    ax.plot([x, x + 0.25], [y - 0.05, y - 0.5], color=INK, lw=1.3)
    ax.text(x, y - 0.8, label, ha="center", va="top", fontsize=fs, color=INK, fontweight="bold")


def title(ax, x, y, text, fs=11):
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, fontweight="bold", color=INK)


# ----------------------------------------------------------------------------------------------- 1 architecture
def architecture():
    fig, ax = canvas(16, 10.4)
    title(ax, 8, 10.0, "FinGuard system architecture (modular monolith)")
    # clients
    box(ax, 7.2, 8.8, 6.4, 0.9, "Web browser: React 19 single-page app\nTypeScript, Tailwind 4, ECharts, React Flow", GREY, GREY_E, 8.2, True)
    box(ax, 13.4, 8.8, 3.6, 0.9, "E-mail inbox\n(verification, reset, alerts)", GREY, GREY_E, 8)
    # edge
    box(ax, 7.2, 7.4, 7.4, 0.8, "Edge: Vite proxy (development) / Caddy 2 HTTPS (production)", AMBER, AMBER_E, 8.2, True)
    arrow(ax, (7.2, 8.35), (7.2, 7.8), "HTTPS  /  WSS")
    # django
    ax.add_patch(FancyBboxPatch((1.2, 3.55), 10.2, 3.0, boxstyle="round,pad=0,rounding_size=0.15", fc="#f8fafc", ec=BLUE_E, lw=1.6))
    ax.text(1.45, 6.3, "Django 5.2 backend, served by Daphne (ASGI)", fontsize=9.5, fontweight="bold", color=BLUE_E, va="center")
    box(ax, 3.2, 5.35, 3.4, 0.95, "Django REST Framework\n/api/v1 + OpenAPI", BLUE, BLUE_E, 8)
    box(ax, 6.8, 5.35, 3.0, 0.95, "Channels (WebSocket)\nalerts, imports, cases", BLUE, BLUE_E, 8)
    box(ax, 10.0, 5.35, 2.0, 0.95, "SimpleJWT\n+ RBAC", BLUE, BLUE_E, 8.2)
    box(ax, 3.2, 4.2, 3.4, 0.8, "Service layer (14 apps)", VIOLET, VIOLET_E, 8.5, True)
    box(ax, 6.8, 4.2, 3.0, 0.8, "ml_engine / graph / risk /\nduplicates libraries", VIOLET, VIOLET_E, 8)
    box(ax, 10.0, 4.2, 2.0, 0.8, "Audit log\n(DB triggers)", VIOLET, VIOLET_E, 8)
    arrow(ax, (8, 7.0), (8, 6.55))
    # workers
    ax.add_patch(FancyBboxPatch((12.2, 3.55), 3.4, 3.0, boxstyle="round,pad=0,rounding_size=0.15", fc="#f8fafc", ec=GREEN_E, lw=1.6))
    ax.text(12.4, 6.3, "Background processing", fontsize=9.5, fontweight="bold", color=GREEN_E, va="center")
    box(ax, 13.9, 5.35, 2.9, 0.95, "Celery worker\nimport, detect, risk,\ngraph, OCR, PDF, mail", GREEN, GREEN_E, 7.6)
    box(ax, 13.9, 4.2, 2.9, 0.8, "Celery beat\nhourly analytics rollup", GREEN, GREEN_E, 7.4)
    arrow(ax, (11.4, 5.35), (12.45, 5.35), "tasks", off=(0, 0.28))
    # data
    box(ax, 3.0, 1.9, 4.2, 1.2, "PostgreSQL 16\nsystem of record (46 models)\nappend-only audit", GREEN, GREEN_E, 8.2, True)
    box(ax, 7.9, 1.9, 3.4, 1.2, "Redis 7\nCelery broker, Channels\nlayer, throttle cache", AMBER, AMBER_E, 8.2, True)
    box(ax, 11.9, 1.9, 3.4, 1.2, "Neo4j 5 Community\n(optional) rebuildable\ngraph projection", GREY, GREY_E, 8.2, True)
    arrow(ax, (3.0, 3.55), (3.0, 2.5), "SQL")
    arrow(ax, (7.9, 3.55), (7.9, 2.5), "pub/sub")
    arrow(ax, (12.0, 3.55), (12.0, 2.5), "Bolt (sync)", ls="--")
    # file/media + smtp
    box(ax, 15.2, 1.9, 1.4, 1.2, "Media\nvolume", GREY, GREY_E, 8)
    arrow(ax, (14.2, 3.55), (15.0, 2.5), "files")
    box(ax, 13.4, 7.4, 3.2, 0.8, "SMTP server", GREY, GREY_E, 8.5)
    arrow(ax, (13.9, 6.55), (13.6, 7.0), "mail")
    arrow(ax, (13.4, 8.35), (13.4, 7.8), "delivers", ls="--")
    ax.text(8, 0.55, "Solid arrows: runtime calls.  Dashed: optional / one-way projection.  PostgreSQL is authoritative; Neo4j can be rebuilt from it.", ha="center", fontsize=8, color=GREY_E)
    save(fig, "fig_architecture")


# ----------------------------------------------------------------------------------------------- 2 use case
def use_case():
    fig, ax = canvas(17, 12.4)
    title(ax, 8.5, 12.0, "Use case diagram")
    ax.add_patch(FancyBboxPatch((4.0, 0.4), 9.0, 11.0, boxstyle="round,pad=0,rounding_size=0.2", fc="white", ec=GREY_E, lw=1.5))
    ax.text(8.5, 11.15, "FinGuard", ha="center", fontsize=10, fontweight="bold", color=GREY_E)
    ucs = {
        "reg": (8.5, 10.4, "Register and confirm e-mail"),
        "login": (8.5, 9.5, "Sign in / reset password"),
        "imp": (8.5, 8.6, "Import transactions (CSV, XLSX, API)"),
        "mon": (8.5, 7.7, "Search and view transactions"),
        "det": (8.5, 6.8, "Run anomaly / behaviour / graph analysis"),
        "dup": (8.5, 5.9, "Scan and review duplicates (OCR)"),
        "risk": (8.5, 5.0, "Score risk and view explanation"),
        "alert": (8.5, 4.1, "Triage alerts"),
        "case": (8.5, 3.2, "Investigate cases and evidence"),
        "dash": (8.5, 2.3, "View analytics and export reports"),
        "adm": (8.5, 1.4, "Manage users, roles, risk and alert policy"),
        "aud": (11.3, 1.4, "Read audit log"),
    }
    pos = {}
    for k, (x, y, t) in ucs.items():
        w = 4.9 if k != "aud" else 2.9
        ax.add_patch(Ellipse((x, y), w, 0.74, fc=BLUE, ec=BLUE_E, lw=1.2))
        ax.text(x, y, t, ha="center", va="center", fontsize=7.6, color=INK)
        pos[k] = (x, y, w)
    ax.patches[-1].set_center((11.9, 1.4))
    pos["aud"] = (11.9, 1.4, 2.9)
    ax.texts[-1].set_position((11.9, 1.4))
    ax.patches[-2].set_center((6.9, 1.4))
    ax.texts[-2].set_position((6.9, 1.4))
    pos["adm"] = (6.9, 1.4, 4.9)
    actors = {
        "New user": (1.6, 10.4, ["reg"]),
        "Super Admin": (1.6, 7.9, ["login", "adm", "imp", "mon", "det", "risk", "alert", "case", "dash", "aud"]),
        "Financial Analyst": (1.6, 5.3, ["login", "imp", "mon", "det", "dup", "risk", "alert", "dash"]),
        "Fraud Investigator": (15.4, 7.4, ["login", "mon", "risk", "alert", "case", "dup"]),
        "Auditor": (15.4, 4.3, ["login", "aud", "case", "mon"]),
        "Management": (15.4, 1.8, ["login", "dash"]),
    }
    for name, (x, y, links) in actors.items():
        actor(ax, x, y, name)
        for k in links:
            ux, uy, w = pos[k]
            sx = ux - w / 2 + 0.05 if x < 8 else ux + w / 2 - 0.05
            ax.plot([x + (0.35 if x < 8 else -0.35), sx], [y + 0.1, uy], color=GREY_E, lw=0.7, alpha=0.7)
    ax.text(8.5, 0.12, "Registration needs e-mail confirmation and a Super Admin's approval; every other use case is limited by the role's permissions.", ha="center", fontsize=7.8, color=GREY_E)
    save(fig, "fig_use_case")


# ----------------------------------------------------------------------------------------------- 3 DFD level 0
def dfd0():
    fig, ax = canvas(17, 8.2)
    title(ax, 8.5, 7.85, "Data flow diagram, level 0 (context)")
    cx, cy, a, b = 8.5, 3.9, 3.0, 3.2
    ax.add_patch(Ellipse((cx, cy), 2 * a, 2 * b, fc=BLUE, ec=BLUE_E, lw=2))
    ax.text(cx, cy, "0\nFinGuard\nplatform", ha="center", va="center", fontsize=13, fontweight="bold", color=INK)

    def edge_x(y, left=True):
        import math

        dx = a * math.sqrt(max(1 - ((y - cy) / b) ** 2, 0.01))
        return cx - dx if left else cx + dx

    def ent(x, y, t):
        box(ax, x, y, 3.2, 1.2, t, GREY, GREY_E, 8.6, True, round_=0.03)

    ent(1.8, 6.4, "Authorised users\n(5 roles)")
    ent(1.8, 3.9, "New applicant")
    ent(1.8, 1.4, "Data sources\nCSV, XLSX, API,\ninvoice images")
    ent(15.2, 5.9, "Mail server (SMTP)")
    ent(15.2, 1.9, "Neo4j graph store\n(optional)")
    for y, i_lab, o_lab in [(6.4, "credentials, queries,\nreview decisions", "pages, scores, alerts,\nreports (PDF / CSV)"), (3.9, "registration data,\nconfirmation token", "status messages")]:
        arrow(ax, (3.4, y + 0.3), (edge_x(y + 0.3), y + 0.3), i_lab, off=(0, 0.5), fs=7.2)
        arrow(ax, (edge_x(y - 0.3), y - 0.3), (3.4, y - 0.3), o_lab, off=(0, -0.55), fs=7.2)
    arrow(ax, (3.4, 1.4), (edge_x(1.4), 1.4), "transaction files,\ninvoice images", off=(0, 0.5), fs=7.2)
    arrow(ax, (edge_x(5.9, False), 5.9), (13.6, 5.9), "verification, reset,\nalert e-mails", off=(0, 0.5), fs=7.2)
    arrow(ax, (edge_x(1.9, False), 1.9), (13.6, 1.9), "graph projection\n(accounts, edges)", off=(0, 0.5), fs=7.2, ls="--")
    save(fig, "fig_dfd0")


# ----------------------------------------------------------------------------------------------- 4 DFD level 1
def dfd1():
    fig, ax = canvas(17, 11.2)
    title(ax, 8.5, 10.85, "Data flow diagram, level 1")

    def proc(x, y, n, t, w=3.2):
        ax.add_patch(Ellipse((x, y), w, 1.5, fc=BLUE, ec=BLUE_E, lw=1.4))
        ax.text(x, y, f"{n}\n{t}", ha="center", va="center", fontsize=8, fontweight="bold", color=INK)

    def store(x, y, t, w=3.0):
        ax.plot([x - w / 2, x + w / 2], [y + 0.32, y + 0.32], color=INK, lw=1.4)
        ax.plot([x - w / 2, x + w / 2], [y - 0.32, y - 0.32], color=INK, lw=1.4)
        ax.text(x, y, t, ha="center", va="center", fontsize=7.4, color=INK)

    def ent(x, y, t):
        box(ax, x, y, 2.4, 0.85, t, GREY, GREY_E, 8.2, True, round_=0.03)

    ent(1.5, 9.3, "User / role")
    ent(1.5, 6.1, "Data source")
    box(ax, 16.0, 3.1, 1.9, 0.85, "Mail\nserver", GREY, GREY_E, 8.2, True, round_=0.03)
    proc(4.8, 9.3, "1.0", "Authenticate,\nregister, authorise")
    proc(4.8, 6.1, "2.0", "Import and\nvalidate")
    proc(9.0, 6.1, "3.0", "Detect: ML, behaviour,\ngraph, duplicates", 3.9)
    proc(13.0, 6.1, "4.0", "Score risk,\nexplain")
    proc(13.0, 3.1, "5.0", "Raise alerts")
    proc(8.7, 3.1, "6.0", "Manage cases")
    proc(4.4, 3.1, "7.0", "Analytics,\nreports")
    store(9.6, 9.3, "D1  Users, roles, audit log")
    store(4.8, 7.8, "D2  Datasets, import jobs", 3.1)
    store(9.0, 7.8, "D3  Transactions, accounts", 3.1)
    store(14.2, 7.8, "D4  Predictions, behaviour, graph, duplicates", 4.6)
    store(13.0, 1.3, "D5  Alerts, risk, explanations", 3.4)
    store(8.7, 1.3, "D6  Cases, notes, evidence", 3.2)
    store(4.4, 1.3, "D7  Daily aggregates", 2.8)
    # 1.0
    arrow(ax, (2.7, 9.45), (3.2, 9.45), "credentials", off=(0, 0.3), fs=7)
    arrow(ax, (3.2, 9.15), (2.7, 9.15), "tokens, pages", off=(0, -0.3), fs=7)
    arrow(ax, (6.4, 9.45), (8.1, 9.45), None)
    arrow(ax, (8.1, 9.15), (6.4, 9.15), None)
    ax.text(7.25, 9.75, "read / write", ha="center", fontsize=7)
    # 2.0 / 3.0 / 4.0
    arrow(ax, (2.7, 6.1), (3.2, 6.1), "files / API", off=(0, 0.3), fs=7)
    arrow(ax, (4.8, 6.85), (4.8, 7.45), "rows", off=(0.35, 0), fs=7)
    arrow(ax, (6.4, 6.1), (7.05, 6.1), None)
    ax.text(6.72, 6.45, "clean", ha="center", fontsize=7)
    arrow(ax, (9.0, 6.85), (9.0, 7.45), None, style="<|-|>")
    arrow(ax, (10.95, 6.1), (11.4, 6.1), None)
    ax.text(11.18, 6.45, "signals", ha="center", fontsize=7)
    arrow(ax, (13.0, 6.85), (13.0, 7.45), None)
    # 4.0 -> 5.0 -> 6.0 -> 7.0 and stores
    arrow(ax, (13.0, 5.35), (13.0, 3.85), "high / critical", off=(0.75, 0), fs=7)
    arrow(ax, (11.4, 3.1), (10.3, 3.1), "alert to case", off=(0, 0.3), fs=7)
    arrow(ax, (7.1, 3.1), (6.0, 3.1), "statistics", off=(0, 0.3), fs=7)
    arrow(ax, (13.0, 2.35), (13.0, 1.65), None)
    arrow(ax, (8.7, 2.35), (8.7, 1.65), None)
    arrow(ax, (4.4, 2.35), (4.4, 1.65), None)
    arrow(ax, (14.6, 3.1), (15.05, 3.1), None)
    ax.text(14.85, 3.5, "e-mail", ha="center", fontsize=7)
    ax.text(8.5, 0.35, "Process 4.0 also stores risk assessments and explanations in D5, and 1.0 sends verification e-mails (arrows omitted for clarity).", ha="center", fontsize=7.6, color=GREY_E)
    save(fig, "fig_dfd1")


# ----------------------------------------------------------------------------------------------- 5 ERD
def erd():
    fig, ax = canvas(20, 13.6)
    title(ax, 10, 13.2, "Entity relationship diagram (principal tables of 46 models)")
    ents = {
        "Role": (2.2, 11.8, ["id PK", "name (unique)", "description"], GREEN, GREEN_E),
        "User": (2.2, 8.8, ["id PK", "email (unique)", "role_id FK", "approval_status", "email_verified_at", "is_active"], GREEN, GREEN_E),
        "AuditLog": (2.2, 5.3, ["id PK", "actor_id FK", "action", "resource_type, resource_id", "changes (JSON)", "created_at"], GREEN, GREEN_E),
        "Dataset": (7.4, 11.8, ["id PK", "name", "row_count", "created_by FK"], BLUE, BLUE_E),
        "ImportJob": (7.4, 9.0, ["id PK", "dataset_id FK", "file_sha256", "status", "accepted / rejected"], BLUE, BLUE_E),
        "Account": (7.4, 6.0, ["id PK", "dataset_id FK", "account_ref", "account_type"], BLUE, BLUE_E),
        "Transaction": (12.4, 9.0, ["id PK", "dataset_id FK", "import_job_id FK", "sender_id FK", "receiver_id FK", "amount, tx_type", "occurred_at, status"], BLUE, BLUE_E),
        "MLModel": (17.6, 12.0, ["id PK", "name", "algorithm"], VIOLET, VIOLET_E),
        "ModelVersion": (17.6, 9.7, ["id PK", "model_id FK", "algorithm", "artifact_sha256", "seed, data hash"], VIOLET, VIOLET_E),
        "DetectionRun": (17.6, 7.0, ["id PK", "model_version_id FK", "dataset_id FK", "status"], VIOLET, VIOLET_E),
        "Prediction": (17.6, 4.4, ["id PK", "run_id FK", "transaction_id FK", "score, label"], VIOLET, VIOLET_E),
        "Explanation": (17.6, 2.1, ["id PK", "prediction_id FK", "assessment_id FK", "method (SHAP / LIME)"], AMBER, AMBER_E),
        "RiskAssessment": (12.4, 4.4, ["id PK", "transaction_id FK", "run_id FK, config_id FK", "overall_score", "components (JSON)", "coverage"], AMBER, AMBER_E),
        "Alert": (7.4, 2.6, ["id PK", "transaction_id FK", "assessment_id FK", "assignee_id FK", "severity, status", "dedup_key"], RED, RED_E),
        "Case": (2.2, 2.4, ["id PK", "case_ref (unique)", "status, priority", "assignee_id FK", "outcome"], RED, RED_E),
    }
    sizes = {}
    for name, (x, y, fields, fc, ec) in ents.items():
        h = 0.62 + 0.3 * len(fields)
        w = 3.5
        ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0,rounding_size=0.06", fc="white", ec=ec, lw=1.5))
        ax.add_patch(FancyBboxPatch((x - w / 2, y + h / 2 - 0.42), w, 0.42, boxstyle="round,pad=0,rounding_size=0.06", fc=fc, ec=ec, lw=1.5))
        ax.text(x, y + h / 2 - 0.21, name, ha="center", va="center", fontsize=8.6, fontweight="bold", color=INK)
        for i, f in enumerate(fields):
            ax.text(x - w / 2 + 0.12, y + h / 2 - 0.42 - 0.22 - 0.3 * i, f, ha="left", va="center", fontsize=7.2, color=INK, family="monospace")
        sizes[name] = (x, y, w, h)

    def pt(name, side, dx=0.0):
        x, y, w, h = sizes[name]
        return {"r": (x + w / 2, y), "l": (x - w / 2, y), "t": (x + dx, y + h / 2), "b": (x + dx, y - h / 2)}[side]

    def rel(a, sa, b, sb, la="1", lb="N", da=0.0, db=0.0):
        p1, p2 = pt(a, sa, da), pt(b, sb, db)
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=GREY_E, lw=1.1, zorder=1)
        for t, lab in ((0.14, la), (0.86, lb)):
            ax.text(p1[0] + (p2[0] - p1[0]) * t, p1[1] + (p2[1] - p1[1]) * t + 0.17, lab, fontsize=7.6, fontweight="bold", ha="center", color=INK, bbox=dict(fc="white", ec="none", pad=0.4))

    rel("Role", "b", "User", "t")
    rel("User", "b", "AuditLog", "t")
    rel("User", "r", "Dataset", "l")
    rel("Dataset", "b", "ImportJob", "t")
    rel("Dataset", "r", "Transaction", "t")
    rel("ImportJob", "r", "Transaction", "l")
    rel("Account", "r", "Transaction", "b", da=0, db=-1.2)
    rel("MLModel", "b", "ModelVersion", "t")
    rel("ModelVersion", "b", "DetectionRun", "t")
    rel("DetectionRun", "b", "Prediction", "t")
    rel("Transaction", "r", "Prediction", "l")
    rel("Prediction", "b", "Explanation", "t")
    rel("Transaction", "b", "RiskAssessment", "t")
    rel("RiskAssessment", "l", "Alert", "r")
    rel("Alert", "l", "Case", "r", "N", "N")
    ax.text(9, 0.62, "Case also owns CaseNote, CaseEvidence and CaseEvent (immutable) and links to alerts and transactions through CaseAlert and CaseTransaction.", ha="center", fontsize=7.8, color=GREY_E)
    ax.text(9, 0.18, "PK primary key, FK foreign key; N is the many side. Behaviour, graph, duplicate, alert-policy, risk-run and analytics tables are described in section 3.1.", ha="center", fontsize=7.8, color=GREY_E)
    save(fig, "fig_erd")


# ----------------------------------------------------------------------------------------------- 6 activity
def activity():
    fig, ax = canvas(16, 14.2)
    title(ax, 8, 13.8, "Activity diagram: from imported data to a closed case")
    LX, RX, BW = 5.0, 12.6, 7.4

    def node(x, y, t, w=BW, h=0.8, fc=BLUE, ec=BLUE_E):
        box(ax, x, y, w, h, t, fc, ec, 8.2, round_=0.35)

    def diamond(x, y, t, w=3.4, h=1.3):
        ax.add_patch(Polygon([(x, y + h / 2), (x + w / 2, y), (x, y - h / 2), (x - w / 2, y)], fc=AMBER, ec=AMBER_E, lw=1.3))
        ax.text(x, y, t, ha="center", va="center", fontsize=7.6)

    def final(x, y):
        ax.add_patch(plt.Circle((x, y), 0.2, fc="white", ec=INK, lw=2))
        ax.add_patch(plt.Circle((x, y), 0.1, fc=INK))

    ax.add_patch(plt.Circle((LX, 13.1), 0.2, fc=INK))
    node(LX, 12.2, "Analyst uploads CSV / XLSX and maps the columns")
    arrow(ax, (LX, 12.9), (LX, 12.6))
    node(LX, 11.1, "Validate every row; rejected rows go to an error report")
    arrow(ax, (LX, 11.8), (LX, 11.5))
    diamond(LX, 9.9, "Any rows\naccepted?")
    arrow(ax, (LX, 10.7), (LX, 10.55))
    node(RX, 9.9, "Import fails; the user\ndownloads the error report", 4.4, 0.9, RED, RED_E)
    arrow(ax, (LX + 1.7, 9.9), (RX - 2.2, 9.9), "no", off=(0, 0.25))
    final(15.3, 9.9)
    arrow(ax, (RX + 2.2, 9.9), (15.1, 9.9))
    node(LX, 8.6, "Store transactions and accounts (bulk, chunked, resumable)")
    arrow(ax, (LX, 9.25), (LX, 9.0), "yes", off=(0.4, 0))
    node(LX, 7.4, "Run detection, behaviour, graph and duplicate analysis")
    arrow(ax, (LX, 8.2), (LX, 7.8))
    node(LX, 6.2, "Combine the signals into a 0-100 risk score with coverage")
    arrow(ax, (LX, 7.0), (LX, 6.6))
    diamond(LX, 4.9, "Score at or above\nalert threshold?")
    arrow(ax, (LX, 5.8), (LX, 5.55))
    node(RX, 4.9, "No alert; the score stays\nvisible on the transaction", 4.4, 0.9, GREY, GREY_E)
    arrow(ax, (LX + 1.7, 4.9), (RX - 2.2, 4.9), "no", off=(0, 0.25))
    node(LX, 3.6, "Create a deduplicated alert with an evidence snapshot")
    arrow(ax, (LX, 4.25), (LX, 4.0), "yes", off=(0.4, 0))
    node(LX, 2.5, "Analyst acknowledges, assigns or escalates; opens a case")
    arrow(ax, (LX, 3.2), (LX, 2.9))
    node(LX, 1.4, "Investigator reviews evidence, explanation and graph")
    arrow(ax, (LX, 2.1), (LX, 1.8))
    node(RX, 1.4, "Resolve with an outcome\nand summary, then close", 4.4, 0.9, GREEN, GREEN_E)
    arrow(ax, (LX + BW / 2, 1.4), (RX - 2.2, 1.4))
    node(RX, 3.1, "Dashboards and false-positive\nstatistics update", 4.4, 0.9, GREEN, GREEN_E)
    arrow(ax, (RX, 1.85), (RX, 2.65))
    final(RX, 0.35)
    arrow(ax, (RX, 0.95), (RX, 0.55))
    save(fig, "fig_activity")


# ----------------------------------------------------------------------------------------------- 7 sequences
def sequence(name, ttl, parts, msgs, h):
    n = len(parts)
    fig, ax = canvas(3.4 * n, h)
    title(ax, 1.7 * n, h - 0.4, ttl)
    xs = [1.7 + 3.4 * i for i in range(n)]
    for x, p in zip(xs, parts):
        box(ax, x, h - 1.3, 2.5, 0.7, p, GREY, GREY_E, 8.4, True, round_=0.05)
        ax.plot([x, x], [h - 1.65, 0.5], color=GREY_E, lw=1.0, ls=(0, (4, 3)))
    y = h - 2.3
    for m in msgs:
        a, b, t, kind = m
        x1, x2 = xs[a], xs[b]
        if a == b:
            ax.annotate("", xy=(x1, y - 0.35), xytext=(x1, y), arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.1, connectionstyle="arc3,rad=-0.9"))
            ax.text(x1 + 0.3, y - 0.1, t, fontsize=7.4, va="center", ha="left", color=INK)
            y -= 0.8
            continue
        ls = "--" if kind == "ret" else "-"
        arrow(ax, (x1, y), (x2, y), None, ls=ls, lw=1.1)
        ax.text((x1 + x2) / 2, y + 0.18, t, fontsize=7.4, ha="center", va="bottom", color=INK)
        y -= 0.75
    save(fig, name)


def sequences():
    sequence(
        "fig_seq_signup",
        "Sequence diagram: self-registration, e-mail confirmation and approval",
        ["Applicant\n(browser)", "API (DRF)", "PostgreSQL", "Celery worker\n+ SMTP", "Super Admin\n(browser)"],
        [
            (0, 1, "POST /auth/register/ {email, password}", "call"),
            (1, 2, "create pending_user, approval=pending", "call"),
            (1, 3, "queue verification e-mail (after commit)", "call"),
            (1, 0, "202 generic message (no account hint)", "ret"),
            (3, 0, "e-mail with signed 24 h link", "ret"),
            (0, 1, "POST /auth/verify-email/ {token}", "call"),
            (1, 2, "set email_verified_at", "call"),
            (1, 3, "notify Super Admins", "call"),
            (3, 4, "e-mail: new registration", "ret"),
            (4, 1, "POST /users/{id}/approve/ {role}", "call"),
            (1, 2, "assign role, approval=approved (audited)", "call"),
            (1, 3, "queue approval e-mail", "call"),
            (0, 1, "POST /auth/login/ -> 200 + JWT", "call"),
        ],
        12.6,
    )
    sequence(
        "fig_seq_pipeline",
        "Sequence diagram: import and scoring run as background jobs",
        ["Analyst\n(browser)", "API (DRF)", "Celery worker", "PostgreSQL", "Channels\n(WebSocket)"],
        [
            (0, 1, "POST /datasets/{id}/imports/ (file + mapping)", "call"),
            (1, 3, "ImportJob = queued, file SHA-256", "call"),
            (1, 2, "enqueue run_import", "call"),
            (1, 0, "202 + job id", "ret"),
            (2, 3, "bulk insert chunks, row errors", "call"),
            (2, 4, "progress events", "call"),
            (4, 0, "live progress bar", "ret"),
            (0, 1, "POST /detection/runs/ (model version)", "call"),
            (1, 2, "enqueue run_detection", "call"),
            (2, 3, "store Prediction rows", "call"),
            (0, 1, "POST /risk/runs/ then /alerts/evaluate/", "call"),
            (2, 3, "RiskAssessment, Alert (deduplicated)", "call"),
            (2, 4, "new alert pushed", "call"),
            (4, 0, "alert badge updates", "ret"),
        ],
        12.8,
    )


# ----------------------------------------------------------------------------------------------- 8 class (cases)
def class_diagram():
    fig, ax = canvas(18, 10.6)
    title(ax, 9, 10.25, "Class diagram: investigation and alert domain (Django models)")
    ax.text(9, 9.6, "Case status changes go through one service function that checks the transition table and the user's permission;\nevery change appends a CaseEvent. A closed case cannot be edited.", ha="center", fontsize=8, color=GREY_E)
    boxes: dict[str, tuple[float, float, float, float]] = {}

    def klass(key, x, y, name, attrs, w, fc=RED, ec=RED_E):
        h = 0.62 + 0.3 * len(attrs)
        ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0,rounding_size=0.05", fc="white", ec=ec, lw=1.5, zorder=2))
        ax.add_patch(FancyBboxPatch((x - w / 2, y + h / 2 - 0.42), w, 0.42, boxstyle="round,pad=0,rounding_size=0.05", fc=fc, ec=ec, lw=1.5, zorder=3))
        ax.text(x, y + h / 2 - 0.21, name, ha="center", va="center", fontsize=9, fontweight="bold", zorder=4)
        for i, a_ in enumerate(attrs):
            ax.text(x - w / 2 + 0.12, y + h / 2 - 0.42 - 0.22 - 0.3 * i, a_, fontsize=7.2, va="center", family="monospace", zorder=4)
        boxes[key] = (x, y, w, h)

    klass("case", 9.0, 6.6, "Case", ["+ case_ref: str  (FG-YYYY-NNNNNN)", "+ title: str", "+ status: new | under_review | investigation", "    | escalated | resolved | closed", "+ priority: low | medium | high | critical", "+ outcome: confirmed_suspicious | false_positive", "    | inconclusive | referred", "+ assignee, created_by: User", "+ resolved_by, closed_by: User"], 7.2)
    klass("alert", 2.6, 7.4, "Alert", ["+ alert_type: str", "+ severity: str", "+ status: new | acknowledged", "    | escalated | closed", "+ dedup_key: str", "+ assignee: User", "+ evidence: JSON snapshot"], 4.6, BLUE, BLUE_E)
    klass("tx", 15.6, 7.9, "Transaction", ["+ amount: Decimal", "+ tx_type: str", "+ occurred_at: datetime", "+ sender, receiver: Account"], 4.2, GREEN, GREEN_E)
    klass("ca", 2.6, 3.3, "CaseAlert", ["+ case: Case", "+ alert: Alert", "+ linked_by: User"], 3.6)
    klass("ct", 15.6, 4.9, "CaseTransaction", ["+ case: Case", "+ transaction: Transaction", "+ note: str"], 4.2)
    klass("note", 4.9, 1.3, "CaseNote", ["+ case: Case", "+ author: User", "+ kind: comment | note", "+ revisions: CaseNoteRevision[]"], 4.8)
    klass("ev", 9.9, 1.3, "CaseEvidence", ["+ case: Case", "+ sha256: str  (checked on download)", "+ stored_name: random", "+ uploaded_by: User"], 4.8)
    klass("evt", 14.9, 1.3, "CaseEvent  (immutable)", ["+ case: Case", "+ event_type, actor: User", "+ from_status, to_status", "+ payload: JSON"], 4.6)

    def pt(k, side, dx=0.0, dy=0.0):
        x, y, w, h = boxes[k]
        return {"r": (x + w / 2, y + dy), "l": (x - w / 2, y + dy), "t": (x + dx, y + h / 2), "b": (x + dx, y - h / 2)}[side]

    def link(a_, sa, b_, sb, la="1", lb="N", da=0.0, db=0.0, dya=0.0, dyb=0.0):
        if sa in "tb":
            p1 = pt(a_, sa, da)
        else:
            p1 = pt(a_, sa, dy=dya)
        p2 = pt(b_, sb, db) if sb in "tb" else pt(b_, sb, dy=dyb)
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=GREY_E, lw=1.2, zorder=1)
        for t, lab in ((0.12, la), (0.88, lb)):
            ax.text(p1[0] + (p2[0] - p1[0]) * t, p1[1] + (p2[1] - p1[1]) * t + 0.15, lab, fontsize=8, fontweight="bold", ha="center", bbox=dict(fc="white", ec="none", pad=0.4), zorder=5)

    link("alert", "b", "ca", "t")
    link("ca", "r", "case", "l", "N", "1", dyb=-1.2)
    link("tx", "b", "ct", "t")
    link("ct", "l", "case", "r", "N", "1", dyb=-1.2)
    link("case", "b", "note", "t", "1", "N", da=-1.4, db=0.0)
    link("case", "b", "ev", "t", "1", "N", da=0.9, db=0.0)
    link("case", "b", "evt", "t", "1", "N", da=3.2, db=0.0)
    save(fig, "fig_class")


# ----------------------------------------------------------------------------------------------- 9 case state machine
def state_machine():
    fig, ax = canvas(15, 5.6)
    title(ax, 7.5, 5.2, "Case status state machine (enforced server-side)")
    ax.add_patch(plt.Circle((0.5, 3.0), 0.2, fc=INK))
    spec = {"new": (2.0, 1.6), "under_review": (5.4, 2.4), "investigation": (8.9, 2.4), "resolved": (11.9, 2.0), "closed": (14.2, 1.4)}
    cols = {"new": (BLUE, BLUE_E), "under_review": (BLUE, BLUE_E), "investigation": (VIOLET, VIOLET_E), "resolved": (GREEN, GREEN_E), "closed": (GREY, GREY_E)}
    for k, (x, w) in spec.items():
        box(ax, x, 3.0, w, 0.9, k.replace("_", " "), cols[k][0], cols[k][1], 8.6, True, round_=0.3)
    box(ax, 8.9, 1.0, 2.2, 0.9, "escalated", RED, RED_E, 8.6, True, round_=0.3)
    arrow(ax, (0.7, 3.0), (1.2, 3.0))
    arrow(ax, (2.8, 3.0), (4.2, 3.0), "take for review", off=(0.0, 0.3), fs=6.6)
    arrow(ax, (6.6, 3.0), (7.7, 3.0), "investigate", off=(0, 0.3), fs=6.6)
    arrow(ax, (10.1, 3.0), (10.9, 3.0), "resolve", off=(0, 0.3), fs=6.6)
    arrow(ax, (12.9, 3.0), (13.5, 3.0), "close", off=(0, 0.3), fs=6.6)
    arrow(ax, (5.4, 3.45), (11.9, 3.45), "resolve directly (false positive)", rad=-0.35, off=(0, 0.95), fs=7)
    arrow(ax, (8.5, 2.55), (8.5, 1.45), "escalate", off=(-0.55, 0), fs=7)
    arrow(ax, (9.3, 1.45), (9.3, 2.55), "back to investigation", off=(1.0, 0), fs=7)
    ax.text(7.5, 0.15, "Anything not drawn is rejected (409), including staying in the same status. Each move writes an immutable CaseEvent.", ha="center", fontsize=7.8, color=GREY_E)
    save(fig, "fig_case_states")


# ----------------------------------------------------------------------------------------------- 10 risk pipeline
def risk_pipeline():
    fig, ax = canvas(19, 6.6)
    title(ax, 9.5, 6.2, "Risk scoring: six components combined with configurable weights")
    comps = [
        ("A  Anomaly", "ML model score (50 = the model's own threshold)", "25 %"),
        ("B  Behaviour", "deviation from the sender's own history", "20 %"),
        ("G  Graph", "strongest pattern: cycle, chain, fan-in/out, cluster", "20 %"),
        ("F  Frequency", "burst of transactions in a short window", "15 %"),
        ("D  Duplicate", "similarity to an earlier undismissed transaction", "10 %"),
        ("H  History", "human-confirmed duplicates in earlier transactions", "10 %"),
    ]
    for i, (n, d, w) in enumerate(comps):
        y = 5.0 - i * 0.78
        box(ax, 2.0, y, 3.2, 0.62, n, BLUE, BLUE_E, 8.8, True, round_=0.08)
        ax.text(3.9, y, d, fontsize=7.4, va="center", ha="left", color=INK)
        ax.text(11.3, y, "weight " + w, fontsize=7.6, va="center", ha="right", color=GREY_E)
        arrow(ax, (11.5, y), (12.5, 2.7 + (y - 2.7) * 0.3), None, lw=0.9)
    box(ax, 14.2, 2.7, 3.4, 2.0, "R = sum(w_i x S_i)\n/ sum(w_i of the\navailable components)", AMBER, AMBER_E, 8.8, True)
    arrow(ax, (15.9, 2.7), (16.7, 2.7))
    box(ax, 17.8, 4.0, 1.9, 0.55, "Medium  from 30", GREEN, GREEN_E, 7.4)
    box(ax, 17.8, 2.7, 1.9, 0.55, "High  from 60", AMBER, AMBER_E, 7.4)
    box(ax, 17.8, 1.4, 1.9, 0.55, "Critical  from 80", RED, RED_E, 7.4)
    ax.text(9.5, 0.35, "An unavailable component (for example a cold-start account) is excluded and reported through coverage; it is never treated as zero.\nThree policies: renormalize, neutral_prior, strict. Weights and thresholds are versioned in RiskConfig; the weights shown are the defaults.", ha="center", fontsize=7.6, color=GREY_E)
    save(fig, "fig_risk")


# ----------------------------------------------------------------------------------------------- 11 deployment
def deployment():
    fig, ax = canvas(15, 8.2)
    title(ax, 7.5, 7.8, "Production deployment (docker-compose.prod.yml, single host)")
    ax.add_patch(FancyBboxPatch((1.6, 0.8), 12.2, 6.3, boxstyle="round,pad=0,rounding_size=0.2", fc="#f8fafc", ec=GREY_E, lw=1.5))
    ax.text(1.9, 6.85, "Docker host: one Compose network, only the web service publishes ports 80 and 443", fontsize=8.4, color=GREY_E, va="center")
    box(ax, 8.0, 5.9, 5.6, 0.85, "web: Caddy 2 + built React app\nautomatic HTTPS, CSP, security headers", AMBER, AMBER_E, 8.2, True)
    box(ax, 0.9, 5.9, 1.4, 0.8, "Browser", GREY, GREY_E, 8.4, True)
    arrow(ax, (1.6, 5.9), (5.2, 5.9), "HTTPS 443", off=(0, 0.25))
    box(ax, 3.9, 4.2, 3.4, 0.9, "worker: Celery", GREEN, GREEN_E, 8.4, True)
    box(ax, 7.6, 4.2, 3.4, 0.9, "backend: Daphne (ASGI)\nDjango + DRF + Channels", BLUE, BLUE_E, 8.2, True)
    box(ax, 11.4, 4.2, 2.4, 0.9, "beat: scheduler", GREEN, GREEN_E, 8.4, True)
    box(ax, 4.6, 2.1, 3.0, 1.0, "db: PostgreSQL 16\nvolume pgdata", GREEN, GREEN_E, 8.2, True)
    box(ax, 8.2, 2.1, 2.4, 1.0, "redis: Redis 7", AMBER, AMBER_E, 8.4, True)
    box(ax, 11.6, 2.1, 2.4, 1.0, "neo4j (optional\nCompose profile)", GREY, GREY_E, 8)
    arrow(ax, (7.6, 5.48), (7.6, 4.65), "/api, /ws", off=(0.65, 0), fs=7)
    arrow(ax, (6.9, 3.75), (5.4, 2.6))
    arrow(ax, (7.9, 3.75), (8.0, 2.6))
    arrow(ax, (4.1, 3.75), (4.6, 2.6))
    arrow(ax, (5.0, 3.75), (7.6, 2.6))
    arrow(ax, (11.2, 3.75), (9.0, 2.6))
    arrow(ax, (8.6, 3.75), (11.2, 2.6), None, ls="--")
    ax.text(7.5, 0.4, "Scripts: backup.sh (pg_dump + media + SHA-256), restore.sh, smoke.sh. Health: /api/v1/health/ and /api/v1/health/ready/.", ha="center", fontsize=7.8, color=GREY_E)
    save(fig, "fig_deployment")


if __name__ == "__main__":
    architecture()
    use_case()
    dfd0()
    dfd1()
    erd()
    activity()
    sequences()
    class_diagram()
    state_machine()
    risk_pipeline()
    deployment()
