import { PageHero } from "../components/scenes/PageHero";
import {
  Card3D,
  CardGrid,
  Chip,
  Initials,
  useViewMode,
  ViewToggle,
} from "../components/ui/cards";
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
  const [view, setView] = useViewMode("imports");
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
      <div className="relative [&>a]:absolute [&>a]:right-6 [&>a]:top-6 [&>a]:z-10 [&>button]:absolute [&>button]:right-6 [&>button]:top-6 [&>button]:z-10">
        <PageHero eyebrow="Data" title="Imports" tone="cyan" scene="layers" />
        {can("imports.create") && (
          <Link
            to="/imports/new"
            className="rounded-md btn-glow px-3 py-1.5 text-sm font-medium text-white"
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
            <div className="space-y-3">
              <ViewToggle mode={view} onChange={setView} />
              {view === "cards" ? (
                <CardGrid min="20rem">
                  {q.data.results.map((j) => (
                    <Card3D
                      key={j.id}
                      tone={
                        j.status === "failed"
                          ? "red"
                          : j.status === "completed"
                            ? "green"
                            : "indigo"
                      }
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <Link
                          className="font-mono text-blue-700 hover:underline"
                          to={`/imports/${j.id}`}
                        >
                          #{j.id}
                        </Link>
                        <ImportStatusBadge status={j.status} />
                      </div>
                      <h2 className="mt-3 break-all text-sm font-semibold text-slate-800">
                        {j.file_name}
                      </h2>
                      <p className="text-xs text-slate-500">{j.dataset_name}</p>
                      <div className="mt-3 grid grid-cols-2 gap-2 text-center">
                        <div className="rounded-lg bg-emerald-400/10 p-2">
                          <p className="text-xl font-semibold tabular-nums">
                            {j.rows_accepted.toLocaleString()}
                          </p>
                          <p className="text-[10px] uppercase tracking-wider text-slate-500">
                            Accepted
                          </p>
                        </div>
                        <div className="rounded-lg bg-red-500/10 p-2">
                          <p className="text-xl font-semibold tabular-nums">
                            {j.rows_rejected.toLocaleString()}
                          </p>
                          <p className="text-[10px] uppercase tracking-wider text-slate-500">
                            Rejected
                          </p>
                        </div>
                      </div>
                      <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-3 text-xs text-slate-500">
                        <span>{j.created_by_email ?? "—"}</span>
                        <span>
                          {j.started_at ? formatDateTime(j.started_at) : "—"}
                        </span>
                      </div>
                    </Card3D>
                  ))}
                </CardGrid>
              ) : (
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
              )}
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
