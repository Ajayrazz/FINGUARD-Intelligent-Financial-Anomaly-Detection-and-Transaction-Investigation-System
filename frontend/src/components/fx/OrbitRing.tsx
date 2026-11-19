const CARDS: { tag: string; title: string; bars: number[] }[] = [
  {
    tag: "ML · RULES",
    title: "Anomaly detection",
    bars: [30, 55, 40, 85, 35, 60, 25],
  },
  {
    tag: "GRAPH",
    title: "Network analytics",
    bars: [50, 30, 70, 45, 60, 35, 55],
  },
  {
    tag: "XAI",
    title: "Explainable scores",
    bars: [70, 45, 60, 30, 80, 40, 65],
  },
  {
    tag: "WORKFLOW",
    title: "Case management",
    bars: [35, 65, 50, 75, 45, 55, 30],
  },
  { tag: "RISK", title: "Risk scoring", bars: [25, 40, 65, 90, 55, 70, 45] },
  {
    tag: "DATA",
    title: "Duplicate detection",
    bars: [60, 35, 55, 40, 70, 30, 50],
  },
];

/** Decorative 3D ring of product feature cards, slowly orbiting (pauses on hover). Hidden from assistive tech. */
export function OrbitRing() {
  const n = CARDS.length;
  return (
    <div
      className="orbit-scene mx-auto flex h-72 w-full max-w-xl items-center justify-center"
      aria-hidden="true"
    >
      <div className="orbit-ring h-0 w-0">
        {CARDS.map((c, i) => (
          <div
            key={c.title}
            className="orbit-card glass rounded-xl p-3"
            style={{
              transform: `rotateY(${(360 / n) * i}deg) translateZ(17rem)`,
            }}
          >
            <p className="font-mono text-[10px] tracking-widest text-indigo-300">
              {c.tag}
            </p>
            <p className="mt-1 text-sm font-semibold text-slate-800">
              {c.title}
            </p>
            <div className="mt-3 flex h-10 items-end gap-1">
              {c.bars.map((b, k) => (
                <span
                  key={k}
                  className="flex-1 rounded-sm bg-gradient-to-t from-indigo-600 to-violet-400"
                  style={{ height: `${b}%` }}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
