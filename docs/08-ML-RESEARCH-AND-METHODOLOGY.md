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

## Data stage status
Splits, leakage checks (register items 1, 4 groundwork, 7) and dataset findings: see doc 19. Item 3 now has measured motivation (98.1% of PaySim frauds leave the sender at balance 0).

## Algorithm 1 — Logistic Regression baseline (executed 2026-11-19, seed 42)
Reproduce: `python -m ml_engine.experiments.baseline --dataset paysim --feature-set core|core+balance`, `--dataset creditcard`;
register with `python manage.py register_experiment <results.json>`. Artifacts + `results.json` in `datasets/artifacts/<run>/`.

- **Why used:** interpretable, fast reference; every later model must beat it to justify its complexity.
- **Features:** PaySim `core` = type one-hot, log amount, merchant-receiver flag, causal prior receiver/sender history (strictly earlier steps); `core+balance` adds balance-derived features (balances, accounting errors, drained flag, amount/balance ratio). `step`, `isFlaggedFraud`, ids are never features. ULB = `V1–V28` + log amount (`Time` excluded).
- **Preprocessing:** `StandardScaler` inside a sklearn `Pipeline`, fitted on train only.
- **Training:** `LogisticRegression(C=1, class_weight="balanced", max_iter=300)`; no hyper-parameter search yet (baseline). Imbalance handled by class weights on train only.
- **Threshold:** maximises F1 on validation, frozen before test.
- **Metrics:** PR-AUC (primary), ROC-AUC, recall at 0.1% / 1% false-positive rate, precision/recall/F1 at the frozen threshold, precision@k, bootstrap 95% CI (100 resamples, seed 42).
- **Latency (CPU, in-container, measured):** single transaction ≈ 0.10 ms median; batch ≈ 8×10⁶ rows/s (PaySim features), ≈ 4×10⁷ (ULB). Model scoring only; feature computation and I/O excluded.

Test-split results (chronological hold-out; train/validation in `results.json`):

| Run | Test base rate | PR-AUC [95% CI] | ROC-AUC | Recall @ FPR 1% | At frozen threshold: P / R / F1 |
|---|---|---|---|---|---|
| PaySim, `core` (no balance fields) | 0.436% | 0.194 [0.182, 0.207] | 0.926 | 0.358 | 0.745 / 0.073 / 0.133 |
| PaySim, `core+balance` | 0.436% | **0.989** [0.987, 0.992] | 1.000 | 0.999 | 0.988 / 0.992 / 0.990 |
| ULB credit-card (de-duplicated) | 0.122% | 0.729 [0.618, 0.842] | 0.977 | 0.808 | 0.970 / 0.615 / 0.753 |

Validation PR-AUC (where the threshold was chosen): PaySim core 0.013 (base rate 0.058%), core+balance 0.887, ULB 0.793.

**Interpretation (and cautions):**
1. The PaySim 0.989 is **not evidence of a strong detector**. It comes almost entirely from balance fields: 98.1% of frauds drain the sender to 0, and the simulator's accounting errors separate fraud almost perfectly. Without them the same model reaches PR-AUC 0.19 (≈ 45× the 0.44% base rate, but weak in absolute terms). Both numbers are reported; the honest operational claim is the `core` one, since real institutions' balance behaviour does not follow this simulator.
2. PaySim `core` PR-AUC is 0.013 on validation and 0.194 on test only because the base rate differs 7.6× (doc 19); compare each against its base rate, not each other.
3. Train PR-AUC (0.73) is below test (0.99) for `core+balance`: the cause was not investigated (a likely factor is the very different mix of legitimate volume and fraud per hour across periods, doc 19). It is not overfitting to test: nothing was tuned on test.
4. ULB test has 52 frauds: the CI is wide (0.62–0.84). Differences smaller than that between models will not be claimed.
5. PaySim `core` precision at the frozen threshold is high (0.745) but recall tiny (0.073): the validation-chosen threshold, set on a 0.058% base rate with weak scores, transfers poorly — an instance of the drift described in doc 19.
- **Limitations:** linear model; no tuning; one seed (the LR solver is deterministic, so seed variance is only in the bootstrap); no rolling-window drift analysis yet.
