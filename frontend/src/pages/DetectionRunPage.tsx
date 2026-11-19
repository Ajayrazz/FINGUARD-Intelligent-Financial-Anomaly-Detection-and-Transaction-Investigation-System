import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type {
  DetectionRun,
  Paginated,
  PredictionRow,
  ScoreSummary,
} from "../api/types";
import {
  RunStatusBadge,
  isRunActive,
} from "../components/detection/RunStatusBadge";
import { ScoreHistogram } from "../components/detection/ScoreHistogram";
import { Button } from "../components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/states";
import { formatAmount, formatDateTime } from "../lib/format";

export default function DetectionRunPage() {
  const { id } = useParams();
  const [page, setPage] = useState(1);
  const [flaggedOnly, setFlaggedOnly] = useState(true);
  const run = useQuery({
    queryKey: ["detection-run", id],
    queryFn: ({ signal }) =>
      api.get<DetectionRun>(`/detection/runs/${id}/`, signal),
    refetchInterval: (query) =>
      query.state.data && isRunActive(query.state.data.status) ? 2000 : false,
  });
  const done = run.data?.status === "succeeded";
  const preds = useQuery({
    queryKey: ["detection-predictions", id, page, flaggedOnly],
    enabled: done,
    queryFn: ({ signal }) =>
      api.get<Paginated<PredictionRow>>(
        `/detection/runs/${id}/predictions/?page=${page}${flaggedOnly ? "&flagged=true" : ""}`,
        signal,
      ),
  });
  if (run.isPending) return <LoadingState />;
  if (run.isError)
    return (
      <ErrorState
        message={run.error.message}
        onRetry={() => void run.refetch()}
      />
    );
  const r = run.data;
  const summary = r.score_summary as ScoreSummary;
  return (
    <section>
      <p className="text-sm">
        <Link className="text-blue-700 hover:underline" to="/detection">
          ← Detection runs
        </Link>
      </p>
      <h1 className="mt-1 text-2xl font-semibold">
        Detection run #{r.id} <RunStatusBadge status={r.status} />
      </h1>
      {r.is_mock_data && (
        <p
          role="note"
          className="mt-2 rounded border border-amber-300 bg-amber-50 p-2 text-sm text-amber-900"
        >
          This dataset is MOCK (random) data. Scores on it carry no meaning
          about real fraud.
        </p>
      )}
      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-slate-600">Model</dt>
          <dd>
            {r.model_name}{" "}
            <span className="text-slate-500">({r.algorithm})</span>
          </dd>
        </div>
        <div>
          <dt className="text-slate-600">Dataset</dt>
          <dd>{r.dataset_name}</dd>
        </div>
        <div>
          <dt className="text-slate-600">Scored</dt>
          <dd className="tabular-nums">{r.rows_scored.toLocaleString()}</dd>
        </div>
        <div>
          <dt className="text-slate-600">
            Flagged (score ≥ {r.threshold.toFixed(3)})
          </dt>
          <dd className="tabular-nums">{r.rows_flagged.toLocaleString()}</dd>
        </div>
        <div>
          <dt className="text-slate-600">Threshold source</dt>
          <dd>{r.threshold_source}</dd>
        </div>
        <div>
          <dt className="text-slate-600">Started</dt>
          <dd>{r.started_at ? formatDateTime(r.started_at) : "—"}</dd>
        </div>
        <div>
          <dt className="text-slate-600">Finished</dt>
          <dd>{r.finished_at ? formatDateTime(r.finished_at) : "—"}</dd>
        </div>
        <div>
          <dt className="text-slate-600">By</dt>
          <dd>{r.created_by_email ?? "—"}</dd>
        </div>
      </dl>
      {r.status === "failed" && (
        <div
          role="alert"
          className="mt-3 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800"
        >
          Run failed: {r.error_message || "unknown error"}
        </div>
      )}
      {isRunActive(r.status) && <LoadingState label="Scoring transactions…" />}
      {done && summary.histogram && (
        <div className="mt-4">
          <h2 className="font-semibold">Score distribution</h2>
          <ScoreHistogram summary={summary} />
        </div>
      )}
      {done && (
        <div className="mt-6">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Highest-scoring transactions</h2>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={flaggedOnly}
                onChange={(e) => {
                  setFlaggedOnly(e.target.checked);
                  setPage(1);
                }}
              />
              Flagged only
            </label>
          </div>
          {preds.isPending && <LoadingState />}
          {preds.isError && (
            <ErrorState
              message={preds.error.message}
              onRetry={() => void preds.refetch()}
            />
          )}
          {preds.data && preds.data.results.length === 0 && (
            <EmptyState
              title="No transactions to show"
              hint="Nothing scored at or above the threshold."
            />
          )}
          {preds.data && preds.data.results.length > 0 && (
            <>
              <div className="mt-2 overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-slate-300 text-slate-600">
                    <tr>
                      <th className="py-2">Transaction</th>
                      <th>Type</th>
                      <th className="text-right">Amount</th>
                      <th>Sender</th>
                      <th>Receiver</th>
                      <th className="text-right">Score</th>
                      <th>Flag</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preds.data.results.map((p) => (
                      <tr key={p.id} className="border-b border-slate-100">
                        <td className="py-2">
                          <Link
                            className="text-blue-700 hover:underline"
                            to={`/transactions/${p.transaction_id}`}
                          >
                            {p.external_id}
                          </Link>
                        </td>
                        <td>{p.tx_type}</td>
                        <td className="text-right tabular-nums">
                          {formatAmount(p.amount)}
                        </td>
                        <td>{p.sender}</td>
                        <td>{p.receiver ?? "—"}</td>
                        <td className="text-right tabular-nums">
                          {p.score.toFixed(4)}
                        </td>
                        <td>{p.flagged ? "Flagged" : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="mt-3 flex items-center gap-3 text-sm">
                <Button
                  variant="secondary"
                  disabled={!preds.data.previous}
                  onClick={() => setPage((p) => p - 1)}
                >
                  Previous
                </Button>
                <span>
                  Page {page} · {preds.data.count.toLocaleString()} transactions
                </span>
                <Button
                  variant="secondary"
                  disabled={!preds.data.next}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </Button>
              </div>
            </>
          )}
        </div>
      )}
    </section>
  );
}
