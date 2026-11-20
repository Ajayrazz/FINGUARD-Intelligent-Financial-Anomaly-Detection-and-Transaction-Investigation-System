import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, downloadFile } from "../api/client";
import type {
  AnalyticsOverview,
  DetectionPerf,
  FalsePositives,
  HighRiskAccount,
  InvestigationsSummary,
  RiskDistribution,
  SuspiciousTx,
  VolumePoint,
} from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { EChart } from "../components/charts/EChart";
import { pie3dOption } from "../components/charts/pie3d";
import { Tilt } from "../components/fx/Tilt";
import { PageHero } from "../components/scenes/PageHero";
import { Button } from "../components/ui/Button";
import { Card3D, CardGrid, Chip, Ring } from "../components/ui/cards";
import { StatTile } from "../components/ui/StatTile";
import { useToast } from "../components/ui/Toast";
import { formatDateTime } from "../lib/format";
import { usePageTitle } from "../lib/usePageTitle";

const AXIS = {
  axisLabel: { color: "#b8bde0" },
  axisLine: { lineStyle: { color: "#3b4180" } },
  splitLine: { lineStyle: { color: "rgba(129,140,248,0.15)" } },
};
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
const REPORTS = [
  { id: "volume", label: "Transaction volume" },
  { id: "risk-distribution", label: "Risk distribution" },
  { id: "high-risk-accounts", label: "Highest-risk accounts" },
  { id: "false-positives", label: "False-positive analysis" },
  { id: "investigations", label: "Investigation summary" },
  { id: "recent-suspicious", label: "Recent suspicious transactions" },
] as const;
const titleCase = (s: string) =>
  s.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
const pct = (x: number | null) =>
  x === null ? "—" : `${(x * 100).toFixed(1)}%`;

function Panel({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <Tilt max={3} className="h-full">
      <section className="h-full rounded-2xl border border-indigo-400/20 bg-gradient-to-br from-indigo-500/[0.07] via-white/[0.02] to-transparent p-4 shadow-lg shadow-black/30">
        <h2 className="text-base font-semibold text-slate-800">{title}</h2>
        {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
        <div className="mt-2">{children}</div>
      </section>
    </Tilt>
  );
}
const Empty = ({ text }: { text: string }) => (
  <p className="flex h-48 items-center justify-center text-sm text-slate-500">
    {text}
  </p>
);

export default function AnalyticsPage() {
  usePageTitle("Analytics");
  const { can } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const [dataset, setDataset] = useState("");
  const [gran, setGran] = useState<"day" | "week" | "month">("day");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [report, setReport] =
    useState<(typeof REPORTS)[number]["id"]>("volume");

  const qs = new URLSearchParams();
  if (dataset) qs.set("dataset", dataset);
  if (from) qs.set("from", from);
  if (to) qs.set("to", to);
  const base = qs.toString();
  const withExtra = (extra: Record<string, string>) => {
    const p = new URLSearchParams(base);
    Object.entries(extra).forEach(([k, v]) => p.set(k, v));
    return p.toString();
  };
  const useAnalytics = <T,>(key: string, path: string, query = base) =>
    useQuery({
      queryKey: ["analytics", key, query],
      queryFn: ({ signal }) =>
        api.get<T>(`/analytics/${path}/?${query}`, signal),
    });

  const datasets = useQuery({
    queryKey: ["analytics", "datasets"],
    queryFn: ({ signal }) =>
      api.get<{ id: number; name: string }[]>("/analytics/datasets/", signal),
  });
  const overview = useAnalytics<AnalyticsOverview>("overview", "overview");
  const volume = useAnalytics<{ series: VolumePoint[] }>(
    "volume",
    "volume",
    withExtra({ granularity: gran }),
  );
  const risk = useAnalytics<RiskDistribution>("risk", "risk-distribution");
  const accounts = useAnalytics<HighRiskAccount[]>(
    "accounts",
    "accounts/high-risk",
  );
  const recent = useAnalytics<SuspiciousTx[]>("recent", "recent-suspicious");
  const inv = useAnalytics<InvestigationsSummary>(
    "inv",
    "investigations/summary",
  );
  const fp = useAnalytics<FalsePositives>("fp", "false-positives");
  const perf = useQuery({
    queryKey: ["analytics", "perf"],
    queryFn: ({ signal }) =>
      api.get<DetectionPerf[]>("/analytics/detection-performance/", signal),
  });

  const refresh = useMutation({
    mutationFn: () =>
      api.post(`/analytics/refresh/${dataset ? `?dataset=${dataset}` : ""}`),
    onSuccess: () => {
      toast("success", "Analytics rebuilt from the source tables");
      void qc.invalidateQueries({ queryKey: ["analytics"] });
    },
    onError: (e: unknown) =>
      toast("error", e instanceof ApiError ? e.message : "Refresh failed"),
  });
  const exportAs = (file: "csv" | "pdf") =>
    void downloadFile(
      `/analytics/export/?${withExtra({ report, file, granularity: gran })}`,
      `finguard-${report}.${file}`,
    ).catch((e: unknown) =>
      toast("error", e instanceof ApiError ? e.message : "Export failed"),
    );

  const volumeChart = useMemo(() => {
    const s = volume.data?.series ?? [];
    return {
      tooltip: { trigger: "axis" },
      legend: { top: 0, textStyle: { color: "#b8bde0" } },
      grid: { left: 8, right: 16, top: 36, bottom: 8, containLabel: true },
      xAxis: {
        type: "category",
        data: s.map((p) => p.period.slice(0, 10)),
        ...AXIS,
      },
      yAxis: [
        {
          type: "value",
          name: "Transactions",
          nameTextStyle: { color: "#b8bde0", align: "left" },
          ...AXIS,
        },
        {
          type: "value",
          name: "Value",
          nameTextStyle: { color: "#b8bde0" },
          splitLine: { show: false },
          axisLabel: { color: "#b8bde0" },
        },
      ],
      series: [
        {
          name: "Transactions",
          type: "bar",
          data: s.map((p) => p.transactions),
          barMaxWidth: 26,
          itemStyle: {
            borderRadius: [8, 8, 0, 0],
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "#818cf8" },
                { offset: 1, color: "#4f46e5" },
              ],
            },
            shadowBlur: 12,
            shadowColor: "rgba(99,102,241,0.6)",
          },
          animationDelay: (i: number) => i * 40,
        },
        {
          name: "Value",
          type: "line",
          yAxisIndex: 1,
          smooth: 0.4,
          symbol: "circle",
          symbolSize: 8,
          data: s.map((p) => Number(p.value)),
          lineStyle: {
            width: 4,
            color: "#22d3ee",
            shadowBlur: 14,
            shadowColor: "#22d3ee",
          },
          itemStyle: { color: "#fff", borderColor: "#22d3ee", borderWidth: 2 },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(34,211,238,0.35)" },
                { offset: 1, color: "rgba(34,211,238,0)" },
              ],
            },
          },
        },
        {
          name: "Flagged",
          type: "line",
          smooth: 0.4,
          symbolSize: 8,
          data: s.map((p) => p.flagged),
          lineStyle: {
            width: 3,
            color: "#f472b6",
            shadowBlur: 12,
            shadowColor: "#f472b6",
          },
          itemStyle: { color: "#f472b6" },
        },
      ],
    };
  }, [volume.data]);

  const riskPie = useMemo(() => {
    const color: Record<string, string> = {
      low: "#10b981",
      medium: "#f59e0b",
      high: "#f97316",
      critical: "#ef4444",
      unscored: "#64748b",
    };
    return pie3dOption(
      Object.entries(risk.data?.counts ?? {})
        .filter(([, v]) => v > 0)
        .map(([k, v]) => ({
          name: `${titleCase(k)}: ${v.toLocaleString("en-IN")}`,
          value: v,
          color: color[k] ?? "#818cf8",
        })),
    );
  }, [risk.data]);

  const gauge = (value: number | null, name: string, color: string) => ({
    series: [
      {
        type: "gauge",
        startAngle: 200,
        endAngle: -20,
        min: 0,
        max: 100,
        radius: "92%",
        progress: {
          show: true,
          width: 14,
          itemStyle: { color, shadowBlur: 16, shadowColor: color },
        },
        axisLine: {
          lineStyle: { width: 14, color: [[1, "rgba(129,140,248,0.18)"]] },
        },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        pointer: { show: false },
        anchor: { show: false },
        title: { offsetCenter: [0, "62%"], color: "#b8bde0", fontSize: 12 },
        detail: {
          valueAnimation: true,
          offsetCenter: [0, "10%"],
          fontSize: 30,
          fontWeight: 700,
          color: "#fff",
          formatter: value === null ? "n/a" : "{value}%",
        },
        data: [
          {
            value: value === null ? 0 : Number((value * 100).toFixed(1)),
            name,
          },
        ],
      },
    ],
  });

  const perfChart = useMemo(() => {
    const rows = (perf.data ?? []).slice(0, 8);
    const names = rows.map((r) => r.model);
    const metrics = ["PR-AUC", "ROC-AUC", "Recall @ 1% FPR"];
    const data = rows.flatMap((r) => [
      [r.model, "PR-AUC", r.pr_auc ?? 0],
      [r.model, "ROC-AUC", r.roc_auc ?? 0],
      [r.model, "Recall @ 1% FPR", r.recall_at_fpr_1pct ?? 0],
    ]);
    return {
      tooltip: {},
      visualMap: {
        show: false,
        min: 0,
        max: 1,
        dimension: 2,
        inRange: { color: ["#4f46e5", "#a78bfa", "#22d3ee", "#34d399"] },
      },
      xAxis3D: { type: "category", data: names, ...AX3D },
      yAxis3D: { type: "category", data: metrics, ...AX3D },
      zAxis3D: { type: "value", min: 0, max: 1, ...AX3D },
      grid3D: {
        boxWidth: 160,
        boxDepth: 40,
        environment: "none",
        light: { main: { intensity: 1.3 }, ambient: { intensity: 0.5 } },
        viewControl: VIEW3D,
      },
      series: [
        {
          type: "bar3D",
          data,
          shading: "lambert",
          bevelSize: 0.25,
          barSize: 10,
        },
      ],
    };
  }, [perf.data]);

  const funnel = useMemo(() => {
    const order = [
      "new",
      "under_review",
      "investigation",
      "escalated",
      "resolved",
      "closed",
    ];
    const by = inv.data?.by_status ?? {};
    const colors = [
      "#22d3ee",
      "#38bdf8",
      "#818cf8",
      "#a78bfa",
      "#d946ef",
      "#f472b6",
    ];
    return {
      tooltip: { trigger: "item" },
      series: [
        {
          type: "funnel",
          sort: "none",
          left: "8%",
          width: "84%",
          gap: 4,
          minSize: "20%",
          label: { color: "#fff", fontWeight: 600, formatter: "{b}: {c}" },
          itemStyle: {
            borderWidth: 0,
            shadowBlur: 18,
            shadowColor: "rgba(124,58,237,0.5)",
          },
          data: order
            .filter((k) => by[k] !== undefined)
            .map((k) => ({
              name: titleCase(k),
              value: Math.max(1, by[k] ?? 0),
              itemStyle: { color: colors[order.indexOf(k)] },
            })),
        },
      ],
    };
  }, [inv.data]);

  const o = overview.data;
  const lab = fp.data?.labelled;

  return (
    <section className="space-y-6">
      <PageHero eyebrow="Insights" title="Analytics" tone="cyan" scene="trend">
        <p className="mt-2 text-sm text-slate-600">
          Volume, risk, false positives, investigations and model quality, all
          computed from stored data.
        </p>
      </PageHero>

      <form
        className="animate-glow flex flex-wrap items-end gap-3 rounded-2xl border border-indigo-400/30 bg-white/[0.03] p-4 text-sm"
        onSubmit={(e) => e.preventDefault()}
        aria-label="Analytics filters"
      >
        <label>
          <span className="block font-medium">Dataset</span>
          <select
            className="mt-1 w-64 rounded border border-slate-300 p-1.5"
            value={dataset}
            onChange={(e) => setDataset(e.target.value)}
          >
            <option value="">All datasets</option>
            {(datasets.data ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="block font-medium">Group by</span>
          <select
            className="mt-1 rounded border border-slate-300 p-1.5"
            value={gran}
            onChange={(e) => setGran(e.target.value as typeof gran)}
          >
            <option value="day">Day</option>
            <option value="week">Week</option>
            <option value="month">Month</option>
          </select>
        </label>
        <label>
          <span className="block font-medium">From</span>
          <input
            type="date"
            className="mt-1 rounded border border-slate-300 p-1.5"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </label>
        <label>
          <span className="block font-medium">To</span>
          <input
            type="date"
            className="mt-1 rounded border border-slate-300 p-1.5"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </label>
        {can("analytics.refresh") && (
          <Button
            variant="secondary"
            disabled={refresh.isPending}
            onClick={() => refresh.mutate()}
          >
            {refresh.isPending ? "Rebuilding…" : "Rebuild rollup"}
          </Button>
        )}
        <p className="basis-full text-xs text-slate-500">
          {o?.refreshed_at
            ? `Rollup refreshed ${formatDateTime(o.refreshed_at)} (hourly, or on demand).`
            : "Rollup builds on first use."}{" "}
          Dates filter the volume series and the investigation counts.
        </p>
      </form>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
        <StatTile
          label="Transactions"
          value={o?.transactions ?? 0}
          tone="indigo"
        />
        <StatTile
          label="Value"
          value={Math.round(Number(o?.value ?? 0))}
          tone="cyan"
          hint="sum of amounts"
        />
        <StatTile
          label="Flagged"
          value={o?.flagged ?? 0}
          tone="pink"
          hint="latest detection run"
        />
        <StatTile
          label="High risk"
          value={o?.high_risk_transactions ?? 0}
          tone="amber"
          hint="high + critical"
        />
        <StatTile
          label="Open alerts"
          value={o?.open_alerts ?? 0}
          tone="violet"
        />
        <StatTile label="Open cases" value={o?.open_cases ?? 0} tone="green" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="lg:col-span-2">
          <Panel
            title="Volume over time"
            subtitle="Transactions (bars), value (area) and flagged (line)"
          >
            {(volume.data?.series.length ?? 0) > 0 ? (
              <EChart
                option={volumeChart}
                height={340}
                label="Combined chart of transaction count, value and flagged count per period"
              />
            ) : (
              <Empty text="No transactions in this selection." />
            )}
          </Panel>
        </div>
        <Panel
          title="Risk distribution"
          subtitle="Latest risk run of each dataset"
        >
          {(risk.data?.total ?? 0) > 0 ? (
            <>
              <EChart
                option={riskPie}
                height={280}
                label="Rotating 3D pie chart of scored transactions by risk category"
              />
              <ul
                className="mt-1 flex flex-wrap justify-center gap-2 text-xs"
                aria-label="Risk categories"
              >
                {Object.entries(risk.data?.counts ?? {})
                  .filter(([, v]) => v > 0)
                  .map(([k, v]) => (
                    <li
                      key={k}
                      className="rounded-full border border-indigo-400/25 bg-white/5 px-3 py-1"
                    >
                      {titleCase(k)}:{" "}
                      <strong>{v.toLocaleString("en-IN")}</strong>
                    </li>
                  ))}
              </ul>
            </>
          ) : (
            <Empty text="No risk run yet. Score a dataset on the Risk Analysis page." />
          )}
        </Panel>
        <Panel title="Investigation pipeline" subtitle="Cases by status">
          {(inv.data?.total ?? 0) > 0 ? (
            <>
              <EChart
                option={funnel}
                height={230}
                label="Funnel chart of cases by workflow status"
              />
              <dl className="mt-2 grid grid-cols-3 gap-2 text-center text-xs">
                {(
                  [
                    ["Median", inv.data?.resolution_hours.median],
                    ["Mean", inv.data?.resolution_hours.mean],
                    ["Slowest", inv.data?.resolution_hours.max],
                  ] as const
                ).map(([k, v]) => (
                  <div key={k} className="rounded-lg bg-white/5 p-2">
                    <dt className="uppercase tracking-wider text-slate-500">
                      {k} resolution
                    </dt>
                    <dd className="text-base font-semibold tabular-nums">
                      {v === null || v === undefined ? "—" : `${v} h`}
                    </dd>
                  </div>
                ))}
              </dl>
            </>
          ) : (
            <Empty text="No cases yet." />
          )}
        </Panel>
        <Panel
          title="False positives: investigator decisions"
          subtitle="False share of decided alerts and cases"
        >
          <div className="grid grid-cols-2 gap-2">
            <div>
              <EChart
                option={gauge(
                  fp.data?.investigated.alerts.rate ?? null,
                  "Alerts",
                  "#f472b6",
                )}
                height={190}
                label={`Gauge of the alert false-positive rate: ${pct(fp.data?.investigated.alerts.rate ?? null)}`}
              />
              <p className="text-center text-xs text-slate-500">
                {fp.data?.investigated.alerts.false_positive ?? 0} false ·{" "}
                {fp.data?.investigated.alerts.true_positive ?? 0} true
              </p>
            </div>
            <div>
              <EChart
                option={gauge(
                  fp.data?.investigated.cases.rate ?? null,
                  "Cases",
                  "#a78bfa",
                )}
                height={190}
                label={`Gauge of the case false-positive rate: ${pct(fp.data?.investigated.cases.rate ?? null)}`}
              />
              <p className="text-center text-xs text-slate-500">
                {fp.data?.investigated.cases.false_positive ?? 0} false ·{" "}
                {fp.data?.investigated.cases.confirmed_suspicious ?? 0}{" "}
                confirmed
              </p>
            </div>
          </div>
        </Panel>
        <Panel
          title="False positives: labelled research data"
          subtitle="Latest detection run vs ground-truth labels (evaluation only, not predictions)"
        >
          {lab && lab.runs.length > 0 ? (
            <>
              <dl className="grid grid-cols-2 gap-2 text-center">
                {(
                  [
                    ["True positives", lab.tp, "bg-emerald-400/10"],
                    ["False positives", lab.fp, "bg-pink-500/10"],
                    ["False negatives", lab.fn, "bg-amber-400/10"],
                    ["True negatives", lab.tn, "bg-white/5"],
                  ] as const
                ).map(([k, v, c]) => (
                  <div key={k} className={`rounded-xl p-3 ${c}`}>
                    <dt className="text-xs uppercase tracking-wider text-slate-500">
                      {k}
                    </dt>
                    <dd className="text-2xl font-semibold tabular-nums">
                      {v.toLocaleString("en-IN")}
                    </dd>
                  </div>
                ))}
              </dl>
              <p className="mt-3 text-center text-sm">
                Precision <strong>{pct(lab.precision)}</strong> · Recall{" "}
                <strong>{pct(lab.recall)}</strong> · False-positive rate{" "}
                <strong>{pct(lab.false_positive_rate)}</strong>
              </p>
            </>
          ) : (
            <Empty text="No labelled data with a detection run." />
          )}
        </Panel>
      </div>

      <Panel
        title="Model comparison"
        subtitle="Offline test-split quality of registered models · drag to rotate"
      >
        {(perf.data?.length ?? 0) > 0 ? (
          <>
            <EChart
              option={perfChart}
              height={340}
              label="3D bar chart comparing PR-AUC, ROC-AUC and recall at one percent false-positive rate for each registered model"
            />
            <CardGrid min="16rem">
              {(perf.data ?? []).slice(0, 6).map((m) => (
                <Card3D key={m.id} tone="cyan">
                  <p className="break-all text-sm font-semibold">{m.model}</p>
                  <p className="text-xs text-slate-500">
                    {m.algorithm} · {m.dataset}
                  </p>
                  <div className="mt-2 flex items-center justify-between gap-2 text-xs text-slate-600">
                    <span>
                      {m.latency_ms_median !== null
                        ? `${m.latency_ms_median.toFixed(2)} ms median latency`
                        : "latency n/a"}
                      <br />
                      {m.throughput_rows_per_s !== null
                        ? `${Math.round(m.throughput_rows_per_s).toLocaleString("en-IN")} rows/s`
                        : "throughput n/a"}
                    </span>
                    <Ring
                      value={m.pr_auc ?? 0}
                      label="PR-AUC"
                      size={60}
                      tone="cyan"
                    />
                  </div>
                </Card3D>
              ))}
            </CardGrid>
          </>
        ) : (
          <Empty text="No registered models with test results." />
        )}
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel
          title="Highest-risk accounts"
          subtitle="By highest transaction score in the latest risk run"
        >
          {(accounts.data?.length ?? 0) > 0 ? (
            <div className="stagger grid gap-3 sm:grid-cols-2">
              {(accounts.data ?? []).slice(0, 6).map((a) => (
                <Card3D
                  key={a.account}
                  tone={
                    a.max_score >= 80
                      ? "red"
                      : a.max_score >= 60
                        ? "amber"
                        : "violet"
                  }
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      {can("accounts.read") ? (
                        <Link
                          className="break-all font-mono text-blue-700"
                          to={`/accounts/${a.account}`}
                        >
                          {a.account_ref}
                        </Link>
                      ) : (
                        <span className="break-all font-mono">
                          {a.account_ref}
                        </span>
                      )}
                      <p className="mt-1 text-xs text-slate-500">
                        {a.high_or_critical} high/critical of {a.assessments}
                      </p>
                    </div>
                    <Ring
                      value={a.max_score}
                      max={100}
                      decimals={1}
                      size={64}
                      label="max"
                      tone={a.max_score >= 80 ? "red" : "amber"}
                    />
                  </div>
                </Card3D>
              ))}
            </div>
          ) : (
            <Empty text="No risk run yet." />
          )}
        </Panel>
        <Panel
          title="Recent suspicious transactions"
          subtitle="High and critical, newest first"
        >
          {(recent.data?.length ?? 0) > 0 ? (
            <div className="stagger space-y-2">
              {(recent.data ?? []).slice(0, 6).map((t) => (
                <div
                  key={t.transaction}
                  className="flex flex-wrap items-center gap-2 rounded-xl border border-indigo-400/15 bg-white/[0.04] p-3"
                >
                  <Chip tone={t.category === "critical" ? "red" : "amber"}>
                    {t.category}
                  </Chip>
                  {can("transactions.read") ? (
                    <Link
                      className="font-mono text-sm text-blue-700"
                      to={`/transactions/${t.transaction}`}
                    >
                      {t.external_id}
                    </Link>
                  ) : (
                    <span className="font-mono text-sm">{t.external_id}</span>
                  )}
                  <span className="text-xs text-slate-500">
                    {t.account_ref} · {Number(t.amount).toLocaleString("en-IN")}
                  </span>
                  <span className="ml-auto text-sm font-semibold tabular-nums">
                    {t.score}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <Empty text="Nothing high-risk yet." />
          )}
        </Panel>
      </div>

      {can("analytics.export") && (
        <section
          aria-labelledby="export-title"
          className="rounded-2xl border border-indigo-400/20 bg-white/[0.03] p-4"
        >
          <h2 id="export-title" className="text-base font-semibold">
            Export a report
          </h2>
          <p className="text-xs text-slate-500">
            Uses the dataset and date filters above. Spreadsheet cells that
            start with = + - or @ are neutralised.
          </p>
          <div className="mt-3 flex flex-wrap items-end gap-3 text-sm">
            <label>
              <span className="block font-medium">Report</span>
              <select
                className="mt-1 rounded border border-slate-300 p-1.5"
                value={report}
                onChange={(e) => setReport(e.target.value as typeof report)}
              >
                {REPORTS.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.label}
                  </option>
                ))}
              </select>
            </label>
            <Button onClick={() => exportAs("csv")}>Download CSV</Button>
            <Button variant="secondary" onClick={() => exportAs("pdf")}>
              Download PDF
            </Button>
          </div>
        </section>
      )}
    </section>
  );
}
