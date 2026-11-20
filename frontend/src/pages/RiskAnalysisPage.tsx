import { EChart } from "../components/charts/EChart";
import { MiniBars, StackBar, ThresholdBar } from "../components/ui/visuals";
import {
  Card3D,
  CardGrid,
  Ring,
  useViewMode,
  ViewToggle,
} from "../components/ui/cards";
import { PageHero } from "../components/scenes/PageHero";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type {
  Dataset,
  Paginated,
  RiskAssessment,
  RiskAssessmentDetail,
  RiskCategory,
  RiskConfig,
  RiskRun,
} from "../api/types";
import { useAuth } from "../auth/AuthContext";
import {
  RunStatusBadge,
  isRunActive,
} from "../components/detection/RunStatusBadge";
import { BreakdownTable } from "../components/risk/BreakdownTable";
import { RiskBadge } from "../components/risk/RiskBadge";
import {
  CATEGORY_LABEL,
  COMPONENT_LABEL,
  COMPONENT_ORDER,
} from "../components/risk/riskLabels";
import { Button } from "../components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/states";
import { useToast } from "../components/ui/Toast";
import { formatDateTime } from "../lib/format";

const CATEGORIES: RiskCategory[] = [
  "critical",
  "high",
  "medium",
  "low",
  "unscored",
];

function ConfigCard({
  cfg,
  canConfigure,
  onActivated,
}: {
  cfg: RiskConfig;
  canConfigure: boolean;
  onActivated: () => void;
}) {
  const toast = useToast();
  const activate = useMutation({
    mutationFn: () => api.post(`/risk/config/${cfg.id}/activate/`),
    onSuccess: () => {
      toast("success", `Version ${cfg.version} is now active`);
      onActivated();
    },
    onError: (e: unknown) =>
      toast("error", e instanceof ApiError ? e.message : "Could not activate"),
  });
  return (
    <Card3D tone={cfg.is_active ? "pink" : "indigo"} selected={cfg.is_active}>
      <p className="font-semibold">
        Version {cfg.version}{" "}
        {cfg.is_active && (
          <span className="animate-glow rounded bg-indigo-600 px-1.5 text-xs font-normal text-white">
            active
          </span>
        )}{" "}
        <span className="font-normal capitalize text-slate-500">
          · {cfg.source}
        </span>
      </p>
      <div className="mt-3">
        <StackBar
          parts={COMPONENT_ORDER.map((k) => ({
            label: COMPONENT_LABEL[k].name,
            value: cfg.weights[k],
          }))}
        />
      </div>
      <p className="mt-2 text-sm text-slate-700">
        {COMPONENT_ORDER.map(
          (k) => `${k} ${(cfg.weights[k] * 100).toFixed(0)}%`,
        ).join(" · ")}
      </p>
      <ThresholdBar
        medium={cfg.thresholds.medium}
        high={cfg.thresholds.high}
        critical={cfg.thresholds.critical}
      />
      <p className="mt-2 text-sm text-slate-700">
        Medium ≥ {cfg.thresholds.medium} · High ≥ {cfg.thresholds.high} ·
        Critical ≥ {cfg.thresholds.critical} · policy{" "}
        {cfg.missing_signal_policy} · min coverage{" "}
        {(cfg.min_coverage * 100).toFixed(0)}%
        {cfg.model_version_name && ` · model ${cfg.model_version_name}`}
      </p>
      {cfg.notes && <p className="mt-1 text-xs text-slate-500">{cfg.notes}</p>}
      {canConfigure && !cfg.is_active && (
        <Button
          className="mt-3 self-start"
          variant="secondary"
          disabled={activate.isPending}
          onClick={() => activate.mutate()}
        >
          Activate version {cfg.version}
        </Button>
      )}
    </Card3D>
  );
}

function NewConfigForm({
  base,
  onCreated,
}: {
  base: RiskConfig;
  onCreated: () => void;
}) {
  const toast = useToast();
  const [w, setW] = useState<Record<string, string>>(
    Object.fromEntries(
      COMPONENT_ORDER.map((k) => [k, String(base.weights[k])]),
    ),
  );
  const [t, setT] = useState<Record<string, string>>({
    medium: String(base.thresholds.medium),
    high: String(base.thresholds.high),
    critical: String(base.thresholds.critical),
  });
  const [policy, setPolicy] = useState<string>(base.missing_signal_policy);
  const [minCov, setMinCov] = useState(String(base.min_coverage));
  const sum = COMPONENT_ORDER.reduce((s, k) => s + Number(w[k]), 0);
  const create = useMutation({
    mutationFn: () =>
      api.post("/risk/config/", {
        weights: Object.fromEntries(
          COMPONENT_ORDER.map((k) => [k, Number(w[k])]),
        ),
        thresholds: {
          medium: Number(t.medium),
          high: Number(t.high),
          critical: Number(t.critical),
        },
        missing_signal_policy: policy,
        min_coverage: Number(minCov),
      }),
    onSuccess: () => {
      toast("success", "New version created (not active yet)");
      onCreated();
    },
    onError: (e: unknown) =>
      toast(
        "error",
        e instanceof ApiError ? e.message : "Invalid configuration",
      ),
  });
  return (
    <form
      className="mt-4 space-y-3 rounded-2xl border border-indigo-400/30 bg-white/[0.04] p-4 text-sm"
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate();
      }}
    >
      <h3 className="font-semibold">New configuration version</h3>
      <div className="flex flex-wrap gap-3">
        {COMPONENT_ORDER.map((k) => (
          <label key={k}>
            {COMPONENT_LABEL[k].name} weight
            <input
              aria-label={`${COMPONENT_LABEL[k].name} weight`}
              className="ml-1 w-16 rounded border border-slate-300 p-1"
              type="number"
              step="0.01"
              min="0"
              max="1"
              value={w[k]}
              onChange={(e) => setW({ ...w, [k]: e.target.value })}
            />
          </label>
        ))}
      </div>
      <p
        className={Math.abs(sum - 1) < 1e-6 ? "text-green-800" : "text-red-700"}
      >
        Weights sum to {sum.toFixed(2)} (must be 1.00)
      </p>
      <div
        aria-hidden="true"
        className="h-2 overflow-hidden rounded-full bg-white/10"
      >
        <div
          className={`h-full rounded-full transition-all duration-500 ${Math.abs(sum - 1) < 1e-6 ? "bg-gradient-to-r from-emerald-400 to-cyan-400" : "bg-gradient-to-r from-pink-500 to-red-500"}`}
          style={{ width: `${Math.min(100, Math.max(0, sum * 100))}%` }}
        />
      </div>
      <div className="flex flex-wrap gap-3">
        {(["medium", "high", "critical"] as const).map((k) => (
          <label key={k} className="capitalize">
            {k} from
            <input
              aria-label={`${k} threshold`}
              className="ml-1 w-16 rounded border border-slate-300 p-1"
              type="number"
              value={t[k]}
              onChange={(e) => setT({ ...t, [k]: e.target.value })}
            />
          </label>
        ))}
        <label>
          Missing signals
          <select
            className="ml-1 rounded border border-slate-300 p-1"
            value={policy}
            onChange={(e) => setPolicy(e.target.value)}
          >
            <option value="renormalize">Renormalise</option>
            <option value="neutral_prior">Neutral prior</option>
            <option value="strict">Strict (no score)</option>
          </select>
        </label>
        <label>
          Min coverage
          <input
            aria-label="Minimum coverage"
            className="ml-1 w-16 rounded border border-slate-300 p-1"
            type="number"
            step="0.05"
            min="0"
            max="1"
            value={minCov}
            onChange={(e) => setMinCov(e.target.value)}
          />
        </label>
      </div>
      <Button type="submit" disabled={create.isPending}>
        Create version
      </Button>
    </form>
  );
}

const AX3D = {
  axisLabel: { textStyle: { color: "#b8bde0" } },
  axisLine: { lineStyle: { color: "#4b5195" } },
  splitLine: { lineStyle: { color: "rgba(129,140,248,0.18)" } },
  axisPointer: { show: false },
};
const VIEW3D = {
  autoRotate: true,
  autoRotateSpeed: 6,
  distance: 200,
  alpha: 24,
  beta: 30,
  zoomSensitivity: 0,
  panSensitivity: 0,
};

export default function RiskAnalysisPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const [dataset, setDataset] = useState("");
  const [category, setCategory] = useState<"" | RiskCategory>("");
  const [selected, setSelected] = useState<number | null>(null);
  const [view, setView] = useViewMode("risk-rows");
  const datasets = useQuery({
    queryKey: ["datasets"],
    queryFn: ({ signal }) => api.get<Dataset[]>("/datasets/", signal),
  });
  const configs = useQuery({
    queryKey: ["risk-configs"],
    queryFn: ({ signal }) => api.get<RiskConfig[]>("/risk/config/", signal),
  });
  const runs = useQuery({
    queryKey: ["risk-runs"],
    queryFn: ({ signal }) => api.get<Paginated<RiskRun>>("/risk/runs/", signal),
    refetchInterval: (query) =>
      query.state.data?.results.some((r) => isRunActive(r.status))
        ? 3000
        : false,
  });
  const latest = (runs.data?.results ?? []).find(
    (r) => String(r.dataset) === dataset && r.status === "succeeded",
  );
  const distChart = useMemo(
    () => ({
      tooltip: { trigger: "item" },
      series: [
        {
          type: "pie",
          roseType: "radius",
          radius: ["15%", "75%"],
          itemStyle: { borderRadius: 8 },
          label: { color: "#b8bde0" },
          data: CATEGORIES.map((c) => ({
            name: CATEGORY_LABEL[c],
            value: latest?.category_counts[c] ?? 0,
          })).filter((d) => d.value > 0),
        },
      ],
    }),
    [latest],
  );
  const start = useMutation({
    mutationFn: () =>
      api.post<RiskRun>("/risk/runs/", { dataset: Number(dataset) }),
    onSuccess: () => {
      toast("success", "Risk scoring started");
      void qc.invalidateQueries({ queryKey: ["risk-runs"] });
    },
    onError: (e: unknown) =>
      toast("error", e instanceof ApiError ? e.message : "Could not start"),
  });
  const rows = useQuery({
    queryKey: ["risk-assessments", latest?.id, category],
    enabled: !!latest,
    queryFn: ({ signal }) =>
      api.get<Paginated<RiskAssessment>>(
        `/risk/assessments/?run=${latest!.id}&scored=true${category ? `&category=${category}` : ""}`,
        signal,
      ),
  });
  const scatter3d = useMemo(
    () => ({
      tooltip: {},
      visualMap: {
        show: false,
        min: 0,
        max: 100,
        dimension: 2,
        inRange: { color: ["#34d399", "#fbbf24", "#f43f5e"] },
      },
      xAxis3D: {
        type: "category",
        data: CATEGORIES.filter((c) => c !== "unscored").map(
          (c) => CATEGORY_LABEL[c],
        ),
        ...AX3D,
      },
      yAxis3D: { type: "value", name: "Coverage %", min: 0, max: 100, ...AX3D },
      zAxis3D: { type: "value", name: "Score", min: 0, max: 100, ...AX3D },
      grid3D: {
        boxWidth: 120,
        boxDepth: 70,
        environment: "none",
        viewControl: VIEW3D,
      },
      series: [
        {
          type: "scatter3D",
          symbolSize: 14,
          itemStyle: { opacity: 0.9 },
          data: (rows.data?.results ?? [])
            .filter((r) => r.overall_score !== null)
            .map((r) => [
              CATEGORY_LABEL[r.category],
              Math.round(r.weight_coverage * 100),
              r.overall_score,
            ]),
        },
      ],
    }),
    [rows.data],
  );
  const detail = useQuery({
    queryKey: ["risk-assessment", selected],
    enabled: selected !== null,
    queryFn: ({ signal }) =>
      api.get<RiskAssessmentDetail>(`/risk/assessments/${selected}/`, signal),
  });
  const active = configs.data?.find((c) => c.is_active);
  const total = latest ? Math.max(latest.rows_total, 1) : 1;
  return (
    <section className="space-y-4">
      <PageHero
        eyebrow="Detect"
        title="Risk Analysis"
        tone="pink"
        scene="gauge"
      />
      <p className="text-sm text-slate-600">
        One 0–100 score per transaction from six signals, with every component
        and the signal coverage shown. Scores prioritise review; they are not
        findings.
      </p>

      <div className="animate-glow flex flex-wrap items-end gap-3 rounded-2xl border border-indigo-400/30 bg-white/[0.03] p-4">
        <label className="text-sm">
          <span className="block font-medium">Dataset</span>
          <select
            className="mt-1 w-80 rounded border border-slate-300 p-1.5"
            value={dataset}
            onChange={(e) => {
              setDataset(e.target.value);
              setSelected(null);
            }}
          >
            <option value="">Select…</option>
            {(datasets.data ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.row_count.toLocaleString()} rows)
              </option>
            ))}
          </select>
        </label>
        {can("risk.run") && (
          <Button
            disabled={!dataset || start.isPending}
            onClick={() => start.mutate()}
          >
            Score with active configuration
          </Button>
        )}
        <p className="basis-full text-xs text-slate-600">
          Uses the latest detection run, behavioural analysis, graph snapshot
          and duplicate scan of the dataset. Signals that were never run show as
          unavailable.
        </p>
      </div>

      <div>
        <h2 className="font-semibold">Configuration</h2>
        {configs.isPending && <LoadingState />}
        {configs.isError && <ErrorState message={configs.error.message} />}
        {configs.data && (
          <div className="stagger mt-2 grid gap-4 md:grid-cols-2">
            {configs.data.slice(0, 4).map((c) => (
              <ConfigCard
                key={c.id}
                cfg={c}
                canConfigure={can("risk.configure")}
                onActivated={() =>
                  void qc.invalidateQueries({ queryKey: ["risk-configs"] })
                }
              />
            ))}
          </div>
        )}
        {can("risk.configure") && active && (
          <NewConfigForm
            key={active.id}
            base={active}
            onCreated={() =>
              void qc.invalidateQueries({ queryKey: ["risk-configs"] })
            }
          />
        )}
      </div>

      {dataset && !latest && !runs.isPending && (
        <EmptyState
          title="No finished risk run for this dataset"
          hint={can("risk.run") ? "Start one above." : undefined}
        />
      )}
      {latest && (
        <>
          <div>
            <h2 className="font-semibold">
              Run #{latest.id} <RunStatusBadge status={latest.status} />{" "}
              <span className="text-sm font-normal text-slate-600">
                · config v{latest.config_version} ·{" "}
                {latest.rows_scored.toLocaleString()} scored ·{" "}
                {latest.finished_at ? formatDateTime(latest.finished_at) : ""}
              </span>
            </h2>
            <div className="mt-2 grid items-center gap-4 lg:grid-cols-2">
              <ul
                className="space-y-2 text-sm"
                aria-label="Category distribution"
              >
                {CATEGORIES.map((c) => {
                  const n = latest.category_counts[c] ?? 0;
                  return (
                    <li key={c} className="flex items-center gap-2">
                      <span className="w-20">{CATEGORY_LABEL[c]}</span>
                      <span
                        className="h-3 origin-left rounded bg-gradient-to-r from-indigo-500 to-pink-400 transition-all duration-700"
                        style={{
                          width: `${Math.max((n / total) * 100, n > 0 ? 1 : 0)}%`,
                          maxWidth: "60%",
                        }}
                        aria-hidden
                      />
                      <span className="tabular-nums">{n.toLocaleString()}</span>
                    </li>
                  );
                })}
              </ul>
              <EChart
                option={distChart}
                height={220}
                label="Rose chart of scored transactions by risk category"
              />
            </div>
            <p className="mt-1 text-xs text-slate-600">
              Signal coverage in this run:{" "}
              {Object.entries(latest.coverage_summary)
                .map(
                  ([k, v]) =>
                    `${(Number(k) * 100).toFixed(0)}% → ${v.toLocaleString()}`,
                )
                .join(" · ")}
            </p>
          </div>
          {(rows.data?.results.length ?? 0) > 0 && (
            <div className="rounded-2xl border border-indigo-400/20 bg-white/[0.03] p-3">
              <h2 className="text-base font-semibold">Score landscape</h2>
              <p className="text-xs text-slate-500">
                Category, signal coverage and score for the shown transactions ·
                drag to rotate
              </p>
              <EChart
                option={scatter3d}
                height={320}
                label="3D scatter chart of risk score against signal coverage for each risk category"
              />
            </div>
          )}
          <div>
            <div className="flex items-center justify-between">
              <h2 className="font-semibold">Highest-scoring transactions</h2>
              <label className="text-sm">
                Category{" "}
                <select
                  className="rounded border border-slate-300 p-1"
                  value={category}
                  onChange={(e) =>
                    setCategory(e.target.value as "" | RiskCategory)
                  }
                >
                  <option value="">All scored</option>
                  {CATEGORIES.filter((c) => c !== "unscored").map((c) => (
                    <option key={c} value={c}>
                      {CATEGORY_LABEL[c]}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {rows.isPending && <LoadingState />}
            {rows.isError && <ErrorState message={rows.error.message} />}
            {rows.data && rows.data.results.length === 0 && (
              <EmptyState title="Nothing in this category" />
            )}
            {rows.data && rows.data.results.length > 0 && (
              <div className="space-y-3">
                <ViewToggle mode={view} onChange={setView} />
                {view === "cards" ? (
                  <CardGrid min="19rem">
                    {rows.data.results.map((r) => (
                      <Card3D
                        key={r.id}
                        tone={
                          r.category === "critical"
                            ? "red"
                            : r.category === "high"
                              ? "amber"
                              : r.category === "medium"
                                ? "violet"
                                : r.category === "low"
                                  ? "green"
                                  : "slate"
                        }
                        selected={selected === r.id}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <button
                              className="break-all font-mono text-blue-700 hover:underline"
                              onClick={() => setSelected(r.id)}
                            >
                              {r.external_id}
                            </button>
                            <div className="mt-2 flex flex-wrap items-center gap-2">
                              <RiskBadge category={r.category} />
                              {r.capped && (
                                <span
                                  title="held at High: low coverage"
                                  className="text-xs text-slate-500"
                                >
                                  capped*
                                </span>
                              )}
                            </div>
                            <p className="mt-2 text-xs text-slate-500">
                              Signal coverage{" "}
                              {(r.weight_coverage * 100).toFixed(0)}%
                            </p>
                          </div>
                          <Ring
                            value={r.overall_score ?? 0}
                            max={100}
                            decimals={1}
                            size={76}
                            label="risk"
                            tone={
                              r.category === "critical"
                                ? "red"
                                : r.category === "high"
                                  ? "amber"
                                  : r.category === "medium"
                                    ? "violet"
                                    : "green"
                            }
                          />
                        </div>
                        <div className="mt-3">
                          <MiniBars
                            items={COMPONENT_ORDER.map((k) => ({
                              label: k,
                              value: r.component_values[k] ?? null,
                            }))}
                          />
                        </div>
                      </Card3D>
                    ))}
                  </CardGrid>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="mt-1 w-full text-left text-sm">
                      <thead className="border-b border-slate-300 text-slate-600">
                        <tr>
                          <th className="py-1">Transaction</th>
                          <th className="text-right">Score</th>
                          <th>Category</th>
                          <th className="text-right">Coverage</th>
                          {COMPONENT_ORDER.map((k) => (
                            <th
                              key={k}
                              className="text-right"
                              title={COMPONENT_LABEL[k].name}
                            >
                              {k}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {rows.data.results.map((r) => (
                          <tr
                            key={r.id}
                            className={`border-b border-slate-100 ${selected === r.id ? "bg-slate-100" : ""}`}
                          >
                            <td className="py-1">
                              <button
                                className="text-blue-700 hover:underline"
                                onClick={() => setSelected(r.id)}
                              >
                                {r.external_id}
                              </button>
                            </td>
                            <td className="text-right tabular-nums">
                              {r.overall_score?.toFixed(1)}
                            </td>
                            <td>
                              <RiskBadge category={r.category} />
                              {r.capped && (
                                <span title="held at High: low coverage">
                                  {" "}
                                  *
                                </span>
                              )}
                            </td>
                            <td className="text-right tabular-nums">
                              {(r.weight_coverage * 100).toFixed(0)}%
                            </td>
                            {COMPONENT_ORDER.map((k) => (
                              <td key={k} className="text-right tabular-nums">
                                {r.component_values[k] != null
                                  ? r.component_values[k]!.toFixed(0)
                                  : "–"}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}
      {selected !== null && (
        <div
          role="region"
          aria-label="Assessment breakdown"
          className="rounded-md border border-slate-300 p-4"
        >
          {detail.isPending && <LoadingState />}
          {detail.isError && <ErrorState message={detail.error.message} />}
          {detail.data && (
            <>
              <p className="mb-2 text-sm">
                <Link
                  className="text-blue-700 hover:underline"
                  to={`/transactions/${detail.data.transaction}`}
                >
                  Transaction {detail.data.external_id}
                </Link>{" "}
                · sender{" "}
                <Link
                  className="font-mono text-blue-700 hover:underline"
                  to={`/accounts/${detail.data.account}`}
                >
                  {detail.data.account_ref}
                </Link>
              </p>
              <BreakdownTable a={detail.data} />
            </>
          )}
        </div>
      )}
    </section>
  );
}
