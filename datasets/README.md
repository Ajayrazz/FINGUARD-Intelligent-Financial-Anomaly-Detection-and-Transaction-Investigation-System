# Datasets

Raw data is git-ignored (large, licensed). Layout and checks are described in `docs/19-DATASET-PROFILE-AND-PREPROCESSING.md`.

| Dataset | Source | Expected file |
|---|---|---|
| PaySim (primary) | Kaggle "Synthetic Financial Datasets For Fraud Detection" (Lopez-Rojas et al.) | `raw/PS_20174392719_1491204439457_log.csv` |
| ULB credit-card | Kaggle "Credit Card Fraud Detection" (ULB Machine Learning Group; database licence: DbCL) | `raw/creditcard.csv` |
| Elliptic Bitcoin | Kaggle "Elliptic Data Set" (only needed from Phase 7B) | not downloaded yet |

Steps: download the archives from Kaggle (account required), unzip into `datasets/raw/`, then
`docker compose exec backend python -m ml_engine.data.prepare`. Outputs land in `datasets/processed/`.
Never put API tokens in the repository.
