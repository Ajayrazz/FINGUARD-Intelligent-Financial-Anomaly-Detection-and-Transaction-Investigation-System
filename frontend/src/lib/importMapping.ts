export const FIELDS: { key: string; label: string; required?: boolean }[] = [
  { key: "transaction_id", label: "Transaction ID (generated if blank)" },
  { key: "sender", label: "Sender account", required: true },
  { key: "receiver", label: "Receiver account" },
  { key: "amount", label: "Amount", required: true },
  { key: "occurred_at", label: "Timestamp" },
  { key: "step", label: "Time step (e.g. PaySim hour)" },
  { key: "tx_type", label: "Transaction type" },
  { key: "currency", label: "Currency" },
  { key: "merchant_name", label: "Merchant name" },
  { key: "merchant_category", label: "Merchant category" },
  { key: "status", label: "Status" },
  { key: "sender_balance_before", label: "Sender balance before" },
  { key: "sender_balance_after", label: "Sender balance after" },
  { key: "receiver_balance_before", label: "Receiver balance before" },
  { key: "receiver_balance_after", label: "Receiver balance after" },
  { key: "ground_truth_label", label: "Fraud label (evaluation only)" },
];

/** source column -> canonical field ('' = not mapped; kept in metadata) */
export type ColumnMap = Record<string, string>;

/** Mirrors the server rules so problems are shown before upload. The server remains the authority. */
export function mappingProblems(map: ColumnMap): string[] {
  const targets = Object.values(map).filter(Boolean);
  const problems: string[] = [];
  for (const f of FIELDS.filter((x) => x.required)) {
    if (!targets.includes(f.key))
      problems.push(`Map a column to "${f.label}".`);
  }
  if (!targets.includes("occurred_at") && !targets.includes("step")) {
    problems.push('Map a column to "Timestamp" or "Time step".');
  }
  for (const t of new Set(targets)) {
    if (targets.filter((x) => x === t).length > 1) {
      problems.push(
        `More than one column is mapped to "${FIELDS.find((f) => f.key === t)?.label ?? t}".`,
      );
    }
  }
  return problems;
}

export function toApiMapping(
  map: ColumnMap,
  options: Record<string, unknown>,
): string {
  const columns = Object.fromEntries(Object.entries(map).filter(([, v]) => v));
  const cleaned = Object.fromEntries(
    Object.entries(options).filter(([, v]) => v !== "" && v !== undefined),
  );
  return JSON.stringify({ columns, options: cleaned });
}
