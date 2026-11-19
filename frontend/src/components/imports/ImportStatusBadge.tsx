import type { ImportStatus } from "../../api/types";

const tones: Record<ImportStatus, string> = {
  pending: "bg-slate-200 text-slate-800",
  validating: "bg-blue-100 text-blue-800",
  running: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  completed_with_errors: "bg-amber-100 text-amber-800",
  failed: "bg-red-100 text-red-800",
  cancelled: "bg-slate-200 text-slate-800",
};
const labels: Record<ImportStatus, string> = {
  pending: "Queued",
  validating: "Validating",
  running: "Running",
  completed: "Completed",
  completed_with_errors: "Completed with errors",
  failed: "Failed",
  cancelled: "Cancelled",
};

export const isActive = (s: ImportStatus) =>
  s === "pending" || s === "validating" || s === "running";

export function ImportStatusBadge({ status }: { status: ImportStatus }) {
  return (
    <span
      className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${tones[status]}`}
    >
      {labels[status]}
    </span>
  );
}
