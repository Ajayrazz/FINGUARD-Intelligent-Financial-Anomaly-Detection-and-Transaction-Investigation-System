import { PageHero } from "../components/scenes/PageHero";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
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
      className="mt-4 flex flex-wrap items-end gap-3 rounded-md border border-slate-200 bg-slate-50 p-4"
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
  const q = useQuery({
    queryKey: ["detection-runs", page],
    queryFn: ({ signal }) =>
      api.get<Paginated<DetectionRun>>(`/detection/runs/?page=${page}`, signal),
    refetchInterval: (query) =>
      query.state.data?.results.some((r) => isRunActive(r.status))
        ? 3000
        : false,
  });
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
