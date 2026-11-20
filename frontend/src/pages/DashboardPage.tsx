import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import { api, type ReadinessResponse } from "../api/client";
import type {
  AlertRow,
  AlertSummary,
  AnalyticsOverview,
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
import { pie3dOption } from "../components/charts/pie3d";
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
    <Tilt max={3} className="h-full">
      <section className="h-full rounded-2xl border border-indigo-400/20 bg-gradient-to-br from-indigo-500/[0.07] via-white/[0.02] to-transparent p-4 shadow-lg shadow-black/30">
        <h2 className="text-base font-semibold text-slate-800">{title}</h2>
        {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
        <div className="mt-2">{children}</div>
      </section>
    </Tilt>
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

  const analytics = useQuery({
    queryKey: ["analytics", "overview", ""],
    enabled: can("analytics.read"),
    queryFn: ({ signal }) =>
      api.get<AnalyticsOverview>("/analytics/overview/?", signal),
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

  const alertStatus = useMemo(() => {
    const color: Record<string, string> = {
      new: "#f472b6",
      acknowledged: "#22d3ee",
      escalated: "#fbbf24",
      closed: "#34d399",
    };
    return pie3dOption(
      Object.entries(alerts.data?.by_status ?? {}).map(([k, v]) => ({
        name: `${titleCase(k)}: ${v}`,
        value: v ?? 0,
        color: color[k] ?? "#818cf8",
      })),
    );
  }, [alerts.data]);

  const outcomes = useMemo(() => {
    const entries = Object.entries(cases.data?.outcomes ?? {});
    const color: Record<string, string> = {
      confirmed_suspicious: "#f43f5e",
      false_positive: "#34d399",
      inconclusive: "#fbbf24",
      referred: "#22d3ee",
    };
    return {
      tooltip: { trigger: "item" },
      polar: { radius: ["18%", "78%"], center: ["50%", "52%"] },
      angleAxis: {
        type: "category",
        data: entries.map(([k]) => titleCase(k)),
        axisLabel: { color: "#b8bde0" },
        axisLine: { lineStyle: { color: "#3b4180" } },
      },
      radiusAxis: { show: false },
      series: [
        {
          type: "bar",
          coordinateSystem: "polar",
          roundCap: true,
          barWidth: 26,
          data: entries.map(([k, v]) => ({
            value: v ?? 0,
            itemStyle: {
              color: color[k] ?? "#a78bfa",
              shadowBlur: 18,
              shadowColor: color[k] ?? "#a78bfa",
            },
          })),
          animationDelay: (i: number) => i * 140,
        },
      ],
      animationEasing: "elasticOut",
    };
  }, [cases.data]);

  const caseStatus = useMemo(() => {
    const order = [
      "new",
      "under_review",
      "investigation",
      "escalated",
      "resolved",
      "closed",
    ];
    const by = cases.data?.by_status ?? {};
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
          left: "10%",
          width: "80%",
          top: 10,
          bottom: 10,
          gap: 4,
          minSize: "18%",
          label: { color: "#fff", fontWeight: 600, formatter: "{b}: {c}" },
          itemStyle: {
            borderWidth: 0,
            shadowBlur: 20,
            shadowColor: "rgba(124,58,237,0.5)",
          },
          emphasis: { itemStyle: { shadowBlur: 40 } },
          data: order
            .filter((k) => (by as Record<string, number>)[k] !== undefined)
            .map((k) => ({
              name: titleCase(k),
              value: Math.max(1, (by as Record<string, number>)[k] ?? 0),
              itemStyle: { color: colors[order.indexOf(k)] },
            })),
          animationDelay: (i: number) => i * 120,
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
          type: "pictorialBar",
          symbol: "roundRect",
          symbolRepeat: true,
          symbolSize: [9, 16],
          symbolMargin: 3,
          data: rows.map((d) => d.row_count),
          itemStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 1,
              y2: 0,
              colorStops: [
                { offset: 0, color: "#22d3ee" },
                { offset: 1, color: "#6366f1" },
              ],
            },
            shadowBlur: 8,
            shadowColor: "rgba(34,211,238,0.6)",
          },
          animationDelay: (i: number) => i * 160,
        },
      ],
    };
  }, [datasets.data]);

  const findingTypes2 = useMemo(() => {
    const sum = new Map<string, { n: number; total: number }>();
    (findings.data?.results ?? []).forEach((f) => {
      const c = sum.get(f.finding_type) ?? { n: 0, total: 0 };
      sum.set(f.finding_type, { n: c.n + 1, total: c.total + f.score });
    });
    const types = [...sum.keys()];
    return {
      tooltip: {},
      radar: {
        radius: "62%",
        indicator: types.map((t) => ({ name: titleCase(t), max: 100 })),
        splitArea: {
          areaStyle: {
            color: ["rgba(52,211,153,0.04)", "rgba(52,211,153,0.10)"],
          },
        },
        axisLine: { lineStyle: { color: "#3b4180" } },
        splitLine: { lineStyle: { color: "#3b4180" } },
        axisName: { color: "#b8bde0" },
      },
      series: [
        {
          type: "radar",
          symbolSize: 9,
          lineStyle: {
            width: 3,
            color: "#34d399",
            shadowBlur: 14,
            shadowColor: "#34d399",
          },
          areaStyle: { color: "rgba(52,211,153,0.35)" },
          itemStyle: { color: "#a7f3d0" },
          data: [
            {
              name: "Average score",
              value: types.map((t) =>
                Number((sum.get(t)!.total / sum.get(t)!.n).toFixed(1)),
              ),
            },
          ],
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
  const riskDist = useMemo(() => {
    const color: Record<string, string> = {
      low: "#10b981",
      medium: "#f59e0b",
      high: "#f97316",
      critical: "#ef4444",
      unscored: "#64748b",
    };
    return {
      tooltip: { formatter: "{b}: {c}" },
      series: [
        {
          type: "treemap",
          roam: false,
          nodeClick: false,
          breadcrumb: { show: false },
          width: "100%",
          height: "100%",
          label: {
            show: true,
            formatter: "{b}\n{c}",
            color: "#fff",
            fontWeight: 600,
            fontSize: 14,
          },
          itemStyle: {
            borderColor: "#0d0e1d",
            borderWidth: 3,
            gapWidth: 3,
            borderRadius: 10,
            shadowBlur: 16,
            shadowColor: "rgba(0,0,0,0.5)",
          },
          data: Object.entries(latestRisk?.category_counts ?? {})
            .filter(([, v]) => v > 0)
            .map(([k, v]) => ({
              name: titleCase(k),
              value: v,
              itemStyle: { color: color[k] ?? "#818cf8" },
            })),
        },
      ],
    };
  }, [latestRisk]);
  const flagRates = useMemo(() => {
    const runs = (detRuns.data?.results ?? [])
      .filter((r) => r.rows_scored > 0)
      .slice(0, 8)
      .reverse();
    return {
      tooltip: { trigger: "axis" },
      grid: { left: 8, right: 20, top: 30, bottom: 8, containLabel: true },
      xAxis: {
        type: "category",
        data: runs.map((r) => `#${r.id}`),
        boundaryGap: false,
        axisLabel: { color: "#b8bde0" },
        axisLine: { lineStyle: { color: "#3b4180" } },
      },
      yAxis: {
        type: "value",
        name: "Flagged %",
        nameTextStyle: { color: "#b8bde0" },
        ...AXIS,
      },
      series: [
        {
          type: "line",
          smooth: 0.45,
          symbol: "circle",
          symbolSize: 12,
          data: runs.map((r) =>
            Number(((r.rows_flagged / r.rows_scored) * 100).toFixed(3)),
          ),
          lineStyle: {
            width: 5,
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
            shadowBlur: 16,
            shadowColor: "rgba(244,114,182,0.7)",
            shadowOffsetY: 8,
          },
          itemStyle: { color: "#fff", borderColor: "#f472b6", borderWidth: 3 },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(167,139,250,0.55)" },
                { offset: 1, color: "rgba(167,139,250,0)" },
              ],
            },
          },
          markPoint: {
            symbol: "pin",
            symbolSize: 46,
            itemStyle: { color: "#f472b6" },
            label: { color: "#fff", fontSize: 10 },
            data: [{ type: "max", name: "Highest" }],
          },
          animationDuration: 1800,
          animationEasing: "cubicOut",
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

      {can("analytics.read") && (
        <section aria-labelledby="analytics-glance">
          <div className="mb-2 flex items-center justify-between">
            <h2 id="analytics-glance" className="text-base font-semibold">
              Analytics at a glance
            </h2>
            <Link to="/analytics" className="text-sm text-blue-700">
              Open analytics →
            </Link>
          </div>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile label="Transactions" value={analytics.data?.transactions ?? 0} tone="indigo" />
            <StatTile label="Flagged" value={analytics.data?.flagged ?? 0} tone="pink" hint="latest detection run" />
            <StatTile label="High risk" value={analytics.data?.high_risk_transactions ?? 0} tone="amber" hint="high + critical" />
            <StatTile label="Open cases" value={analytics.data?.open_cases ?? 0} tone="violet" />
          </div>
        </section>
      )}

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
              <>
                <EChart
                  option={alertStatus}
                  height={280}
                  label="Rotating 3D pie chart of alerts by status"
                />
                <ul
                  className="mt-1 flex flex-wrap justify-center gap-2 text-xs"
                  aria-label="Alerts by status"
                >
                  {Object.entries(alerts.data?.by_status ?? {}).map(
                    ([k, v]) => (
                      <li
                        key={k}
                        className="rounded-full border border-indigo-400/25 bg-white/5 px-3 py-1"
                      >
                        {titleCase(k)}: <strong>{v}</strong>
                      </li>
                    ),
                  )}
                </ul>
              </>
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
                label="Funnel chart of cases by workflow status"
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
                label="Polar bar chart of case outcomes"
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
                label="Pictorial bar chart of transaction counts per dataset"
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
              label="Radar chart of the average score of graph findings per pattern type"
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
              label="Treemap of scored transactions by risk category in the latest risk run"
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
              label="Area line chart of the flag rate of the latest detection runs"
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
