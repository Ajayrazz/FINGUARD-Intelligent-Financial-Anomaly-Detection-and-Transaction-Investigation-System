"""Generate clearly-labelled MOCK transactions for UI development and performance testing.

The data is random and meaningless: dataset name starts with "MOCK", is flagged synthetic, and the description
says so. It must never be used for research metrics (docs/09). Generation runs inside PostgreSQL
(generate_series) so 1M+ rows take seconds.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.datasets.models import Dataset
from apps.transactions.models import Account, Transaction

TX_TYPES = ["PAYMENT", "TRANSFER", "CASH_OUT", "CASH_IN", "DEBIT"]


class Command(BaseCommand):
    help = "Create (or with --purge, delete) a MOCK dataset of random transactions."

    def add_arguments(self, parser):  # noqa: ANN001, ANN201
        parser.add_argument("--name", default="MOCK demo (random data)")
        parser.add_argument("--rows", type=int, default=20_000)
        parser.add_argument("--accounts", type=int, default=2_000)
        parser.add_argument("--purge", action="store_true", help="Delete the named dataset and all its rows")

    def handle(self, *args, **opts):  # noqa: ANN002, ANN003, ANN201
        name = opts["name"]
        if not name.upper().startswith("MOCK"):
            raise CommandError(
                "Mock dataset names must start with 'MOCK' so they cannot be mistaken for real data."
            )
        if opts["purge"]:
            return self._purge(name)
        rows, accounts = opts["rows"], opts["accounts"]
        if rows < 1 or accounts < 10:
            raise CommandError("--rows must be >= 1 and --accounts >= 10")
        if Dataset.objects.filter(name=name).exists():
            raise CommandError(f"Dataset '{name}' exists. Use --purge first.")

        with transaction.atomic():
            ds = Dataset.objects.create(
                name=name,
                source_type=Dataset.SourceType.CUSTOM,
                is_synthetic=True,
                description="MOCK data: randomly generated for UI/performance testing. Not real, not for research.",
            )
            with connection.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO transactions_account (dataset_id, account_ref, account_type, metadata)
                    SELECT %s, 'MOCK-' || CASE WHEN g %% 10 = 0 THEN 'M' ELSE 'C' END || lpad(g::text, 7, '0'),
                           CASE WHEN g %% 10 = 0 THEN 'merchant' ELSE 'customer' END, '{}'::jsonb
                    FROM generate_series(1, %s) g
                    """,
                    [ds.pk, accounts],
                )
                cur.execute(
                    f"""
                    WITH a AS (
                      SELECT array_agg(id ORDER BY id) FILTER (WHERE account_type = 'customer') AS cust,
                             array_agg(id ORDER BY id) AS everyone
                      FROM transactions_account WHERE dataset_id = %s
                    )
                    INSERT INTO transactions_transaction
                      (dataset_id, transaction_id, sender_id, receiver_id, amount, currency, tx_type, occurred_at,
                       merchant_name, merchant_category, status, ground_truth_label, metadata, created_at)
                    SELECT %s, 'MOCK-' || g,
                           a.cust[1 + floor(random() * cardinality(a.cust))::int],
                           a.everyone[1 + floor(random() * cardinality(a.everyone))::int],
                           round((power(random(), 3) * 50000)::numeric, 2), '',
                           (ARRAY{TX_TYPES!r})[1 + floor(random() * {len(TX_TYPES)})::int],
                           timestamptz '2026-01-01 00:00+00' + random() * interval '90 days',
                           '', '', 'completed', random() < 0.001, '{{}}'::jsonb, now()
                    FROM generate_series(1, %s) g, a
                    """,
                    [ds.pk, ds.pk, rows],
                )
                cur.execute(
                    """
                    UPDATE transactions_account acc SET first_seen_at = s.first, last_seen_at = s.last
                    FROM (SELECT sender_id AS id, min(occurred_at) AS first, max(occurred_at) AS last
                          FROM transactions_transaction WHERE dataset_id = %s GROUP BY sender_id) s
                    WHERE acc.id = s.id
                    """,
                    [ds.pk],
                )
            ds.row_count = rows
            ds.save(update_fields=["row_count"])
        with connection.cursor() as cur:
            cur.execute("ANALYZE transactions_transaction")
            cur.execute("ANALYZE transactions_account")
        self.stdout.write(self.style.SUCCESS(f"Created '{name}': {rows} transactions, {accounts} accounts"))

    def _purge(self, name: str) -> None:
        ds = Dataset.objects.filter(name=name).first()
        if ds is None:
            raise CommandError(f"No dataset named '{name}'")
        with transaction.atomic():
            Transaction.objects.filter(dataset=ds).delete()
            Account.objects.filter(dataset=ds).delete()
            ds.delete()
        self.stdout.write(self.style.SUCCESS(f"Purged '{name}'"))
