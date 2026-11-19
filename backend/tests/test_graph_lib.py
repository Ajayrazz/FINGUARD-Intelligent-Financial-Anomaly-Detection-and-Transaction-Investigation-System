"""Graph library: planted cycle / rapid chain / fan-in / fan-out / shared beneficiaries are found; benign data is not."""

import numpy as np
import pandas as pd
import pytest

from graph_engine_lib import CONFIG, algorithms, analysis

H = 3600.0
T0 = 1_767_225_600.0


def edges(rows):
    """rows: (src, dst, amount, t_seconds_after_T0)"""
    return pd.DataFrame(
        {"tx_id": range(1, len(rows) + 1), "src": [r[0] for r in rows], "dst": [r[1] for r in rows],
         "amount": [float(r[2]) for r in rows], "t": [T0 + r[3] for r in rows]}
    )  # fmt: skip


def test_time_ordered_cycle_is_found_once_with_evidence():
    df = edges([(1, 2, 1000, 0), (2, 3, 990, H), (3, 1, 980, 2 * H), (9, 8, 5, 0)])
    found, trunc = algorithms.find_cycles(df)
    assert not trunc and len(found) == 1
    f = found[0]
    assert sorted(f["account_ids"]) == [1, 2, 3] and f["type"] == "cycle"
    assert f["evidence"]["length"] == 3 and f["evidence"]["amount_retention"] > 0.97 and f["score"] > 70
    assert len(f["transaction_ids"]) == 3


def test_cycle_requires_time_order_and_window():
    wrong_order = edges(
        [(1, 2, 100, 2 * H), (2, 3, 100, H), (3, 1, 100, 0)]
    )  # edges exist but not as a time-ordered loop
    assert algorithms.find_cycles(wrong_order)[0] == []
    too_slow = edges([(1, 2, 100, 0), (2, 3, 100, H), (3, 1, 100, 30 * 86400)])
    assert algorithms.find_cycles(too_slow)[0] == []
    assert algorithms.find_cycles(too_slow, {**CONFIG, "cycle": {**CONFIG["cycle"], "window_s": 60 * 86400.0}})[0] != []


def test_ping_pong_two_cycle_and_repeats_are_deduplicated_with_a_count():
    df = edges([(1, 2, 500, 0), (2, 1, 500, H), (1, 2, 500, 2 * H), (2, 1, 500, 3 * H)])
    found, _ = algorithms.find_cycles(df)
    assert len(found) == 1 and found[0]["evidence"]["occurrences"] >= 2


def test_cycle_length_is_bounded():
    n = 8
    df = edges([(i, (i + 1) % n, 100, i * 60) for i in range(n)])  # an 8-cycle, max_len default 5
    assert algorithms.find_cycles(df)[0] == []


def test_cycle_budget_marks_truncation_instead_of_silently_stopping():
    rng = np.random.default_rng(0)
    rows = [
        (int(a), int(b), 10, float(t))
        for a, b, t in zip(
            rng.integers(0, 6, 400), rng.integers(0, 6, 400), np.sort(rng.integers(0, 6 * 3600, 400)), strict=True
        )
        if a != b
    ]
    found, trunc = algorithms.find_cycles(edges(rows), {**CONFIG, "cycle": {**CONFIG["cycle"], "budget": 200}})
    assert trunc is True


def test_rapid_pass_through_chain_is_found_and_slow_or_leaky_ones_are_not():
    fast = edges([(1, 2, 10000, 0), (2, 3, 9900, 600), (3, 4, 9800, 1200), (4, 5, 9700, 1800)])
    found, _ = algorithms.find_chains(fast)
    assert len(found) == 1 and found[0]["account_ids"] == [1, 2, 3, 4, 5] and found[0]["evidence"]["hops"] == 4
    assert found[0]["score"] > 50
    slow = edges([(1, 2, 10000, 0), (2, 3, 9900, 3 * H), (3, 4, 9800, 6 * H)])
    assert algorithms.find_chains(slow)[0] == []  # each hop exceeds one hour
    leaky = edges([(1, 2, 10000, 0), (2, 3, 4000, 600), (3, 4, 3900, 1200)])
    assert algorithms.find_chains(leaky)[0] == []  # only 40% forwarded
    two_hops = edges([(1, 2, 100, 0), (2, 3, 100, 60)])
    assert algorithms.find_chains(two_hops)[0] == []  # below min_hops=3


def test_chain_does_not_count_money_returned_to_the_sender():
    df = edges([(1, 2, 100, 0), (2, 1, 100, 60), (1, 3, 100, 120)])  # 2 sends it straight back: not a pass-through
    assert algorithms.find_chains(df)[0] == []


def test_fan_in_and_fan_out_in_a_window_and_merchants_are_exempt():
    fan_in = edges([(s, 100, 50, s * 600) for s in range(1, 9)])  # 8 senders in ~80 minutes
    f, _ = algorithms.find_fans(fan_in)
    assert (
        len(f) == 1
        and f[0]["type"] == "fan_in"
        and f[0]["account_ids"][0] == 100
        and f[0]["evidence"]["distinct_counterparties"] == 8
    )
    assert algorithms.find_fans(fan_in, merchants={100})[0] == []  # fan-in to a merchant is ordinary commerce
    fan_out = edges([(200, d, 50, d * 600) for d in range(1, 9)])
    assert algorithms.find_fans(fan_out)[0][0]["type"] == "fan_out"
    spread = edges([(s, 100, 50, s * 2 * 86400) for s in range(1, 9)])  # one a day-and-a-half apart: never 5 in 24h
    assert algorithms.find_fans(spread)[0] == []


def test_shared_beneficiaries_need_two_common_payees():
    df = edges(
        [
            (1, 10, 100, 0),
            (1, 11, 100, 1),
            (2, 10, 100, 2),
            (2, 11, 100, 3),
            (3, 10, 100, 4),
            (3, 11, 100, 5),
            (4, 12, 5, 6),
            *[
                (100 + i, 200 + i, 5, 10 + i) for i in range(60)
            ],  # unrelated senders: the group must stand out from them
        ]
    )
    found, _ = algorithms.find_shared_beneficiaries(df)
    assert len(found) == 1
    ev = found[0]["evidence"]
    assert ev["senders"] == [1, 2, 3] and ev["beneficiaries"] == [10, 11]
    one_common = edges([(1, 10, 1, 0), (2, 10, 1, 1), (3, 10, 1, 2)])  # share just one payee
    assert algorithms.find_shared_beneficiaries(one_common)[0] == []


def test_merchants_and_chance_overlaps_do_not_form_shared_beneficiary_groups():
    rows = [(s, d, 1, s) for s in range(1, 4) for d in (10, 11)]
    assert algorithms.find_shared_beneficiaries(edges(rows), merchants={10, 11})[0] == []  # ordinary shops
    two_only = edges([(1, 10, 1, 0), (1, 11, 1, 1), (2, 10, 1, 2), (2, 11, 1, 3)])
    assert algorithms.find_shared_beneficiaries(two_only)[0] == []  # two senders are a coincidence, not a group
    # a random many-customer / few-shops background must not chain into one giant group
    rng = np.random.default_rng(3)
    bg = edges(
        [
            (int(a), int(b), 5.0, float(t))
            for a, b, t in zip(rng.integers(0, 120, 400), rng.integers(1000, 1040, 400), range(400), strict=True)
        ]
    )
    assert algorithms.find_shared_beneficiaries(bg)[0] == []


def test_hub_beneficiaries_are_ignored_for_sharing():
    rows = [(s, d, 1, s) for s in range(1, 8) for d in (50, 51)]
    cfg = {**CONFIG, "shared": {**CONFIG["shared"], "max_dst_fanin": 5}}
    assert algorithms.find_shared_beneficiaries(edges(rows), cfg=cfg)[0] == []


def test_metrics_and_dense_cluster():
    clique = [(a, b, 100, a * 10 + b) for a in range(1, 6) for b in range(1, 6) if a != b]
    df = edges([*clique, (6, 7, 1, 0)])
    m, comm = algorithms.node_metrics(df)
    assert set(m.columns) >= {"in_degree", "out_degree", "pagerank", "clustering", "community_id"}
    assert m.loc[1, "in_degree"] == 4 and m.loc[1, "clustering"] > 0.9
    assert m.loc[6, "community_id"] == -1 and 6 not in comm  # a lone pair has no community
    found = algorithms.find_dense_clusters(df, comm)
    assert len(found) == 1 and found[0]["evidence"]["density"] == pytest.approx(1.0)
    assert found[0]["evidence"]["avg_clustering"] == pytest.approx(1.0)


def test_stars_and_trees_are_not_dense_clusters():
    star = edges([(s, 100, 10, s) for s in range(1, 8)])  # one hub, seven spokes: density < 1 and clustering 0
    _, comm = algorithms.node_metrics(star)
    assert algorithms.find_dense_clusters(star, comm) == []
    four_star = edges([(1, 100, 1, 0), (2, 100, 1, 1), (3, 100, 1, 2)])  # the 4-account star that fooled the first rule
    _, comm = algorithms.node_metrics(four_star)
    assert algorithms.find_dense_clusters(four_star, comm) == []


def test_analyze_end_to_end_scores_planted_accounts_above_background():
    rng = np.random.default_rng(1)
    background = [
        (int(a), int(b), float(rng.integers(10, 500)), float(rng.integers(0, 30 * 86400)))
        for a, b in zip(rng.integers(1000, 1400, 600), rng.integers(1400, 1800, 600), strict=True)
    ]
    planted = [
        (1, 2, 5000, 0),
        (2, 3, 4900, 600),
        (3, 1, 4800, 1200),  # cycle
        (11, 12, 9000, 0),
        (12, 13, 8900, 300),
        (13, 14, 8800, 600),
        (14, 15, 8700, 900),  # rapid chain
        *[(s, 99, 100, s * 300) for s in range(20, 28)],
    ]  # fan-in
    res = analysis.analyze(edges(background + planted))
    types = {f["type"] for f in res["findings"]}
    assert {"cycle", "chain", "fan_in"} <= types
    m = res["metrics"]
    planted_scores = m.loc[[1, 2, 3, 11, 12, 99], "graph_risk_score"]
    assert planted_scores.min() > 20 and planted_scores.min() > m.drop(
        index=[1, 2, 3, 11, 12, 13, 14, 15, 99, *range(20, 28)]
    )["graph_risk_score"].quantile(0.95)
    assert res["summary"]["edges"] == len(background) + len(planted) and not any(res["truncated"].values())


def test_cleaning_drops_self_loops_nulls_and_zero_amounts():
    df = pd.DataFrame(
        {
            "tx_id": [1, 2, 3, 4],
            "src": [1, 2, 3, 4],
            "dst": [1, None, 5, 6],
            "amount": [5.0, 5.0, 0.0, 7.0],
            "t": [0.0] * 4,
        }
    )
    assert list(analysis.clean_edges(df)["tx_id"]) == [4]


def test_future_edges_do_not_change_findings_about_the_past():
    """Findings on a prefix of the data are unchanged when later edges are appended (as-of safety of the detectors)."""
    base = [
        (1, 2, 1000, 0),
        (2, 3, 990, H),
        (3, 1, 980, 2 * H),
        (11, 12, 9000, 0),
        (12, 13, 8900, 300),
        (13, 14, 8800, 600),
    ]
    later = [(5, 6, 1, 40 * 86400), (6, 5, 1, 41 * 86400)]
    a = analysis.analyze(edges(base))["findings"]
    full = edges(base + later)
    b = analysis.analyze(full)["findings"]
    key = lambda f: (f["type"], tuple(f["account_ids"]), f["score"])  # noqa: E731
    assert {key(f) for f in a} <= {key(f) for f in b}
