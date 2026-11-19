"""Detectors. Each returns (findings, truncated). A finding is a dict:
{type, account_ids, transaction_ids, score (0-100, heuristic), evidence}."""

from __future__ import annotations

import math
from bisect import bisect_right
from collections import Counter, defaultdict
from typing import Any

import networkx as nx
import numpy as np
import pandas as pd
from scipy.stats import poisson

from . import CONFIG


def _cap(ids: list[int], cfg: dict[str, Any]) -> list[int]:
    return [int(i) for i in ids[: cfg["max_txids_per_finding"]]]


def aggregate_graph(df: pd.DataFrame) -> nx.DiGraph:
    """One directed edge per (src, dst) with count, total amount, first/last time."""
    if df.empty:
        return nx.DiGraph()
    agg = (
        df.groupby(["src", "dst"], sort=False)
        .agg(count=("tx_id", "size"), total=("amount", "sum"), first_t=("t", "min"), last_t=("t", "max"))
        .reset_index()
    )
    return nx.from_pandas_edgelist(
        agg, "src", "dst", edge_attr=["count", "total", "first_t", "last_t"], create_using=nx.DiGraph
    )


# --------------------------------------------------------------------------------------- cycles
def find_cycles(df: pd.DataFrame, cfg: dict[str, Any] = CONFIG) -> tuple[list[dict[str, Any]], bool]:
    """Time-ordered cycles of 2..max_len accounts: transactions t1 < t2 < ... < tk with dst_i = src_{i+1} and
    dst_k = src_1, all within `window_s`. Only strongly connected components can contain cycles, so the search
    runs inside them; the first (earliest) transaction fixes the start, so a cycle is found once per rotation."""
    c = cfg["cycle"]
    G = aggregate_graph(df)
    findings: dict[tuple[int, ...], dict[str, Any]] = {}
    truncated = False
    budget = c["budget"]
    for comp in nx.strongly_connected_components(G):
        if len(comp) < 2:
            continue
        sub = df[df["src"].isin(comp) & df["dst"].isin(comp)].sort_values("t", kind="stable")
        out: dict[int, list[tuple[float, int, int, float]]] = defaultdict(list)
        for tx, s, d, a, t in zip(sub["tx_id"], sub["src"], sub["dst"], sub["amount"], sub["t"], strict=True):
            out[int(s)].append((float(t), int(d), int(tx), float(a)))
        times = {n: [e[0] for e in lst] for n, lst in out.items()}
        for start, lst in out.items():
            for t0, d0, tx0, a0 in lst:
                stack = [(d0, t0, [start, d0], [tx0], [a0])]
                while stack:
                    node, t_last, path, txs, amts = stack.pop()
                    budget -= 1
                    if budget <= 0:
                        return list(findings.values()), True
                    edges = out.get(node, [])
                    lo = bisect_right(times.get(node, []), t_last)
                    for t, d, tx, a in edges[lo:]:
                        if t - t0 > c["window_s"]:
                            break
                        if d == start and len(path) >= 2:
                            ns = tuple(path)
                            key = _canon(ns)
                            span = t - t0
                            amts2 = [*amts, a]
                            f = findings.get(key)
                            occ = f["evidence"]["occurrences"] + 1 if f else 1
                            if f is None or span < f["evidence"]["span_s"]:
                                findings[key] = _cycle_finding(ns, [*txs, tx], amts2, span, occ, c, cfg)
                            else:
                                f["evidence"]["occurrences"] = occ
                        elif d not in path and len(path) < c["max_len"]:
                            stack.append((d, t, [*path, d], [*txs, tx], [*amts, a]))
                if len(findings) >= c["max_findings"]:
                    return list(findings.values()), True
    return list(findings.values()), truncated


def _canon(nodes: tuple[int, ...]) -> tuple[int, ...]:
    i = nodes.index(min(nodes))
    return nodes[i:] + nodes[:i]


def _cycle_finding(nodes, txs, amts, span, occurrences, c, cfg) -> dict[str, Any]:
    retention = min(amts) / max(amts) if max(amts) > 0 else 0.0
    speed = 1.0 - min(span / c["window_s"], 1.0)
    score = 40.0 + 20.0 * retention + 30.0 * speed + min(10.0, 2.5 * (occurrences - 1))
    return {
        "type": "cycle", "account_ids": [int(n) for n in nodes], "transaction_ids": _cap(txs, cfg),
        "score": round(min(score, 100.0), 2),
        "evidence": {"length": len(nodes), "span_s": float(span), "amount_retention": retention,
                     "total_amount": float(sum(amts)), "occurrences": occurrences},
    }  # fmt: skip


# --------------------------------------------------------------------------------------- chains
def find_chains(df: pd.DataFrame, cfg: dict[str, Any] = CONFIG) -> tuple[list[dict[str, Any]], bool]:
    """Rapid pass-through chains: transaction e_out leaves an account within `max_hop_s` after e_in arrived and
    forwards at least `retention` of its amount. Each outgoing transaction links to its best (latest eligible,
    largest) incoming one, giving a forest; maximal paths of >= min_hops transactions are reported."""
    c = cfg["chain"]
    if df.empty:
        return [], False
    d = df.sort_values("t", kind="stable")
    by_dst = {int(k): g for k, g in d.groupby("dst", sort=False)}
    pred: dict[int, int] = {}
    info: dict[int, tuple[int, int, float, float]] = {}  # tx -> (src, dst, amount, t)
    for tx, s, dd, a, t in zip(d["tx_id"], d["src"], d["dst"], d["amount"], d["t"], strict=True):
        info[int(tx)] = (int(s), int(dd), float(a), float(t))
    for v, g_out in d.groupby("src", sort=False):
        g_in = by_dst.get(int(v))
        if g_in is None:
            continue
        t_in, a_in, tx_in, s_in = (
            g_in["t"].to_numpy(),
            g_in["amount"].to_numpy(),
            g_in["tx_id"].to_numpy(),
            g_in["src"].to_numpy(),
        )
        for tx, dd, a, t in zip(g_out["tx_id"], g_out["dst"], g_out["amount"], g_out["t"], strict=True):
            hi = int(np.searchsorted(t_in, t, side="left"))  # incoming strictly earlier
            lo = int(np.searchsorted(t_in, t - c["max_hop_s"], side="left"))
            best = None
            for j in range(hi - 1, lo - 1, -1):  # latest first
                if a >= c["retention"] * a_in[j] and a <= a_in[j] * 1.0001 and s_in[j] != dd:
                    best = int(tx_in[j])
                    break
            if best is not None:
                pred[int(tx)] = best
    children: dict[int, list[int]] = defaultdict(list)
    for tx, p in pred.items():
        children[p].append(tx)
    roots = [p for p in children if p not in pred]
    findings: list[dict[str, Any]] = []
    for r in roots:
        stack = [[r]]
        while stack:
            path = stack.pop()
            kids = children.get(path[-1])
            if kids:
                stack.extend([*path, k] for k in kids)
            elif len(path) >= c["min_hops"]:
                findings.append(_chain_finding(path, info, c, cfg))
                if len(findings) >= c["max_findings"]:
                    return findings, True
    return findings, False


def _chain_finding(path: list[int], info, c, cfg) -> dict[str, Any]:
    rows = [info[t] for t in path]
    amts = [r[2] for r in rows]
    times = [r[3] for r in rows]
    accounts = [rows[0][0], *[r[1] for r in rows]]
    gaps = np.diff(times)
    retention = amts[-1] / amts[0] if amts[0] > 0 else 0.0
    speed = 1.0 - float(np.mean(gaps)) / c["max_hop_s"] if len(gaps) else 0.0
    base = 100.0 * (1.0 - math.exp(-(len(path) - 1) / 2.0))
    score = base * (0.5 + 0.5 * max(retention, 0.0)) * (0.5 + 0.5 * max(speed, 0.0))
    return {
        "type": "chain", "account_ids": [int(a) for a in accounts], "transaction_ids": _cap(path, cfg),
        "score": round(min(score, 100.0), 2),
        "evidence": {"hops": len(path), "span_s": float(times[-1] - times[0]), "amount_retention": retention,
                     "first_amount": amts[0], "last_amount": amts[-1], "mean_gap_s": float(np.mean(gaps)) if len(gaps) else 0.0},
    }  # fmt: skip


# --------------------------------------------------------------------------------------- fan-in / fan-out
def find_fans(
    df: pd.DataFrame, merchants: set[int] | None = None, cfg: dict[str, Any] = CONFIG
) -> tuple[list[dict[str, Any]], bool]:
    """fan_in: an account receiving from >= min_n distinct senders inside `window_s`; fan_out: the mirror image.
    Fan-in to merchants is normal commerce and is skipped unless `include_merchants`."""
    c = cfg["fan"]
    merchants = merchants or set()
    findings: list[dict[str, Any]] = []
    for kind, key, other in (("fan_in", "dst", "src"), ("fan_out", "src", "dst")):
        d = df.sort_values([key, "t"], kind="stable")
        for acct, g in d.groupby(key, sort=False):
            if len(g) < c["min_n"]:
                continue
            if kind == "fan_in" and int(acct) in merchants and not c["include_merchants"]:
                continue
            t, o, tx, a = g["t"].to_numpy(), g[other].to_numpy(), g["tx_id"].to_numpy(), g["amount"].to_numpy()
            counts: Counter = Counter()
            lo, best, best_range = 0, 0, (0, 0)
            for hi in range(len(t)):
                counts[o[hi]] += 1
                while t[hi] - t[lo] > c["window_s"]:
                    counts[o[lo]] -= 1
                    if counts[o[lo]] == 0:
                        del counts[o[lo]]
                    lo += 1
                if len(counts) > best:
                    best, best_range = len(counts), (lo, hi)
            if best >= c["min_n"]:
                lo, hi = best_range
                findings.append({
                    "type": kind, "account_ids": [int(acct), *[int(x) for x in sorted(set(o[lo : hi + 1]))][:50]],
                    "transaction_ids": _cap(list(tx[lo : hi + 1]), cfg),
                    "score": round(100.0 * (1.0 - math.exp(-(best - c["min_n"] + 1) / 5.0)), 2),
                    "evidence": {"distinct_counterparties": int(best), "window_s": c["window_s"],
                                 "total_amount": float(a[lo : hi + 1].sum()), "transactions": int(hi - lo + 1)},
                })  # fmt: skip
                if len(findings) >= c["max_findings"]:
                    return findings, True
    return findings, False


# --------------------------------------------------------------------------------------- shared beneficiaries
def find_shared_beneficiaries(
    df: pd.DataFrame, merchants: set[int] | None = None, cfg: dict[str, Any] = CONFIG
) -> tuple[list[dict[str, Any]], bool]:
    """Groups of >= min_senders senders that each pay the SAME >= min_common beneficiaries.

    Built from beneficiary pairs: a pair (b1, b2) paid by >= min_senders common senders qualifies; pairs with the
    identical sender set merge into one finding. Merchants and hub beneficiaries (more than `max_dst_fanin`
    senders) are skipped: many customers using the same two shops is ordinary commerce. Each sender contributes
    at most 20 beneficiaries (pair enumeration is quadratic in that number)."""
    c = cfg["shared"]
    merchants = merchants or set()
    pairs = df[["src", "dst"]].drop_duplicates()
    fanin = pairs.groupby("dst")["src"].nunique()
    pairs = pairs[pairs["dst"].map(fanin).between(c["min_senders"], c["max_dst_fanin"]) & ~pairs["dst"].isin(merchants)]
    src_to_dst: dict[int, list[int]] = {
        int(k): sorted(int(x) for x in v)[:20] for k, v in pairs.groupby("src")["dst"].apply(list).items()
    }
    pair_senders: dict[tuple[int, int], list[int]] = defaultdict(list)
    for sender, dsts in src_to_dst.items():
        for i in range(len(dsts)):
            for j in range(i + 1, len(dsts)):
                pair_senders[(dsts[i], dsts[j])].append(sender)
    # A pair of beneficiaries qualifies only if its common-sender count is unlikely by chance: with n_sender senders
    # in total and fan-ins f1, f2, independent choice gives f1*f2/n_senders common senders on average; require a
    # Poisson tail probability below 1% after a Bonferroni correction over the candidate pairs.
    n_senders = max(int(df["src"].nunique()), 1)
    n_pairs = max(len(pair_senders), 1)
    groups: dict[frozenset[int], set[int]] = defaultdict(set)
    for (b1, b2), senders in pair_senders.items():
        k = len(senders)
        if k < c["min_senders"]:
            continue
        expected = float(fanin[b1] * fanin[b2]) / n_senders
        if poisson.sf(k - 1, expected) * n_pairs < 0.01:
            groups[frozenset(senders)].update((b1, b2))
    findings: list[dict[str, Any]] = []
    for senders_fs, bens in sorted(groups.items(), key=lambda kv: (-len(kv[0]), sorted(kv[0]))):
        senders = sorted(senders_fs)
        benef = sorted(bens)
        sub = df[df["src"].isin(senders) & df["dst"].isin(benef)]
        findings.append({
            "type": "shared_beneficiary", "account_ids": senders[:100] + benef[:50], "transaction_ids": _cap(list(sub["tx_id"]), cfg),
            "score": round(min(100.0, 30.0 + 15.0 * (len(senders) - c["min_senders"] + 1) + 10.0 * (len(benef) - c["min_common"])), 2),
            "evidence": {"senders": senders[:100], "beneficiaries": benef[:50], "total_amount": float(sub["amount"].sum())},
        })  # fmt: skip
        if len(findings) >= c["max_findings"]:
            return findings, True
    return findings, False


# --------------------------------------------------------------------------------------- metrics, communities
def node_metrics(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[int, int]]:
    """Per-account degree, weighted degree, PageRank, clustering and Louvain community (components of >= 3 only)."""
    G = aggregate_graph(df)
    if G.number_of_nodes() == 0:
        return pd.DataFrame(
            columns=["in_degree", "out_degree", "weighted_in", "weighted_out", "pagerank", "clustering", "community_id"]
        ), {}
    m = pd.DataFrame({
        "in_degree": pd.Series(dict(G.in_degree())), "out_degree": pd.Series(dict(G.out_degree())),
        "weighted_in": pd.Series(dict(G.in_degree(weight="total"))), "weighted_out": pd.Series(dict(G.out_degree(weight="total"))),
        "pagerank": pd.Series(nx.pagerank(G, weight="total") if G.number_of_edges() else {}),
    })  # fmt: skip
    U = G.to_undirected()
    m["clustering"] = 0.0
    m["community_id"] = -1
    communities: dict[int, int] = {}
    next_id = 0
    for comp in nx.connected_components(U):
        if len(comp) < 3:
            continue
        sub = U.subgraph(comp)
        m.loc[list(comp), "clustering"] = pd.Series(nx.clustering(sub))
        for members in nx.community.louvain_communities(sub, weight="total", seed=42):
            for n in members:
                communities[int(n)] = next_id
            next_id += 1
    for n, cid in communities.items():
        m.loc[n, "community_id"] = cid
    return m, communities


def find_dense_clusters(
    df: pd.DataFrame, communities: dict[int, int], cfg: dict[str, Any] = CONFIG
) -> list[dict[str, Any]]:
    """Communities that are genuinely interconnected: at least `min_size` accounts, undirected density >= min_density
    and average clustering >= min_clustering. (Stars and trees - one hub with spokes - have clustering 0 and are
    not clusters, however small.)"""
    c = cfg["dense"]
    by_comm: dict[int, set[int]] = defaultdict(set)
    for n, cid in communities.items():
        by_comm[cid].add(n)
    findings = []
    for cid, nodes in by_comm.items():
        if not c["min_size"] <= len(nodes) <= c["max_size"]:
            continue
        sub = df[df["src"].isin(nodes) & df["dst"].isin(nodes)]
        und = {tuple(sorted(p)) for p in zip(sub["src"], sub["dst"], strict=True)}
        density = len(und) / (len(nodes) * (len(nodes) - 1) / 2)
        if density < c["min_density"]:
            continue
        U = nx.Graph()
        U.add_edges_from(und)
        clustering = float(np.mean(list(nx.clustering(U).values())))
        if clustering < c["min_clustering"]:
            continue
        findings.append({
            "type": "dense_cluster", "account_ids": sorted(int(n) for n in nodes)[:100], "transaction_ids": _cap(list(sub["tx_id"]), cfg),
            "score": round(min(100.0, 100.0 * density * clustering * (1 - math.exp(-len(nodes) / 6.0))), 2),
            "evidence": {"community_id": int(cid), "size": len(nodes), "density": density, "avg_clustering": clustering,
                         "total_amount": float(sub["amount"].sum())},
        })  # fmt: skip
    return findings
