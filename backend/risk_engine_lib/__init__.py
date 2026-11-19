"""Risk scoring: combines component scores A, B, G, F, D, H (each 0-100 or *unavailable*) into one explainable score.

Pure functions (no Django, no I/O). Unavailable is never silently treated as 0: it is excluded and reported through
`weight_coverage`, or imputed/refused according to the configured policy (docs/08).

Component meanings (docs/15 D-067):
  A anomaly   - model score of the transaction, normalised to 0-100 (50 = the model's alert threshold)
  B behaviour - deviation from the sender's own history (amount, spend jump, new counterparty, hour)
  G graph     - highest score of a graph pattern (cycle, chain, fan-in/out, shared beneficiaries, cluster) involving
                either account that had completed by the time of the transaction
  F frequency - burst/velocity of the sender's transactions (the burst component of the behaviour engine)
  D duplicate - similarity of the transaction to an earlier one that has not been dismissed by a reviewer
  H history   - human-confirmed duplicates in the accounts' earlier transactions
"""

COMPONENTS = ("A", "B", "G", "F", "D", "H")
ALGORITHM_VERSION = "r1"
POLICIES = ("renormalize", "neutral_prior", "strict")
DEFAULT_WEIGHTS = {"A": 0.25, "B": 0.20, "G": 0.20, "F": 0.15, "D": 0.10, "H": 0.10}
DEFAULT_THRESHOLDS = {"medium": 30.0, "high": 60.0, "critical": 80.0}
DEFAULT_MIN_COVERAGE = 0.5
