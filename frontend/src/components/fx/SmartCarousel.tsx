import { useEffect, useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";

export type SlideKind =
  "bars" | "kanban" | "pulse" | "network" | "gauge" | "line";
export interface Slide {
  id: string;
  tag: string;
  title: string;
  text: string;
  metric: number | string;
  metricLabel: string;
  to: string;
  kind: SlideKind;
}

const ACCENT: Record<SlideKind, string> = {
  bars: "#f472b6",
  kanban: "#a78bfa",
  pulse: "#22d3ee",
  network: "#34d399",
  gauge: "#fbbf24",
  line: "#818cf8",
};

/** Decorative mini screen drawn in CSS/SVG; the same facts are always available as text on the card. */
function Mock({ kind }: { kind: SlideKind }) {
  const c = ACCENT[kind];
  return (
    <div
      aria-hidden="true"
      className="relative h-40 overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-b from-slate-900/80 to-slate-950/90 p-3"
    >
      <div className="mb-2 flex gap-1.5">
        {[0, 1, 2].map((i) => (
          <span key={i} className="h-1.5 w-1.5 rounded-full bg-white/25" />
        ))}
      </div>
      {kind === "bars" && (
        <div className="flex h-24 items-end gap-2">
          {[45, 70, 38, 90, 60, 80, 52].map((h, i) => (
            <span
              key={i}
              className="flex-1 origin-bottom rounded-t-md"
              style={{
                height: `${h}%`,
                background: `linear-gradient(to top, ${c}, #fff3)`,
                animation: `grow 3.6s ease-in-out ${i * 0.25}s infinite`,
              }}
            />
          ))}
        </div>
      )}
      {kind === "kanban" && (
        <div className="grid h-24 grid-cols-3 gap-2 text-[8px] tracking-widest text-slate-500">
          {["NEW", "REVIEW", "DONE"].map((col, ci) => (
            <div key={col} className="relative rounded-lg bg-white/5 p-1.5">
              {col}
              {[0, 1].map((r) => (
                <span
                  key={r}
                  className="mt-1.5 block h-3.5 rounded bg-white/10"
                />
              ))}
              {ci === 0 && (
                <span
                  className="absolute left-1.5 right-1.5 top-9 h-4 rounded border border-cyan-300/60 bg-cyan-400/20"
                  style={{ animation: "hop 6s ease-in-out infinite" }}
                />
              )}
            </div>
          ))}
        </div>
      )}
      {kind === "pulse" && (
        <svg viewBox="0 0 200 80" className="h-24 w-full">
          <path
            d="M0 42h50l8-26 12 52 10-40 8 14h112"
            fill="none"
            stroke={c}
            strokeWidth="3"
            strokeLinejoin="round"
            strokeLinecap="round"
            className="flow-dash"
            style={{ filter: `drop-shadow(0 0 6px ${c})` }}
          />
          <circle
            cx="70"
            cy="68"
            r="4"
            fill="#f472b6"
            className="animate-glow"
          />
        </svg>
      )}
      {kind === "network" && (
        <svg viewBox="0 0 200 80" className="h-24 w-full">
          <g stroke={c} strokeOpacity="0.5" strokeWidth="1.5">
            <path
              d="M30 55 70 20 120 45 165 18M70 20 85 68 120 45"
              fill="none"
            />
          </g>
          {[
            [30, 55],
            [70, 20],
            [120, 45],
            [165, 18],
            [85, 68],
          ].map(([x, y], i) => (
            <circle
              key={i}
              cx={x}
              cy={y}
              r="5"
              fill={i === 1 ? "#f472b6" : "#c7d2fe"}
              className={i === 1 ? "animate-glow" : ""}
            />
          ))}
        </svg>
      )}
      {kind === "gauge" && (
        <svg viewBox="0 0 200 90" className="h-24 w-full">
          <path
            d="M30 80a70 70 0 0 1 140 0"
            fill="none"
            stroke="url(#carGauge)"
            strokeWidth="12"
            strokeLinecap="round"
          />
          <defs>
            <linearGradient id="carGauge" x1="0" x2="1">
              <stop offset="0" stopColor="#34d399" />
              <stop offset="0.55" stopColor="#fbbf24" />
              <stop offset="1" stopColor="#f43f5e" />
            </linearGradient>
          </defs>
          <g
            style={{
              transformOrigin: "100px 80px",
              animation: "needle 6s ease-in-out infinite",
            }}
          >
            <path
              d="M100 80 100 28"
              stroke="#fff"
              strokeWidth="4"
              strokeLinecap="round"
            />
          </g>
          <circle cx="100" cy="80" r="6" fill="#fff" />
        </svg>
      )}
      {kind === "line" && (
        <svg viewBox="0 0 200 80" className="h-24 w-full">
          {[25, 50, 75].map((y) => (
            <line
              key={y}
              x1="0"
              x2="200"
              y1={y}
              y2={y}
              stroke="rgb(129 140 248 / 0.2)"
            />
          ))}
          <polyline
            points="0,68 30,50 60,58 95,30 130,40 165,14 200,22"
            fill="none"
            stroke={c}
            strokeWidth="3.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{
              strokeDasharray: 400,
              animation: "trend-draw 4s ease-in-out infinite",
              filter: `drop-shadow(0 0 6px ${c})`,
            }}
          />
        </svg>
      )}
    </div>
  );
}

/**
 * 3D carousel of glass cards (centre card in front, neighbours tilted back) with an orbit glow underneath.
 * Auto-advances unless the pointer or keyboard focus is inside, or the user prefers reduced motion.
 */
export function SmartCarousel({ slides }: { slides: Slide[] }) {
  const n = slides.length;
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);
  const reduce =
    typeof window !== "undefined" &&
    (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false);

  useEffect(() => {
    if (paused || reduce || n < 2) return;
    const t = setInterval(() => setActive((a) => (a + 1) % n), 5500);
    return () => clearInterval(t);
  }, [paused, reduce, n]);
  useEffect(() => setActive((a) => Math.min(a, Math.max(0, n - 1))), [n]);
  if (n === 0) return null;

  const go = (d: number) => setActive((a) => (a + d + n) % n);
  const onKey = (e: KeyboardEvent) => {
    if (e.key === "ArrowRight") go(1);
    if (e.key === "ArrowLeft") go(-1);
  };

  return (
    <section
      aria-roledescription="carousel"
      aria-label="Highlights"
      className="relative mt-4"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
      onKeyDown={onKey}
    >
      <div
        className="relative mx-auto h-[26rem] w-full max-w-5xl"
        style={{ perspective: "1500px" }}
      >
        {/* orbit glow under the cards */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 bottom-0 h-40"
        >
          <div
            className="absolute inset-x-[4%] bottom-0 h-40 rounded-[50%] border border-indigo-400/30"
            style={{
              background:
                "radial-gradient(ellipse at 50% 0%, rgb(99 102 241 / 0.28), transparent 70%)",
              animation: "orbit-glow 6s ease-in-out infinite",
            }}
          />
          <div className="absolute inset-x-[-2%] bottom-6 h-32 rounded-[50%] border border-dashed border-indigo-300/20" />
        </div>
        <div
          className="absolute inset-0"
          style={{ transformStyle: "preserve-3d" }}
        >
          {slides.map((s, i) => {
            let off = i - active;
            if (off > n / 2) off -= n;
            if (off < -n / 2) off += n;
            const a = Math.abs(off);
            const isActive = off === 0;
            return (
              <div
                key={s.id}
                role="group"
                aria-roledescription="slide"
                aria-label={`${i + 1} of ${n}: ${s.title}`}
                aria-hidden={isActive ? undefined : true}
                onClick={() => !isActive && setActive(i)}
                className="carousel-card absolute left-1/2 top-4 w-[min(20rem,72%)]"
                style={{
                  transform: `translateX(calc(-50% + ${off * 84}%)) translateZ(${-a * 170}px) rotateY(${-off * 26}deg) scale(${1 - a * 0.06})`,
                  opacity: a > 2 ? 0 : 1,
                  filter: `brightness(${1 - a * 0.28})`,
                  zIndex: 20 - a,
                  pointerEvents: a > 2 ? "none" : "auto",
                  cursor: isActive ? "default" : "pointer",
                  WebkitBoxReflect:
                    "below 4px linear-gradient(transparent 76%, rgba(0,0,0,0.16))",
                }}
              >
                <article
                  className="rounded-3xl border border-indigo-300/25 bg-gradient-to-b from-[#1a1b3d] to-[#0b0c1f] p-3.5 shadow-2xl shadow-black/60"
                  style={{
                    boxShadow: isActive
                      ? "0 30px 70px -20px rgb(99 102 241 / 0.55)"
                      : undefined,
                  }}
                >
                  <Mock kind={s.kind} />
                  <div className="mt-3 flex items-center justify-between">
                    <span className="font-mono text-[11px] tracking-[0.25em] text-slate-500">
                      {s.tag}
                    </span>
                    <span className="rounded-full border border-cyan-300/40 bg-cyan-400/10 px-2.5 py-0.5 font-mono text-[10px] tracking-widest text-cyan-200">
                      LIVE
                    </span>
                  </div>
                  <h2 className="mt-1 text-xl font-semibold text-slate-800">
                    {s.title}
                  </h2>
                  <p className="mt-1 text-sm text-slate-600">{s.text}</p>
                  <div className="mt-3 flex items-end justify-between border-t border-white/10 pt-3">
                    <p className="text-slate-800">
                      <span className="text-2xl font-semibold tabular-nums">
                        {typeof s.metric === "number"
                          ? s.metric.toLocaleString("en-IN")
                          : s.metric}
                      </span>{" "}
                      <span className="text-sm text-slate-500">
                        {s.metricLabel}
                      </span>
                    </p>
                    <Link
                      to={s.to}
                      tabIndex={isActive ? 0 : -1}
                      className="btn-glow rounded-full px-4 py-1.5 text-sm font-medium text-white no-underline"
                    >
                      Open →
                    </Link>
                  </div>
                </article>
              </div>
            );
          })}
        </div>
      </div>
      {n > 1 && (
        <div className="relative z-30 mt-5 flex items-center justify-center gap-3">
          <button
            type="button"
            aria-label="Previous highlight"
            onClick={() => go(-1)}
            className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-300 hover:bg-white/10"
          >
            ‹
          </button>
          <div
            className="flex gap-2"
            role="group"
            aria-label="Choose a highlight"
          >
            {slides.map((s, i) => (
              <button
                key={s.id}
                type="button"
                aria-label={`Show ${s.title}`}
                aria-current={i === active}
                onClick={() => setActive(i)}
                className={`h-2 rounded-full transition-all ${i === active ? "w-7 bg-indigo-400" : "w-2 bg-white/30 hover:bg-white/50"}`}
              />
            ))}
          </div>
          <button
            type="button"
            aria-label="Next highlight"
            onClick={() => go(1)}
            className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-300 hover:bg-white/10"
          >
            ›
          </button>
        </div>
      )}
    </section>
  );
}
