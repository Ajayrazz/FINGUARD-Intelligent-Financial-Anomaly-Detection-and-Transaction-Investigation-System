import { EChart } from "../components/charts/EChart";
import {
  Card3D,
  CardGrid,
  Chip,
  Ring,
  useViewMode,
  ViewToggle,
} from "../components/ui/cards";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api } from "../api/client";
import type { ModelVersionRow } from "../api/types";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/states";

const pct = (x: number) => `${(x * 100).toFixed(2)}%`;

export default function ModelPerformancePage() {
  const [dataset, setDataset] = useState("");
  const [view, setView] = useViewMode("models");
  const q = useQuery({
    queryKey: ["model-versions"],
    queryFn: ({ signal }) =>
      api.get<ModelVersionRow[]>("/model-versions/", signal),
  });
  const rows = useMemo(
    () =>
      (q.data ?? [])
        .filter((m) => !dataset || m.dataset === dataset)
        .sort(
          (a, b) =>
            (b.test_metrics?.pr_auc ?? -1) - (a.test_metrics?.pr_auc ?? -1),
        ),
    [q.data, dataset],
  );
  const datasets = [...new Set((q.data ?? []).map((m) => m.dataset))];
  const chart3d = useMemo(() => {
    const algos = [...new Set(rows.map((m) => m.algorithm))];
    const dsets = [...new Set(rows.map((m) => m.dataset))];
    const best = new Map<string, number>();
    rows.forEach((m) => {
      if (!m.test_metrics) return;
      const k = `${m.algorithm}|${m.dataset}`;
      best.set(k, Math.max(best.get(k) ?? 0, m.test_metrics.pr_auc));
    });
    const data = [...best.entries()].map(([k, v]) => {
      const [a, d] = k.split("|");
      return [a, d, Number(v.toFixed(3))];
    });
    const ax = {
      axisLabel: { textStyle: { color: "#b8bde0" } },
      axisLine: { lineStyle: { color: "#4b5195" } },
      splitLine: { lineStyle: { color: "rgba(129,140,248,0.18)" } },
      axisPointer: { show: false },
    };
    return {
      tooltip: {},
      visualMap: {
        show: false,
        min: 0,
        max: 1,
        dimension: 2,
        inRange: { color: ["#4f46e5", "#a78bfa", "#22d3ee", "#34d399"] },
      },
      xAxis3D: { type: "category", data: algos, ...ax },
      yAxis3D: { type: "category", data: dsets, ...ax },
      zAxis3D: { type: "value", min: 0, max: 1, name: "PR-AUC", ...ax },
      grid3D: {
        boxWidth: 140,
        boxDepth: 50,
        environment: "none",
        light: { main: { intensity: 1.3 }, ambient: { intensity: 0.5 } },
        viewControl: {
          autoRotate: true,
          autoRotateSpeed: 5,
          distance: 210,
          alpha: 22,
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
  }, [rows]);
  return (
    <section>
      <h1 className="text-2xl font-semibold">Model Performance</h1>
      <p className="mt-1 text-sm text-slate-600">
        Offline results on held-out, chronologically later data from the
        research datasets (not on platform data). Ranked by PR-AUC, the primary
        metric for rare fraud.
      </p>
      <p
        role="note"
        className="mt-2 rounded border border-amber-300 bg-amber-50 p-2 text-sm text-amber-900"
      >
        Read with care: PaySim models using <strong>core+balance</strong>{" "}
        features reach near-perfect scores because the simulator's balance
        fields reveal the label. Compare models using the <strong>core</strong>{" "}
        feature set. ULB intervals are wide (52 test frauds).
      </p>
      {rows.some((m) => m.test_metrics) && (
        <div className="mt-4 rounded-2xl border border-indigo-400/20 bg-white/[0.03] p-3">
          <h2 className="text-base font-semibold">
            Best PR-AUC by algorithm and dataset
          </h2>
          <p className="text-xs text-slate-500">
            3D view · drag to rotate · higher is better
          </p>
          <EChart
            option={chart3d}
            height={320}
            label="3D bar chart of the best test PR-AUC for each algorithm and dataset"
          />
        </div>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-4">
        <ViewToggle mode={view} onChange={setView} />
        <label className="block text-sm">
          <span className="font-medium">Dataset </span>
          <select
            className="ml-2 rounded border border-slate-300 p-1"
            value={dataset}
            onChange={(e) => setDataset(e.target.value)}
          >
            <option value="">All</option>
            {datasets.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="mt-4">
        {q.isPending && <LoadingState />}
        {q.isError && (
          <ErrorState
            message={q.error.message}
            onRetry={() => void q.refetch()}
          />
        )}
        {q.data && rows.length === 0 && (
          <EmptyState
            title="No registered models"
            hint="Run the experiments and register them with `manage.py register_experiment`."
          />
        )}
        {rows.length > 0 &&
          (view === "cards" ? (
            <CardGrid min="21rem">
              {rows.map((m) => (
                <Card3D key={m.id} tone={m.scorable ? "green" : "indigo"}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h2 className="break-all text-sm font-semibold text-slate-800">
                        {m.model_name}
                      </h2>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        <Chip tone="violet">{m.algorithm}</Chip>
                        <Chip tone="cyan">{m.task_type}</Chip>
                        <Chip>{m.dataset}</Chip>
                        <Chip>{m.feature_set ?? "—"}</Chip>
                        {m.scorable && <Chip tone="green">scorable</Chip>}
                      </div>
                    </div>
                    {m.test_metrics && (
                      <Ring
                        value={m.test_metrics.pr_auc}
                        label="PR-AUC"
                        tone={
                          m.test_metrics.pr_auc > 0.7
                            ? "green"
                            : m.test_metrics.pr_auc > 0.3
                              ? "amber"
                              : "pink"
                        }
                      />
                    )}
                  </div>
                  {m.test_metrics ? (
                    <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                      <div className="rounded-lg bg-white/5 p-2">
                        <p className="text-[10px] uppercase tracking-wider text-slate-500">
                          ROC-AUC
                        </p>
                        <p className="font-semibold tabular-nums">
                          {m.test_metrics.roc_auc.toFixed(3)}
                        </p>
                      </div>
                      <div className="rounded-lg bg-white/5 p-2">
                        <p className="text-[10px] uppercase tracking-wider text-slate-500">
                          Recall @1% FPR
                        </p>
                        <p className="font-semibold tabular-nums">
                          {m.test_metrics.recall_at_fpr_1pct.toFixed(3)}
                        </p>
                      </div>
                      <div className="rounded-lg bg-white/5 p-2">
                        <p className="text-[10px] uppercase tracking-wider text-slate-500">
                          Base rate
                        </p>
                        <p className="font-semibold tabular-nums">
                          {pct(m.test_metrics.base_rate)}
                        </p>
                      </div>
                    </div>
                  ) : (
                    <p className="mt-4 text-sm text-slate-500">
                      no test evaluation
                    </p>
                  )}
                  {m.test_metrics?.pr_auc_ci95 && (
                    <p className="mt-2 text-xs text-slate-500">
                      PR-AUC 95% CI [{m.test_metrics.pr_auc_ci95[0].toFixed(3)},{" "}
                      {m.test_metrics.pr_auc_ci95[1].toFixed(3)}]
                    </p>
                  )}
                </Card3D>
              ))}
            </CardGrid>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">
                  Registered model versions and their test-split metrics
                </caption>
                <thead className="border-b border-slate-300 text-slate-600">
                  <tr>
                    <th className="py-2">Model</th>
                    <th>Algorithm</th>
                    <th>Type</th>
                    <th>Dataset</th>
                    <th>Features</th>
                    <th className="text-right">PR-AUC [95% CI]</th>
                    <th className="text-right">Base rate</th>
                    <th className="text-right">ROC-AUC</th>
                    <th className="text-right">Recall @ 1% FPR</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((m) => (
                    <tr key={m.id} className="border-b border-slate-100">
                      <td className="py-2">
                        {m.model_name}
                        {m.scorable && (
                          <span className="ml-2 rounded bg-green-100 px-1.5 text-xs text-green-800">
                            scorable
                          </span>
                        )}
                      </td>
                      <td>{m.algorithm}</td>
                      <td className="capitalize">{m.task_type}</td>
                      <td>{m.dataset}</td>
                      <td>{m.feature_set ?? "—"}</td>
                      {m.test_metrics ? (
                        <>
                          <td className="text-right tabular-nums">
                            {m.test_metrics.pr_auc.toFixed(3)}
                            {m.test_metrics.pr_auc_ci95 && (
                              <span className="text-slate-500">
                                {" "}
                                [{m.test_metrics.pr_auc_ci95[0].toFixed(
                                  3,
                                )}, {m.test_metrics.pr_auc_ci95[1].toFixed(3)}]
                              </span>
                            )}
                          </td>
                          <td className="text-right tabular-nums">
                            {pct(m.test_metrics.base_rate)}
                          </td>
                          <td className="text-right tabular-nums">
                            {m.test_metrics.roc_auc.toFixed(3)}
                          </td>
                          <td className="text-right tabular-nums">
                            {m.test_metrics.recall_at_fpr_1pct.toFixed(3)}
                          </td>
                        </>
                      ) : (
                        <td colSpan={4} className="text-slate-500">
                          no test evaluation
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
      </div>
    </section>
  );
}
