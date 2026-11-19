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

## Phase 6 as built
- **Account Behavior** (`/accounts/:id/behavior`, `behavior.read`, linked from the account page): direction (outgoing/incoming) and window selectors, summary statistics, last-7-days vs window table, spending trend (daily/weekly/monthly bars), hour-of-day histogram, merchant categories or an explicit "not available". Empty and thin-history states are explained instead of showing zeros.
- **Transaction detail** gains a *Behavioral deviation* panel: score, signal coverage, one row per component with its evidence, unavailable components with the reason, and an explicit cold-start message.
- Component-tested only. Not built: batch-run UI (runs are API/worker only), a true heatmap (hour histogram only), run-result browsing page, baseline-vs-current charts.

## Phase 7 as built
- **Relationship Graph** (`/graph`, `graph.read`): dataset selector, build button (`graph.run`), Neo4j projection panel (status, PostgreSQL↔Neo4j counts, in-sync flag, sync/rebuild buttons, clear message when Neo4j is down), snapshot list (⚠ when a detector hit its limit), findings table filterable by pattern with links into account networks, and a standing note that scores are uncalibrated.
- **Account network** (`/accounts/:id/graph`, linked from the account page): React Flow diagram on concentric rings by depth (fill = graph risk score with text legend, ⚑ = in a finding, bold border = this account), depth / direction / minimum amount / data-source controls, a **Connections table** with the same data (accessible alternative to the diagram), edge details with link to the transaction, a truncation notice when caps were hit, and a timeline of transactions in the network. Clicking an account re-centres.
- Component-tested only (React Flow is mocked in jsdom); the diagram has not been rendered in a browser. Not built: community drill-down, ranked neighbours, force-directed layout, the dashboard mini-graph.

## Phase 8 as built
**Duplicate Detection** (`/duplicates`, `duplicates.read`) with two tabs. *Candidates*: filters (kind, class, review status; default pending), table with class and score, and a detail panel with a side-by-side comparison (differing fields highlighted and announced to screen readers), invoice images side by side, collapsible evidence, the standing "evidence, not proof" note, review buttons (confirm / not a duplicate / legitimate repeat, with notes — only with `duplicates.review`) and a PDF report. *Invoices*: upload (PNG/JPEG/PDF), list with OCR status/confidence, and a panel with the image and editable extracted fields showing per-field OCR confidence ("not found" when OCR found nothing), an explicit "not yet verified by a person" label, and Verify-and-save. Scan buttons (transactions / invoices) with `duplicates.run`. Component-tested only. Not built: threshold sliders, per-dataset scan selector in the UI, alert hookup (Phase 11), zoom/annotation on images.

## Phase 9 as built
- **Risk Analysis** (`/risk`, `risk.read`): dataset selector and "Score with active configuration" (`risk.run`); configuration cards (weights, thresholds, policy, minimum coverage, source, notes) with activation (`risk.configure`) and a new-version form with a live "weights sum to" check; latest run with category distribution (counts + bars), signal-coverage summary; a table of the highest-scoring transactions with the six component values and coverage (`*` = held at High for low coverage); selecting a row opens the full breakdown.
- **Risk assessment panel** on the transaction page: score, category (always written out), coverage, config/algorithm/policy, a low-coverage note, and per signal: value, weight, contribution, or "Unavailable — reason" (never a zero), plus the standing note that a score is not a finding of wrongdoing.
- Component-tested only. Not built: history chart, side-by-side assessment comparison UI (the compare API exists), calibration UI (CLI only), alert thresholds.

## Phase 10 as built
The transaction page gains an **Explanation** panel (`explain.read`; generate/regenerate with `explain.generate`): the five sections (Prediction / Indicator / Evidence / Assessment / Outcome) as a summary, the exact model version and prediction being explained, SHAP contribution bars (direction and value always printed, never colour alone), LIME with a caveat that it is random and its background, behaviour / network / risk narratives, a timeline, a red *Out of date* banner with the reason when an explanation is stale (and a plain note when another model scored later), skipped methods with reasons, a PDF report button, and the standing non-proof note. Component-tested only. Not built: explanation comparison across versions, global-importance chart in Model Performance, counterfactual ("what would change this") views.

## Phase 11 as built
**Alerts** (`/alerts`, `alerts.read`): open-alert counts by severity and unassigned count; filters (status [default open], severity, type, assigned to me/none); the server-prioritised queue; a detail panel with the reason, links to the transaction and account, the **evidence as it was when the alert was created**, the history (automatic events labelled), notification outcomes, and the actions the user may take — Acknowledge, Assign (to anyone eligible or "to me"), Escalate (reason required, button disabled until given), Close with an outcome and notes; Evaluate-rules control for a dataset (`alerts.run`); a collapsible active-policy summary with a JSON editor, Create-version and Activate for `alerts.configure`. A toast and queue refresh appear when an alert is pushed (layout-level, only for users who can read alerts); email links open `/alerts?open=<id>`. Component-tested only. Not built: bulk actions, create/link case (Phase 12), a policy form (JSON only), snooze/reopen, per-user notification preferences.

## Phase 12 as built
**Investigations** (`/cases`, `cases.read`): open-case counts by priority, filters (search by case number / title / account, status [default open], priority, assigned), the prioritised list (auto-created cases marked), New case. **Case workspace** (`/cases/:id`): status and priority badges, the actions the server allows for this user and status (take for review, start/return to investigation, escalate with a reason, resolve with an outcome and summary, close), assign / assign to me, alerts (linking to the alert), transactions (add by id), accounts involved (links to the account and its network page), comments and notes (edit your own; earlier versions viewable), evidence (hash shown; upload, download), timeline, PDF report, a read-only banner on closed cases, and the non-proof note. Alerts gain "Open a case from this alert" and show the cases they belong to. Component-tested only. Not built: an embedded graph diagram in the case, an account-history panel, bulk actions, reopening a resolved case, notification of assignees by email.
