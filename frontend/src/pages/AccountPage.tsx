import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { AccountDetail, Paginated, TransactionRow } from "../api/types";
import { TransactionList } from "../components/transactions/TransactionTable";
import { Button } from "../components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/states";
import { formatAmount, formatDateTime } from "../lib/format";

const DIRECTIONS = [
  { key: "both", label: "All" },
  { key: "out", label: "Outgoing" },
  { key: "in", label: "Incoming" },
] as const;

export default function AccountPage() {
  const { id = "" } = useParams();
  const { can } = useAuth();
  const [direction, setDirection] = useState<"both" | "out" | "in">("both");
  const [page, setPage] = useState(1);

  const acct = useQuery({
    queryKey: ["account", id],
    queryFn: ({ signal }) => api.get<AccountDetail>(`/accounts/${id}/`, signal),
  });
  const txs = useQuery({
    queryKey: ["account", id, "transactions", direction, page],
    queryFn: ({ signal }) =>
      api.get<Paginated<TransactionRow>>(
        `/accounts/${id}/transactions/?direction=${direction}&page=${page}`,
        signal,
      ),
  });

  if (acct.isPending) return <LoadingState />;
  if (acct.isError)
    return (
      <ErrorState
        message={acct.error.message}
        onRetry={() => void acct.refetch()}
      />
    );
  const a = acct.data;

  return (
    <section className="space-y-6">
      <div>
        <Link
          to="/transactions"
          className="text-sm text-blue-700 hover:underline"
        >
          ← Transactions
        </Link>
        <h1 className="mt-1 font-mono text-2xl font-semibold">
          {a.account_ref}
        </h1>
        <p className="text-sm text-slate-600 capitalize">
          {a.account_type} · {a.dataset_name}
        </p>
        {can("graph.read") && (
          <p className="mt-1 text-sm">
            <Link
              to={`/accounts/${id}/graph`}
              className="text-blue-700 hover:underline"
            >
              View relationship network →
            </Link>
          </p>
        )}
        {can("behavior.read") && (
          <p className="mt-1 text-sm">
            <Link
              to={`/accounts/${id}/behavior`}
              className="text-blue-700 hover:underline"
            >
              View behavior profile →
            </Link>
          </p>
        )}
      </div>
      <dl className="grid grid-cols-2 gap-4 rounded-lg border border-slate-200 p-4 sm:grid-cols-3">
        <div>
          <dt className="text-xs text-slate-500">Sent</dt>
          <dd className="text-sm tabular-nums">
            {a.sent_count.toLocaleString()} · {formatAmount(a.sent_total)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Received</dt>
          <dd className="text-sm tabular-nums">
            {a.received_count.toLocaleString()} ·{" "}
            {formatAmount(a.received_total)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Last seen</dt>
          <dd className="text-sm">
            {a.last_seen_at ? formatDateTime(a.last_seen_at) : "—"}
          </dd>
        </div>
      </dl>
      <div>
        <h2 className="text-lg font-semibold">Transactions</h2>
        <div role="tablist" className="mt-2 flex gap-2">
          {DIRECTIONS.map((d) => (
            <button
              key={d.key}
              role="tab"
              aria-selected={direction === d.key}
              onClick={() => {
                setDirection(d.key);
                setPage(1);
              }}
              className={`rounded-md px-3 py-1 text-sm ${direction === d.key ? "bg-slate-900 text-white" : "border border-slate-300"}`}
            >
              {d.label}
            </button>
          ))}
        </div>
        <div className="mt-3">
          {txs.isPending && <LoadingState />}
          {txs.isError && (
            <ErrorState
              message={txs.error.message}
              onRetry={() => void txs.refetch()}
            />
          )}
          {txs.data && txs.data.results.length === 0 && (
            <EmptyState title="No transactions in this direction" />
          )}
          {txs.data && txs.data.results.length > 0 && (
            <>
              <TransactionList rows={txs.data.results} viewKey="account-tx" />
              <div className="mt-3 flex items-center gap-3 text-sm">
                <Button
                  variant="secondary"
                  disabled={!txs.data.previous}
                  onClick={() => setPage((p) => p - 1)}
                >
                  Previous
                </Button>
                <span>
                  Page {page} · {txs.data.count.toLocaleString()} transactions
                </span>
                <Button
                  variant="secondary"
                  disabled={!txs.data.next}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
