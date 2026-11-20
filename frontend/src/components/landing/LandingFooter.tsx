import { Link } from "react-router-dom";
import { Logo } from "../fx/Logo";

const LETTERS = "FINGUARD".split("");
const PRINCIPLES = [
  "Permissions enforced on the server",
  "Append-only audit log",
  "Public and synthetic data only",
  "Scores explain themselves",
];

/** Animated footer: a moving perspective grid "horizon" with a glowing sun, rising sparks and a shimmering wordmark. */
export function LandingFooter({ signedIn }: { signedIn: boolean }) {
  return (
    <footer className="relative z-10 mt-16 overflow-hidden border-t border-indigo-400/20 pt-16">
      {/* horizon */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 bottom-0 h-[26rem]"
      >
        <span
          className="absolute bottom-24 left-1/2 h-72 w-72 rounded-full"
          style={{
            background:
              "radial-gradient(circle, rgb(244 114 182 / 0.55), rgb(99 102 241 / 0.35) 45%, transparent 70%)",
            animation: "sun-pulse 6s ease-in-out infinite",
          }}
        />
        <div className="footer-grid absolute inset-x-[-20%] bottom-0 h-72" />
        {Array.from({ length: 14 }, (_, i) => (
          <span
            key={i}
            className="absolute bottom-16 h-1.5 w-1.5 rounded-full bg-indigo-300"
            style={{
              left: `${(i * 37) % 100}%`,
              boxShadow: "0 0 8px #a5b4fc",
              animation: `rise-loop ${6 + (i % 5)}s linear ${(i * 0.7) % 6}s infinite`,
            }}
          />
        ))}
      </div>

      <div className="relative mx-auto max-w-6xl px-4">
        <div className="grid gap-10 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <div>
            <p className="flex items-center gap-2 text-lg font-semibold">
              <Logo size={26} />
              <span className="gradient-text">FinGuard</span>
            </p>
            <p className="mt-3 max-w-xs text-sm text-slate-600">
              Machine learning, graph analytics and explainable AI for financial
              anomaly detection and investigation.
            </p>
            <a
              href="#content"
              className="group mt-5 inline-flex items-center gap-2 rounded-full border border-slate-300 px-4 py-2 text-sm hover:bg-white/10"
            >
              Back to top
              <span
                aria-hidden="true"
                className="animate-float inline-block group-hover:text-indigo-300"
              >
                ↑
              </span>
            </a>
          </div>
          <nav aria-label="Footer explore">
            <p className="font-mono text-xs tracking-[0.2em] text-indigo-300">
              EXPLORE
            </p>
            <ul className="mt-3 space-y-2 text-sm">
              {[
                ["#features", "Features"],
                ["#flow", "How it works"],
                ["#insights", "Insights"],
                ["#roles", "Roles"],
              ].map(([h, l]) => (
                <li key={h}>
                  <a
                    className="inline-block text-slate-700 transition hover:translate-x-1 hover:text-white"
                    href={h}
                  >
                    {l}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
          <nav aria-label="Footer platform">
            <p className="font-mono text-xs tracking-[0.2em] text-violet-300">
              PLATFORM
            </p>
            <ul className="mt-3 space-y-2 text-sm">
              <li>
                <Link
                  className="inline-block text-slate-700 transition hover:translate-x-1 hover:text-white"
                  to={signedIn ? "/dashboard" : "/login"}
                >
                  {signedIn ? "Dashboard" : "Sign in"}
                </Link>
              </li>
              <li className="text-slate-500">
                Accounts are created by an administrator
              </li>
            </ul>
          </nav>
          <div>
            <p className="font-mono text-xs tracking-[0.2em] text-pink-300">
              PRINCIPLES
            </p>
            <ul className="mt-3 flex flex-wrap gap-2">
              {PRINCIPLES.map((p) => (
                <li
                  key={p}
                  className="rounded-full border border-indigo-400/25 bg-indigo-500/10 px-3 py-1 text-xs text-slate-700"
                >
                  {p}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* wordmark */}
        <p
          aria-hidden="true"
          className="wordmark mt-14 flex select-none justify-center whitespace-nowrap text-center font-bold leading-none tracking-tight"
          style={{ fontSize: "clamp(3rem, 15vw, 11rem)" }}
        >
          {LETTERS.map((c, i) => (
            <span
              key={i}
              className="animate-float inline-block"
              style={{ animationDelay: `${i * 0.25}s` }}
            >
              {c}
            </span>
          ))}
        </p>

        <p className="relative mx-auto mt-6 max-w-2xl pb-8 text-center text-sm text-slate-500">
          Built and evaluated on public and synthetic data only. Scores and
          flags are automated indicators for prioritising review, not proof of
          wrongdoing.
        </p>
      </div>
    </footer>
  );
}
