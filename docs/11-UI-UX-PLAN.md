# 11 — UI/UX Plan

**Direction:** dense, calm, investigation-first fintech UI. Dark-capable neutral palette (slate), one accent, semantic risk colours (Low green / Medium amber / High orange / Critical red — always paired with text/icon, never colour alone). Typography: Inter (UI) + tabular-nums for money. 8-pt spacing scale. Tokens in Tailwind config.

**Shell:** left sidebar (role-filtered nav), top bar (global search, dataset selector, job/notification bell, user menu), breadcrumb, page header with actions.

**Design-system components (built once, reused):** Button, Input/Select/DatePicker, DataTable (server-side sort/filter/paginate, column toggle, row selection, CSV export), FilterBar, StatCard, RiskBadge, StatusBadge, Tabs, Dialog/ConfirmDialog, Drawer, Toast, Skeleton/EmptyState/ErrorState, Chart wrappers (Recharts with a11y labels), GraphCanvas (React Flow), Timeline, EvidenceList, ExplanationPanel, JobProgress, PermissionGate.

**Every page ships with:** loading skeleton, empty state, error state with retry, keyboard access, role gating (UI hiding is cosmetic; backend enforces).

## Pages
| Page | Purpose | Key interactions | Backend |
|---|---|---|---|
| Login | Auth | validation, lockout/throttle message, session-expiry redirect | auth |
| Overview | KPIs: volume, value, suspicious count, high-risk accounts; trends; risk distribution; recent suspicious; investigation summary; model KPIs; mini graph | date/dataset filters; click-through to filtered lists | analytics |
| Transactions | Search/filter/sort/paginate; import wizard (upload → map columns → validate preview → progress); import history/errors | row → detail drawer/page | transactions, datasets |
| Transaction detail | What/why/who: details, sender/receiver cards, risk breakdown, explanation, related txns, mini-graph, alert, case, audit events | links to every related entity (per Part 9) | many |
| Anomaly Detection | Runs, scores, anomalous txns, anomaly-score visual, model/version selector | run detection, threshold slider (view only) | detection |
| Account Behavior | Profile, spending trend (day/week/month), baseline vs current, timing heatmap, deviation score | account search, window selector | behavioral |
| Relationship Graph | Neighbourhood explorer, findings list (cycles, chains, shared beneficiaries), communities, edge click → transaction, timeline | depth/amount/time filters, expand node | graph |
| Risk Analysis | Score distribution, component breakdown, coverage, history compare, config view (admin edit) | compare assessments | risk |
| Duplicate Detection | Candidates by class, side-by-side comparison, invoice upload/OCR review, human verification | confirm / not duplicate / legit repeat | duplicates |
| Alerts | Prioritised queue, filters, assign/ack/escalate, realtime toasts | bulk actions, link/create case | alerts |
| Investigations | Case list + workspace (summary, notes, evidence, timeline, related graph, transactions, status stepper, close/resolution) | validated transitions with reason dialogs | investigations |
| Reports | Generate/download PDFs/CSV, status of jobs | | reports |
| Model Performance | Compare versions: PR/ROC curves, confusion matrix, latency/throughput, drift-over-time | | models |
| User Management | Users, roles, activation | | accounts |
| Audit Logs | Search/filter, detail diff, export | | audit |

Language rules: use "flagged for review", "risk indicators", "model score"; never "fraudster/criminal/guilty". Explanation panel always splits Prediction / Indicator / Evidence / Assessment / Outcome and shows the non-proof disclaimer.

Prototyping rule: any UI built before its API exists uses a clearly labelled mock provider, removed before the phase is accepted.

## Phase 5D as built
- **Anomaly Detection** (`/detection`, `/detection/:id`; `detection.read`, start form needs `detection.run`): model-version and dataset selectors (only scorable models), run list with live status polling, run page with threshold/flag counts, log-scaled score histogram, and a paginated table of highest-scoring transactions (flagged-only toggle) linking to the transaction. MOCK datasets show a warning.
- **Model Performance** (`/models`; `models.read`): registered versions ranked by test PR-AUC with bootstrap interval, base rate, ROC-AUC and recall at 1% false-positive rate; dataset filter; a standing caution that `core+balance` PaySim results are saturated.
- Both are component-tested only (not browser-tested). Not built: side-by-side comparison charts, threshold slider, per-transaction score panel on the transaction page.
