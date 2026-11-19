"""Pure-Python graph analytics (NetworkX/pandas; no Django, no database, no Neo4j).

Input is an edge frame with columns: tx_id (int), src (int), dst (int), amount (float), t (UTC epoch seconds).
All detectors are time-aware and bounded (depth, window, budget) so they cannot blow up on dense graphs; when a
budget is hit the result says so (`truncated`) instead of silently dropping findings.
"""

CONFIG = {
    "version": "g1",
    "cycle": {"max_len": 5, "window_s": 7 * 86400.0, "budget": 300_000, "max_findings": 500},
    "chain": {"min_hops": 3, "max_hop_s": 3600.0, "retention": 0.8, "max_findings": 500},
    "fan": {"window_s": 86400.0, "min_n": 5, "include_merchants": False, "max_findings": 500},
    "shared": {"min_common": 2, "min_senders": 3, "max_dst_fanin": 500, "max_findings": 500},
    "dense": {"min_size": 5, "max_size": 200, "min_density": 0.5, "min_clustering": 0.5},
    "weights": {"cycle": 0.25, "chain": 0.25, "fan": 0.20, "shared": 0.15, "cluster": 0.15},
    "blend_max": 0.5,
    "max_txids_per_finding": 50,
}
