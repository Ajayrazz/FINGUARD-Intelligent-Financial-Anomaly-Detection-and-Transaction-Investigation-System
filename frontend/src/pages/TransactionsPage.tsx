import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { api } from "../api/client";
import type { Dataset, Paginated, TransactionRow } from "../api/types";
import {
  TransactionList,
  type SortState,
} from "../components/transactions/TransactionTable";
import { Button } from "../components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/states";

const TYPES = ["PAYMENT", "TRANSFER", "CASH_OUT", "CASH_IN", "DEBIT"];
const STATUSES = ["pending", "completed", "failed", "reversed"];
const FILTER_KEYS = [
  "q",
  "tx_type",
  "status",
  "amount_min",
  "amount_max",
  "occurred_after",
  "occurred_before",
] as const;

export default function TransactionsPage() {
  const [params, setParams] = useSearchParams();
  const { can } = useAuth();
  const datasets = useQuery({
    queryKey: ["datasets"],
    queryFn: ({ signal }) => api.get<Dataset[]>("/datasets/", signal),
  });

  const dataset =
    params.get("dataset") ??
    (datasets.data?.[0] ? String(datasets.data[0].id) : "");
  const page = Number(params.get("page") ?? "1");
  const ordering = params.get("ordering") ?? "-occurred_at";
  const sort: SortState = {
    field: ordering.replace("-", "") === "amount" ? "amount" : "occurred_at",
    desc: ordering.startsWith("-"),
  };

  const update = (changes: Record<string, string | null>, keepPage = false) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(changes)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    if (!keepPage) next.delete("page");
    setParams(next, { replace: true });
  };

  const query = new URLSearchParams({ dataset, ordering, page: String(page) });
  for (const k of FILTER_KEYS) {
    const v = params.get(k);
    if (v) query.set(k, v);
  }
  const txs = useQuery({
    queryKey: ["transactions", query.toString()],
    queryFn: ({ signal }) =>
      api.get<Paginated<TransactionRow>>(
        `/transactions/?${query.toString()}`,
        signal,
      ),
    enabled: dataset !== "",
  });

  const onSort = (field: SortState["field"]) =>
    update({
      ordering: sort.field === field && sort.desc ? field : `-${field}`,
    });
  const field =
    "mt-1 block rounded-md border border-slate-300 px-2 py-1 text-sm";

  return (
    <section>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Transactions</h1>
        {can("imports.create") && (
          <Link
            to="/imports/new"
            className="rounded-md btn-glow px-3 py-1.5 text-sm font-medium text-white"
          >
            Import data
          </Link>
        )}
      </div>

      {datasets.isError && (
        <ErrorState
          message={datasets.error.message}
          onRetry={() => void datasets.refetch()}
        />
      )}
      {datasets.data && datasets.data.length === 0 && (
        <div className="mt-4">
          <EmptyState
            title="No datasets yet"
            hint={
              can("imports.create")
                ? "Use “Import data” to upload a CSV or Excel file."
                : "Ask an analyst to import data."
            }
          />
        </div>
      )}

      {datasets.data && datasets.data.length > 0 && (
        <>
          <form
            className="mt-4 flex flex-wrap items-end gap-3"
            onSubmit={(e) => e.preventDefault()}
            aria-label="Transaction filters"
          >
            <label className="text-sm">
              Dataset
              <select
                className={field}
                value={dataset}
                onChange={(e) => update({ dataset: e.target.value })}
              >
                {datasets.data.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.row_count.toLocaleString()})
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              Search (exact ID / account)
              <input
                className={field}
                defaultValue={params.get("q") ?? ""}
                key={`q-${params.get("q") ?? ""}`}
                onKeyDown={(e) => {
                  if (e.key === "Enter")
                    update({ q: e.currentTarget.value.trim() || null });
                }}
                onBlur={(e) => {
                  if (e.target.value.trim() !== (params.get("q") ?? ""))
                    update({ q: e.target.value.trim() || null });
                }}
                placeholder="Press Enter"
              />
            </label>
            <label className="text-sm">
              Type
              <select
                className={field}
                value={params.get("tx_type") ?? ""}
                onChange={(e) => update({ tx_type: e.target.value || null })}
              >
                <option value="">All</option>
                {TYPES.map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              Status
              <select
                className={field}
                value={params.get("status") ?? ""}
                onChange={(e) => update({ status: e.target.value || null })}
              >
                <option value="">All</option>
                {STATUSES.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              Min amount
              <input
                type="number"
                min="0"
                className={`${field} w-28`}
                value={params.get("amount_min") ?? ""}
                onChange={(e) => update({ amount_min: e.target.value || null })}
              />
            </label>
            <label className="text-sm">
              Max amount
              <input
                type="number"
                min="0"
                className={`${field} w-28`}
                value={params.get("amount_max") ?? ""}
                onChange={(e) => update({ amount_max: e.target.value || null })}
              />
            </label>
            <label className="text-sm">
              From
              <input
                type="date"
                className={field}
                value={params.get("occurred_after")?.slice(0, 10) ?? ""}
                onChange={(e) =>
                  update({
                    occurred_after: e.target.value
                      ? `${e.target.value}T00:00:00Z`
                      : null,
                  })
                }
              />
            </label>
            <label className="text-sm">
              To
              <input
                type="date"
                className={field}
                value={params.get("occurred_before")?.slice(0, 10) ?? ""}
                onChange={(e) =>
                  update({
                    occurred_before: e.target.value
                      ? `${e.target.value}T23:59:59Z`
                      : null,
                  })
                }
              />
            </label>
            <Button
              variant="secondary"
              onClick={() =>
                setParams(new URLSearchParams({ dataset }), { replace: true })
              }
            >
              Clear filters
            </Button>
          </form>

          <div className="mt-4">
            {txs.isPending && dataset !== "" && (
              <LoadingState label="Loading transactions…" />
            )}
            {txs.isError && (
              <ErrorState
                message={txs.error.message}
                onRetry={() => void txs.refetch()}
              />
            )}
            {txs.data && txs.data.results.length === 0 && (
              <EmptyState title="No transactions match these filters" />
            )}
            {txs.data && txs.data.results.length > 0 && (
              <>
                <TransactionList
                  rows={txs.data.results}
                  sort={sort}
                  onSort={onSort}
                />
                <div className="mt-3 flex items-center gap-3 text-sm">
                  <Button
                    variant="secondary"
                    disabled={!txs.data.previous}
                    onClick={() => update({ page: String(page - 1) }, true)}
                  >
                    Previous
                  </Button>
                  <span>
                    Page {page} · {txs.data.count.toLocaleString()} transactions
                  </span>
                  <Button
                    variant="secondary"
                    disabled={!txs.data.next}
                    onClick={() => update({ page: String(page + 1) }, true)}
                  >
                    Next
                  </Button>
                </div>
              </>
            )}
          </div>
        </>
      )}
    </section>
  );
}
