import {
  Background,
  Controls,
  MarkerType,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type {
  GraphEdge,
  GraphEdgeDetail,
  GraphNode,
  GraphTimelineEvent,
  Neighborhood,
} from "../api/types";
import { ErrorState, LoadingState } from "../components/ui/states";
import { formatAmount, formatDateTime } from "../lib/format";
import { ringLayout } from "../lib/graphLayout";

const riskTone = (n: GraphNode) =>
  n.graph_risk_score === null
    ? "#e2e8f0"
    : n.graph_risk_score >= 60
      ? "#fecaca"
      : n.graph_risk_score >= 30
        ? "#fde68a"
        : "#bbf7d0";

function EdgePanel({
  edge,
  refs,
}: {
  edge: GraphEdge;
  refs: Record<number, string>;
}) {
  const tx = edge.transaction_ids[0];
  const q = useQuery({
    queryKey: ["graph-edge", tx],
    enabled: tx !== undefined,
    queryFn: ({ signal }) =>
      api.get<GraphEdgeDetail>(`/graph/edges/${tx}/`, signal),
  });
  return (
    <div
      role="region"
      aria-label="Selected connection"
      className="rounded-md border border-slate-300 p-3 text-sm"
    >
      <h3 className="font-semibold">
        {refs[edge.source]} → {refs[edge.target]}
      </h3>
      <p>
        {edge.count} transaction(s) · total {formatAmount(String(edge.total))} ·{" "}
        {formatDateTime(edge.first_at)} – {formatDateTime(edge.last_at)}
      </p>
      {q.data && (
        <p className="mt-1">
          Latest:{" "}
          <Link
            className="text-blue-700 hover:underline"
            to={`/transactions/${q.data.transaction_id}`}
          >
            {q.data.external_id}
          </Link>{" "}
          · {q.data.tx_type} · {formatAmount(q.data.amount, q.data.currency)} ·{" "}
          {q.data.status}
        </p>
      )}
    </div>
  );
}

export default function RelationshipGraphPage() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const [depth, setDepth] = useState(1);
  const [direction, setDirection] = useState<"both" | "out" | "in">("both");
  const [minAmount, setMinAmount] = useState(0);
  const [source, setSource] = useState<"auto" | "postgres" | "neo4j">("auto");
  const [selected, setSelected] = useState<GraphEdge | null>(null);
  const qs = `depth=${depth}&direction=${direction}&min_amount=${minAmount}&source=${source}`;
  const hood = useQuery({
    queryKey: ["graph-neighborhood", id, depth, direction, minAmount, source],
    queryFn: ({ signal }) =>
      api.get<Neighborhood>(
        `/graph/accounts/${id}/neighborhood/?${qs}`,
        signal,
      ),
  });
  const timeline = useQuery({
    queryKey: ["graph-timeline", id, depth, direction, minAmount, source],
    queryFn: ({ signal }) =>
      api.get<{ events: GraphTimelineEvent[] }>(
        `/graph/accounts/${id}/timeline/?${qs}`,
        signal,
      ),
  });
  const refs = useMemo(
    () =>
      Object.fromEntries(
        (hood.data?.nodes ?? []).map((n) => [n.id, n.account_ref]),
      ),
    [hood.data],
  );
  const { nodes, edges } = useMemo(() => {
    if (!hood.data) return { nodes: [] as Node[], edges: [] as Edge[] };
    const pos = ringLayout(hood.data.nodes);
    const nodes: Node[] = hood.data.nodes.map((n) => ({
      id: String(n.id),
      position: pos[n.id] ?? { x: 0, y: 0 },
      data: { label: `${n.account_ref}${n.in_finding ? " ⚑" : ""}` },
      style: {
        background: riskTone(n),
        border: n.depth === 0 ? "3px solid #0f172a" : "1px solid #475569",
        borderRadius: 8,
        color: "#0f172a",
        fontSize: 11,
        padding: 6,
      },
    }));
    const edges: Edge[] = hood.data.edges.map((e) => ({
      id: `${e.source}-${e.target}`,
      source: String(e.source),
      target: String(e.target),
      label: e.count > 1 ? `${e.count}×` : undefined,
      markerEnd: { type: MarkerType.ArrowClosed },
      style: { strokeWidth: Math.min(1 + Math.log10(e.total + 1), 5) },
    }));
    return { nodes, edges };
  }, [hood.data]);

  return (
    <section className="space-y-4">
      <p className="text-sm">
        <Link className="text-blue-700 hover:underline" to={`/accounts/${id}`}>
          ← Account
        </Link>{" "}
        ·{" "}
        <Link className="text-blue-700 hover:underline" to="/graph">
          Graph analysis
        </Link>
      </p>
      <h1 className="text-2xl font-semibold">Relationship network</h1>
      <div className="flex flex-wrap gap-4 text-sm">
        <label>
          Depth{" "}
          <select
            className="rounded border border-slate-300 p-1"
            value={depth}
            onChange={(e) => setDepth(Number(e.target.value))}
          >
            {[1, 2, 3].map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
        </label>
        <label>
          Direction{" "}
          <select
            className="rounded border border-slate-300 p-1"
            value={direction}
            onChange={(e) =>
              setDirection(e.target.value as "both" | "out" | "in")
            }
          >
            <option value="both">Both</option>
            <option value="out">Outgoing</option>
            <option value="in">Incoming</option>
          </select>
        </label>
        <label>
          Data source{" "}
          <select
            className="rounded border border-slate-300 p-1"
            value={source}
            onChange={(e) =>
              setSource(e.target.value as "auto" | "postgres" | "neo4j")
            }
          >
            <option value="auto">Automatic (PostgreSQL)</option>
            <option value="postgres">PostgreSQL</option>
            <option value="neo4j">Neo4j projection</option>
          </select>
        </label>
        <label>
          Min amount{" "}
          <input
            type="number"
            min={0}
            className="w-28 rounded border border-slate-300 p-1"
            value={minAmount}
            onChange={(e) => setMinAmount(Math.max(0, Number(e.target.value)))}
          />
        </label>
      </div>
      {hood.isPending && <LoadingState />}
      {hood.isError && (
        <ErrorState
          message={hood.error.message}
          onRetry={() => void hood.refetch()}
        />
      )}
      {hood.data && (
        <>
          <p className="text-sm text-slate-600">
            {hood.data.nodes.length} accounts · {hood.data.edges.length}{" "}
            connections · data from{" "}
            <strong>
              {hood.data.source === "neo4j" ? "Neo4j" : "PostgreSQL"}
            </strong>
            {hood.data.truncated && (
              <span
                role="status"
                className="ml-2 rounded bg-amber-100 px-1.5 text-amber-900"
              >
                Truncated: caps reached (200 accounts / 500 connections). Narrow
                the filters.
              </span>
            )}
          </p>
          <div
            className="h-[520px] overflow-hidden rounded-md border border-slate-300"
            aria-label="Network diagram (a table of the same connections follows)"
          >
            <ReactFlow
              nodes={nodes}
              edges={edges}
              fitView
              nodesConnectable={false}
              onNodeClick={(_, n) => nav(`/accounts/${n.id}/graph`)}
              onEdgeClick={(_, e) =>
                setSelected(
                  hood.data.edges.find(
                    (x) => `${x.source}-${x.target}` === e.id,
                  ) ?? null,
                )
              }
            >
              <Background />
              <Controls showInteractive={false} />
            </ReactFlow>
          </div>
          <p className="text-xs text-slate-600">
            Fill = graph risk score of the latest analysis (green &lt; 30, amber
            30–59, red ≥ 60, grey = not scored); ⚑ = part of a detected pattern;
            bold border = this account. Click an account to re-centre, a line
            for its transactions.
          </p>
          {selected && <EdgePanel edge={selected} refs={refs} />}
          <div className="overflow-x-auto">
            <h2 className="font-semibold">Connections</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-300 text-slate-600">
                  <tr>
                    <th className="py-1">From</th>
                    <th>To</th>
                    <th className="text-right">Transactions</th>
                    <th className="text-right">Total</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {hood.data.edges.map((e) => (
                    <tr
                      key={`${e.source}-${e.target}`}
                      className="border-b border-slate-100"
                    >
                      <td className="py-1 font-mono">{refs[e.source]}</td>
                      <td className="font-mono">{refs[e.target]}</td>
                      <td className="text-right tabular-nums">{e.count}</td>
                      <td className="text-right tabular-nums">
                        {formatAmount(String(e.total))}
                      </td>
                      <td>
                        <button
                          className="text-blue-700 hover:underline"
                          onClick={() => setSelected(e)}
                        >
                          Details
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
      {timeline.data && timeline.data.events.length > 0 && (
        <div>
          <h2 className="font-semibold">Timeline in this network</h2>
          <ol className="mt-1 max-h-72 space-y-1 overflow-y-auto text-sm">
            {timeline.data.events.slice(0, 50).map((t) => (
              <li key={t.transaction_id}>
                <span className="text-slate-500">
                  {formatDateTime(t.occurred_at)}
                </span>{" "}
                <span className="font-mono">{t.sender}</span> →{" "}
                <span className="font-mono">{t.receiver ?? "—"}</span>{" "}
                {formatAmount(t.amount)}{" "}
                <span className="text-slate-500">({t.tx_type})</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}
