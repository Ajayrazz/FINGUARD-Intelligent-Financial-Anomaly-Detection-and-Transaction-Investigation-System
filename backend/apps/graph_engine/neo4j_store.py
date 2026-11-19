"""Neo4j projection of a dataset's transaction graph (one-way from PostgreSQL, idempotent, rebuildable).

Graph model: (:Account {key: "<dataset>:<account pk>", ds, id})-[:TX {pk, amount, ts, type}]->(:Account).
Display data (references, types, scores) always comes from PostgreSQL; Neo4j stores topology and edge facts only.
"""

from __future__ import annotations

import threading
from typing import Any

from django.conf import settings

_driver = None
_lock = threading.Lock()


class Neo4jUnavailable(Exception):
    """Neo4j cannot be reached or rejected the request. Callers fall back to PostgreSQL; writes are never blocked."""


def get_driver():  # noqa: ANN201
    global _driver
    with _lock:
        if _driver is None:
            from neo4j import GraphDatabase

            _driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                connection_timeout=3,
                max_connection_lifetime=600,
            )
        return _driver


def reset_driver() -> None:
    global _driver
    with _lock:
        if _driver is not None:
            _driver.close()
        _driver = None


def run(query: str, **params: Any) -> list[dict[str, Any]]:
    from neo4j.exceptions import AuthError, Neo4jError, ServiceUnavailable

    try:
        with get_driver().session(database=settings.NEO4J_DATABASE) as session:
            return [dict(r) for r in session.run(query, **params)]
    except (ServiceUnavailable, AuthError, OSError) as exc:
        raise Neo4jUnavailable(type(exc).__name__) from exc
    except Neo4jError as exc:
        raise Neo4jUnavailable(f"{exc.code}") from exc


def ensure_schema() -> None:
    run("CREATE CONSTRAINT account_key IF NOT EXISTS FOR (a:Account) REQUIRE a.key IS UNIQUE")
    run("CREATE INDEX tx_pk IF NOT EXISTS FOR ()-[t:TX]-() ON (t.pk)")
    run("CREATE INDEX account_ds IF NOT EXISTS FOR (a:Account) ON (a.ds)")


def is_available() -> bool:
    try:
        run("RETURN 1 AS ok")
        return True
    except Neo4jUnavailable:
        return False


def upsert_edges(dataset_id: int, rows: list[dict[str, Any]]) -> None:
    """MERGE nodes and edges; running it again with the same rows changes nothing."""
    run(
        """
        UNWIND $rows AS r
        MERGE (a:Account {key: r.sk}) ON CREATE SET a.ds = $ds, a.id = r.s
        MERGE (b:Account {key: r.dk}) ON CREATE SET b.ds = $ds, b.id = r.d
        MERGE (a)-[t:TX {pk: r.pk}]->(b)
        SET t.amount = r.amount, t.ts = r.ts, t.type = r.type
        """,
        rows=rows,
        ds=dataset_id,
    )


def delete_dataset(dataset_id: int) -> None:
    while True:  # batched so a big dataset does not need one giant transaction
        deleted = run(
            "MATCH (a:Account {ds: $ds}) WITH a LIMIT 20000 DETACH DELETE a RETURN count(*) AS n", ds=dataset_id
        )[0]["n"]
        if deleted == 0:
            return


def counts(dataset_id: int) -> dict[str, int]:
    nodes = run("MATCH (a:Account {ds: $ds}) RETURN count(a) AS n", ds=dataset_id)[0]["n"]
    edges = run("MATCH (:Account {ds: $ds})-[t:TX]->() RETURN count(t) AS n", ds=dataset_id)[0]["n"]
    return {"nodes": int(nodes), "edges": int(edges)}


def edges_for(
    dataset_id: int, frontier: list[int], direction: str, min_amount: float, ts_from: float, ts_to: float, limit: int
) -> list[dict[str, Any]]:
    keys = [f"{dataset_id}:{a}" for a in frontier]
    pattern = {"out": "(a)-[t:TX]->(b)", "in": "(a)<-[t:TX]-(b)"}
    rows: list[dict[str, Any]] = []
    for d in ("out", "in") if direction == "both" else (direction,):
        res = run(
            f"""
            MATCH {pattern[d]} WHERE a.key IN $keys AND t.ts >= $f AND t.ts <= $to AND t.amount >= $min
            WITH a.id AS x, b.id AS y, count(t) AS n, sum(t.amount) AS total, min(t.ts) AS first_t, max(t.ts) AS last_t,
                 collect(t.pk)[..5] AS tx
            RETURN x, y, n, total, first_t, last_t, tx ORDER BY total DESC LIMIT $limit
            """,
            keys=keys,
            f=ts_from,
            to=ts_to,
            min=min_amount,
            limit=limit,
        )
        for r in res:
            src, dst = (r["x"], r["y"]) if d == "out" else (r["y"], r["x"])
            rows.append(
                {
                    "src": src,
                    "dst": dst,
                    "count": r["n"],
                    "total": r["total"],
                    "first_t": r["first_t"],
                    "last_t": r["last_t"],
                    "tx_ids": list(r["tx"]),
                }
            )
    return rows
