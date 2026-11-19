import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "../../api/client";
import type { RiskAssessmentDetail } from "../../api/types";
import { ErrorState, LoadingState } from "../ui/states";
import { BreakdownTable } from "./BreakdownTable";

/** Latest risk assessment of one transaction, with the full breakdown. */
export function RiskPanel({ transactionId }: { transactionId: number }) {
  const q = useQuery({
    queryKey: ["tx-risk", transactionId],
    queryFn: ({ signal }) =>
      api.get<RiskAssessmentDetail>(
        `/transactions/${transactionId}/risk/`,
        signal,
      ),
  });
  if (q.isPending) return <LoadingState />;
  if (q.isError && q.error instanceof ApiError && q.error.status === 404)
    return (
      <div>
        <h2 className="text-lg font-semibold">Risk assessment</h2>
        <p className="mt-1 text-sm text-slate-600">
          This transaction has not been scored yet. Run risk scoring for its
          dataset from the Risk Analysis page.
        </p>
      </div>
    );
  if (q.isError)
    return (
      <ErrorState message={q.error.message} onRetry={() => void q.refetch()} />
    );
  return (
    <div>
      <h2 className="text-lg font-semibold">Risk assessment</h2>
      <BreakdownTable a={q.data} />
    </div>
  );
}
