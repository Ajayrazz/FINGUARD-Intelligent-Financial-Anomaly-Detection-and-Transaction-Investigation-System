import { PageHero } from "../components/scenes/PageHero";
import {
  Card3D,
  CardGrid,
  Chip,
  Ring,
  useViewMode,
  ViewToggle,
} from "../components/ui/cards";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type {
  Dataset,
  FindingType,
  GraphFinding,
  GraphSnapshot,
  Paginated,
  SyncStatus,
} from "../api/types";
import { useAuth } from "../auth/AuthContext";
import {
  RunStatusBadge,
  isRunActive,
} from "../components/detection/RunStatusBadge";
import { Button } from "../components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/states";
import { useToast } from "../components/ui/Toast";
import { FINDING_LABEL } from "../lib/graphLayout";
import { formatDateTime } from "../lib/format";

function SyncPanel({ datasetId }: { datasetId: number }) {
  const { can } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({
    queryKey: ["graph-sync", datasetId],
    queryFn: ({ signal }) =>
      api.get<SyncStatus>(`/graph/datasets/${datasetId}/sync/`, signal),
    refetchInterval: (query) =>
      query.state.data?.status === "running" ? 3000 : false,
  });
  const sync = useMutation({
    mutationFn: (rebuild: boolean) =>
      api.post(
        `/graph/datasets/${datasetId}/sync/${rebuild ? "?rebuild=true" : ""}`,
      ),
    onSuccess: () => {
      toast("success", "Neo4j sync queued");
      void qc.invalidateQueries({ queryKey: ["graph-sync", datasetId] });
    },
    onError: (e: Error) => toast("error", e.message),
  });
  if (q.isPending) return <LoadingState />;
  if (q.isError)
    return (
      <ErrorState message={q.error.message} onRetry={() => void q.refetch()} />
    );
  const s = q.data;
  return (
    <div className="rounded-md border border-slate-200 p-3 text-sm">
      <h3 className="font-semibold">Neo4j projection</h3>
      <p className="mt-1">
        Status: <strong className="capitalize">{s.status}</strong> · PostgreSQL:{" "}
        {s.drift.postgres.nodes.toLocaleString()} accounts /{" "}
        {s.drift.postgres.edges.toLocaleString()} transactions
        {s.drift.neo4j && (
          <>
            {" "}
            · Neo4j: {s.drift.neo4j.nodes.toLocaleString()} /{" "}
            {s.drift.neo4j.edges.toLocaleString()} (
            {s.drift.in_sync ? "in sync" : "out of sync"})
          </>
        )}
      </p>
      {s.drift.error && (
        <p role="alert" className="mt-1 text-amber-800">
          {s.drift.error}. Graph views fall back to PostgreSQL.
        </p>
      )}
      {s.last_error && <p className="mt-1 text-red-700">{s.last_error}</p>}
      {can("graph.run") && (
        <div className="mt-2 flex gap-2">
          <Button
            variant="secondary"
            disabled={sync.isPending || s.status === "running"}
            onClick={() => sync.mutate(false)}
          >
            Sync new transactions
          </Button>
          <Button
            variant="secondary"
            disabled={sync.isPending || s.status === "running"}
            onClick={() => sync.mutate(true)}
          >
            Rebuild projection
          </Button>
        </div>
      )}
    </div>
  );
}

export default function GraphOverviewPage() {
  const [view, setView] = useViewMode("graph-snaps");
  const [findView, setFindView] = useViewMode("graph-findings");
  const { can } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const [dataset, setDataset] = useState("");
  const [type, setType] = useState<"" | FindingType>("");
  const datasets = useQuery({
    queryKey: ["datasets"],
    queryFn: ({ signal }) => api.get<Dataset[]>("/datasets/", signal),
  });
  const snaps = useQuery({
    queryKey: ["graph-snapshots"],
    queryFn: ({ signal }) =>
      api.get<Paginated<GraphSnapshot>>("/graph/snapshots/", signal),
    refetchInterval: (query) =>
      query.state.data?.results.some((s) => isRunActive(s.status))
        ? 3000
        : false,
  });
  const build = useMutation({
    mutationFn: () =>
      api.post<GraphSnapshot>("/graph/snapshots/", {
        dataset: Number(dataset),
      }),
    onSuccess: () => {
      toast("success", "Graph build started");
      void qc.invalidateQueries({ queryKey: ["graph-snapshots"] });
    },
    onError: (e: Error) => toast("error", e.message),
  });
  const latest = (snaps.data?.results ?? []).find(
    (s) => String(s.dataset) === dataset && s.status === "succeeded",
  );
  const findings = useQuery({
    queryKey: ["graph-findings", latest?.id, type],
    enabled: !!latest,
    queryFn: ({ signal }) =>
      api.get<Paginated<GraphFinding>>(
        `/graph/findings/?snapshot=${latest!.id}${type ? `&type=${type}` : ""}`,
        signal,
      ),
  });
  return (
    <section className="space-y-4">
      <PageHero
        eyebrow="Detect"
        title="Relationship Graph"
        tone="green"
        scene="graph"
      />
      <p className="text-sm text-slate-600">
        Build a graph of who paid whom, review detected patterns, then open any
        account's network.
      </p>
      <div className="flex flex-wrap items-end gap-3 rounded-md border border-slate-200 bg-slate-50 p-4">
        <label className="text-sm">
          <span className="block font-medium">Dataset</span>
          <select
            className="mt-1 w-80 rounded border border-slate-300 p-1.5"
            value={dataset}
            onChange={(e) => setDataset(e.target.value)}
          >
            <option value="">Select…</option>
            {(datasets.data ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.row_count.toLocaleString()} rows)
              </option>
            ))}
          </select>
        </label>
        {can("graph.run") && (
          <Button
            disabled={!dataset || build.isPending}
            onClick={() => build.mutate()}
          >
            Build graph analysis
          </Button>
        )}
      </div>
      {dataset && <SyncPanel datasetId={Number(dataset)} />}
      {snaps.isPending && <LoadingState />}
      {snaps.isError && (
        <ErrorState
          message={snaps.error.message}
          onRetry={() => void snaps.refetch()}
        />
      )}
      {snaps.data && (
        <div className="overflow-x-auto">
          <h2 className="font-semibold">Snapshots</h2>
          {snaps.data.results.length === 0 ? (
            <EmptyState title="No graph analyses yet" />
          ) : (
            <div className="space-y-3">
              <ViewToggle mode={view} onChange={setView} />
              {view === "cards" ? (
                <CardGrid min="19rem">
                  {snaps.data.results.map((s) => (
                    <Card3D
                      key={s.id}
                      tone={
                        s.status === "failed"
                          ? "red"
                          : s.status === "succeeded"
                            ? "cyan"
                            : "indigo"
                      }
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-mono text-slate-700">
                          #{s.id}
                        </span>
                        <RunStatusBadge status={s.status} />
                      </div>
                      <h3 className="mt-3 text-sm font-semibold text-slate-800">
                        {s.dataset_name}
                        {s.is_mock_data && (
                          <span className="ml-2">
                            <Chip tone="amber">DEMO/MOCK</Chip>
                          </span>
                        )}
                      </h3>
                      {s.error_message && (
                        <p className="mt-1 text-sm text-red-700">
                          {s.error_message}
                        </p>
                      )}
                      <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                        <div className="rounded-lg bg-white/5 p-2">
                          <p className="text-lg font-semibold tabular-nums">
                            {s.node_count.toLocaleString()}
                          </p>
                          <p className="text-[10px] uppercase tracking-wider text-slate-500">
                            Accounts
                          </p>
                        </div>
                        <div className="rounded-lg bg-white/5 p-2">
                          <p className="text-lg font-semibold tabular-nums">
                            {s.edge_count.toLocaleString()}
                          </p>
                          <p className="text-[10px] uppercase tracking-wider text-slate-500">
                            Edges
                          </p>
                        </div>
                        <div className="rounded-lg bg-pink-500/10 p-2">
                          <p className="text-lg font-semibold tabular-nums">
                            {s.finding_count.toLocaleString()}
                            {Object.values(s.truncated).some(Boolean) && (
                              <span title="a detector hit its limit; some findings are missing">
                                {" "}
                                ⚠
                              </span>
                            )}
                          </p>
                          <p className="text-[10px] uppercase tracking-wider text-slate-500">
                            Findings
                          </p>
                        </div>
                      </div>
                      <p className="mt-auto pt-3 text-xs text-slate-500">
                        {s.built_at ? formatDateTime(s.built_at) : "—"}
                      </p>
                    </Card3D>
                  ))}
                </CardGrid>
              ) : (
                <div className="overflow-x-auto">
                  <table className="mt-1 w-full text-left text-sm">
                    <thead className="border-b border-slate-300 text-slate-600">
                      <tr>
                        <th className="py-1">#</th>
                        <th>Dataset</th>
                        <th>Status</th>
                        <th className="text-right">Accounts</th>
                        <th className="text-right">Edges</th>
                        <th className="text-right">Findings</th>
                        <th>Built</th>
                      </tr>
                    </thead>
                    <tbody>
                      {snaps.data.results.map((s) => (
                        <tr key={s.id} className="border-b border-slate-100">
                          <td className="py-1">{s.id}</td>
                          <td>
                            {s.dataset_name}
                            {s.is_mock_data && (
                              <span className="ml-2 rounded bg-amber-100 px-1.5 text-xs text-amber-800">
                                DEMO/MOCK
                              </span>
                            )}
                          </td>
                          <td>
                            <RunStatusBadge status={s.status} />
                            {s.error_message && (
                              <span className="ml-2 text-red-700">
                                {s.error_message}
                              </span>
                            )}
                          </td>
                          <td className="text-right tabular-nums">
                            {s.node_count.toLocaleString()}
                          </td>
                          <td className="text-right tabular-nums">
                            {s.edge_count.toLocaleString()}
                          </td>
                          <td className="text-right tabular-nums">
                            {s.finding_count.toLocaleString()}
                            {Object.values(s.truncated).some(Boolean) && (
                              <span title="a detector hit its limit; some findings are missing">
                                {" "}
                                ⚠
                              </span>
                            )}
                          </td>
                          <td className="whitespace-nowrap">
                            {s.built_at ? formatDateTime(s.built_at) : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}
      {dataset && latest && (
        <div>
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Findings in snapshot #{latest.id}</h2>
            <label className="text-sm">
              Type{" "}
              <select
                className="rounded border border-slate-300 p-1"
                value={type}
                onChange={(e) => setType(e.target.value as "" | FindingType)}
              >
                <option value="">All</option>
                {Object.entries(FINDING_LABEL).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {findings.isPending && <LoadingState />}
          {findings.isError && <ErrorState message={findings.error.message} />}
          {findings.data && findings.data.results.length === 0 && (
            <EmptyState title="No findings of this type" />
          )}
          {findings.data && findings.data.results.length > 0 && (
            <div className="space-y-3">
              <ViewToggle mode={findView} onChange={setFindView} />
              {findView === "cards" ? (
                <CardGrid min="19rem">
                  {findings.data.results.map((f) => (
                    <Card3D
                      key={f.id}
                      tone={
                        f.score >= 60 ? "red" : f.score >= 30 ? "amber" : "cyan"
                      }
                    >
                      <div className="flex items-center justify-between gap-3">
                        <h3 className="text-sm font-semibold text-slate-800">
                          {FINDING_LABEL[f.finding_type] ?? f.finding_type}
                        </h3>
                        <Ring
                          value={f.score}
                          max={100}
                          decimals={0}
                          size={60}
                          label="score"
                          tone={
                            f.score >= 60
                              ? "red"
                              : f.score >= 30
                                ? "amber"
                                : "cyan"
                          }
                        />
                      </div>
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {f.accounts.slice(0, 6).map((a) => (
                          <Link
                            key={a.id}
                            className="rounded-lg bg-white/5 px-2 py-0.5 font-mono text-xs text-blue-700 hover:underline"
                            to={`/accounts/${a.id}/graph`}
                          >
                            {a.account_ref}
                          </Link>
                        ))}
                        {f.account_ids.length > 6 && (
                          <Chip>{`+${f.account_ids.length - 6}`}</Chip>
                        )}
                      </div>
                      <p className="mt-3 text-xs text-slate-600">
                        {Object.entries(f.evidence)
                          .filter(([, v]) => typeof v === "number")
                          .slice(0, 3)
                          .map(
                            ([k, v]) =>
                              `${k.replace(/_/g, " ")}: ${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`,
                          )
                          .join(" · ")}
                      </p>
                    </Card3D>
                  ))}
                </CardGrid>
              ) : (
                <div className="overflow-x-auto">
                  <table className="mt-1 w-full text-left text-sm">
                    <thead className="border-b border-slate-300 text-slate-600">
                      <tr>
                        <th className="py-1">Pattern</th>
                        <th className="text-right">Score</th>
                        <th>Accounts</th>
                        <th>Evidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {findings.data.results.map((f) => (
                        <tr
                          key={f.id}
                          className="border-b border-slate-100 align-top"
                        >
                          <td className="py-1">
                            {FINDING_LABEL[f.finding_type] ?? f.finding_type}
                          </td>
                          <td className="text-right tabular-nums">
                            {f.score.toFixed(0)}
                          </td>
                          <td>
                            {f.accounts.slice(0, 6).map((a) => (
                              <Link
                                key={a.id}
                                className="mr-2 font-mono text-blue-700 hover:underline"
                                to={`/accounts/${a.id}/graph`}
                              >
                                {a.account_ref}
                              </Link>
                            ))}
                            {f.account_ids.length > 6 &&
                              `+${f.account_ids.length - 6}`}
                          </td>
                          <td className="text-slate-600">
                            {Object.entries(f.evidence)
                              .filter(([, v]) => typeof v === "number")
                              .slice(0, 3)
                              .map(
                                ([k, v]) =>
                                  `${k.replace(/_/g, " ")}: ${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`,
                              )
                              .join(" · ")}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
          <p className="mt-2 text-xs text-slate-600">
            Scores are heuristic and uncalibrated; they rank patterns, they do
            not prove wrongdoing.
          </p>
        </div>
      )}
    </section>
  );
}
