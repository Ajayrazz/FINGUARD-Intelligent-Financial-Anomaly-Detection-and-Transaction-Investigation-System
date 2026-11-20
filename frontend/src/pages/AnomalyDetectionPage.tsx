import { EChart } from "../components/charts/EChart";
import {
  Card3D,
  CardGrid,
  Chip,
  Ring,
  useViewMode,
  ViewToggle,
} from "../components/ui/cards";
import { PageHero } from "../components/scenes/PageHero";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type {
  Dataset,
  DetectionRun,
  ModelVersionRow,
  Paginated,
} from "../api/types";
import { useAuth } from "../auth/AuthContext";
import {
  RunStatusBadge,
  isRunActive,
} from "../components/detection/RunStatusBadge";
import { Button } from "../components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/states";
import { useToast } from "../components/ui/Toast";
import { formatDateTime } from "../lib/format";

function StartRunForm() {
  const qc = useQueryClient();
  const toast = useToast();
  const [version, setVersion] = useState("");
  const [dataset, setDataset] = useState("");
  const models = useQuery({
    queryKey: ["model-versions"],
    queryFn: ({ signal }) =>
      api.get<ModelVersionRow[]>("/model-versions/", signal),
  });
  const datasets = useQuery({
    queryKey: ["datasets"],
    queryFn: ({ signal }) => api.get<Dataset[]>("/datasets/", signal),
  });
  const start = useMutation({
    mutationFn: () =>
      api.post<DetectionRun>("/detection/runs/", {
        model_version: Number(version),
        dataset: Number(dataset),
      }),
    onSuccess: () => {
      toast("success", "Detection run started");
      void qc.invalidateQueries({ queryKey: ["detection-runs"] });
    },
    onError: (e: Error) => toast("error", e.message),
  });
  const usable = (models.data ?? []).filter(
    (m) => m.scorable && m.status !== "retired",
  );
  return (
    <form
      className="animate-glow mt-4 flex flex-wrap items-end gap-3 rounded-2xl border border-indigo-400/30 bg-white/[0.03] p-4"
      onSubmit={(e) => {
        e.preventDefault();
        start.mutate();
      }}
    >
      <label className="text-sm">
        <span className="block font-medium">Model version</span>
        <select
          className="mt-1 w-72 rounded border border-slate-300 p-1.5"
          value={version}
          onChange={(e) => setVersion(e.target.value)}
        >
          <option value="">Select…</option>
          {usable.map((m) => (
            <option key={m.id} value={m.id}>
              {m.model_name} ({m.algorithm}, {m.feature_set})
            </option>
          ))}
        </select>
      </label>
      <label className="text-sm">
        <span className="block font-medium">Dataset</span>
        <select
          className="mt-1 w-72 rounded border border-slate-300 p-1.5"
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
      <Button type="submit" disabled={!version || !dataset || start.isPending}>
        Run detection
      </Button>
      <p className="basis-full text-xs text-slate-600">
        Only models whose features can be computed from stored transactions are
        listed. The alert threshold is the one frozen on validation data during
        training. Scores are model output, not labels.
      </p>
    </form>
  );
}

export default function AnomalyDetectionPage() {
  const { can } = useAuth();
  const [page, setPage] = useState(1);
  const [view, setView] = useViewMode("detection-runs");
  const q = useQuery({
    queryKey: ["detection-runs", page],
    queryFn: ({ signal }) =>
      api.get<Paginated<DetectionRun>>(`/detection/runs/?page=${page}`, signal),
    refetchInterval: (query) =>
      query.state.data?.results.some((r) => isRunActive(r.status))
        ? 3000
        : false,
  });
  const chart3d = useMemo(() => {
    const runs = (q.data?.results ?? []).filter((r) => r.rows_scored > 0);
    const models = [...new Set(runs.map((r) => r.model_name))];
    const sets = [...new Set(runs.map((r) => r.dataset_name))];
    const ax = {
      axisLabel: { textStyle: { color: "#b8bde0" } },
      axisLine: { lineStyle: { color: "#4b5195" } },
      splitLine: { lineStyle: { color: "rgba(129,140,248,0.18)" } },
      axisPointer: { show: false },
    };
    const data = runs.map((r) => [
      r.model_name,
      r.dataset_name,
      Number(((r.rows_flagged / r.rows_scored) * 100).toFixed(3)),
    ]);
    return {
      tooltip: {},
      visualMap: {
        show: false,
        max: Math.max(1, ...data.map((d) => d[2] as number)),
        dimension: 2,
        inRange: { color: ["#4f46e5", "#a78bfa", "#22d3ee", "#f472b6"] },
      },
      xAxis3D: { type: "category", data: models, ...ax },
      yAxis3D: { type: "category", data: sets, ...ax },
      zAxis3D: { type: "value", name: "Flagged %", ...ax },
      grid3D: {
        boxWidth: 130,
        boxDepth: 60,
        environment: "none",
        light: { main: { intensity: 1.3 }, ambient: { intensity: 0.5 } },
        viewControl: {
          autoRotate: true,
          autoRotateSpeed: 6,
          distance: 210,
          alpha: 24,
          beta: 30,
          zoomSensitivity: 0,
          panSensitivity: 0,
        },
      },
      series: [
        {
          type: "bar3D",
          data,
          shading: "lambert",
          bevelSize: 0.25,
          barSize: 12,
        },
      ],
    };
  }, [q.data]);
  return (
    <section>
      <PageHero
        eyebrow="Detect"
        title="Anomaly Detection"
        tone="violet"
        scene="radar"
      />
      <p className="mt-1 text-sm text-slate-600">
        Score a dataset's transactions with a registered model and review the
        highest-scoring ones.
      </p>
      {can("detection.run") && <StartRunForm />}
      {(q.data?.results.length ?? 0) > 0 && (
        <div className="mt-4 rounded-2xl border border-indigo-400/20 bg-white/[0.03] p-3">
          <h2 className="text-base font-semibold">
            Flag rate by model and dataset
          </h2>
          <p className="text-xs text-slate-500">
            3D view of the runs on this page · drag to rotate
          </p>
          <EChart
            option={chart3d}
            height={300}
            label="3D bar chart of the share of transactions flagged by each model on each dataset"
          />
        </div>
      )}
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
            title="No detection runs yet"
            hint={
              can("detection.run")
                ? "Pick a model and a dataset above."
                : undefined
            }
          />
        )}
        {q.data && q.data.results.length > 0 && (
          <>
            <div className="space-y-3">
              <ViewToggle mode={view} onChange={setView} />
              {view === "cards" ? (
                <CardGrid min="21rem">
                  {q.data.results.map((r) => {
                    const rate =
                      r.rows_scored > 0
                        ? (r.rows_flagged / r.rows_scored) * 100
                        : 0;
                    return (
                      <Card3D
                        key={r.id}
                        tone={
                          r.status === "failed"
                            ? "red"
                            : rate >= 5
                              ? "amber"
                              : "violet"
                        }
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <Link
                            className="font-mono text-blue-700 hover:underline"
                            to={`/detection/${r.id}`}
                          >
                            {r.id}
                          </Link>
                          <RunStatusBadge status={r.status} />
                        </div>
                        <div className="mt-3 flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <h2 className="break-all text-sm font-semibold text-slate-800">
                              {r.model_name}
                            </h2>
                            <p className="mt-1 text-xs text-slate-500">
                              {r.dataset_name}
                              {r.is_mock_data && (
                                <span className="ml-2">
                                  <Chip tone="amber">MOCK</Chip>
                                </span>
                              )}
                            </p>
                            <p className="mt-2 text-xs text-slate-500">
                              {r.algorithm}
                            </p>
                          </div>
                          <Ring
                            value={rate}
                            max={Math.max(10, rate)}
                            decimals={rate < 1 ? 2 : 1}
                            size={72}
                            label="flagged %"
                            tone={rate >= 5 ? "amber" : "violet"}
                          />
                        </div>
                        <div className="mt-3 grid grid-cols-2 gap-2 text-center">
                          <div className="rounded-lg bg-white/5 p-2">
                            <p className="text-lg font-semibold tabular-nums">
                              {r.rows_scored.toLocaleString()}
                            </p>
                            <p className="text-[10px] uppercase tracking-wider text-slate-500">
                              Scored
                            </p>
                          </div>
                          <div className="rounded-lg bg-pink-500/10 p-2">
                            <p className="text-lg font-semibold tabular-nums">
                              {r.rows_flagged.toLocaleString()}
                            </p>
                            <p className="text-[10px] uppercase tracking-wider text-slate-500">
                              Flagged
                            </p>
                          </div>
                        </div>
                        <p className="mt-auto pt-3 text-xs text-slate-500">
                          {r.started_at ? formatDateTime(r.started_at) : "—"}
                        </p>
                      </Card3D>
                    );
                  })}
                </CardGrid>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="border-b border-slate-300 text-slate-600">
                      <tr>
                        <th className="py-2">#</th>
                        <th>Model</th>
                        <th>Dataset</th>
                        <th>Status</th>
                        <th className="text-right">Scored</th>
                        <th className="text-right">Flagged</th>
                        <th>Started</th>
                      </tr>
                    </thead>
                    <tbody>
                      {q.data.results.map((r) => (
                        <tr key={r.id} className="border-b border-slate-100">
                          <td className="py-2">
                            <Link
                              className="text-blue-700 hover:underline"
                              to={`/detection/${r.id}`}
                            >
                              {r.id}
                            </Link>
                          </td>
                          <td>{r.model_name}</td>
                          <td>
                            {r.dataset_name}
                            {r.is_mock_data && (
                              <span className="ml-2 rounded bg-amber-100 px-1.5 text-xs text-amber-800">
                                MOCK
                              </span>
                            )}
                          </td>
                          <td>
                            <RunStatusBadge status={r.status} />
                          </td>
                          <td className="text-right tabular-nums">
                            {r.rows_scored.toLocaleString()}
                          </td>
                          <td className="text-right tabular-nums">
                            {r.rows_flagged.toLocaleString()}
                          </td>
                          <td className="whitespace-nowrap">
                            {r.started_at ? formatDateTime(r.started_at) : "—"}
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
                Page {page} · {q.data.count} runs
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
