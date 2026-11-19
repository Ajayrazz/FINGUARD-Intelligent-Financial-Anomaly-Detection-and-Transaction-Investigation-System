"""Graph analysis through the API: planted patterns, neighborhood caps, Neo4j sync/drift/fallback, permissions."""

import pytest

from apps.audit.models import AuditLog
from apps.datasets.models import Dataset
from apps.graph_engine import neo4j_store, scenario, services
from apps.graph_engine.models import AccountGraphMetrics, GraphFinding, GraphSnapshot, Neo4jSyncState
from apps.transactions.models import Account, Transaction

pytestmark = pytest.mark.django_db


@pytest.fixture
def demo():
    return scenario.build()


@pytest.fixture
def analyst(make_user, api_as):
    return api_as(make_user("financial_analyst"))


def acct(ds, ref):
    return Account.objects.get(dataset=ds, account_ref=ref)


def build_snapshot(api, ds, run_tasks):
    with run_tasks(execute=True):
        res = api.post("/api/v1/graph/snapshots/", {"dataset": ds.pk}, format="json")
    assert res.status_code == 202, res.content
    return GraphSnapshot.objects.get(pk=res.data["id"])


def test_snapshot_finds_every_planted_pattern_and_stores_results(demo, analyst, run_tasks):
    snap = build_snapshot(analyst, demo, run_tasks)
    assert snap.status == "succeeded" and snap.finding_count == snap.findings.count() > 0
    assert snap.edge_count == Transaction.objects.filter(dataset=demo).count()
    by_type = {}
    for f in snap.findings.all():
        by_type.setdefault(f.finding_type, []).append(f)
    refs = {a.pk: a.account_ref for a in Account.objects.filter(dataset=demo)}
    names = lambda f: {refs[i] for i in f.account_ids}  # noqa: E731
    assert any(names(f) == {"A1", "A2", "A3"} for f in by_type["cycle"])
    assert any(names(f) == {"B1", "B2", "B3", "B4", "B5"} for f in by_type["chain"])
    fan = [f for f in by_type["fan_in"] if refs[f.account_ids[0]] == "F0"]
    assert fan and fan[0].evidence["distinct_counterparties"] == 8
    sb = by_type["shared_beneficiary"][0]
    assert set(sb.evidence["senders"]) == {acct(demo, s).pk for s in ("S1", "S2", "S3")}
    assert AuditLog.objects.filter(action="graph.snapshot.completed").exists()


def test_graph_score_ranks_planted_accounts_above_background(demo, analyst, run_tasks):
    snap = build_snapshot(analyst, demo, run_tasks)
    scores = {
        m.account.account_ref: m.graph_risk_score
        for m in AccountGraphMetrics.objects.filter(snapshot=snap).select_related("account")
    }
    planted = [scores[r] for r in ("A1", "A2", "A3", "B2", "B3", "F0") if r in scores]
    background = [v for r, v in scores.items() if r.startswith(("C", "M"))]
    assert planted and background and min(planted) > max(background)
    m = analyst.get(f"/api/v1/graph/accounts/{acct(demo, 'A1').pk}/metrics/").json()
    assert m["metrics"]["graph_risk_score"] > 30 and any(f["finding_type"] == "cycle" for f in m["findings"])
    assert set(m["metrics"]["components"]) == {"cycle", "chain", "fan", "shared", "cluster"}


def test_findings_api_filters_and_orders(demo, analyst, run_tasks):
    snap = build_snapshot(analyst, demo, run_tasks)
    body = analyst.get(f"/api/v1/graph/findings/?snapshot={snap.pk}").json()
    scores = [f["score"] for f in body["results"]]
    assert scores == sorted(scores, reverse=True) and body["count"] == snap.finding_count
    cyc = analyst.get(f"/api/v1/graph/findings/?dataset={demo.pk}&type=cycle").json()
    assert cyc["count"] >= 1 and {f["finding_type"] for f in cyc["results"]} == {"cycle"}
    assert cyc["results"][0]["accounts"][0]["account_ref"]
    assert analyst.get(f"/api/v1/graph/findings/?snapshot={snap.pk}&min_score=abc").status_code == 400
    assert analyst.get("/api/v1/graph/findings/").status_code == 400
    assert analyst.get("/api/v1/graph/findings/?snapshot=999999").status_code == 404


def test_snapshot_as_of_excludes_later_transactions(demo, analyst, run_tasks):
    with run_tasks(execute=True):
        res = analyst.post(
            "/api/v1/graph/snapshots/", {"dataset": demo.pk, "as_of": "2026-01-12T00:00:00Z"}, format="json"
        )
    snap = GraphSnapshot.objects.get(pk=res.data["id"])
    assert snap.edge_count == Transaction.objects.filter(dataset=demo, occurred_at__lt="2026-01-12T00:00:00Z").count()
    refs = {a.pk: a.account_ref for a in Account.objects.filter(dataset=demo)}
    types = {(f.finding_type, frozenset(refs[i] for i in f.account_ids)) for f in snap.findings.all()}
    assert ("cycle", frozenset({"A1", "A2", "A3"})) in types  # 11 Jan: already happened
    assert not any(t == "chain" for t, _ in types)  # the chain is on 13 Jan: not yet visible


def test_empty_dataset_rejected_and_permissions(make_dataset, demo, make_user, api_as):
    empty = make_dataset()
    analyst = api_as(make_user("financial_analyst"))
    r = analyst.post("/api/v1/graph/snapshots/", {"dataset": empty.pk}, format="json")
    assert r.status_code == 400 and r.json()["error"]["code"] == "graph_not_possible"
    inv = api_as(make_user("fraud_investigator"))
    assert inv.get("/api/v1/graph/snapshots/").status_code == 200
    assert inv.post("/api/v1/graph/snapshots/", {"dataset": demo.pk}, format="json").status_code == 403
    assert inv.post(f"/api/v1/graph/datasets/{demo.pk}/sync/").status_code == 403
    assert api_as(make_user("management")).get("/api/v1/graph/snapshots/").status_code == 403


def hood(api, account, **params):
    qs = "&".join(f"{k}={v}" for k, v in {"source": "postgres", **params}.items())
    return api.get(f"/api/v1/graph/accounts/{account.pk}/neighborhood/?{qs}")


def test_neighborhood_depth_direction_and_amount_filters(demo, analyst):
    a2 = acct(demo, "A2")
    both = hood(analyst, a2, depth=1).json()
    refs = {n["account_ref"] for n in both["nodes"]}
    assert (
        refs == {"A1", "A2", "A3"}
        and len(both["edges"]) == 2
        and both["source"] == "postgres"
        and both["truncated"] is False
    )
    out = hood(analyst, a2, depth=1, direction="out").json()
    assert {n["account_ref"] for n in out["nodes"]} == {"A2", "A3"}
    inc = hood(analyst, a2, depth=1, direction="in").json()
    assert {n["account_ref"] for n in inc["nodes"]} == {"A1", "A2"}
    assert hood(analyst, a2, depth=1, min_amount=50_001).json()["edges"] == []  # both A2 edges are at most 50,000
    deeper = hood(analyst, acct(demo, "B1"), depth=3, direction="out").json()
    assert {n["account_ref"]: n["depth"] for n in deeper["nodes"]} == {"B1": 0, "B2": 1, "B3": 2, "B4": 3}


def test_neighborhood_caps_are_reported_not_silent(demo, analyst):
    f0 = acct(demo, "F0")
    res = hood(analyst, f0, depth=1, limit=4).json()
    assert len(res["nodes"]) == 4 and res["truncated"] is True
    assert hood(analyst, f0, depth=9).json()["depth"] == 3  # depth is clamped to the hard cap
    assert hood(analyst, f0, depth="x").status_code == 400
    assert hood(analyst, f0, direction="sideways").status_code == 400
    assert hood(analyst, f0, **{"from": "garbage"}).status_code == 400
    assert analyst.get(f"/api/v1/graph/accounts/{f0.pk}/neighborhood/?source=neo4j").status_code == 409  # not synced


def test_neighborhood_time_window(demo, analyst):
    a1 = acct(demo, "A1")
    assert len(hood(analyst, a1, depth=1, to="2026-01-11T01:00:00Z").json()["edges"]) == 1  # only A1>A2 (11 Jan 00:00)
    assert hood(analyst, a1, depth=1, **{"from": "2026-03-01T00:00:00Z"}).json()["edges"] == []


def test_edge_detail_timeline_and_no_ground_truth(demo, analyst):
    demo.transactions.update(ground_truth_label=True)
    tx = Transaction.objects.filter(dataset=demo, sender=acct(demo, "A1"), receiver=acct(demo, "A2")).first()
    e = analyst.get(f"/api/v1/graph/edges/{tx.pk}/").json()
    assert (
        e["external_id"] == tx.transaction_id and e["sender"]["account_ref"] == "A1" and "label" not in str(e).lower()
    )
    tl = analyst.get(f"/api/v1/graph/accounts/{acct(demo, 'A2').pk}/timeline/?source=postgres").json()
    assert len(tl["events"]) == 3 or len(tl["events"]) == 2  # transactions among A1, A2, A3
    times = [ev["occurred_at"] for ev in tl["events"]]
    assert times == sorted(times, reverse=True)


# ---------------------------------------------------------------- Neo4j (real container; ids >= 900000 never touch dev data)
@pytest.fixture
def neo(demo):
    if not neo4j_store.is_available():
        pytest.skip("Neo4j is not reachable")
    big = Dataset.objects.create(id=900_000 + demo.pk, name="DEMO neo4j test (synthetic)", is_synthetic=True)
    # copy the scenario into the high-id dataset so Neo4j keys cannot collide with real projections
    ids = {}
    for a in Account.objects.filter(dataset=demo):
        ids[a.pk] = Account.objects.create(dataset=big, account_ref=a.account_ref, account_type=a.account_type)
    Transaction.objects.bulk_create([
        Transaction(dataset=big, transaction_id=t.transaction_id, sender=ids[t.sender_id], receiver=ids[t.receiver_id] if t.receiver_id else None,
                    amount=t.amount, currency=t.currency, tx_type=t.tx_type, occurred_at=t.occurred_at)
        for t in Transaction.objects.filter(dataset=demo)])  # fmt: skip
    neo4j_store.delete_dataset(big.pk)
    yield big
    neo4j_store.delete_dataset(big.pk)


def test_sync_is_idempotent_incremental_and_drift_checked(neo):
    state = services.sync_dataset(neo.pk)
    assert (
        state.status == "synced"
        and state.edges_synced == Transaction.objects.filter(dataset=neo, receiver__isnull=False).count()
    )
    drift = services.drift_check(neo.pk)
    assert drift["in_sync"] is True and drift["neo4j"] == drift["postgres"]
    services.sync_dataset(neo.pk)  # nothing new: no duplicates
    assert services.drift_check(neo.pk)["neo4j"]["edges"] == drift["neo4j"]["edges"]
    # a late transaction is picked up from the watermark only
    Transaction.objects.create(dataset=neo, transaction_id="LATE", sender=acct(neo, "A1"), receiver=acct(neo, "B1"),
                               amount=1, tx_type="TRANSFER", occurred_at="2026-03-01T00:00:00Z")  # fmt: skip
    assert services.drift_check(neo.pk)["in_sync"] is False  # drift is detected
    state = services.sync_dataset(neo.pk)
    assert state.edges_synced == drift["postgres"]["edges"] + 1 and services.drift_check(neo.pk)["in_sync"] is True


def test_rebuild_reloads_from_postgres(neo):
    services.sync_dataset(neo.pk)
    neo4j_store.run(
        "MATCH (a:Account {ds: $ds})-[t:TX]->() WITH t LIMIT 5 DELETE t", ds=neo.pk
    )  # corrupt the projection
    assert services.drift_check(neo.pk)["in_sync"] is False
    services.sync_dataset(neo.pk, rebuild=True)
    assert services.drift_check(neo.pk)["in_sync"] is True


def test_neo4j_neighborhood_matches_postgres(neo, analyst):
    services.sync_dataset(neo.pk)
    for ref, depth, direction in (("A2", 1, "both"), ("B1", 3, "out"), ("F0", 1, "in"), ("C000", 2, "both")):
        a = Account.objects.filter(dataset=neo, account_ref=ref).first()
        if a is None:
            continue
        pg = hood(analyst, a, depth=depth, direction=direction).json()
        nj = hood(analyst, a, depth=depth, direction=direction, source="neo4j").json()
        assert nj["source"] == "neo4j" and pg["source"] == "postgres"
        key = lambda e: (e["source"], e["target"], e["count"], round(e["total"], 2))  # noqa: E731
        assert sorted(map(key, nj["edges"])) == sorted(map(key, pg["edges"]))
        assert {n["id"] for n in nj["nodes"]} == {n["id"] for n in pg["nodes"]}


def test_auto_uses_postgres_neo4j_only_on_request_and_outage_is_a_clear_error(neo, analyst, monkeypatch):
    a = acct(neo, "A2")
    url = f"/api/v1/graph/accounts/{a.pk}/neighborhood/"
    assert analyst.get(url).json()["source"] == "postgres"
    assert analyst.get(f"{url}?source=neo4j").status_code == 409  # not synced yet
    services.sync_dataset(neo.pk)
    assert analyst.get(url).json()["source"] == "postgres"  # auto stays on the measured-faster store (D-057)
    assert analyst.get(f"{url}?source=neo4j").json()["source"] == "neo4j"

    def down(*args, **kwargs):
        raise neo4j_store.Neo4jUnavailable("ServiceUnavailable")

    with monkeypatch.context() as m:  # undone before the fixture teardown talks to Neo4j again
        m.setattr(neo4j_store, "run", down)
        res = analyst.get(url).json()
        assert res["source"] == "postgres" and len(res["edges"]) == 2  # the default path never depends on Neo4j
        err = analyst.get(f"{url}?source=neo4j")
        assert err.status_code == 409 and "Neo4j is unavailable" in err.json()["error"]["message"]


def test_neo4j_outage_fails_the_sync_but_never_blocks_postgres_writes(neo, analyst, monkeypatch):
    def down(*args, **kwargs):
        raise neo4j_store.Neo4jUnavailable("ServiceUnavailable")

    with monkeypatch.context() as m:  # undone before the fixture teardown talks to Neo4j again
        m.setattr(neo4j_store, "run", down)
        state = services.sync_dataset(neo.pk)
        assert state.status == "failed" and "Neo4j unavailable" in state.last_error
        res = analyst.post(
            "/api/v1/transactions/ingest/",
            {
                "dataset": neo.pk,
                "transactions": [
                    {"sender": "Z1", "receiver": "Z2", "amount": "5", "occurred_at": "2026-04-01T00:00:00Z"}
                ],
            },
            format="json",
        )
        assert res.status_code in (200, 201, 207), res.content  # ingestion is unaffected by Neo4j being down
        assert Neo4jSyncState.objects.get(dataset=neo).status == "failed"
        drift = services.drift_check(neo.pk)
        assert drift["neo4j"] is None and "Neo4j unavailable" in drift["error"]


def test_sync_endpoint_reports_status_and_queues_work(neo, analyst, run_tasks):
    s = analyst.get(f"/api/v1/graph/datasets/{neo.pk}/sync/").json()
    assert s["status"] == "never" and s["drift"]["postgres"]["edges"] > 0
    with run_tasks(execute=True):
        assert analyst.post(f"/api/v1/graph/datasets/{neo.pk}/sync/").status_code == 202
    s = analyst.get(f"/api/v1/graph/datasets/{neo.pk}/sync/").json()
    assert s["status"] == "synced" and s["drift"]["in_sync"] is True
    assert AuditLog.objects.filter(action="graph.sync.requested").exists()
    GraphFinding.objects.count()  # model import sanity
