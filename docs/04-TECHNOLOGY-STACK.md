# 04 — Technology Stack

Baseline per master prompt Part 3. Version pins are **proposals** to be locked in Phase 1 (verify latest compatible releases at that time).

## Frontend
| Concern | Choice | Notes |
|---|---|---|
| Framework/build/lang | React + Vite + TypeScript (`strict`) | Node 22 LTS in Docker |
| Styling | Tailwind CSS | Design tokens in `tailwind.config`; shared UI kit under `src/components/ui` |
| Charts | Recharts | |
| Graph | React Flow | Fine for hundreds of nodes; server caps neighbourhood size (depth/limit) |
| Server state | TanStack Query | *Proposed addition* — caching, loading/error states (needs approval, D-007) |
| Forms | React Hook Form + Zod | *Proposed addition* — validation (D-007) |
| Routing | React Router | auth-aware, role-aware route guards |
| Realtime | native WebSocket → Django Channels | |
| Tests | Vitest, Testing Library, Playwright | |

## Backend
Python 3.12 · Django 5.x LTS line · DRF · SimpleJWT (+ token blacklist) · drf-spectacular · django-filter · django-cors-headers · Channels + channels-redis (Daphne/Uvicorn ASGI) · Celery + Redis (+ celery-beat for periodic analytics) · openpyxl (Excel) · pandas/numpy · bcrypt via Django `BCryptSHA256PasswordHasher` (needs `bcrypt` package; Argon2 is a stronger option — D-009).
Reports: **ReportLab** (pure-Python PDF; avoids WeasyPrint system deps) — D-010. Charts in PDFs via matplotlib.
Storage: local `media/` volume in dev; S3-compatible abstraction (`django-storages`) for production evidence/model artifacts.

## Data / ML / Graph
scikit-learn, XGBoost, PyTorch (CPU build; autoencoder only), pandas, NumPy, NetworkX (+ `python-louvain` or NetworkX built-in `louvain_communities`), SHAP, LIME, imbalanced-learn (only if resampling experiments are run), joblib for sklearn artifacts, XGBoost native JSON, PyTorch `state_dict` + config. **PyTorch Geometric: deferred**, installed only if the GNN gate (D-012) passes.
Duplicates/OCR: Tesseract (system package in Docker) via `pytesseract`, `pdf2image`/Poppler or PyMuPDF, Pillow, OpenCV-headless only if needed, `rapidfuzz` (fuzzy), `imagehash` (perceptual hash for image similarity).

## Databases
PostgreSQL 16 (`psycopg` 3) · Redis 7 · Neo4j 5 Community (official `neo4j` Python driver; GDS plugin optional — Community GDS has concurrency limits, so NetworkX is the primary algorithm engine).

## Infrastructure
Docker + Compose (dev, prod overlays), `.env` per environment, Git/GitHub (+ GitHub Actions CI: lint, tests), deployment target decided in Phase 16 (Render is cheaper/simpler; AWS EC2 + managed Postgres if Neo4j/Celery memory needs demand it).

## Local machine note
Current Mac has Python **3.14** and Node **25**. Several ML packages (PyTorch, XGBoost wheels, SHAP/numba) may lag on 3.14, so **all development runs in Docker (Python 3.12, Node 22)** — D-002.
