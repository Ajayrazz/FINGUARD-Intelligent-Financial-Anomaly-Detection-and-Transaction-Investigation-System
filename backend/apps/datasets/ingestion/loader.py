"""Bulk persistence of one cleaned chunk: accounts via INSERT..ON CONFLICT, transactions via COPY.

Account references are resolved per chunk (indexed `= ANY()` lookup) instead of cached in Python, because
PaySim has ~9M distinct accounts and a process-wide dict would need GBs of RAM.
"""

import pandas as pd
from django.db import connection, transaction

TX_COLUMNS = [
    "dataset_id", "import_job_id", "transaction_id", "sender_id", "receiver_id", "amount", "currency", "tx_type",
    "occurred_at", "step", "sender_balance_before", "sender_balance_after", "receiver_balance_before",
    "receiver_balance_after", "merchant_name", "merchant_category", "status", "ground_truth_label", "metadata",
    "created_at",
]  # fmt: skip
ADVISORY_NAMESPACE = 4_001  # pg_advisory_xact_lock(namespace, dataset_id): serialises writers per dataset
JOB_LOCK_NAMESPACE = 4_002  # session lock (namespace, job_id): one worker per job; freed automatically if it dies


def lock_dataset(dataset_id: int) -> None:
    with connection.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(%s, %s)", [ADVISORY_NAMESPACE, dataset_id])


def try_lock_job(job_id: int) -> bool:
    with connection.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s, %s)", [JOB_LOCK_NAMESPACE, job_id])
        return bool(cur.fetchone()[0])


def unlock_job(job_id: int) -> None:
    with connection.cursor() as cur:
        cur.execute("SELECT pg_advisory_unlock(%s, %s)", [JOB_LOCK_NAMESPACE, job_id])


def existing_transaction_ids(dataset_id: int, ids: list[str]) -> set[str]:
    if not ids:
        return set()
    with connection.cursor() as cur:
        cur.execute(
            "SELECT transaction_id FROM transactions_transaction WHERE dataset_id = %s AND transaction_id = ANY(%s)",
            [dataset_id, ids],
        )
        return {r[0] for r in cur.fetchall()}


def _account_type(ref: str, merchant_prefix: str, customer_prefix: str) -> str:
    if merchant_prefix and ref.startswith(merchant_prefix):
        return "merchant"
    if customer_prefix and ref.startswith(customer_prefix):
        return "customer"
    return "unknown"


def resolve_accounts(dataset_id: int, refs: set[str], merchant_prefix: str, customer_prefix: str) -> dict[str, int]:
    if not refs:
        return {}
    ref_list = sorted(refs)
    types = [_account_type(r, merchant_prefix, customer_prefix) for r in ref_list]
    with connection.cursor() as cur:
        cur.execute(
            """
            INSERT INTO transactions_account (dataset_id, account_ref, account_type, metadata)
            SELECT %s, ref, typ, '{}'::jsonb FROM unnest(%s::text[], %s::text[]) AS t(ref, typ)
            ON CONFLICT (dataset_id, account_ref) DO NOTHING
            """,
            [dataset_id, ref_list, types],
        )
        cur.execute(
            "SELECT account_ref, id FROM transactions_account WHERE dataset_id = %s AND account_ref = ANY(%s)",
            [dataset_id, ref_list],
        )
        return dict(cur.fetchall())


def copy_transactions(dataset_id: int, job_id: int, good: pd.DataFrame, opts: dict) -> int:
    """Insert validated rows. Must run inside the caller's transaction."""
    if good.empty:
        return 0
    refs = set(good["sender"]) | {r for r in good["receiver"] if r}
    accounts = resolve_accounts(dataset_id, refs, opts.get("merchant_prefix", ""), opts.get("customer_prefix", ""))
    df = good.copy()
    df["sender_id"] = df["sender"].map(accounts)
    df["receiver_id"] = df["receiver"].map(lambda r: accounts.get(r) if r else None)
    df["dataset_id"] = dataset_id
    df["import_job_id"] = job_id
    df["created_at"] = pd.Timestamp.now(tz="UTC")
    out = df[TX_COLUMNS].astype(object).where(df[TX_COLUMNS].notna(), None)
    with (
        connection.cursor() as cur,
        cur.copy(f"COPY transactions_transaction ({', '.join(TX_COLUMNS)}) FROM STDIN") as copy,
    ):
        for row in out.itertuples(index=False, name=None):
            copy.write_row([v.to_pydatetime() if isinstance(v, pd.Timestamp) else v for v in row])
    return len(out)


def refresh_account_activity(dataset_id: int, job_id: int) -> None:
    """Set first/last seen on every account touched by a job.

    Aggregates into a temp table, ANALYZEs it, then updates by primary key. A single UPDATE..FROM over a UNION
    subquery planned badly on freshly loaded tables (no statistics yet) and ran for minutes on 100k rows.
    """
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute("ANALYZE transactions_transaction")
        cur.execute("DROP TABLE IF EXISTS _job_activity")
        cur.execute(
            """
            CREATE TEMP TABLE _job_activity ON COMMIT DROP AS
            SELECT acct, min(ts) AS first_ts, max(ts) AS last_ts FROM (
              SELECT sender_id AS acct, occurred_at AS ts FROM transactions_transaction WHERE import_job_id = %s
              UNION ALL
              SELECT receiver_id, occurred_at FROM transactions_transaction
              WHERE import_job_id = %s AND receiver_id IS NOT NULL
            ) u GROUP BY acct
            """,
            [job_id, job_id],
        )
        cur.execute("ANALYZE _job_activity")
        cur.execute(
            """
            UPDATE transactions_account a
            SET first_seen_at = LEAST(COALESCE(a.first_seen_at, s.first_ts), s.first_ts),
                last_seen_at = GREATEST(COALESCE(a.last_seen_at, s.last_ts), s.last_ts)
            FROM _job_activity s
            WHERE a.id = s.acct AND a.dataset_id = %s
            """,
            [dataset_id],
        )
        cur.execute("DROP TABLE IF EXISTS _job_activity")
