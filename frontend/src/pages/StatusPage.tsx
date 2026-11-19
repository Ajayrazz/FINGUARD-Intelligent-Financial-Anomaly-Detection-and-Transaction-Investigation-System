import { useQuery } from "@tanstack/react-query";
import { api, type ReadinessResponse } from "../api/client";
import { Tilt } from "../components/fx/Tilt";
import { ErrorState, LoadingState } from "../components/ui/states";

/** Infrastructure status. The analytics Overview Dashboard is delivered in Phase 14. */
export default function StatusPage() {
  const q = useQuery({
    queryKey: ["health-ready"],
    queryFn: ({ signal }) =>
      api.get<ReadinessResponse>("/health/ready/", signal),
  });
  return (
    <section>
      <h1 className="text-2xl font-semibold">System status</h1>
      <Tilt className="mt-4 max-w-md">
        <div
          className="animate-glow rounded-xl border border-indigo-400/30 bg-white/5 p-4"
          aria-live="polite"
        >
          {q.isPending && <LoadingState label="Checking backend…" />}
          {q.isError && (
            <ErrorState
              message={`Backend unreachable: ${q.error.message}`}
              onRetry={() => void q.refetch()}
            />
          )}
          {q.data && (
            <ul>
              {Object.entries(q.data.checks).map(([name, status]) => (
                <li key={name} className="flex justify-between py-1">
                  <span>{name}</span>
                  <span
                    className={
                      status === "ok" ? "text-risk-low" : "text-risk-critical"
                    }
                  >
                    {status}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Tilt>
    </section>
  );
}
