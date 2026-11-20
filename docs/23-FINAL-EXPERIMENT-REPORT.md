# 23 — Final experiment report (RQ1–RQ6)

Rule from doc 08: **no result is reported unless an executed, reproducible experiment produced it.** This report only collects what was run; details, tables and limitations are in doc 08 and doc 19. Nothing below was added or rerun in Phase 16.

| RQ | Question | Status | What the evidence says |
|---|---|---|---|
| RQ1 | Does a hybrid (supervised + unsupervised) beat individual models? | **Not executed** | Individual models were evaluated (RF, XGBoost, LR, Isolation Forest, LOF, One-Class SVM, autoencoder); no hybrid or stacked model was built or tested. No claim. |
| RQ2 | Do graph features improve a supervised model? | **Not executed** | Graph analytics exist as detectors/scores (Phase 7), but the paired "tabular vs tabular + graph features" experiment (Phase 7B) and the GNN go/no-go decision (D-012) were not run. On the real slice the detectors found 84 fan-in patterns and no cycles/chains, so there is little graph signal in PaySim's structure. No claim. |
| RQ3 | Does unsupervised learning find fraud without labels? | **Partial** | Unsupervised models were trained without labels and evaluated on held-out labels: on PaySim `core` they are weak (Isolation Forest PR-AUC 0.035, LOF 0.099, One-Class SVM 0.046, autoencoder 0.007); with balance features Isolation Forest reaches 0.494 and LOF 0.416 (the simulator leaks the label there). On ULB they are far below supervised models (0.005–0.056 vs 0.73–0.76). The planned overlap analysis with supervised alerts and the manual review of unmatched top-k were **not** done. |
| RQ4 | Can explanations be trusted/communicated? | **Executed** (real PaySim slice, no labels) | SHAP is exact (additivity error ≤ 8.4e-7), deterministic and faithful by the deletion test (removing its top-k features lowers the score 2–5× more than random). LIME is much less reliable: top-3 overlap between seeds 0.68–0.75, agreement with SHAP 17–46 %, its top feature barely lowers the score when removed. SHAP is shown first. The planned small structured usability review with a rubric with human reviewers was **not** done. |
| RQ5 | Does the combined risk score prioritise better than one model score? | **Executed, unresolved** | On the later half of the real slice (80 frauds): PR-AUC 0.073 [0.034–0.129] for the model alone, 0.069 for default weights, 0.073 for tuned weights (collapsed to the model alone). No benefit shown. Cause: with PaySim's single-use senders three of six signals carry no information; only 80 evaluation frauds. Needs data with repeat accounts. |
| RQ6 | How much does performance decay over time? | **Not executed** | One chronological train/validation/test split exists; a rolling-window drift study was not run. The only related observation is the validation-to-test base-rate shift on PaySim (doc 19): XGBoost validation PR-AUC 0.184 vs test 0.417, and thresholds tuned on validation transfer poorly. No decay curve. |

## Headline results that are supported
1. On PaySim without balance fields, XGBoost > Random Forest > Logistic Regression ≫ Isolation Forest (non-overlapping bootstrap intervals; one seed, one split). XGBoost PR-AUC 0.417 (base rate 0.436 %).
2. With balance fields PaySim is separable by construction (PR-AUC 1.000): informative about the simulator, not about real fraud.
3. On ULB, LR, RF and XGBoost are statistically indistinguishable (52 test frauds).
4. Inference is cheap: XGBoost/LR ≈ 0.05–0.1 ms per transaction, Random Forest ≈ 12 ms, LOF ≈ 14 ms; batch XGBoost 10⁷ rows/s (doc 20).
5. The platform's scoring matches the research code exactly on the same rows (PR-AUC 0.2109 both ways).

## Threats to validity
Synthetic data (PaySim) and heavily pre-processed data (ULB); one seed and one split, so no seed variance; small hyper-parameter searches; a very low base rate with few test positives; PaySim's receiver/sender structure removes the behavioural and frequency signals; heuristic, uncalibrated constants in the behaviour, graph and risk engines.

## What would complete the study
Run RQ1 (hybrid), RQ2 (graph features, paired over seeds) and RQ6 (rolling windows) on the existing pipeline; do the RQ3 overlap analysis and the RQ4 reviewer rubric; repeat RQ5 on a dataset with repeat accounts. These need your go-ahead on scope and time (open decisions in the tracker).
