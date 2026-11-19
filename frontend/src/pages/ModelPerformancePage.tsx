import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api } from "../api/client";
import type { ModelVersionRow } from "../api/types";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/states";

const pct = (x: number) => `${(x * 100).toFixed(2)}%`;

export default function ModelPerformancePage() {
  const [dataset, setDataset] = useState("");
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
      <label className="mt-3 block text-sm">
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
        {rows.length > 0 && (
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
                              [{m.test_metrics.pr_auc_ci95[0].toFixed(3)},{" "}
                              {m.test_metrics.pr_auc_ci95[1].toFixed(3)}]
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
        )}
      </div>
    </section>
  );
}
