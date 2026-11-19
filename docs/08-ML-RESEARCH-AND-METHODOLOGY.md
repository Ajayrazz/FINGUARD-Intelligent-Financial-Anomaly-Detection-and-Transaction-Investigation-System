# 08 — ML, Research and Methodology

**Rule:** no result is reported unless produced by an executed, reproducible experiment. Numbers appear in this doc only after Phase 5/7B/9 runs.

## Research questions → experiments
| RQ | Experiment | Primary metric | Phase |
|---|---|---|---|
| RQ1 hybrid > individual | Compare RF, XGB, IF, and hybrid (supervised score + unsupervised score → stacked/weighted) on PaySim chronological test | PR-AUC, recall@fixed-FPR | 5, 9 |
| RQ2 graph features help | Same model, tabular-only vs tabular+graph features (time-respecting), paired over seeds | ΔPR-AUC with bootstrap CI | 7B |
| RQ3 unsupervised finds unlabeled | Train IF/LOF/OCSVM/AE w/o labels; evaluate on held-out labels *and* manual review of top-k not matched by supervised model | PR-AUC, overlap analysis | 5 |
| RQ4 XAI communication | SHAP/LIME stability + fidelity checks (top-k feature agreement across runs, deletion test); small structured usability review with documented rubric | stability, fidelity | 10 |
| RQ5 risk score improves prioritisation | Compare alert queues ranked by single model score vs combined R: precision@k, workload at target recall | precision@k, alerts/true-positive | 9 |
| RQ6 temporal drift | Train on early periods, test on successive later windows; track metric decay | PR-AUC by window | 5, 9 |

## Pipeline (matches the 19-step methodology)
Collect → explore (EDA notebook/report) → clean → missing values → duplicate analysis → type conversion → categorical encoding → normalisation (only for scale-sensitive models; fit on train) → imbalance analysis → feature engineering → model development → validation → graph construction → risk scoring → explainability → integration → testing → evaluation → comparative analysis.

## Data-leakage register (must be addressed in code + tests)
1. **Chronological split** by `step`/time; never random for PaySim. Validation window sits between train and test.
2. **Account/behavioral/graph features** computed using only data strictly before the transaction's timestamp (expanding or rolling windows with `closed='left'`). Unit test: perturbing future rows doesn't change a past feature.
3. **PaySim balance fields:** `newbalanceOrig`/`oldbalanceOrg` relationships (e.g., sender balance drained to 0 in fraud) and `isFlaggedFraud` are known leakage-prone/degenerate; evaluate with and without balance-derived features and document. `isFlaggedFraud` excluded from features.
4. **Preprocessing fit on train only** (scalers, encoders, imputers) via sklearn `Pipeline`.
5. **Imbalance handling** (class weights, resampling) applied to train only; threshold chosen on validation, frozen for test.
6. **Graph features**: snapshot graph built from train window only for training rows; for test rows use graph up to the row's time (incremental) — expensive, so a windowed approximation is documented if used.
7. **Same-account label leakage** across splits discussed; optionally group-aware validation.
8. ULB: `Time` is seconds from first transaction (2 days) — chronological split; features V1–V28 are PCA outputs (no domain explanation possible — SHAP names only). Elliptic: use its provided time-step split (train steps 1–34, test 35–49), unknown labels excluded from metrics.

## Algorithm documentation template (filled per algorithm in Phase 5, appended to this doc)
Why used · Required features · Preprocessing · Training procedure · Hyperparameters (+search method) · Validation strategy · Metrics · Limitations · Inference latency (measured) · Artifact format.

Planned order (baseline first, then complexity as justified):
1. Logistic Regression (class-weighted; scaled features) — baseline.
2. Random Forest.
3. XGBoost (`scale_pos_weight`, early stopping on validation).
4. Isolation Forest (unsupervised; main unlabeled detector).
5. LOF (`novelty=True` for inference; subsample fit — O(n²) memory/time).
6. One-Class SVM (subsample; scale; kernel RBF — poor scaling, documented).
7. Autoencoder (PyTorch, trained on legitimate-only/unlabelled data; reconstruction error score).
8. GNN — **gated** (D-012): only if graph features show benefit and Elliptic experiments are in scope.

## Metrics
Accuracy (reported but not used for selection), precision, recall, F1, **PR-AUC (primary)**, ROC-AUC, FPR, recall at fixed FPR, precision@k, detection latency (ms/txn single and batch), throughput (txn/s). Thresholds selected on validation; confidence intervals via bootstrap or multiple seeds.

## Hybrid / ensemble definition (RQ1)
Candidate: `hybrid = w_s·rank(supervised_score) + w_u·rank(unsupervised_score)`, weights tuned on validation; also stacking with logistic regression meta-model. Both reported against components.

## Behavioral score (B)
Robust deviation per account: median/MAD z-scores for amount, rate (tx per window vs historical), hour-of-day rarity (histogram surprisal), new-counterparty indicator, burst indicator (k tx in t minutes). Mapped to 0–100 via a documented monotone transform (e.g., `100·(1−exp(−z/τ))` calibrated on validation). Cold-start → unavailable.

## Graph score (G)
Combination of normalised: cycle membership, rapid-chain participation, fan-in/out percentile, shared-beneficiary count, proximity to previously flagged accounts (only *past* flags), community risk density. Weights configurable; evaluated in RQ2.

## Duplicate score (D)
Exact ID → 100; invoice-number+vendor+amount+date exact → high; fuzzy: `rapidfuzz` token-set ratio on vendor, normalised invoice-number edit distance, amount equality/relative diff, date proximity; image: perceptual hash (pHash/dHash) Hamming distance. Combined weighted similarity; classes by configurable thresholds; legitimate-repeat heuristic (regular interval + same vendor/amount, distinct invoice numbers).

## Risk scoring and missing signals
Formula (initial, configurable, versioned): `R = 0.25A + 0.20B + 0.20G + 0.15F + 0.10D + 0.10H`.
**Missing-signal policy (default `renormalize`)**: `R = Σ wᵢSᵢ / Σ wᵢ` over *available* components; store `weight_coverage = Σ wᵢ(avail) / Σ wᵢ`. If coverage < `min_coverage` (default 0.5) the assessment is flagged `low_coverage` and capped from "Critical" auto-escalation without analyst review. Other policies selectable for experiments: `neutral_prior` (impute population median), `strict` (no score). Comparability rule: scores with different coverage are comparable only within ±policy tolerance; UI always shows coverage and which components were unavailable; historical comparisons group by `config_version` + `algorithm_version`. Never treat unavailable as 0 silently.
Calibration (Phase 9): grid/Bayesian search or logistic-regression weights on validation labels (PaySim) maximising PR-AUC / precision@k; report weight sensitivity.
Categories: 0–29 Low, 30–59 Medium, 60–79 High, 80–100 Critical (configurable, not regulatory).

## Explainability design
- Tree models: SHAP `TreeExplainer`; IF: SHAP on tree structure (slower; sample background) or surrogate; AE: per-feature reconstruction error contribution; LOF/OCSVM: LIME or kernel-SHAP on samples only.
- LIME for local tabular explanations where tree SHAP is unsuitable; document instability.
- Each `Explanation` stores model_version, prediction id, feature values, contributions, background-data description, generator version.
- UI always labels sections: Model prediction · Anomaly indicator · Supporting evidence · Investigator assessment · Final outcome; includes non-proof disclaimer.

## Reproducibility
`python manage.py train_model --config experiments/<name>.yaml` (or Celery) → writes `ModelVersion`, `ModelEvaluation`, artifacts, and a JSON experiment record. Seeds fixed; dataset SHA recorded; library versions captured.
