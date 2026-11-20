# 21 — User guide

FinGuard helps a team find suspicious financial activity, understand why it was flagged, and record what was decided. **Scores and flags are automated indicators for prioritising review, not proof of wrongdoing.** Only a person can decide an outcome.

## Signing in
Open the site and choose **Sign in**. Accounts are created by a Super Admin. After 5 wrong passwords an account is locked for a while. Sessions end when you click **Sign out** (a refresh happens quietly in the background).

## Roles
| Role | Can do |
|---|---|
| **Financial Analyst** | Import data, run detection / behaviour / graph / duplicate / risk analysis, review and close alerts, open cases, rebuild analytics |
| **Fraud Investigator** | Review alerts, run the full case workflow (assign, escalate, resolve, close), notes and evidence, explanations |
| **Auditor** | Read-only across the platform, plus **Audit Logs** and **User Management** (view) |
| **Management** | Dashboard and **Analytics** (read, export) |
| **Super Admin** | Everything, plus users, roles and risk/alert configuration |
Menus only show what your role may open; the server enforces the same rules.

## Navigating
The top bar has **Dashboard**, **Analytics** and four menus: **Data** (Transactions, Imports), **Detect** (Anomaly Detection, Relationship Graph, Duplicate Detection, Risk Analysis), **Respond** (Alerts, Investigations) and **Govern** (Model Performance, User Management, Audit Logs). Most lists show **Cards** and have a **Table view** switch (denser, also best for screen readers). Press Tab to reach "Skip to content" at the top of every page.

## Typical workflow
1. **Import** (Data → Imports → New import): upload a CSV/Excel file, map columns (PaySim files are recognised automatically), watch progress; rejected rows are listed and exportable.
2. **Detect**: *Anomaly Detection* scores a dataset with a trained model; *Relationship Graph* builds who-paid-whom and finds cycles, rapid chains, fan-in/out and shared beneficiaries; *Duplicate Detection* finds repeated payments and duplicate invoices (upload invoices, correct the OCR fields, confirm or reject candidates); *Risk Analysis* combines the signals into one 0–100 score with a breakdown and the signal coverage.
3. **Alerts**: a prioritised queue. Open one to see the reason and evidence, acknowledge, assign, escalate or close it with an outcome. Critical alerts open a case automatically.
4. **Investigations**: a case collects alerts and transactions, notes, evidence files (hashed on upload) and a timeline. Move it through *Under review → Investigation → Escalated ↔ Investigation → Resolved → Closed*; resolving needs an outcome and a written summary. Closed cases are read-only; the history stays. *PDF report* downloads a summary.
5. **Understand a score**: open a transaction, then *Explain* for SHAP/LIME and a plain-language summary. SHAP is exact; LIME is approximate and can vary between runs, so SHAP is shown first. Look for the "STALE" note: it means newer results exist.
6. **Analytics** (insight for managers): volume over time, risk distribution, false-positive rates, investigation times, model quality; filter by dataset and dates; export CSV/PDF.

## Reading the numbers safely
* *Risk coverage* tells you how many of the six signals were available. Low coverage means the score is thin; the platform caps such scores at High.
* On PaySim, senders usually appear once, so behaviour and frequency signals are unavailable ("cold start"): that is a data property, not a fault.
* Models trained with balance fields look perfect on PaySim because the simulator leaks the label; compare models using the *core* feature set (Model Performance explains this).
* "False-positive rate" on Analytics comes from investigators' decisions; the labelled research view compares model flags with the dataset's own labels and is for evaluation only.

## Getting help
Audit Logs (Auditor / Super Admin) show who did what and when. Report problems with the time, the page and what you clicked.
