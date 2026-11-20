import type { ReactNode } from "react";
import {
  BarsScene,
  BeaconScene,
  CubeScene,
  FlowScene,
  GaugeScene,
  GraphMiniScene,
  GyroScene,
  LayersScene,
  LedgerScene,
  MergeScene,
  PeopleScene,
  RadarScene,
  TrendScene,
} from "./Scenes";

const SCENES = {
  flow: FlowScene,
  layers: LayersScene,
  radar: RadarScene,
  graph: GraphMiniScene,
  merge: MergeScene,
  gauge: GaugeScene,
  beacon: BeaconScene,
  cube: CubeScene,
  bars: BarsScene,
  people: PeopleScene,
  gyro: GyroScene,
  trend: TrendScene,
  ledger: LedgerScene,
} as const;

const TONES = {
  indigo: {
    text: "linear-gradient(90deg,#c7d2fe,#818cf8)",
    bg: "from-indigo-500/25",
    eyebrow: "text-indigo-300",
  },
  cyan: {
    text: "linear-gradient(90deg,#a5f3fc,#22d3ee)",
    bg: "from-cyan-400/20",
    eyebrow: "text-cyan-300",
  },
  violet: {
    text: "linear-gradient(90deg,#ddd6fe,#a78bfa)",
    bg: "from-violet-500/25",
    eyebrow: "text-violet-300",
  },
  pink: {
    text: "linear-gradient(90deg,#fbcfe8,#f472b6)",
    bg: "from-pink-500/20",
    eyebrow: "text-pink-300",
  },
  amber: {
    text: "linear-gradient(90deg,#fde68a,#fbbf24)",
    bg: "from-amber-400/20",
    eyebrow: "text-amber-300",
  },
  green: {
    text: "linear-gradient(90deg,#bbf7d0,#34d399)",
    bg: "from-emerald-400/20",
    eyebrow: "text-emerald-300",
  },
  red: {
    text: "linear-gradient(90deg,#fecaca,#f87171)",
    bg: "from-red-500/25",
    eyebrow: "text-red-300",
  },
} as const;

export type SceneName = keyof typeof SCENES;
export type HeroTone = keyof typeof TONES;

/** Full-width page header: eyebrow, gradient title (the page's h1) and a distinct animated 3D scene. */
export function PageHero({
  eyebrow,
  title,
  tone,
  scene,
  children,
}: {
  eyebrow: string;
  title: string;
  tone: HeroTone;
  scene: SceneName;
  children?: ReactNode;
}) {
  const t = TONES[tone];
  const Scene = SCENES[scene];
  return (
    <header
      className={`relative mb-6 grid items-center gap-4 overflow-hidden rounded-2xl border border-indigo-400/20 bg-gradient-to-br ${t.bg} via-transparent to-transparent p-6 md:grid-cols-[1.3fr_1fr] md:p-8`}
    >
      <div className="relative z-10">
        <p
          className={`font-mono text-xs tracking-[0.25em] uppercase ${t.eyebrow}`}
        >
          {eyebrow}
        </p>
        <h1
          className="mt-2 text-3xl font-semibold md:text-4xl"
          style={{
            backgroundImage: t.text,
            WebkitBackgroundClip: "text",
            backgroundClip: "text",
            color: "transparent",
          }}
        >
          {title}
        </h1>
        {children}
      </div>
      <div aria-hidden="true" className="relative hidden h-44 md:block">
        <Scene />
      </div>
    </header>
  );
}
