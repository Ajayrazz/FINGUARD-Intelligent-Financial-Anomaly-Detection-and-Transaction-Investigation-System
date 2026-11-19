"""Graph analysis services: snapshot build, Neo4j sync + drift check, neighborhood and timeline queries."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
from django.conf import settings
from django.db import connection
from django.db import transaction as db_transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.datasets.models import Dataset
from apps.transactions.models import Account, Transaction
from graph_engine_lib import CONFIG, analysis

from . import neo4j_store
from .models import AccountGraphMetrics, GraphFinding, GraphSnapshot, Neo4jSyncState

log = logging.getLogger(__name__)
SYNC_BATCH = 5000
MAX_DEPTH, MAX_NODES, MAX_EDGES = 3, 200, 500


class GraphError(Exception):
    """A request cannot be served (message is safe to show)."""


# ------------------------------------------------------------------------------------ snapshots
def create_snapshot(*, dataset: Dataset, user: Any, as_of: datetime | None, window_days: int | None) -> GraphSnapshot:
    if not Transaction.objects.filter(dataset=dataset, receiver__isnull=False).exists():
        raise GraphError("The dataset has no transactions with a receiver, so there is no graph.")
    if as_of is None:
        last = (
            Transaction.objects.filter(dataset=dataset)
            .order_by("-occurred_at")
            .values_list("occurred_at", flat=True)
            .first()
        )
        as_of = last + timedelta(seconds=1) if last else timezone.now()
    snap = GraphSnapshot.objects.create(
        dataset=dataset, as_of=as_of, window_days=window_days, params=CONFIG, created_by=user
    )
    audit.log(
        "graph.snapshot.created",
        actor=user,
        resource_type="graph_snapshot",
        resource_id=snap.pk,
        changes={"dataset": dataset.pk, "as_of": as_of.isoformat(), "window_days": window_days},
    )
    return snap


def load_edges(dataset: Dataset, as_of: datetime, window_days: int | None) -> pd.DataFrame:
    qs = Transaction.objects.filter(dataset=dataset, receiver__isnull=False, occurred_at__lt=as_of)
    if window_days:
        qs = qs.filter(occurred_at__gte=as_of - timedelta(days=window_days))
    if qs.count() > settings.GRAPH_MAX_ROWS:
        raise GraphError(f"Dataset exceeds the graph limit of {settings.GRAPH_MAX_ROWS:,} transactions.")
    df = pd.DataFrame.from_records(
        qs.values_list("id", "sender_id", "receiver_id", "amount", "occurred_at"),
        columns=["tx_id", "src", "dst", "amount", "occurred_at"],
    )
    if df.empty:
        return df.assign(t=pd.Series(dtype="float64")).drop(columns=["occurred_at"])
    df["amount"] = df["amount"].astype(float)
    df["t"] = (pd.to_datetime(df["occurred_at"], utc=True) - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds()
    return df.drop(columns=["occurred_at"])


def execute_snapshot(snapshot_id: int) -> None:
    snap = GraphSnapshot.objects.select_related("dataset").get(pk=snapshot_id)
    if snap.status == GraphSnapshot.Status.SUCCEEDED:
        return
    snap.status, snap.error_message = GraphSnapshot.Status.RUNNING, ""
    snap.save(update_fields=["status", "error_message"])
    try:
        edges = load_edges(snap.dataset, snap.as_of, snap.window_days)
        merchants = set(
            Account.objects.filter(dataset=snap.dataset, account_type="merchant").values_list("pk", flat=True)
        )
        res = analysis.analyze(edges, merchants)
        metrics: pd.DataFrame = res["metrics"]
        in_finding = {a for f in res["findings"] for a in f["account_ids"]}
        keep = metrics[((metrics["in_degree"] + metrics["out_degree"]) >= 2) | metrics.index.isin(in_finding)]
        with db_transaction.atomic():
            GraphFinding.objects.filter(snapshot=snap).delete()
            AccountGraphMetrics.objects.filter(snapshot=snap).delete()
            GraphFinding.objects.bulk_create(
                [
                    GraphFinding(
                        snapshot=snap,
                        finding_type=f["type"],
                        account_ids=f["account_ids"],
                        transaction_ids=f["transaction_ids"],
                        score=f["score"],
                        evidence=f["evidence"],
                    )
                    for f in res["findings"]
                ],
                batch_size=1000,
            )
            comp_cols = [c for c in keep.columns if c.startswith("component_")]
            rows = []
            for acct, r in keep.iterrows():
                rows.append(
                    AccountGraphMetrics(
                        snapshot=snap,
                        account_id=int(acct),
                        in_degree=int(r["in_degree"]),
                        out_degree=int(r["out_degree"]),
                        weighted_in=float(r["weighted_in"]),
                        weighted_out=float(r["weighted_out"]),
                        pagerank=float(r["pagerank"]),
                        clustering=float(r["clustering"]),
                        community_id=int(r["community_id"]),
                        graph_risk_score=float(r["graph_risk_score"]),
                        components={c[10:]: float(r[c]) for c in comp_cols},
                    )
                )
                if len(rows) >= 5000:
                    AccountGraphMetrics.objects.bulk_create(rows)
                    rows = []
            if rows:
                AccountGraphMetrics.objects.bulk_create(rows)
            snap.node_count, snap.edge_count = res["summary"]["nodes"], res["summary"]["edges"]
            snap.finding_count, snap.truncated = len(res["findings"]), res["truncated"]
            snap.status, snap.built_at = GraphSnapshot.Status.SUCCEEDED, timezone.now()
            snap.save()
        audit.log(
            "graph.snapshot.completed",
            actor=snap.created_by,
            resource_type="graph_snapshot",
            resource_id=snap.pk,
            changes={"nodes": snap.node_count, "edges": snap.edge_count, "findings": snap.finding_count},
        )
    except Exception as exc:  # noqa: BLE001 - surface as a failed snapshot, not a lost task
        log.exception("graph snapshot %s failed", snapshot_id)
        msg = str(exc) if isinstance(exc, GraphError) else "Unexpected error."
        snap.status, snap.error_message = GraphSnapshot.Status.FAILED, msg[:500]
        snap.save(update_fields=["status", "error_message"])
        audit.log(
            "graph.snapshot.failed",
            actor=snap.created_by,
            resource_type="graph_snapshot",
            resource_id=snap.pk,
            changes={"error": msg[:200]},
        )


# ------------------------------------------------------------------------------------ Neo4j sync
def sync_dataset(dataset_id: int, *, rebuild: bool = False) -> Neo4jSyncState:
    """Project new transactions (id > watermark) into Neo4j. Idempotent (MERGE); `rebuild` wipes the dataset first.
    A Neo4j outage marks the sync failed and changes nothing in PostgreSQL."""
    state, _ = Neo4jSyncState.objects.get_or_create(dataset_id=dataset_id)
    state.status, state.last_error, state.started_at = Neo4jSyncState.Status.RUNNING, "", timezone.now()
    state.save()
    try:
        neo4j_store.ensure_schema()
        if rebuild:
            neo4j_store.delete_dataset(dataset_id)
            state.last_tx_id = state.edges_synced = state.nodes_synced = 0
            state.save()
        while True:
            rows = list(
                Transaction.objects.filter(dataset_id=dataset_id, receiver__isnull=False, id__gt=state.last_tx_id)
                .order_by("id")
                .values_list("id", "sender_id", "receiver_id", "amount", "occurred_at", "tx_type")[:SYNC_BATCH]
            )
            if not rows:
                break
            neo4j_store.upsert_edges(
                dataset_id,
                [
                    {
                        "pk": r[0],
                        "s": r[1],
                        "d": r[2],
                        "sk": f"{dataset_id}:{r[1]}",
                        "dk": f"{dataset_id}:{r[2]}",
                        "amount": float(r[3]),
                        "ts": r[4].timestamp(),
                        "type": r[5],
                    }
                    for r in rows
                ],
            )
            state.last_tx_id, state.edges_synced = rows[-1][0], state.edges_synced + len(rows)
            state.save(update_fields=["last_tx_id", "edges_synced", "updated_at"])
        state.nodes_synced = neo4j_store.counts(dataset_id)["nodes"]
        state.status, state.finished_at = Neo4jSyncState.Status.SYNCED, timezone.now()
    except neo4j_store.Neo4jUnavailable as exc:
        state.status, state.last_error, state.finished_at = (
            Neo4jSyncState.Status.FAILED,
            f"Neo4j unavailable: {exc}",
            timezone.now(),
        )
    state.save()
    return state


def drift_check(dataset_id: int) -> dict[str, Any]:
    """Compare what PostgreSQL says should be projected with what Neo4j holds."""
    with connection.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM transactions_transaction WHERE dataset_id = %s AND receiver_id IS NOT NULL",
            [dataset_id],
        )
        edges = cur.fetchone()[0]
        cur.execute(
            """SELECT count(*) FROM (
                 SELECT sender_id AS a FROM transactions_transaction WHERE dataset_id = %s AND receiver_id IS NOT NULL
                 UNION
                 SELECT receiver_id FROM transactions_transaction WHERE dataset_id = %s AND receiver_id IS NOT NULL
               ) x""",
            [dataset_id, dataset_id],
        )
        nodes = cur.fetchone()[0]
    out: dict[str, Any] = {"postgres": {"nodes": nodes, "edges": edges}, "neo4j": None, "in_sync": None, "error": None}
    try:
        out["neo4j"] = neo4j_store.counts(dataset_id)
        out["in_sync"] = out["neo4j"] == out["postgres"]
    except neo4j_store.Neo4jUnavailable as exc:
        out["error"] = f"Neo4j unavailable: {exc}"
    return out


# ------------------------------------------------------------------------------------ neighborhood
def _pg_edges(
    dataset_id: int, frontier: list[int], direction: str, min_amount: float, ts_from: float, ts_to: float, limit: int
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for d in ("out", "in") if direction == "both" else (direction,):
        col, other = ("sender_id", "receiver_id") if d == "out" else ("receiver_id", "sender_id")
        sql = f"""
            SELECT sender_id, receiver_id, count(*), sum(amount), min(extract(epoch FROM occurred_at)),
                   max(extract(epoch FROM occurred_at)), (array_agg(id ORDER BY occurred_at DESC))[1:5]
            FROM transactions_transaction
            WHERE dataset_id = %s AND {col} = ANY(%s) AND receiver_id IS NOT NULL AND amount >= %s
              AND occurred_at >= to_timestamp(%s) AND occurred_at <= to_timestamp(%s)
            GROUP BY sender_id, receiver_id ORDER BY sum(amount) DESC LIMIT %s
        """  # noqa: S608 - col/other are fixed identifiers chosen above, never user input
        with connection.cursor() as cur:
            cur.execute(sql, [dataset_id, frontier, min_amount, ts_from, ts_to, limit])
            for s, r, n, total, first_t, last_t, tx in cur.fetchall():
                rows.append(
                    {
                        "src": s,
                        "dst": r,
                        "count": n,
                        "total": float(total),
                        "first_t": float(first_t),
                        "last_t": float(last_t),
                        "tx_ids": list(tx),
                    }
                )
        del other
    return rows


def pick_source(dataset_id: int, requested: str) -> str:
    """`auto` uses PostgreSQL: measured on 343k real transactions it answers a depth-1 neighborhood in ~2 ms against
    ~200 ms for Neo4j (docs/08, D-057). Neo4j is used when asked for explicitly and only if the projection is synced."""
    if requested in ("auto", "postgres"):
        return "postgres"
    state = Neo4jSyncState.objects.filter(dataset_id=dataset_id).first()
    if not (state and state.status == Neo4jSyncState.Status.SYNCED):
        raise GraphError("The Neo4j projection of this dataset is not synced; use source=postgres or run a sync.")
    return "neo4j"


def neighborhood(
    account: Account,
    *,
    depth: int,
    limit: int,
    direction: str,
    min_amount: float,
    ts_from: float,
    ts_to: float,
    source: str = "auto",
) -> dict[str, Any]:
    depth, limit = max(1, min(depth, MAX_DEPTH)), max(2, min(limit, MAX_NODES))
    src = pick_source(account.dataset_id, source)
    fetch = neo4j_store.edges_for if src == "neo4j" else _pg_edges
    nodes: dict[int, int] = {account.pk: 0}
    edges: dict[tuple[int, int], dict[str, Any]] = {}
    frontier, truncated = [account.pk], False
    for level in range(1, depth + 1):
        try:
            rows = fetch(account.dataset_id, frontier, direction, min_amount, ts_from, ts_to, MAX_EDGES)
        except neo4j_store.Neo4jUnavailable:
            raise GraphError("Neo4j is unavailable; use source=postgres.") from None
        nxt: list[int] = []
        for r in rows:
            for ep in (r["src"], r["dst"]):
                if ep not in nodes:
                    if len(nodes) >= limit:
                        truncated = True
                        continue
                    nodes[ep] = level
                    nxt.append(ep)
            if r["src"] in nodes and r["dst"] in nodes:
                if len(edges) >= MAX_EDGES:
                    truncated = True
                else:
                    edges[(r["src"], r["dst"])] = r
            else:
                truncated = True
        frontier = nxt
        if not frontier:
            break
    return _decorate(account, nodes, edges, truncated, src, depth)


def _decorate(
    account: Account,
    nodes: dict[int, int],
    edges: dict[tuple[int, int], dict[str, Any]],
    truncated: bool,
    source: str,
    depth: int,
) -> dict[str, Any]:
    accts = {a.pk: a for a in Account.objects.filter(pk__in=nodes)}
    snap = (
        GraphSnapshot.objects.filter(dataset_id=account.dataset_id, status="succeeded").order_by("-created_at").first()
    )
    score: dict[int, float] = {}
    flagged: set[int] = set()
    if snap:
        score = dict(
            AccountGraphMetrics.objects.filter(snapshot=snap, account_id__in=nodes).values_list(
                "account_id", "graph_risk_score"
            )
        )
        for ids in GraphFinding.objects.filter(snapshot=snap, account_ids__overlap=list(nodes)).values_list(
            "account_ids", flat=True
        ):
            flagged.update(set(ids) & set(nodes))
    return {
        "center": account.pk,
        "source": source,
        "depth": depth,
        "truncated": truncated,
        "snapshot": snap.pk if snap else None,
        "nodes": [
            {
                "id": n,
                "account_ref": accts[n].account_ref if n in accts else str(n),
                "account_type": accts[n].account_type if n in accts else "unknown",
                "depth": d,
                "graph_risk_score": score.get(n),
                "in_finding": n in flagged,
            }
            for n, d in nodes.items()
        ],
        "edges": [
            {
                "source": e["src"],
                "target": e["dst"],
                "count": e["count"],
                "total": e["total"],
                "first_at": datetime.fromtimestamp(e["first_t"], UTC),
                "last_at": datetime.fromtimestamp(e["last_t"], UTC),
                "transaction_ids": e["tx_ids"],
            }
            for e in edges.values()
        ],
    }
