import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, type ReadinessResponse } from "../api/client";
import { Logo } from "../components/fx/Logo";

interface FooterGroup {
  label: string;
  items: { to: string; label: string }[];
}

/** Footer for the signed-in app: animated horizon, page links the role may open, live system status, wordmark. */
export function AppFooter({ groups }: { groups: FooterGroup[] }) {
  const health = useQuery({
    queryKey: ["health-ready"],
    queryFn: ({ signal }) =>
      api.get<ReadinessResponse>("/health/ready/", signal),
  });
  const checks = Object.entries(health.data?.checks ?? {});
  return (
    <footer className="relative z-10 mx-auto mt-4 w-[min(80rem,calc(100%-1rem))] overflow-hidden rounded-t-3xl border border-b-0 border-indigo-400/20 bg-[#07071280] pt-10 backdrop-blur">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 bottom-0 h-56"
      >
        <span
          className="absolute bottom-10 left-1/2 h-48 w-48 rounded-full"
          style={{
            background:
              "radial-gradient(circle, rgb(244 114 182 / 0.45), rgb(99 102 241 / 0.3) 45%, transparent 70%)",
            animation: "sun-pulse 6s ease-in-out infinite",
          }}
        />
        <div className="footer-grid absolute inset-x-[-20%] bottom-0 h-48" />
        {Array.from({ length: 10 }, (_, i) => (
          <span
            key={i}
            className="absolute bottom-10 h-1.5 w-1.5 rounded-full bg-indigo-300"
            style={{
              left: `${(i * 41) % 100}%`,
              boxShadow: "0 0 8px #a5b4fc",
              animation: `rise-loop ${6 + (i % 4)}s linear ${(i * 0.8) % 6}s infinite`,
            }}
          />
        ))}
      </div>

      <div className="relative px-5 md:px-8">
        <div className="grid gap-8 md:grid-cols-[1fr_3fr_1fr]">
          <div>
            <p className="flex items-center gap-2 text-lg font-semibold">
              <Logo size={24} />
              <span className="gradient-text">FinGuard</span>
            </p>
            <p className="mt-2 max-w-xs text-sm text-slate-600">
              Detect, trace and explain suspicious financial activity.
            </p>
            <a
              href="#content"
              className="group mt-4 inline-flex items-center gap-2 rounded-full border border-slate-300 px-4 py-1.5 text-sm no-underline hover:bg-white/10"
            >
              Back to top
              <span aria-hidden="true" className="animate-float inline-block">
                ↑
              </span>
            </a>
          </div>

          <nav
            aria-label="Footer"
            className="grid grid-cols-2 gap-6 sm:grid-cols-[repeat(auto-fit,minmax(6rem,1fr))]"
          >
            {groups.map((g) => (
              <div key={g.label}>
                <p className="font-mono text-xs tracking-[0.2em] text-indigo-300 uppercase">
                  {g.label}
                </p>
                <ul className="mt-2 space-y-1.5 text-sm">
                  {g.items.map((i) => (
                    <li key={i.to}>
                      <Link
                        to={i.to}
                        className="inline-block text-slate-700 no-underline transition hover:translate-x-1 hover:text-white"
                      >
                        {i.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </nav>

          <div>
            <p className="font-mono text-xs tracking-[0.2em] text-pink-300 uppercase">
              System
            </p>
            <ul
              className="mt-2 flex flex-wrap gap-2 text-xs"
              aria-label="System status"
            >
              {health.isPending && (
                <li className="text-slate-500">Checking…</li>
              )}
              {health.isError && (
                <li className="rounded-full border border-red-400/40 bg-red-400/10 px-3 py-1 text-risk-critical">
                  Backend unreachable
                </li>
              )}
              {checks.map(([name, status]) => (
                <li
                  key={name}
                  className={`flex items-center gap-1.5 rounded-full border px-3 py-1 ${status === "ok" ? "border-emerald-400/40 bg-emerald-400/10 text-risk-low" : "border-red-400/40 bg-red-400/10 text-risk-critical"}`}
                >
                  <span
                    aria-hidden="true"
                    className="h-1.5 w-1.5 rounded-full bg-current"
                    style={{ animation: "ping-ring 2s ease-out infinite" }}
                  />
                  {name}: {status}
                </li>
              ))}
            </ul>
          </div>
        </div>

        <p
          aria-hidden="true"
          className="wordmark mt-8 flex select-none justify-center whitespace-nowrap font-bold leading-none tracking-tight"
          style={{ fontSize: "clamp(2.5rem, 11vw, 7rem)" }}
        >
          {"FINGUARD".split("").map((c, i) => (
            <span
              key={i}
              className="animate-float inline-block"
              style={{ animationDelay: `${i * 0.25}s` }}
            >
              {c}
            </span>
          ))}
        </p>
        <p className="relative mx-auto max-w-2xl pb-6 pt-3 text-center text-xs text-slate-500">
          Public and synthetic data only. Scores and flags are automated
          indicators for prioritising review, not proof of wrongdoing.
        </p>
      </div>
    </footer>
  );
}
