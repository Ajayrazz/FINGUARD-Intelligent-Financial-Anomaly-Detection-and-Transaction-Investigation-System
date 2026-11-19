# 02 — Functional Requirements

The authoritative per-requirement list (IDs, phase, priority, acceptance, status) is the matrix in [18-REQUIREMENTS-TRACEABILITY.md](18-REQUIREMENTS-TRACEABILITY.md). This document defines the **behavioral rules** that cut across requirements.

## ID scheme
`FR-M<n>-<nn>` module requirements (M1–M10) · `FR-UI-<nn>` pages · `FR-ROLE-<nn>` role capabilities · `PLAT-<nn>` platform requirements (async, realtime, OCR pipeline, etc.) · `RQ<n>` research questions.

## Cross-cutting behavioral rules
**Ingestion (M1).** Schema-flexible: a `ColumnMappingProfile` maps source columns → canonical fields; only `transaction_id` (generated if absent), sender, receiver (or merchant), amount, and a time reference are mandatory; everything else is optional and stored as null/`metadata`. Duplicate transaction IDs within a dataset: policy per import = `reject` (default) | `skip` | `flag`; never silently overwritten. Malformed rows → `ImportRowError`, import continues, summary shown.

**Detection (M2).** Supervised models only run on datasets with labels; unsupervised models run anywhere. Predictions stored per (run, transaction) with model version. A prediction is *not* an alert until the risk/alert policy says so.

**Behavioral (M3).** Profiles are computed *as of* a point in time using only prior transactions (no future leakage). Cold-start accounts (< N prior transactions, configurable) yield `behavior_unavailable`, not a score of 0.

**Graph (M4).** Graph built per dataset snapshot and optionally an `as_of` cut-off. Graph-derived features for training use time-respecting graphs only. Neo4j is a rebuildable projection of PostgreSQL.

**Duplicates (M5).** Four classes: `exact`, `strong_similar`, `potential`, `legitimate_repeat`. Similarity score is evidence, never proof; every candidate requires human review before it is labelled confirmed. Recurring legitimate payments (e.g., subscriptions: same vendor/amount at regular intervals) are recognised and suppressed or classed `legitimate_repeat`.

**Alerts (M6).** Deduplicated via `dedup_key = type + subject + time-bucket`; a new alert for the same subject is created only when there is a meaningfully new reason (higher severity or a new signal). Alerts snapshot evidence at creation.

**Risk (M7).** `R = Σ wᵢ·Sᵢ / Σ wᵢ(available)`, components 0–100. Weights/thresholds configurable, versioned (`RiskConfig`); each assessment records `algorithm_version`, config version, component values, availability flags and **coverage** (share of total weight that was available). See [08](08-ML-RESEARCH-AND-METHODOLOGY.md) §Risk for comparability rules.

**Explainability (M8).** Explanations are keyed to (prediction, model version). UI language distinguishes prediction / indicator / evidence / assessment / outcome. A standing disclaimer: contributions are not causation or proof.

**Cases (M9).** Status machine: `New → Under Review → Investigation in Progress → Escalated ↔ Investigation in Progress → Resolved → Closed`; also `Under Review → Resolved` (false positive). Transitions validated server-side; each writes an immutable `CaseEvent`. Closed cases are read-only but history remains. Final outcome is an investigator-set field (`confirmed_suspicious | false_positive | inconclusive | referred`), never model-set.

**Dashboards (M10).** All numbers come from API queries/rollups; empty/loading/error states required on every page.
