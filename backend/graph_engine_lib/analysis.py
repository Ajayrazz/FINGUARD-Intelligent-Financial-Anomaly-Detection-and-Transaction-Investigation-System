"""Run all detectors on an edge frame and turn the results into findings, per-account metrics and a graph score G."""

from __future__ import annotations

from typing import Any

import pandas as pd

from . import CONFIG, algorithms

FINDING_KIND = {
    "cycle": "cycle",
    "chain": "chain",
    "fan_in": "fan",
    "fan_out": "fan",
    "shared_beneficiary": "shared",
    "dense_cluster": "cluster",
}


def clean_edges(df: pd.DataFrame) -> pd.DataFrame:
    """Drop transactions without a receiver, self-loops and non-positive amounts (they carry no flow)."""
    d = df.dropna(subset=["src", "dst"])
    d = d[(d["src"] != d["dst"]) & (d["amount"] > 0)]
    return d.astype(
        {"tx_id": "int64", "src": "int64", "dst": "int64", "amount": "float64", "t": "float64"}
    ).reset_index(drop=True)


def analyze(df: pd.DataFrame, merchants: set[int] | None = None, cfg: dict[str, Any] = CONFIG) -> dict[str, Any]:
    edges = clean_edges(df)
    findings: list[dict[str, Any]] = []
    truncated: dict[str, bool] = {}
    for name, fn in (
        ("cycle", lambda: algorithms.find_cycles(edges, cfg)),
        ("chain", lambda: algorithms.find_chains(edges, cfg)),
        ("fan", lambda: algorithms.find_fans(edges, merchants, cfg)),
        ("shared_beneficiary", lambda: algorithms.find_shared_beneficiaries(edges, merchants, cfg)),
    ):
        found, trunc = fn()
        findings += found
        truncated[name] = trunc
    metrics, communities = algorithms.node_metrics(edges)
    findings += algorithms.find_dense_clusters(edges, communities, cfg)
    metrics = metrics.assign(graph_risk_score=0.0)
    comp = {k: pd.Series(0.0, index=metrics.index) for k in cfg["weights"]}
    for f in findings:
        kind = FINDING_KIND[f["type"]]
        members = (
            f["account_ids"]
            if f["type"] != "shared_beneficiary"
            else f["evidence"]["senders"] + f["evidence"]["beneficiaries"]
        )
        for a in members:
            if a in comp[kind].index and f["score"] > comp[kind][a]:
                comp[kind][a] = f["score"]
    w = cfg["weights"]
    wsum = sum(w.values())
    weighted = sum(w[k] * comp[k] for k in w) / wsum
    top = pd.concat(comp.values(), axis=1).max(axis=1) if len(metrics) else pd.Series(dtype=float)
    metrics["graph_risk_score"] = (cfg["blend_max"] * top + (1 - cfg["blend_max"]) * weighted).round(2)
    for k in w:
        metrics[f"component_{k}"] = comp[k].round(2)
    return {
        "findings": findings, "metrics": metrics, "truncated": truncated,
        "summary": {"nodes": int(len(metrics)), "edges": int(len(edges)), "findings": len(findings), "version": cfg["version"]},
    }  # fmt: skip
