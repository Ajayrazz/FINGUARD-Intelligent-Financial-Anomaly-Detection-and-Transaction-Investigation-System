# 19 — Dataset Profile and Preprocessing (Phase 5A, data stage)

All numbers below come from running `python -m ml_engine.data.prepare` on the real files (2026-11-19). They are
also stored, machine-readable, in `datasets/processed/<name>/{profile,manifest}.json` (git-ignored with the data).
Nothing here is mock data. Phase 5 experiments read only `datasets/processed/`.

## Layout and guarantees
```
datasets/
  archive*.zip                 downloaded Kaggle archives (kept)
  raw/                         extracted CSVs — read-only (chmod 444), never modified
  processed/<name>/            train.parquet  validation.parquet  test.parquet  manifest.json  profile.json
```
- The pipeline only **reads** `raw/`; it hashes each raw file (SHA-256) before and after and aborts if it changed.
- `manifest.json` records raw hash, cleaning stats, split boundaries, per-split counts, output file hashes and library
  versions, so a run can be reproduced and compared. The pipeline is deterministic (no randomness).
- Run in Docker: `docker compose exec backend python -m ml_engine.data.prepare [--dataset paysim|creditcard]` (~50 s).
- Raw SHA-256: PaySim `16910f90…eea6b`, ULB `76274b69…98551a89` (full values in the manifests).

## PaySim (`PS_20174392719_1491204439457_log.csv`, 493 MB)
| Property | Result |
|---|---|
| Rows / columns | 6,362,620 / 11 — schema matches the expected one exactly |
| Missing values | 0 in every column |
| Exact duplicate rows | 0 |
| Fraud (`isFraud=1`) | 8,213 (0.1291%); imbalance 773.7 : 1 |
| Fraud by type | TRANSFER 4,097 (0.77% of 532,909) and CASH_OUT 4,116 (0.18% of 2,237,500); **0 fraud** in PAYMENT, CASH_IN, DEBIT |
| `isFlaggedFraud` | 16 rows flagged (all fraud); 8,197 frauds (99.8%) not flagged → useless as a rule, excluded from features |
| `step` | 1–743 (hourly), all 743 values present |
| Amount | min 0 (16 rows), median 74,872, p99 1.62M, max 92.4M; fraud mean 1.47M vs overall 180k |
| Accounts | 6,353,307 distinct senders (**99.86% appear exactly once; max 3 transactions per sender**); 2,722,362 receivers; 2,150,401 receivers are merchants (`M…`) |
| Balance identity | `old − amount = new` holds for only 19.4% of senders |
| Sender drained to 0 afterwards | 98.1% of frauds vs 56.7% of legitimate rows |

Implications:
1. **Behavioural and graph signals about senders are almost absent**: a sender has no history to learn from. Features
   must lean on transaction attributes, receiver-side history and global/temporal context. Per-sender profiling is
   limited to cold-start handling (documented in doc 17).
2. **Balance fields are strongly leakage-prone**: "sender drained to 0" is nearly a fraud signature produced by the
   simulator's logic. Phase 5 will report every model **with and without balance-derived features**.
3. Only TRANSFER and CASH_OUT can be fraud, so a model's apparent skill partly comes from the `type` column; the
   evaluation also reports metrics restricted to those two types.

### Cleaning decisions (`clean_paysim`)
| Decision | Why |
|---|---|
| Rename to snake_case (`nameOrig→sender`, `oldbalanceOrg→sender_balance_before`, `isFraud→is_fraud`, …) | Matches the platform's transaction model and the Phase 4 import mapping. |
| Add `row_id` (0-based position in the raw file) | Stable key back to the source row; lets tests prove splits are disjoint and complete. |
| Tighten dtypes (`step` int16, `type` category, labels int8); amounts stay float64 | No information loss. |
| **Keep** exact duplicates (there are none) and zero-amount rows (16) | PaySim has no transaction id, so identical rows would be legitimate repeats; nothing to remove here. |
| No imputation, no outlier removal, no scaling in the cleaned data | There are no missing values; extreme amounts are real signal; scaling must be fitted on train only inside each model's pipeline (leakage rule 4). |
| `is_flagged_fraud` kept as a column but **never** a feature | Documented leakage-prone/degenerate. |

## ULB credit-card (`creditcard.csv`, 151 MB)
| Property | Result |
|---|---|
| Rows / columns | 284,807 / 31 (`Time`, `V1–V28`, `Amount`, `Class`) — schema matches |
| Missing values | 0 |
| Exact duplicate rows | **1,081** (19 are frauds) |
| Fraud (`Class=1`) | 492 (0.1727%); imbalance 577.9 : 1 |
| `Time` | 0–172,792 s (48 h from the first transaction) |
| Amount | 0–25,691; 1,825 zero-amount rows; fraud mean 122.2 vs legitimate mean 88.3 |

### Cleaning decisions (`clean_creditcard`)
| Decision | Why |
|---|---|
| **Drop the 1,081 exact duplicates** (keep first); 283,726 rows remain, 473 frauds | A duplicate landing on both sides of a split would leak a training row into evaluation. The count is stored in the manifest. Reported metrics are on the de-duplicated data and say so. |
| Rename `Time/Amount/Class → time/amount/is_fraud`, add `row_id` | Consistent with PaySim. |
| Keep `V1–V28` as given; no scaling in the cleaned file | PCA outputs; scaling (of `amount`, `time`) happens inside train-fitted pipelines. |
| No account column | The behavioural / graph / duplicate modules cannot use this dataset; it is an ML benchmark only. |

## Splitting (no leakage)
Both datasets are split **chronologically**, never randomly, 70 / 15 / 15 by cumulative row share, with the boundary
snapped to a whole time value so rows sharing a timestamp (a PaySim hour) never straddle two splits.
`verify_split` runs on every preparation and aborts (`LeakageError`) unless: the splits are disjoint by `row_id` and
cover every row; train < validation < test strictly in time; every split contains positives.

| Dataset | Split | Rows | Frauds | Fraud rate | Time range |
|---|---|---|---|---|---|
| PaySim | train | 4,463,587 | 3,643 | 0.082% | step 1–323 |
| PaySim | validation | 980,416 | 564 | 0.058% | step 324–378 |
| PaySim | test | 918,617 | 4,006 | 0.436% | step 379–743 |
| ULB | train | 198,609 | 366 | 0.184% | 0–132,906 s |
| ULB | validation | 42,560 | 55 | 0.129% | 132,907–151,320 s |
| ULB | test | 42,557 | 52 | 0.122% | 151,321–172,792 s |

Observations to carry into the experiments:
- **PaySim's fraud rate is not stationary**: 0.058% in validation vs 0.436% in test (7.6×). Thresholds chosen on
  validation will face a very different base rate; PR-AUC and recall at fixed false-positive rate are therefore reported
  per split, and precision-at-threshold is reported with the base rate. This is real concept/prior drift in the data
  (RQ6), not a bug. Measured cause: fraud per hour is roughly constant
  (11.3 / 10.3 / 11.0 per step in train / validation / test) while total volume per hour collapses
  (13,819 / 17,826 / 2,517 rows per step), and some late hours are almost entirely fraud (e.g. steps 75, 149, 223,
  519, 593, 741 have as many frauds as rows). This is a simulator artefact: time-of-run features (`step`, hour of
  day) would be spurious shortcuts and are excluded from the baseline feature set unless justified.
- The chronological split is the realistic protocol but yields **small ULB validation/test positive counts (55 / 52)**,
  so ULB metrics will have wide uncertainty; bootstrap confidence intervals are mandatory there.
- Account overlap (PaySim): only 0.21% of validation senders and 0.24% of test senders were seen earlier. Same-account
  leakage (leakage register item 7) is therefore negligible *and* behavioural features are nearly impossible.

## Tests (`backend/tests/test_ml_data.py`, 17, synthetic frames)
Schema/value validation (missing column, step range, unknown type, negative amount, non-binary label, wrong dtype);
cleaning leaves the raw frame untouched and keeps `row_id`s; duplicate handling; chronological order, completeness and
disjointness; same-timestamp rows never straddle a boundary; `verify_split` detects injected leakage; determinism;
**perturbation test** (changing test-window values does not change the train split); account-overlap report.

## Limitations
- PaySim is synthetic; results do not transfer to real institutions. PaySim time is hours, not clock times.
- ULB features are PCA-anonymised: explanations can only name `V1…V28`.
- Elliptic (graph experiments) is not downloaded yet; it is not needed until Phase 7B.
- The split is a single chronological partition; rolling-window evaluation (RQ6) comes with the experiments.

## Next stage (features and baseline) — see doc 08
Causal features (`ml_engine/features/paysim.py`) use only the row and strictly earlier steps; a perturbation test proves that changing future rows leaves earlier features unchanged. Baseline results: doc 08, "Algorithm 1".
