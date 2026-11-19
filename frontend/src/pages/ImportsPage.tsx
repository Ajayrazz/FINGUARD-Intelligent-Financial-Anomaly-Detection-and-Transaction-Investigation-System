import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { ImportJob, Paginated } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import {
  ImportStatusBadge,
  isActive,
} from "../components/imports/ImportStatusBadge";
import { Button } from "../components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/states";
import { useEvents } from "../hooks/useEvents";
import { formatDateTime } from "../lib/format";

export default function ImportsPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const q = useQuery({
    queryKey: ["imports", page],
    queryFn: ({ signal }) =>
      api.get<Paginated<ImportJob>>(`/imports/?page=${page}`, signal),
    refetchInterval: (query) =>
      query.state.data?.results.some((j) => isActive(j.status)) ? 3000 : false,
  });
  useEvents((e) => {
    if (e.type === "import.progress")
      void qc.invalidateQueries({ queryKey: ["imports"] });
  });

  return (
    <section>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Imports</h1>
        {can("imports.create") && (
          <Link
            to="/imports/new"
            className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700"
          >
            New import
          </Link>
        )}
      </div>
      <p className="mt-1 text-sm text-slate-600">
        History of file imports and API ingestion batches.
      </p>
      <div className="mt-4">
        {q.isPending && <LoadingState />}
        {q.isError && (
          <ErrorState
            message={q.error.message}
            onRetry={() => void q.refetch()}
          />
        )}
        {q.data && q.data.results.length === 0 && (
          <EmptyState
            title="No imports yet"
            hint={
              can("imports.create")
                ? "Start with “New import” to upload a CSV or Excel file."
                : undefined
            }
          />
        )}
        {q.data && q.data.results.length > 0 && (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-300 text-slate-600">
                  <tr>
                    <th className="py-2">#</th>
                    <th>Source</th>
                    <th>Dataset</th>
                    <th>Status</th>
                    <th className="text-right">Accepted</th>
                    <th className="text-right">Rejected</th>
                    <th>By</th>
                    <th>Started</th>
                  </tr>
                </thead>
                <tbody>
                  {q.data.results.map((j) => (
                    <tr key={j.id} className="border-b border-slate-100">
                      <td className="py-2">
                        <Link
                          className="text-blue-700 hover:underline"
                          to={`/imports/${j.id}`}
                        >
                          {j.id}
                        </Link>
                      </td>
                      <td>{j.file_name}</td>
                      <td>{j.dataset_name}</td>
                      <td>
                        <ImportStatusBadge status={j.status} />
                      </td>
                      <td className="text-right tabular-nums">
                        {j.rows_accepted.toLocaleString()}
                      </td>
                      <td className="text-right tabular-nums">
                        {j.rows_rejected.toLocaleString()}
                      </td>
                      <td>{j.created_by_email ?? "—"}</td>
                      <td className="whitespace-nowrap">
                        {j.started_at ? formatDateTime(j.started_at) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3 flex items-center gap-3 text-sm">
              <Button
                variant="secondary"
                disabled={!q.data.previous}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>
              <span>
                Page {page} · {q.data.count} imports
              </span>
              <Button
                variant="secondary"
                disabled={!q.data.next}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
