import { Link } from "react-router-dom";
import type { TransactionRow } from "../../api/types";
import { formatAmount, formatDateTime } from "../../lib/format";
import { StatusBadge } from "../ui/Badge";

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
