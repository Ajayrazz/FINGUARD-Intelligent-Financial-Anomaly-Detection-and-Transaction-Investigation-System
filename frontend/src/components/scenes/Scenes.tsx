import { NetworkScene } from "../landing/NetworkScene";

/* Decorative hero scenes. Each is aria-hidden by its parent; motion stops under prefers-reduced-motion. */

const glassCard =
  "rounded-xl border border-indigo-300/30 bg-indigo-500/15 backdrop-blur-sm";

export function FlowScene() {
  return (
    <div className="scene-3d flex h-full items-center justify-center gap-3">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className={`${glassCard} flex h-24 w-20 flex-col justify-between p-2 animate-float`}
          style={{
            animationDelay: `${i * 0.6}s`,
            transform: `rotateY(${-24 + i * 14}deg)`,
          }}
        >
          <span className="h-2 w-8 rounded bg-indigo-300/70" />
          <span className="text-lg font-semibold text-indigo-100">₹</span>
          <span className="h-1.5 w-12 rounded bg-white/25" />
        </div>
      ))}
      <svg
        viewBox="0 0 60 12"
        className="h-3 w-14 text-indigo-300"
        style={{ animation: "drift 2.4s ease-in-out infinite" }}
      >
        <path
          d="M0 6h52m0 0-6-4m6 4-6 4"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeDasharray="4 3"
        />
      </svg>
    </div>
  );
}

export function LayersScene() {
  return (
    <div className="scene-3d flex h-full items-center justify-center">
      <div
        className="relative h-28 w-40"
        style={{
          transform: "rotateX(58deg) rotateZ(-28deg)",
          transformStyle: "preserve-3d",
        }}
      >
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className="absolute inset-0 rounded-lg border border-cyan-300/50 bg-cyan-400/15 animate-float"
            style={{
              transform: `translateZ(${i * 18}px)`,
              animationDelay: `${i * 0.4}s`,
            }}
          />
        ))}
      </div>
    </div>
  );
}

export function RadarScene() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="relative h-40 w-40 rounded-full border border-violet-300/40 bg-violet-500/10">
        {[0.66, 0.33].map((s) => (
          <span
            key={s}
            className="absolute inset-0 m-auto rounded-full border border-violet-300/30"
            style={{ width: `${s * 100}%`, height: `${s * 100}%` }}
          />
        ))}
        <span
          className="absolute inset-0 rounded-full"
          style={{
            background:
              "conic-gradient(from 0deg, rgb(167 139 250 / 0.55), transparent 28%)",
            animation: "sweep 4s linear infinite",
          }}
        />
        {[
          [30, 28],
          [66, 40],
          [48, 72],
        ].map(([x, y], i) => (
          <span
            key={i}
            className="absolute h-2.5 w-2.5 rounded-full bg-pink-400 shadow-[0_0_10px_#f472b6] animate-glow"
            style={{
              left: `${x}%`,
              top: `${y}%`,
              animationDelay: `${i * 0.8}s`,
            }}
          />
        ))}
      </div>
    </div>
  );
}

export function GraphMiniScene() {
  return (
    <div className="h-full w-full">
      <NetworkScene height={190} />
    </div>
  );
}

export function MergeScene() {
  return (
    <div className="scene-3d flex h-full items-center justify-center">
      <div
        className={`${glassCard} h-24 w-28 p-2`}
        style={{ animation: "merge-l 4s ease-in-out infinite" }}
      >
        <span className="block h-2 w-14 rounded bg-amber-300/70" />
        <span className="mt-2 block h-1.5 w-20 rounded bg-white/25" />
        <span className="mt-1 block h-1.5 w-16 rounded bg-white/25" />
      </div>
      <div
        className="-ml-12 h-24 w-28 rounded-xl border border-amber-300/40 bg-amber-400/15 p-2 backdrop-blur-sm"
        style={{ animation: "merge-r 4s ease-in-out infinite" }}
      >
        <span className="block h-2 w-14 rounded bg-amber-300/70" />
        <span className="mt-2 block h-1.5 w-20 rounded bg-white/25" />
        <span className="mt-1 block h-1.5 w-16 rounded bg-white/25" />
      </div>
    </div>
  );
}

export function GaugeScene() {
  return (
    <div className="flex h-full items-center justify-center">
      <svg viewBox="0 0 200 120" className="h-40 w-64">
        <defs>
          <linearGradient id="gauge" x1="0" x2="1">
            <stop offset="0" stopColor="#34d399" />
            <stop offset="0.5" stopColor="#fbbf24" />
            <stop offset="1" stopColor="#f43f5e" />
          </linearGradient>
        </defs>
        <path
          d="M20 100a80 80 0 0 1 160 0"
          fill="none"
          stroke="url(#gauge)"
          strokeWidth="14"
          strokeLinecap="round"
          style={{ filter: "drop-shadow(0 0 6px rgb(244 114 182 / 0.6))" }}
        />
        <g
          style={{
            transformOrigin: "100px 100px",
            animation: "needle 6s ease-in-out infinite",
          }}
        >
          <path
            d="M100 100 L100 36"
            stroke="#f4f5fc"
            strokeWidth="4"
            strokeLinecap="round"
          />
        </g>
        <circle cx="100" cy="100" r="8" fill="#f4f5fc" />
      </svg>
    </div>
  );
}

export function BeaconScene() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="relative flex h-32 w-32 items-center justify-center">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="absolute inset-0 rounded-full border-2 border-red-400/70"
            style={{
              animation: "ping-ring 3s ease-out infinite",
              animationDelay: `${i}s`,
            }}
          />
        ))}
        <svg
          viewBox="0 0 24 24"
          className="relative h-12 w-12 text-red-300"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M12 3 2 20h20L12 3zM12 10v5M12 18h.01" />
        </svg>
      </div>
    </div>
  );
}

export function CubeScene() {
  return (
    <div className="scene-3d flex h-full items-center justify-center">
      <div className="cube">
        {[1, 2, 3, 4, 5, 6].map((n) => (
          <span key={n} />
        ))}
      </div>
    </div>
  );
}

export function BarsScene() {
  const hs = [55, 85, 40, 100, 70, 90];
  return (
    <div
      className="scene-3d flex h-full items-end justify-center gap-2 pb-4"
      style={{ transform: "rotateY(-18deg) rotateX(8deg)" }}
    >
      {hs.map((h, i) => (
        <span
          key={i}
          className="w-6 origin-bottom rounded-t-md bg-gradient-to-t from-indigo-600 via-violet-400 to-cyan-300 shadow-[0_0_14px_rgb(129_140_248/0.5)]"
          style={{
            height: `${h}%`,
            animation: "grow 3.6s ease-in-out infinite",
            animationDelay: `${i * 0.3}s`,
          }}
        />
      ))}
    </div>
  );
}

export function PeopleScene() {
  return (
    <div
      className="orbit-scene flex h-full items-center justify-center"
      style={{ perspective: 600 }}
    >
      <div
        className="relative h-0 w-0"
        style={{
          transformStyle: "preserve-3d",
          animation: "orbit 18s linear infinite",
        }}
      >
        {["AR", "FA", "FI", "AU", "MG"].map((t, i) => (
          <span
            key={t}
            className="absolute flex h-12 w-12 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-500 text-sm font-semibold text-white shadow-lg"
            style={{
              transform: `rotateY(${i * 72}deg) translateZ(90px)`,
              backfaceVisibility: "hidden",
            }}
          >
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}

export function LedgerScene() {
  return (
    <div className="scene-3d flex h-full items-center justify-center">
      <div
        className="h-32 w-44 overflow-hidden rounded-lg border border-slate-300/40 bg-white/5"
        style={{ transform: "rotateX(24deg) rotateY(-18deg)" }}
      >
        <div
          className="h-full w-full"
          style={{
            backgroundImage:
              "repeating-linear-gradient(to bottom, transparent 0 14px, rgb(165 180 252 / 0.35) 14px 16px, transparent 16px 24px)",
            animation: "ledger 2s linear infinite",
          }}
        />
      </div>
    </div>
  );
}

export function GyroScene() {
  const ring = "absolute inset-0 rounded-full border-2";
  return (
    <div className="scene-3d flex h-full items-center justify-center">
      <div
        className="relative h-36 w-36"
        style={{ transformStyle: "preserve-3d" }}
      >
        <span
          className={`${ring} border-indigo-300/70`}
          style={{ animation: "gyro-a 9s linear infinite" }}
        />
        <span
          className={`${ring} border-cyan-300/70`}
          style={{ animation: "gyro-b 7s linear infinite" }}
        />
        <span
          className={`${ring} border-pink-300/70`}
          style={{ animation: "gyro-c 11s linear infinite" }}
        />
        <span className="absolute inset-0 m-auto h-5 w-5 rounded-full bg-violet-300 shadow-[0_0_24px_#a78bfa] animate-glow" />
      </div>
    </div>
  );
}

export function TrendScene() {
  return (
    <div className="scene-3d flex h-full items-center justify-center">
      <svg
        viewBox="0 0 220 120"
        className="h-40 w-72"
        style={{ transform: "rotateX(18deg) rotateY(-14deg)" }}
      >
        <defs>
          <linearGradient id="trend" x1="0" x2="1">
            <stop offset="0" stopColor="#22d3ee" />
            <stop offset="1" stopColor="#f472b6" />
          </linearGradient>
        </defs>
        {[30, 60, 90].map((y) => (
          <line
            key={y}
            x1="10"
            x2="210"
            y1={y}
            y2={y}
            stroke="rgb(129 140 248 / 0.25)"
          />
        ))}
        <polyline
          points="10,95 45,70 80,82 115,45 150,58 185,22 210,30"
          fill="none"
          stroke="url(#trend)"
          strokeWidth="4"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="flow-dash"
          style={{
            filter: "drop-shadow(0 0 6px #f472b6)",
            strokeDasharray: "400",
            animation: "trend-draw 4s ease-in-out infinite",
          }}
        />
        {[
          [45, 70],
          [115, 45],
          [185, 22],
        ].map(([x, y]) => (
          <circle
            key={x}
            cx={x}
            cy={y}
            r="5"
            fill="#fff"
            className="animate-glow"
          />
        ))}
      </svg>
    </div>
  );
}
