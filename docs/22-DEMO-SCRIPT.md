# 22 — Demo script (≈ 15 minutes)

Goal: show the whole chain on real and clearly labelled demo data. Everything below was exercised by the automated tests and the browser journeys; the steps themselves are a recommended order, not a recording.

## Before the demo (once)
```bash
docker compose up -d                              # dev stack: http://localhost:5173
docker compose exec backend python manage.py migrate
docker compose exec -e FINGUARD_ADMIN_PASSWORD='…strong…' backend python manage.py create_superadmin --email demo@example.com
docker compose exec backend python manage.py seed_behavior_scenario     # 5 × ₹40,000 in 10 minutes (labelled DEMO)
docker compose exec backend python manage.py seed_graph_scenario        # planted cycle, rapid chain, fan-in, shared beneficiaries
docker compose exec backend python manage.py seed_mock_transactions --rows 20000   # random MOCK data for volume
```
Real PaySim/ULB slices and the trained models come from `datasets/` (see docs/19); the demo works without them but then Anomaly Detection lists no models. Create an analyst and an investigator in **User Management**.

## Script
1. **Landing page** (`/`, signed out): purpose, 3D network, roles. Click **Sign in**. *Point out:* public page needs no login; the app does.
2. **Dashboard**: pipeline strip with live counts, quick actions, charts. *Point out:* real counts, 20-second live feeds.
3. **Data → Transactions** (dataset "DEMO behavior scenario"): the five ₹40,000 payments to NEW-PAYEE-X. Switch **Cards / Table view**; sort by amount.
4. **Detect → Anomaly Detection**: pick a model and the PaySim slice, run, open the run (scores, flagged). *Point out:* thresholds frozen on validation; balance-field warning on **Govern → Model Performance**.
5. **Detect → Relationship Graph**: build the DEMO graph dataset; show the cycle, the rapid chain and the fan-in findings; open an account network (React Flow).
6. **Detect → Duplicate Detection**: invoices tab → upload the synthetic invoices (`generate_synthetic_invoices --email …`); show an exact and a strong match; confirm one as a person.
7. **Detect → Risk Analysis**: score the behaviour DEMO dataset; open a transaction's breakdown (components, coverage, excluded signals).
8. **Explain**: from the burst transaction, generate SHAP/summary; show the plain-language investigation summary and the PDF.
9. **Respond → Alerts**: evaluate rules for the DEMO dataset; the burst raises a Critical alert and a case opens automatically.
10. **Respond → Investigations**: open the case, add a note and evidence, escalate, resolve (outcome + summary), close; show the read-only banner and download the PDF.
11. **Analytics**: false-positive gauges now include the decision; export a CSV/PDF.
12. **Govern → Audit Logs**: show the trail of everything just done; **User Management** → sign in as a Management user to show the restricted view.

## What to say about limits
Behaviour and frequency signals are unavailable on real PaySim (single-use senders); the combined risk score was not better than the single model on that data (RQ5, doc 23); LIME is less stable than SHAP; the platform was rehearsed locally and not deployed to a cloud (doc 14).
