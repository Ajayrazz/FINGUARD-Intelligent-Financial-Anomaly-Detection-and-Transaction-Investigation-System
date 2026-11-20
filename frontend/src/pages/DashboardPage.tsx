import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import { api, type ReadinessResponse } from "../api/client";
import type {
  AlertRow,
  AlertSummary,
  AuditLogEntry,
  CaseRow,
  CaseSummary,
  Dataset,
  DetectionRun,
  GraphFinding,
  GraphSnapshot,
  ModelVersionRow,
  Paginated,
  RiskRun,
} from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { EChart } from "../components/charts/EChart";
import { PageHero } from "../components/scenes/PageHero";
import { Icon } from "../components/landing/Icon";
import { Tilt } from "../components/fx/Tilt";
import { Card3D, Chip, Ring } from "../components/ui/cards";
import { FlowLine } from "../components/ui/visuals";
import { StatTile } from "../components/ui/StatTile";
import { formatDateTime } from "../lib/format";
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

  const live = { refetchInterval: 20000 } as const;
  const recentAlerts = useQuery({
    queryKey: ["dash-alerts"],
    enabled: can("alerts.read"),
    ...live,
    queryFn: ({ signal }) =>
      api.get<Paginated<AlertRow>>("/alerts/?page=1&open=true", signal),
  });
  const recentCases = useQuery({
    queryKey: ["dash-cases"],
    enabled: can("cases.read"),
    ...live,
    queryFn: ({ signal }) =>
      api.get<Paginated<CaseRow>>("/cases/?page=1", signal),
  });
  const audit = useQuery({
    queryKey: ["dash-audit"],
    enabled: can("audit.read"),
    ...live,
    queryFn: ({ signal }) =>
      api.get<Paginated<AuditLogEntry>>("/audit/logs/?page=1", signal),
  });
  const detRuns = useQuery({
    queryKey: ["dash-detection"],
    enabled: can("detection.read"),
    queryFn: ({ signal }) =>
      api.get<Paginated<DetectionRun>>("/detection/runs/?page=1", signal),
  });
  const riskRuns = useQuery({
    queryKey: ["dash-risk"],
    enabled: can("risk.read"),
    queryFn: ({ signal }) => api.get<Paginated<RiskRun>>("/risk/runs/", signal),
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

  const findingTypes2 = useMemo(() => {
    const m = new Map<string, number>();
    (findings.data?.results ?? []).forEach((f) =>
      m.set(f.finding_type, (m.get(f.finding_type) ?? 0) + 1),
    );
    return {
      tooltip: { trigger: "item" },
      legend: { bottom: 0, textStyle: { color: "#b8bde0" } },
      series: [
        {
          type: "pie",
          radius: ["45%", "72%"],
          center: ["50%", "44%"],
          itemStyle: {
            borderRadius: 8,
            borderColor: "#0d0e1d",
            borderWidth: 3,
          },
          label: { show: false },
          emphasis: { scaleSize: 8 },
          data: [...m.entries()].map(([k, v]) => ({
            name: titleCase(k),
            value: v,
          })),
        },
      ],
    };
  }, [findings.data]);
  const topModels = useMemo(
    () =>
      [...(models.data ?? [])]
        .filter((m) => m.test_metrics)
        .sort((a, b) => b.test_metrics!.pr_auc - a.test_metrics!.pr_auc)
        .slice(0, 4),
    [models.data],
  );
  const latestRisk = (riskRuns.data?.results ?? []).find(
    (r) => r.status === "succeeded",
  );
  const riskDist = useMemo(
    () => ({
      tooltip: { trigger: "item" },
      series: [
        {
          type: "pie",
          roseType: "radius",
          radius: ["15%", "72%"],
          itemStyle: { borderRadius: 8 },
          label: { color: "#b8bde0" },
          data: Object.entries(latestRisk?.category_counts ?? {})
            .filter(([, v]) => v > 0)
            .map(([k, v]) => ({ name: titleCase(k), value: v })),
        },
      ],
    }),
    [latestRisk],
  );
  const flagRates = useMemo(() => {
    const runs = (detRuns.data?.results ?? [])
      .filter((r) => r.rows_scored > 0)
      .slice(0, 6)
      .reverse();
    return {
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      grid: { left: 8, right: 16, top: 8, bottom: 8, containLabel: true },
      xAxis: { type: "value", name: "Flagged %", ...AXIS },
      yAxis: {
        type: "category",
        data: runs.map((r) => `#${r.id} ${r.model_name}`),
        axisLabel: { color: "#b8bde0", width: 140, overflow: "truncate" },
        axisLine: { lineStyle: { color: "#3b4180" } },
      },
      series: [
        {
          type: "bar",
          barWidth: 14,
          data: runs.map((r) =>
            Number(((r.rows_flagged / r.rows_scored) * 100).toFixed(3)),
          ),
          itemStyle: {
            borderRadius: [0, 8, 8, 0],
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 1,
              y2: 0,
              colorStops: [
                { offset: 0, color: "#7c3aed" },
                { offset: 1, color: "#f472b6" },
              ],
            },
          },
        },
      ],
    };
  }, [detRuns.data]);
  const steps = [
    {
      label: "Import",
      icon: "upload",
      to: "/imports",
      perm: "imports.read",
      n: datasets.data?.length,
      unit: "datasets",
      tone: "cyan",
    },
    {
      label: "Detect",
      icon: "anomaly",
      to: "/detection",
      perm: "detection.read",
      n: detRuns.data?.count,
      unit: "runs",
      tone: "violet",
    },
    {
      label: "Explain",
      icon: "explain",
      to: "/models",
      perm: "models.read",
      n: models.data?.length,
      unit: "models",
      tone: "indigo",
    },
    {
      label: "Investigate",
      icon: "cases",
      to: "/cases",
      perm: "cases.read",
      n: openCases,
      unit: "open cases",
      tone: "pink",
    },
    {
      label: "Audit",
      icon: "audit",
      to: "/audit",
      perm: "audit.read",
      n: audit.data?.count,
      unit: "entries",
      tone: "amber",
    },
  ] as const;
  const actions = [
    {
      to: "/imports/new",
      perm: "imports.create",
      icon: "upload",
      title: "Import data",
      text: "Upload CSV or Excel and map columns",
    },
    {
      to: "/detection",
      perm: "detection.run",
      icon: "anomaly",
      title: "Run detection",
      text: "Score a dataset with a trained model",
    },
    {
      to: "/graph",
      perm: "graph.run",
      icon: "graph",
      title: "Build a graph",
      text: "Find cycles, chains and fans",
    },
    {
      to: "/risk",
      perm: "risk.run",
      icon: "risk",
      title: "Score risk",
      text: "Combine signals into one score",
    },
    {
      to: "/duplicates",
      perm: "duplicates.run",
      icon: "duplicates",
      title: "Scan duplicates",
      text: "Repeated payments and invoices",
    },
    {
      to: "/alerts",
      perm: "alerts.read",
      icon: "shield",
      title: "Review alerts",
      text: "Work the prioritised queue",
    },
  ] as const;
  const checks = Object.entries(health.data?.checks ?? {});
  const hasAny =
    can("alerts.read") ||
    can("cases.read") ||
    can("transactions.read") ||
    can("graph.read") ||
    can("models.read");

  return (
    <section className="space-y-6">
      <PageHero eyebrow="Overview" title="Dashboard" tone="indigo" scene="gyro">
        <p className="mt-2 text-sm text-slate-600">
          Welcome back. Live overview of what needs attention.
        </p>
        <div className="mt-4">
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
      </PageHero>

      <ol
        aria-label="Investigation pipeline"
        className="stagger flex flex-col items-stretch gap-3 md:flex-row md:items-center"
      >
        {steps.map((st, i) => (
          <li key={st.label} className="flex flex-1 items-center gap-3">
            <Tilt className="flex-1">
              <Link
                to={can(st.perm) ? st.to : "/dashboard"}
                aria-disabled={!can(st.perm)}
                className="glass block rounded-2xl p-3 text-center no-underline hover:border-indigo-300"
              >
                <span className="animate-glow mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-indigo-500/20 text-indigo-200">
                  <Icon name={st.icon} />
                </span>
                <span className="mt-2 block text-sm font-semibold">
                  {st.label}
                </span>
                <span className="block text-xs text-slate-500">
                  {can(st.perm) && st.n !== undefined
                    ? `${st.n.toLocaleString("en-IN")} ${st.unit}`
                    : " "}
                </span>
              </Link>
            </Tilt>
            {i < steps.length - 1 && (
              <span className="hidden w-10 md:block">
                <FlowLine />
              </span>
            )}
          </li>
        ))}
      </ol>

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

      {actions.some((a) => can(a.perm)) && (
        <section aria-labelledby="quick-title">
          <h2 id="quick-title" className="mb-2 text-base font-semibold">
            Quick actions
          </h2>
          <div className="stagger grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {actions
              .filter((a) => can(a.perm))
              .map((a) => (
                <Tilt key={a.to + a.title}>
                  <Link
                    to={a.to}
                    className="glass group flex items-center gap-3 rounded-2xl p-4 no-underline hover:border-indigo-300"
                  >
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-violet-500/20 text-violet-200 transition group-hover:scale-110 group-hover:bg-violet-500/35">
                      <Icon name={a.icon} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-semibold">
                        {a.title}
                      </span>
                      <span className="block text-xs text-slate-500">
                        {a.text}
                      </span>
                    </span>
                    <span
                      aria-hidden="true"
                      className="text-indigo-300 transition group-hover:translate-x-1"
                    >
                      →
                    </span>
                  </Link>
                </Tilt>
              ))}
          </div>
        </section>
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

      <div className="grid gap-4 lg:grid-cols-2">
        {can("graph.read") && (findings.data?.results.length ?? 0) > 0 && (
          <Panel title="Pattern mix" subtitle="Graph findings by pattern type">
            <EChart
              option={findingTypes2}
              height={260}
              label="Donut chart of graph findings by pattern type"
            />
          </Panel>
        )}
        {can("risk.read") && latestRisk && (
          <Panel
            title="Risk categories"
            subtitle={`Latest risk run · ${latestRisk.dataset_name}`}
          >
            <EChart
              option={riskDist}
              height={260}
              label="Rose chart of scored transactions by risk category in the latest risk run"
            />
          </Panel>
        )}
        {can("detection.read") && (detRuns.data?.results.length ?? 0) > 0 && (
          <Panel
            title="Detection flag rates"
            subtitle="Share of transactions flagged, latest runs"
          >
            <EChart
              option={flagRates}
              height={260}
              label="Bar chart of the flag rate of the latest detection runs"
            />
          </Panel>
        )}
        {can("models.read") && topModels.length > 0 && (
          <Panel
            title="Top models"
            subtitle="Best test PR-AUC (offline, held-out data)"
          >
            <div className="stagger grid gap-3 sm:grid-cols-2">
              {topModels.map((m) => (
                <Card3D key={m.id} tone="green">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="break-all text-sm font-semibold">
                        {m.model_name}
                      </p>
                      <p className="text-xs text-slate-500">
                        {m.algorithm} · {m.dataset}
                      </p>
                    </div>
                    <Ring
                      value={m.test_metrics!.pr_auc}
                      label="PR-AUC"
                      size={64}
                      tone="green"
                    />
                  </div>
                </Card3D>
              ))}
            </div>
          </Panel>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {can("alerts.read") && (
          <section
            className="rounded-2xl border border-indigo-400/20 bg-white/[0.03] p-4"
            aria-labelledby="live-alerts"
          >
            <div className="flex items-center justify-between">
              <h2
                id="live-alerts"
                className="flex items-center gap-2 text-base font-semibold"
              >
                <span
                  aria-hidden="true"
                  className="relative inline-flex h-2.5 w-2.5"
                >
                  <span
                    className="absolute inset-0 rounded-full bg-pink-400"
                    style={{ animation: "ping-ring 1.8s ease-out infinite" }}
                  />
                  <span className="relative h-2.5 w-2.5 rounded-full bg-pink-400" />
                </span>
                Latest open alerts
              </h2>
              <Link to="/alerts" className="text-sm text-blue-700">
                View all
              </Link>
            </div>
            <div className="stagger mt-3 space-y-2">
              {(recentAlerts.data?.results ?? []).slice(0, 5).map((a) => (
                <Link
                  key={a.id}
                  to={`/alerts?open=${a.id}`}
                  className="block rounded-xl border border-indigo-400/15 bg-white/[0.04] p-3 no-underline transition hover:translate-x-1 hover:border-indigo-300"
                >
                  <span className="flex flex-wrap items-center gap-2">
                    <Chip
                      tone={
                        a.severity === "critical"
                          ? "red"
                          : a.severity === "high"
                            ? "amber"
                            : a.severity === "medium"
                              ? "violet"
                              : "cyan"
                      }
                    >
                      {a.severity}
                    </Chip>
                    <span className="text-sm font-medium">{a.type_label}</span>
                    <span className="ml-auto text-xs text-slate-500">
                      {formatDateTime(a.created_at)}
                    </span>
                  </span>
                  <span className="mt-1 block text-xs text-slate-600">
                    {a.reason}
                  </span>
                </Link>
              ))}
              {recentAlerts.data && recentAlerts.data.results.length === 0 && (
                <Empty text="No open alerts." />
              )}
            </div>
          </section>
        )}
        {can("audit.read") ? (
          <section
            className="rounded-2xl border border-indigo-400/20 bg-white/[0.03] p-4"
            aria-labelledby="live-audit"
          >
            <h2 id="live-audit" className="text-base font-semibold">
              Recent activity
            </h2>
            <ol className="stagger relative mt-3 space-y-3 border-l border-indigo-400/30 pl-5">
              {(audit.data?.results ?? []).slice(0, 7).map((e) => (
                <li key={e.id} className="relative">
                  <span
                    aria-hidden="true"
                    className="absolute -left-[1.6rem] top-1.5 h-2.5 w-2.5 rounded-full bg-indigo-400 shadow-[0_0_8px_#818cf8]"
                  />
                  <p className="font-mono text-sm">{e.action}</p>
                  <p className="text-xs text-slate-500">
                    {e.actor_email || "system"} · {formatDateTime(e.created_at)}
                  </p>
                </li>
              ))}
            </ol>
          </section>
        ) : (
          can("cases.read") && (
            <section
              className="rounded-2xl border border-indigo-400/20 bg-white/[0.03] p-4"
              aria-labelledby="live-cases"
            >
              <h2 id="live-cases" className="text-base font-semibold">
                Recent investigations
              </h2>
              <div className="stagger mt-3 space-y-2">
                {(recentCases.data?.results ?? []).slice(0, 5).map((c) => (
                  <Link
                    key={c.id}
                    to={`/cases/${c.id}`}
                    className="block rounded-xl border border-indigo-400/15 bg-white/[0.04] p-3 no-underline hover:border-indigo-300"
                  >
                    <span className="font-mono text-sm">{c.case_ref}</span>
                    <span className="ml-2 text-sm">{c.title}</span>
                  </Link>
                ))}
              </div>
            </section>
          )
        )}
      </div>
    </section>
  );
}
