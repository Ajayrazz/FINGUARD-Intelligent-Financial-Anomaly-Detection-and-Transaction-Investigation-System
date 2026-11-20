import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { EChart } from "../components/charts/EChart";
import { Logo } from "../components/fx/Logo";
import { NetworkBackground } from "../components/fx/NetworkBackground";
import { OrbitRing } from "../components/fx/OrbitRing";
import { Tilt } from "../components/fx/Tilt";
import { Icon } from "../components/landing/Icon";
import { LandingFooter } from "../components/landing/LandingFooter";
import { NetworkScene } from "../components/landing/NetworkScene";
import { usePageTitle } from "../lib/usePageTitle";

const FEATURES = [
  {
    icon: "anomaly",
    title: "Anomaly detection",
    text: "Rules plus machine-learning models flag unusual transactions, with latency and quality measured per model.",
  },
  {
    icon: "graph",
    title: "Network analytics",
    text: "See who paid whom. Cycles, rapid pass-through chains, fan-in/out and shared beneficiaries surface as findings.",
  },
  {
    icon: "explain",
    title: "Explainable scores",
    text: "Every flag shows which factors pushed it up or down, so an analyst can judge it instead of trusting a number.",
  },
  {
    icon: "risk",
    title: "Risk scoring",
    text: "Model, behaviour, graph and rule signals combine into one transparent, configurable risk score.",
  },
  {
    icon: "cases",
    title: "Case management",
    text: "Turn alerts into investigations with notes, evidence, timelines and a PDF report. Closed cases are read-only.",
  },
  {
    icon: "duplicates",
    title: "Duplicate detection",
    text: "Find repeated transactions and near-identical invoices before they are paid twice.",
  },
] as const;

const STEPS = [
  {
    n: "01",
    title: "Import",
    text: "Upload CSV or Excel with a guided column mapping. Large files run in the background.",
  },
  {
    n: "02",
    title: "Detect",
    text: "Models, behaviour baselines and graph patterns score every transaction.",
  },
  {
    n: "03",
    title: "Explain",
    text: "Each score comes with the reasons behind it.",
  },
  {
    n: "04",
    title: "Investigate",
    text: "Alerts become cases with evidence and a full timeline.",
  },
  {
    n: "05",
    title: "Audit",
    text: "Every action is written to an append-only audit log.",
  },
] as const;

const ROLES = [
  {
    name: "Financial Analyst",
    text: "Imports data, runs detection and reviews risk.",
  },
  {
    name: "Fraud Investigator",
    text: "Works alerts into cases and records outcomes.",
  },
  {
    name: "Auditor",
    text: "Read-only access across the platform, plus audit logs.",
  },
  { name: "Management", text: "Sees the overview dashboard." },
  { name: "Super Admin", text: "Manages users and roles." },
] as const;

const RIBBON = [
  "ANOMALY DETECTION",
  "GRAPH ANALYTICS",
  "EXPLAINABLE AI",
  "RISK SCORING",
  "CASE MANAGEMENT",
  "DUPLICATE DETECTION",
  "AUDIT TRAIL",
];

function Eyebrow({ children }: { children: string }) {
  return (
    <p className="font-mono text-xs tracking-[0.25em] text-indigo-300">
      {children}
    </p>
  );
}

export default function LandingPage() {
  usePageTitle("Financial anomaly detection & investigation");
  const { status } = useAuth();
  const signedIn = status === "authenticated";
  const cta = signedIn ? "/dashboard" : "/login";

  const demo = useMemo(() => {
    const cats = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    const rows = ["Cycles", "Chains", "Fans"];
    const vals = [
      [2, 3, 1, 4, 2, 6, 3],
      [1, 2, 4, 2, 5, 3, 7],
      [3, 1, 2, 6, 4, 8, 5],
    ];
    const data: [string, string, number][] = [];
    rows.forEach((r, ri) =>
      cats.forEach((c, ci) => data.push([c, r, vals[ri]![ci]!])),
    );
    const axis = {
      axisLabel: { textStyle: { color: "#b8bde0" } },
      axisLine: { lineStyle: { color: "#4b5195" } },
      splitLine: { lineStyle: { color: "rgba(129,140,248,0.18)" } },
      axisPointer: { show: false },
    };
    return {
      tooltip: {},
      visualMap: {
        show: false,
        max: 8,
        dimension: 2,
        inRange: { color: ["#4f46e5", "#a78bfa", "#22d3ee", "#f472b6"] },
      },
      xAxis3D: { type: "category", data: cats, ...axis },
      yAxis3D: { type: "category", data: rows, ...axis },
      zAxis3D: { type: "value", ...axis },
      grid3D: {
        boxWidth: 130,
        boxDepth: 50,
        environment: "none",
        light: { main: { intensity: 1.3 }, ambient: { intensity: 0.5 } },
        viewControl: {
          autoRotate: true,
          autoRotateSpeed: 6,
          distance: 200,
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
  }, []);

  return (
    <div className="relative min-h-screen overflow-x-clip font-sans text-slate-800">
      <a href="#content" className="skip-link">
        Skip to content
      </a>
      <NetworkBackground />

      <header className="sticky top-3 z-30 mx-auto w-[min(72rem,calc(100%-1.5rem))]">
        <nav
          aria-label="Primary"
          className="glass flex items-center justify-between gap-3 rounded-full px-4 py-2"
        >
          <Link
            to="/"
            className="flex items-center gap-2 font-semibold tracking-wide"
          >
            <Logo size={26} />
            <span className="gradient-text">FinGuard</span>
          </Link>
          <ul className="hidden items-center gap-6 text-sm text-slate-700 md:flex">
            <li>
              <a className="hover:text-white" href="#features">
                Features
              </a>
            </li>
            <li>
              <a className="hover:text-white" href="#flow">
                How it works
              </a>
            </li>
            <li>
              <a className="hover:text-white" href="#insights">
                Insights
              </a>
            </li>
            <li>
              <a className="hover:text-white" href="#roles">
                Roles
              </a>
            </li>
          </ul>
          <div className="flex items-center gap-2">
            {!signedIn && (
              <Link
                to="/register"
                className="hidden rounded-full px-3 py-1.5 text-sm text-slate-800 hover:bg-white/10 sm:inline"
              >
                Create account
              </Link>
            )}
            <Link
              to={cta}
              className="btn-glow rounded-full px-4 py-1.5 text-sm font-medium text-white"
            >
              {signedIn ? "Open dashboard" : "Sign in"}
            </Link>
          </div>
        </nav>
      </header>

      <main id="content" tabIndex={-1} className="relative z-10 outline-none">
        {/* Hero */}
        <section className="mx-auto grid max-w-6xl items-center gap-6 px-4 pb-10 pt-14 lg:grid-cols-2">
          <div className="animate-rise">
            <Eyebrow>FINANCIAL ANOMALY DETECTION & INVESTIGATION</Eyebrow>
            <h1 className="mt-4 text-4xl font-semibold leading-tight md:text-6xl">
              Spot anomalies.
              <br />
              <span className="gradient-text">Trace networks.</span>
              <br />
              Explain every flag.
            </h1>
            <p className="mt-5 max-w-lg text-lg text-slate-600">
              FinGuard combines machine learning, graph analytics and
              explainable AI so investigators can find suspicious money movement
              and prove why.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                to={cta}
                className="btn-glow rounded-full px-6 py-3 font-medium text-white"
              >
                {signedIn ? "Open dashboard" : "Open the platform"} →
              </Link>
              {!signedIn && (
                <Link
                  to="/register"
                  className="rounded-full border border-indigo-300/50 px-6 py-3 font-medium text-slate-800 hover:bg-white/10"
                >
                  Create account
                </Link>
              )}
              <a
                href="#flow"
                className="rounded-full border border-slate-300 px-6 py-3 font-medium text-slate-800 hover:bg-white/10"
              >
                See how it works
              </a>
            </div>
          </div>
          <div className="relative">
            <NetworkScene height={460} />
            <p className="text-center text-xs text-slate-500">
              Illustrative sample network · a laundering loop highlighted in
              pink
            </p>
          </div>
        </section>

        {/* Ribbon */}
        <div
          className="overflow-hidden border-y border-indigo-400/15 py-4"
          aria-hidden="true"
        >
          <div className="flex w-max animate-[ribbon_40s_linear_infinite] gap-10 font-mono text-xs tracking-[0.25em] text-slate-500">
            {[...RIBBON, ...RIBBON, ...RIBBON].map((w, i) => (
              <span key={i} className="flex items-center gap-10">
                {w} <span className="text-indigo-400">•</span>
              </span>
            ))}
          </div>
        </div>

        {/* Features */}
        <section id="features" className="mx-auto max-w-6xl px-4 py-20">
          <Eyebrow>WHAT IT DOES</Eyebrow>
          <h2 className="mt-3 text-3xl font-semibold md:text-4xl">
            Everything an investigation needs, in one place.
          </h2>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <Tilt key={f.title}>
                <article className="glass h-full rounded-2xl p-5">
                  <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-indigo-500/20 text-indigo-300">
                    <Icon name={f.icon} />
                  </span>
                  <h3 className="mt-4 text-lg font-semibold">{f.title}</h3>
                  <p className="mt-2 text-sm text-slate-600">{f.text}</p>
                </article>
              </Tilt>
            ))}
          </div>
        </section>

        {/* Orbit */}
        <section className="mx-auto max-w-6xl px-4 pb-10 text-center">
          <Eyebrow>MODULES IN ORBIT</Eyebrow>
          <h2 className="mt-3 text-3xl font-semibold md:text-4xl">
            One platform. Every module connected.
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-slate-600">
            Hover to pause the ring.
          </p>
          <div className="mt-10">
            <OrbitRing />
          </div>
        </section>

        {/* Flow */}
        <section id="flow" className="mx-auto max-w-6xl px-4 py-20">
          <Eyebrow>HOW IT WORKS</Eyebrow>
          <h2 className="mt-3 text-3xl font-semibold md:text-4xl">
            From raw file to closed case.
          </h2>
          <ol className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {STEPS.map((s) => (
              <li key={s.n}>
                <Tilt>
                  <div className="glass relative h-full overflow-hidden rounded-2xl p-5">
                    <span className="absolute -right-1 -top-3 text-6xl font-bold text-white/5">
                      {s.n}
                    </span>
                    <p className="font-mono text-xs text-indigo-300">
                      Step {s.n}
                    </p>
                    <h3 className="mt-6 text-lg font-semibold">{s.title}</h3>
                    <p className="mt-2 text-sm text-slate-600">{s.text}</p>
                    <span className="mt-4 block h-1 w-10 rounded bg-indigo-500" />
                  </div>
                </Tilt>
              </li>
            ))}
          </ol>
        </section>

        {/* Insights */}
        <section
          id="insights"
          className="mx-auto grid max-w-6xl items-center gap-8 px-4 py-10 lg:grid-cols-2"
        >
          <div>
            <Eyebrow>INSIGHTS</Eyebrow>
            <h2 className="mt-3 text-3xl font-semibold md:text-4xl">
              See risk in three dimensions.
            </h2>
            <p className="mt-4 max-w-md text-slate-600">
              Dashboards use interactive 3D bars, scatter plots, radars and
              donuts instead of long lists, so the shape of the problem is
              visible at a glance. Drag any 3D chart to rotate it.
            </p>
            <Link
              to={cta}
              className="btn-glow mt-6 inline-block rounded-full px-6 py-3 font-medium text-white"
            >
              {signedIn ? "Open dashboard" : "Sign in to explore"} →
            </Link>
          </div>
          <div className="glass rounded-2xl p-3">
            <EChart
              option={demo}
              height={340}
              label="Illustrative 3D bar chart of weekly graph findings by pattern type"
            />
            <p className="text-center text-xs text-slate-500">
              Illustrative sample data
            </p>
          </div>
        </section>

        {/* Roles */}
        <section id="roles" className="mx-auto max-w-6xl px-4 py-20">
          <Eyebrow>BUILT FOR TEAMS</Eyebrow>
          <h2 className="mt-3 text-3xl font-semibold md:text-4xl">
            The right access for every role.
          </h2>
          <p className="mt-3 max-w-xl text-slate-600">
            Every permission is enforced on the server, not just hidden in the
            interface.
          </p>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {ROLES.map((r) => (
              <Tilt key={r.name}>
                <div className="glass h-full rounded-2xl p-5">
                  <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-violet-500/20 text-violet-300">
                    <Icon name="shield" size={20} />
                  </span>
                  <h3 className="mt-3 font-semibold">{r.name}</h3>
                  <p className="mt-1 text-sm text-slate-600">{r.text}</p>
                </div>
              </Tilt>
            ))}
          </div>
        </section>

        {/* CTA */}
        <section className="mx-auto max-w-6xl px-4 pb-20">
          <div className="glass animate-glow rounded-3xl p-10 text-center">
            <h2 className="text-3xl font-semibold md:text-4xl">
              Ready to investigate?
            </h2>
            <p className="mx-auto mt-3 max-w-lg text-slate-600">
              Sign in to open the platform. Accounts are created by an
              administrator.
            </p>
            <Link
              to={cta}
              className="btn-glow mt-6 inline-block rounded-full px-8 py-3 font-medium text-white"
            >
              {signedIn ? "Open dashboard" : "Sign in"} →
            </Link>
          </div>
        </section>
      </main>

      <LandingFooter signedIn={signedIn} />
    </div>
  );
}
