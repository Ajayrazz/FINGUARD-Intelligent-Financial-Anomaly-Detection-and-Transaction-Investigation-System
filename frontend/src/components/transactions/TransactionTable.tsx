import { Link } from "react-router-dom";
import type { TransactionRow } from "../../api/types";
import { formatAmount, formatDateTime } from "../../lib/format";
import { StatusBadge } from "../ui/Badge";
import {
  Card3D,
  CardGrid,
  Chip,
  useViewMode,
  ViewToggle,
  type Tone,
} from "../ui/cards";

export interface SortState {
  field: "occurred_at" | "amount";
  desc: boolean;
}

export function TransactionTable({
  rows,
  sort,
  onSort,
}: {
  rows: TransactionRow[];
  sort?: SortState;
  onSort?: (field: SortState["field"]) => void;
}) {
  const header = (label: string, field?: SortState["field"], right = false) => {
    const active = field && sort?.field === field;
    return (
      <th
        scope="col"
        className={`py-2 ${right ? "text-right" : ""}`}
        aria-sort={
          active ? (sort.desc ? "descending" : "ascending") : undefined
        }
      >
        {field && onSort ? (
          <button
            type="button"
            onClick={() => onSort(field)}
            className="font-medium hover:underline"
          >
            {label} {active ? (sort.desc ? "▼" : "▲") : ""}
          </button>
        ) : (
          label
        )}
      </th>
    );
  };
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-slate-300 text-slate-600">
          <tr>
            {header("Transaction ID")}
            {header("Sender")}
            {header("Receiver")}
            {header("Type")}
            {header("Amount", "amount", true)}
            {header("Time", "occurred_at")}
            {header("Status")}
          </tr>
        </thead>
        <tbody>
          {rows.map((t) => (
            <tr key={t.id} className="border-b border-slate-100">
              <td className="py-2 font-mono">
                <Link
                  className="text-blue-700 hover:underline"
                  to={`/transactions/${t.id}`}
                >
                  {t.transaction_id}
                </Link>
              </td>
              <td>
                <Link className="hover:underline" to={`/accounts/${t.sender}`}>
                  {t.sender_ref}
                </Link>
              </td>
              <td>
                {t.receiver && t.receiver_ref ? (
                  <Link
                    className="hover:underline"
                    to={`/accounts/${t.receiver}`}
                  >
                    {t.receiver_ref}
                  </Link>
                ) : (
                  "—"
                )}
              </td>
              <td>{t.tx_type}</td>
              <td className="text-right tabular-nums">
                {formatAmount(t.amount, t.currency)}
              </td>
              <td className="whitespace-nowrap">
                {formatDateTime(t.occurred_at)}
              </td>
              <td>
                <StatusBadge status={t.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const TYPE_TONE: Record<string, Tone> = {
  PAYMENT: "indigo",
  TRANSFER: "violet",
  CASH_OUT: "pink",
  CASH_IN: "green",
  DEBIT: "amber",
};

/** Money-flow card: who paid whom, how much, when. */
export function TransactionCards({ rows }: { rows: TransactionRow[] }) {
  return (
    <CardGrid min="19rem">
      {rows.map((t) => (
        <Card3D
          key={t.id}
          tone={
            t.status === "failed"
              ? "red"
              : (TYPE_TONE[t.tx_type.toUpperCase()] ?? "cyan")
          }
        >
          <div className="flex items-center justify-between gap-2">
            <Chip tone={TYPE_TONE[t.tx_type.toUpperCase()] ?? "cyan"}>
              {t.tx_type}
            </Chip>
            <StatusBadge status={t.status} />
          </div>
          <p className="mt-3 text-2xl font-semibold tabular-nums">
            <span className="gradient-text">
              {formatAmount(t.amount, t.currency)}
            </span>
          </p>
          <div className="mt-3 flex items-center gap-2 text-sm">
            <Link
              className="truncate rounded-lg bg-white/5 px-2 py-1 font-mono hover:underline"
              to={`/accounts/${t.sender}`}
            >
              {t.sender_ref}
            </Link>
            <svg
              viewBox="0 0 48 12"
              className="h-3 w-10 shrink-0 text-indigo-300"
              aria-hidden="true"
            >
              <path
                d="M0 6h42m0 0-5-4m5 4-5 4"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeDasharray="3 3"
              />
            </svg>
            {t.receiver && t.receiver_ref ? (
              <Link
                className="truncate rounded-lg bg-white/5 px-2 py-1 font-mono hover:underline"
                to={`/accounts/${t.receiver}`}
              >
                {t.receiver_ref}
              </Link>
            ) : (
              <span className="text-slate-500">—</span>
            )}
          </div>
          <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-3 text-xs text-slate-500">
            <Link
              className="font-mono text-blue-700 hover:underline"
              to={`/transactions/${t.id}`}
            >
              {t.transaction_id}
            </Link>
            <span>{formatDateTime(t.occurred_at)}</span>
          </div>
        </Card3D>
      ))}
    </CardGrid>
  );
}

/** Cards by default, with a Table view switch (kept for dense scanning and screen readers). */
export function TransactionList({
  rows,
  sort,
  onSort,
  viewKey = "transactions",
}: {
  rows: TransactionRow[];
  sort?: SortState;
  onSort?: (field: SortState["field"]) => void;
  viewKey?: string;
}) {
  const [view, setView] = useViewMode(viewKey);
  const sortBtn = (label: string, field: SortState["field"]) => {
    const active = sort?.field === field;
    return (
      <button
        type="button"
        aria-pressed={active}
        onClick={() => onSort?.(field)}
        className={`rounded-lg border px-3 py-1 text-sm ${active ? "border-indigo-300 bg-indigo-500/20" : "border-slate-300 hover:bg-white/10"}`}
      >
        {label} {active ? (sort?.desc ? "▼" : "▲") : ""}
      </button>
    );
  };
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <ViewToggle mode={view} onChange={setView} />
        {view === "cards" && onSort && (
          <div
            role="group"
            aria-label="Sort cards"
            className="flex items-center gap-2 text-sm"
          >
            <span className="text-slate-500">Sort by</span>
            {sortBtn("Time", "occurred_at")}
            {sortBtn("Amount", "amount")}
          </div>
        )}
      </div>
      {view === "cards" ? (
        <TransactionCards rows={rows} />
      ) : (
        <TransactionTable rows={rows} sort={sort} onSort={onSort} />
      )}
    </div>
  );
}
