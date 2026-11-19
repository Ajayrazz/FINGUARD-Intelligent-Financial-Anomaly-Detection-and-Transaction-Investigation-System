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

## Algorithms 2–4 — Random Forest, XGBoost, Isolation Forest (executed 2026-11-19, seed 42)
Reproduce: `python -m ml_engine.experiments.runner --dataset paysim --feature-set core|core+balance --model lr|rf|xgb|iforest` (ULB: `--dataset creditcard`). Same features, splits, frozen-threshold rule and metrics as Algorithm 1. Registered in the model registry (12 versions). Full detail (selection trials, hyper-parameters, versions) is in each `results.json`.

| | Random Forest | XGBoost | Isolation Forest |
|---|---|---|---|
| Why used | Non-linear baseline, robust to scaling | Strong tabular learner, native imbalance handling | Unsupervised: scores rarity without labels (RQ3) |
| Training data | All train positives + 400k sampled negatives of 4.46M (PaySim) / all train rows (ULB) — resampling on train only | Full train split | Full train features, **labels never used in fit** (tested) |
| Hyper-parameters | 100 trees, `max_features=sqrt`, `balanced_subsample`; `min_samples_leaf` ∈ {1,5,20} chosen on validation PR-AUC | `hist`, lr 0.1, subsample/colsample 0.8; `max_depth` ∈ {4,6,8} × `scale_pos_weight` ∈ {1, √(neg/pos)}, early stopping (30) on validation aucpr, chosen on validation PR-AUC | 200 trees, `max_samples=1024`, `contamination=auto`; score = −`score_samples` |
| Threshold | max F1 on validation, frozen for test (for Isolation Forest this is the only use of labels) | same | same |
| Artifact | joblib (`RandomForestClassifier`) | joblib (`XGBClassifier`) | joblib (`IsolationForest`) |

Test-split results (PR-AUC with bootstrap 95% CI; test base rates: PaySim 0.436%, ULB 0.122%):

| Dataset / features | LR | Random Forest | XGBoost | Isolation Forest |
|---|---|---|---|---|
| PaySim `core` | 0.194 [0.182, 0.207] | 0.361 [0.349, 0.375] | **0.417** [0.404, 0.431] | 0.035 [0.033, 0.037] |
| PaySim `core+balance` | 0.989 [0.987, 0.992] | **1.000** | **1.000** | 0.494 [0.476, 0.511] |
| ULB | 0.729 [0.618, 0.842] | 0.764 [0.673, 0.862] | 0.761 [0.667, 0.860] | 0.056 [0.035, 0.089] |

Other test metrics (recall at 1% false-positive rate; precision / recall at the frozen threshold):

| Run | Recall @ FPR 1% | Precision / Recall at threshold |
|---|---|---|
| PaySim core — LR / RF / XGB / IF | 0.358 / 0.677 / 0.695 / 0.092 | 0.745/0.073 · 0.990/0.076 · 0.950/0.179 · 0.057/0.558 |
| PaySim core+balance — LR / RF / XGB / IF | 0.999 / 1.000 / 1.000 / 0.534 | 0.988/0.992 · 1.000/0.993 · 1.000/0.995 · 0.830/0.467 |
| ULB — LR / RF / XGB / IF | 0.808 / 0.827 / 0.827 / 0.577 | 0.970/0.615 · 0.830/0.750 · 0.765/0.750 · 0.080/0.558 |

Measured inference (CPU in Docker; scoring only, feature computation excluded): single transaction — LR 0.1 ms, XGBoost 0.05 ms, Isolation Forest 4–5 ms, Random Forest 12 ms (thread start-up per call with `n_jobs=-1`; a tuned deployment would set `n_jobs=1`); batch — LR 3–8×10⁶ rows/s, XGBoost 1–9×10⁷, RF 1–2×10⁶, Isolation Forest 1.5–1.8×10⁵.

**What the evidence supports**
1. **Without balance fields on PaySim the ranking is XGBoost > Random Forest > LR ≫ Isolation Forest**; the bootstrap intervals do not overlap, so this ordering holds on this test split (it reflects test-row sampling only, one seed, no training-variance estimate). XGBoost's absolute level (PR-AUC 0.42, recall 0.18 at the frozen threshold) is still modest.
2. **With balance fields the supervised tree models separate PaySim perfectly (PR-AUC 1.000 on validation and test).** This confirms that the balance fields encode the label through the simulator's rules; the result says nothing about real-world skill and cannot discriminate between algorithms. The `core` rows are the informative comparison.
3. **ULB: LR, RF and XGBoost are statistically indistinguishable** (intervals overlap heavily, 52 test frauds). No ranking is claimed. Isolation Forest is far lower (0.056) although its ROC-AUC is 0.94: rare ≠ fraudulent in PCA space.
4. **Isolation Forest (unsupervised):** weak on `core` (0.035, barely 8× the base rate) but 0.494 with balance features, i.e. it finds the drained-account anomaly without labels. This is a first, partial answer to RQ3 (unlabeled detection helps only when the features expose the anomaly); the overlap analysis with supervised alerts is still to do.
5. **Hyper-parameter sensitivity is low**: XGBoost's validation PR-AUC on PaySim `core` spans only 0.177–0.184 across all six grid points; Random Forest 0.040–0.105 (leaf size matters). Selection on PaySim validation is noisy because validation has just 564 frauds at a 0.058% base rate.
6. Validation vs test PR-AUC differ strongly on PaySim `core` (XGBoost 0.184 vs 0.417) because of the base-rate shift documented in doc 19; thresholds tuned on validation transfer poorly (high precision, low recall).

**Limitations:** one seed and one chronological split (no seed variance, no rolling-window drift study); small searches; Random Forest uses 9% of train negatives; Isolation Forest thresholding uses validation labels; RQ1 (hybrid) not yet tested; LOF, One-Class SVM and the autoencoder are 5C.

## Algorithms 5–7 — Local Outlier Factor, One-Class SVM, Autoencoder (executed 2026-11-19, seed 42)
Reproduce: `python -m ml_engine.experiments.runner --dataset paysim --feature-set core|core+balance --model lof|ocsvm|ae` (ULB: `--dataset creditcard`). All three are **unsupervised**: they are fitted on unlabeled train features and labels are used only afterwards to pick the alert threshold on validation (a test confirms flipped labels leave scores unchanged). **None was tuned**: one documented configuration each.

| | LOF | One-Class SVM | Autoencoder (PyTorch) |
|---|---|---|---|
| Why used | Local-density outliers (RQ3) | Boundary around "normal" | Reconstruction error as anomaly score (RQ3) |
| Fit data | Seeded 50k-row unlabeled train sample (O(n²)); novelty mode so new rows can be scored | Seeded 20k-row unlabeled train sample (super-linear training) | All 4.46M (PaySim) / 198k (ULB) unlabeled train rows |
| Preprocessing | `StandardScaler` fitted on the train sample | same | `StandardScaler` fitted on train, clipped to ±10σ |
| Hyper-parameters | `n_neighbors=35` | RBF, `gamma=scale`, `nu=0.01` (208–625 support vectors) | MLP d→max(d,16)→max(d/3,4)→…→d, ReLU, Adam 1e-3, batch 2048, ≤15 epochs, patience 3 on unlabeled validation reconstruction loss |
| Score | −LOF | −OCSVM score | per-row mean squared reconstruction error |
| Artifact | joblib | joblib | joblib (scaler + torch module) |

Test-split PR-AUC (bootstrap 95% CI; base rates PaySim 0.436%, ULB 0.122%). Isolation Forest and the supervised models repeated from the tables above:

| Dataset / features | LOF | One-Class SVM | Autoencoder | Isolation Forest | XGBoost |
|---|---|---|---|---|---|
| PaySim `core` | 0.099 [0.091, 0.109] | 0.046 [0.043, 0.049] | 0.007 [0.007, 0.007] | 0.035 | 0.417 |
| PaySim `core+balance` | 0.416 [0.403, 0.430] | 0.175 [0.168, 0.182] | 0.317 [0.308, 0.325] | 0.494 | 1.000 |
| ULB | 0.005 [0.003, 0.011] | 0.048 [0.031, 0.078] | 0.016 [0.009, 0.024] | 0.056 | 0.761 |

ROC-AUC / recall at 1% false-positive rate, test: PaySim core — LOF 0.678 / 0.261, OCSVM 0.779 / 0.278, AE 0.649 / 0.030; PaySim core+balance — LOF 0.995 / 0.970, OCSVM 0.948 / 0.748, AE 0.996 / 1.000; ULB — LOF 0.631 / 0.135, OCSVM 0.923 / 0.481, AE 0.898 / 0.250.

Measured scoring cost (CPU in Docker, model only): single transaction — OCSVM 0.1 ms, autoencoder ~0.7 ms, LOF 2–15 ms (varies; k-NN query against the 50k sample); batch rows/s — autoencoder 0.8–1.7×10⁷, OCSVM 5×10⁴–2.4×10⁵, LOF 2–4×10⁴. LOF scoring of the 6.3M PaySim rows took about 2–3 minutes per feature set; train-split metrics for LOF/OCSVM use a seeded 200k-row sample (stated in `results.json`).

**What the evidence supports**
1. **Unsupervised detection is far weaker than supervised here.** On PaySim `core` the best unsupervised result (LOF 0.099) is a quarter of XGBoost's 0.417; on ULB the best (Isolation Forest 0.056, OCSVM 0.048) is ~1/15 of XGBoost. Anomaly scores for "rare" do not equal "fraud".
2. **Balance features lift all unsupervised models** (PaySim: LOF 0.10→0.42, OCSVM 0.05→0.17, AE 0.007→0.32, IF 0.035→0.49) — the "drained account with accounting error" pattern is anomalous in feature space. The autoencoder and LOF reach ROC-AUC ≈ 0.995 and recall 97–100% at 1% false positives, yet PR-AUC stays ≤ 0.5: they flag the fraud but also many legitimate rows. As in doc 08 above, this reflects simulator rules.
3. **Ranking among unsupervised models depends on the dataset and feature set** (IF best with balance fields; LOF best without; on ULB all are near-chance by PR-AUC), so no single unsupervised winner is claimed. Intervals are narrow on PaySim (large test set) so those orderings hold for this split; ULB intervals are wide.
4. **ULB:** unsupervised PR-AUC ≤ 0.056 even though OCSVM/AE/IF ROC-AUC is 0.90–0.94; PCA components expose few rare-and-fraudulent regions.
5. Validation PR-AUC is tiny for every unsupervised model on PaySim (≤ 0.08) because of the 0.058% validation base rate, so thresholds picked there transfer poorly (see the precision/recall values in `results.json`).

**Limitations:** no tuning (neighbours, nu/gamma, architecture, epochs). The autoencoder always ran all 15 epochs (the early-stop criterion never triggered), so it may be under-trained. LOF and OCSVM see a small train sample (0.3–1% of PaySim train). One seed, one split. The RQ3 follow-up (do unsupervised top-k alerts catch frauds the supervised model misses?) and the hybrid (RQ1) are not run yet.
