import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { api, type ReadinessResponse } from "../api/client";
import type {
  AlertSummary,
  CaseSummary,
  Dataset,
  GraphFinding,
  GraphSnapshot,
  ModelVersionRow,
  Paginated,
} from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { EChart } from "../components/charts/EChart";
import { StatTile } from "../components/ui/StatTile";
import { usePageTitle } from "../lib/usePageTitle";

const SEVERITIES = ["low", "medium", "high", "critical"] as const;
const AXIS = {
  axisLabel: { color: "#b8bde0" },
  axisLine: { lineStyle: { color: "#3b4180" } },
  splitLine: { lineStyle: { color: "rgba(129,140,248,0.15)" } },
};
const GRID3D_BASE = {
  boxWidth: 110,
  boxDepth: 60,
  environment: "none",
  light: {
    main: { intensity: 1.3, shadow: false },
    ambient: { intensity: 0.5 },
  },
  axisPointer: { show: false },
  viewControl: {
    autoRotate: true,
    autoRotateSpeed: 6,
    distance: 190,
    alpha: 24,
    beta: 28,
    rotateSensitivity: 1,
    zoomSensitivity: 0,
    panSensitivity: 0,
  },
};
const AXIS3D = {
  axisLabel: { textStyle: { color: "#b8bde0" } },
  axisLine: { lineStyle: { color: "#4b5195" } },
  splitLine: { lineStyle: { color: "rgba(129,140,248,0.18)" } },
  axisPointer: { show: false },
};
const titleCase = (s: string) =>
  s.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

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
    <section className="rounded-2xl border border-indigo-400/20 bg-white/[0.03] p-4">
      <h2 className="text-base font-semibold text-slate-800">{title}</h2>
      {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
      <div className="mt-2">{children}</div>
    </section>
  );
}

function Empty({ text }: { text: string }) {
  return (
    <p className="flex h-52 items-center justify-center text-sm text-slate-500">
      {text}
    </p>
  );
}

export default function DashboardPage() {
  usePageTitle("Dashboard");
  const { can } = useAuth();
  const health = useQuery({
    queryKey: ["health-ready"],
    queryFn: ({ signal }) =>
      api.get<ReadinessResponse>("/health/ready/", signal),
  });
  const alerts = useQuery({
    queryKey: ["alert-summary"],
    enabled: can("alerts.read"),
    queryFn: ({ signal }) => api.get<AlertSummary>("/alerts/summary/", signal),
  });
  const cases = useQuery({
    queryKey: ["case-summary"],
    enabled: can("cases.read"),
    queryFn: ({ signal }) => api.get<CaseSummary>("/cases/summary/", signal),
  });
  const datasets = useQuery({
    queryKey: ["datasets"],
    enabled: can("transactions.read"),
    queryFn: ({ signal }) => api.get<Dataset[]>("/datasets/", signal),
  });
  const models = useQuery({
    queryKey: ["model-versions"],
    enabled: can("models.read"),
    queryFn: ({ signal }) =>
      api.get<ModelVersionRow[]>("/model-versions/", signal),
  });
  const snaps = useQuery({
    queryKey: ["graph-snapshots"],
    enabled: can("graph.read"),
    queryFn: ({ signal }) =>
      api.get<Paginated<GraphSnapshot>>("/graph/snapshots/", signal),
  });
  const latest = snaps.data?.results.find((s) => s.status === "succeeded");
  const findings = useQuery({
    queryKey: ["graph-findings", latest?.id, ""],
    enabled: !!latest,
    queryFn: ({ signal }) =>
      api.get<Paginated<GraphFinding>>(
        `/graph/findings/?snapshot=${latest!.id}`,
        signal,
      ),
  });

  const openAlerts = SEVERITIES.reduce(
    (n, s) => n + (alerts.data?.open_by_severity[s] ?? 0),
    0,
  );
  const openCases = SEVERITIES.reduce(
    (n, s) => n + (cases.data?.open_by_priority[s] ?? 0),
    0,
  );

  const pressure = useMemo(() => {
    const data: [string, string, number][] = [];
    SEVERITIES.forEach((s) => {
      data.push([
        titleCase(s),
        "Alerts",
        alerts.data?.open_by_severity[s] ?? 0,
      ]);
      data.push([titleCase(s), "Cases", cases.data?.open_by_priority[s] ?? 0]);
    });
    const max = Math.max(1, ...data.map((d) => d[2]));
    return {
      tooltip: {},
      visualMap: {
        show: false,
        max,
        dimension: 2,
        inRange: { color: ["#4f46e5", "#a78bfa", "#22d3ee", "#f472b6"] },
      },
      xAxis3D: { type: "category", data: SEVERITIES.map(titleCase), ...AXIS3D },
      yAxis3D: { type: "category", data: ["Alerts", "Cases"], ...AXIS3D },
      zAxis3D: { type: "value", ...AXIS3D },
      grid3D: GRID3D_BASE,
      series: [
        {
          type: "bar3D",
          data,
          shading: "lambert",
          bevelSize: 0.25,
          barSize: 14,
          label: { show: false },
        },
      ],
    };
  }, [alerts.data, cases.data]);

  const alertStatus = useMemo(
    () => ({
      tooltip: { trigger: "item" },
      legend: { bottom: 0, textStyle: { color: "#b8bde0" } },
      series: [
        {
          type: "pie",
          radius: ["52%", "76%"],
          center: ["50%", "44%"],
          itemStyle: {
            borderRadius: 10,
            borderColor: "#0d0e1d",
            borderWidth: 3,
          },
          label: { show: false },
          emphasis: { scaleSize: 8 },
          data: Object.entries(alerts.data?.by_status ?? {}).map(([k, v]) => ({
            name: titleCase(k),
            value: v,
          })),
        },
      ],
    }),
    [alerts.data],
  );

  const outcomes = useMemo(
    () => ({
      tooltip: { trigger: "item" },
      legend: { bottom: 0, textStyle: { color: "#b8bde0" } },
      series: [
        {
          type: "pie",
          roseType: "radius",
          radius: ["18%", "72%"],
          center: ["50%", "44%"],
          itemStyle: { borderRadius: 8 },
          label: { show: false },
          data: Object.entries(cases.data?.outcomes ?? {}).map(([k, v]) => ({
            name: titleCase(k),
            value: v,
          })),
        },
      ],
    }),
    [cases.data],
  );

  const caseStatus = useMemo(() => {
    const entries = Object.entries(cases.data?.by_status ?? {});
    const max = Math.max(1, ...entries.map(([, v]) => v ?? 0));
    return {
      tooltip: {},
      radar: {
        indicator: entries.map(([k]) => ({ name: titleCase(k), max })),
        splitArea: { areaStyle: { color: ["transparent"] } },
        axisLine: { lineStyle: { color: "#3b4180" } },
        splitLine: { lineStyle: { color: "#3b4180" } },
        axisName: { color: "#b8bde0" },
      },
      series: [
        {
          type: "radar",
          symbolSize: 6,
          lineStyle: { width: 2, color: "#a78bfa" },
          areaStyle: { color: "rgba(167,139,250,0.3)" },
          data: [{ value: entries.map(([, v]) => v ?? 0), name: "Cases" }],
        },
      ],
    };
  }, [cases.data]);

  const findingTypes = useMemo(
    () => [
      ...new Set((findings.data?.results ?? []).map((f) => f.finding_type)),
    ],
    [findings.data],
  );
  const findings3d = useMemo(
    () => ({
      tooltip: {},
      visualMap: {
        show: false,
        min: 0,
        max: 100,
        dimension: 1,
        inRange: { color: ["#22d3ee", "#a78bfa", "#f472b6"] },
      },
      xAxis3D: {
        type: "category",
        data: findingTypes.map(titleCase),
        ...AXIS3D,
      },
      yAxis3D: { type: "value", name: "Score", min: 0, max: 100, ...AXIS3D },
      zAxis3D: { type: "value", name: "Accounts", ...AXIS3D },
      grid3D: { ...GRID3D_BASE, boxWidth: 120 },
      series: [
        {
          type: "scatter3D",
          symbolSize: 16,
          itemStyle: { opacity: 0.9 },
          data: (findings.data?.results ?? []).map((f) => [
            titleCase(f.finding_type),
            f.score,
            f.account_ids.length,
          ]),
        },
      ],
    }),
    [findings.data, findingTypes],
  );

  const datasetBars = useMemo(() => {
    const rows = [...(datasets.data ?? [])].sort(
      (a, b) => a.row_count - b.row_count,
    );
    return {
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      grid: { left: 8, right: 24, top: 8, bottom: 8, containLabel: true },
      xAxis: { type: "value", ...AXIS },
      yAxis: {
        type: "category",
        data: rows.map((d) => d.name),
        axisLabel: { color: "#b8bde0", width: 130, overflow: "truncate" },
        axisLine: { lineStyle: { color: "#3b4180" } },
      },
      series: [
        {
          type: "bar",
          data: rows.map((d) => d.row_count),
          barWidth: 14,
          itemStyle: {
            borderRadius: [0, 8, 8, 0],
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 1,
              y2: 0,
              colorStops: [
                { offset: 0, color: "#4f46e5" },
                { offset: 1, color: "#22d3ee" },
              ],
            },
          },
        },
      ],
    };
  }, [datasets.data]);

  const checks = Object.entries(health.data?.checks ?? {});
  const hasAny =
    can("alerts.read") ||
    can("cases.read") ||
    can("transactions.read") ||
    can("graph.read") ||
    can("models.read");

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">
            <span className="gradient-text">Dashboard</span>
          </h1>
          <p className="text-sm text-slate-600">
            Welcome back. Live overview of what needs attention.
          </p>
        </div>
        <ul
          className="flex flex-wrap gap-2 text-xs"
          aria-label="System health"
          aria-live="polite"
        >
          {health.isPending && (
            <li className="rounded-full border border-slate-300 px-3 py-1">
              Checking backend…
            </li>
          )}
          {health.isError && (
            <li className="rounded-full border border-red-200 bg-red-100 px-3 py-1 text-red-800">
              Backend unreachable
            </li>
          )}
          {checks.map(([name, status]) => (
            <li
              key={name}
              className={`rounded-full border px-3 py-1 ${status === "ok" ? "border-emerald-400/40 bg-emerald-400/10 text-risk-low" : "border-red-400/40 bg-red-400/10 text-risk-critical"}`}
            >
              {name}: {status}
            </li>
          ))}
        </ul>
      </div>

      {hasAny && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          {can("alerts.read") && (
            <StatTile
              label="Open alerts"
              value={openAlerts}
              hint={`${alerts.data?.unassigned_open ?? 0} unassigned`}
              tone="pink"
            />
          )}
          {can("cases.read") && (
            <StatTile
              label="Open cases"
              value={openCases}
              hint={`${cases.data?.unassigned_open ?? 0} unassigned`}
              tone="violet"
            />
          )}
          {can("transactions.read") && (
            <StatTile
              label="Datasets"
              value={datasets.data?.length ?? 0}
              hint={`${(datasets.data ?? []).reduce((n, d) => n + d.row_count, 0).toLocaleString("en-IN")} transactions`}
              tone="cyan"
            />
          )}
          {can("graph.read") && (
            <StatTile
              label="Graph findings"
              value={findings.data?.count ?? 0}
              hint="latest snapshot"
              tone="amber"
            />
          )}
          {can("models.read") && (
            <StatTile
              label="Model versions"
              value={models.data?.length ?? 0}
              tone="indigo"
            />
          )}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {(can("alerts.read") || can("cases.read")) && (
          <Panel
            title="Risk pressure"
            subtitle="Open alerts and cases by severity · drag to rotate"
          >
            <EChart
              option={pressure}
              height={300}
              label={`3D bar chart of open alerts (${openAlerts}) and open cases (${openCases}) by severity`}
            />
          </Panel>
        )}
        {can("graph.read") && (
          <Panel
            title="Network findings"
            subtitle="Pattern type, risk score and accounts involved · drag to rotate"
          >
            {(findings.data?.results.length ?? 0) > 0 ? (
              <EChart
                option={findings3d}
                height={300}
                label={`3D scatter chart of ${findings.data?.count ?? 0} graph findings by type, score and number of accounts`}
              />
            ) : (
              <Empty text="No graph findings yet. Build a graph from the Relationship Graph page." />
            )}
          </Panel>
        )}
        {can("alerts.read") && (
          <Panel title="Alert pipeline" subtitle="All alerts by status">
            {Object.keys(alerts.data?.by_status ?? {}).length > 0 ? (
              <EChart
                option={alertStatus}
                height={280}
                label="Donut chart of alerts by status"
              />
            ) : (
              <Empty text="No alerts yet." />
            )}
          </Panel>
        )}
        {can("cases.read") && (
          <Panel title="Case workflow" subtitle="Cases by status">
            {Object.keys(cases.data?.by_status ?? {}).length > 0 ? (
              <EChart
                option={caseStatus}
                height={280}
                label="Radar chart of cases by status"
              />
            ) : (
              <Empty text="No cases yet." />
            )}
          </Panel>
        )}
        {can("cases.read") && (
          <Panel
            title="Investigation outcomes"
            subtitle="How closed cases ended"
          >
            {Object.keys(cases.data?.outcomes ?? {}).length > 0 ? (
              <EChart
                option={outcomes}
                height={280}
                label="Rose chart of case outcomes"
              />
            ) : (
              <Empty text="No resolved cases yet." />
            )}
          </Panel>
        )}
        {can("transactions.read") && (
          <Panel title="Data volume" subtitle="Transactions per dataset">
            {(datasets.data?.length ?? 0) > 0 ? (
              <EChart
                option={datasetBars}
                height={Math.max(200, 48 * (datasets.data?.length ?? 1) + 40)}
                label="Bar chart of transaction counts per dataset"
              />
            ) : (
              <Empty text="No datasets imported yet." />
            )}
          </Panel>
        )}
      </div>
    </section>
  );
}
