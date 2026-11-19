import type { RunStatus } from "../../api/types";

const tones: Record<RunStatus, string> = {
  pending: "bg-slate-200 text-slate-800",
  running: "bg-blue-100 text-blue-800",
  succeeded: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};
const labels: Record<RunStatus, string> = {
  pending: "Queued",
  running: "Running",
  succeeded: "Completed",
  failed: "Failed",
};

export const isRunActive = (s: RunStatus) => s === "pending" || s === "running";

export function RunStatusBadge({ status }: { status: RunStatus }) {
  return (
    <span
      className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${tones[status]}`}
    >
      {labels[status]}
    </span>
  );
}
