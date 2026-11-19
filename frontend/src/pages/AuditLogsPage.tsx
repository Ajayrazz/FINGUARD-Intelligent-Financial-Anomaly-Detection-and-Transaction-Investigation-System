import { PageHero } from "../components/scenes/PageHero";
import {
  Card3D,
  CardGrid,
  Chip,
  Initials,
  useViewMode,
  ViewToggle,
  type Tone,
} from "../components/ui/cards";
import { useQuery } from "@tanstack/react-query";
import { Fragment, useState } from "react";
import { api } from "../api/client";
import type { AuditLogEntry, Paginated } from "../api/types";
import { Button } from "../components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/states";

const auditTone = (a: string): Tone =>
  a.startsWith("auth")
    ? "indigo"
    : a.startsWith("graph")
      ? "cyan"
      : a.startsWith("detection")
        ? "violet"
        : a.startsWith("case") || a.startsWith("alert")
          ? "pink"
          : a.startsWith("user")
            ? "amber"
            : "slate";

export default function AuditLogsPage() {
  const [view, setView] = useViewMode("audit");
  const [action, setAction] = useState("");
  const [actor, setActor] = useState("");
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<number | null>(null);

  const params = new URLSearchParams({ page: String(page) });
  if (action) params.set("action", action);
  if (actor) params.set("actor_email", actor);
  const q = useQuery({
    queryKey: ["audit", action, actor, page],
    queryFn: ({ signal }) =>
      api.get<Paginated<AuditLogEntry>>(
        `/audit/logs/?${params.toString()}`,
        signal,
      ),
  });

  return (
    <section>
      <PageHero
        eyebrow="Govern"
        title="Audit logs"
        tone="amber"
        scene="ledger"
      />
      <div className="mt-2">
        <ViewToggle mode={view} onChange={setView} />
      </div>
      <p className="mt-1 text-sm text-slate-600">
        Append-only record of security-relevant actions.
      </p>
      <div className="mt-4 flex flex-wrap gap-3">
        <label className="text-sm">
          Action
          <input
            value={action}
            onChange={(e) => {
              setAction(e.target.value);
              setPage(1);
            }}
            placeholder="e.g. auth.login_failed"
            className="mt-1 block rounded-md border border-slate-300 px-2 py-1"
          />
        </label>
        <label className="text-sm">
          Actor email contains
          <input
            value={actor}
            onChange={(e) => {
              setActor(e.target.value);
              setPage(1);
            }}
            className="mt-1 block rounded-md border border-slate-300 px-2 py-1"
          />
        </label>
      </div>

      <div className="mt-4">
        {q.isPending && <LoadingState />}
        {q.isError && (
          <ErrorState
            message={q.error.message}
            onRetry={() => void q.refetch()}
          />
        )}
        {q.data && q.data.results.length === 0 && (
          <EmptyState title="No audit entries match these filters" />
        )}
        {q.data && q.data.results.length > 0 && (
          <>
            {view === "cards" ? (
              <CardGrid min="19rem">
                {q.data.results.map((e) => (
                  <Card3D key={e.id} tone={auditTone(e.action)}>
                    <div className="flex items-start gap-3">
                      <Initials text={e.actor_email || "system"} />
                      <div className="min-w-0 flex-1">
                        <p className="break-all font-mono text-sm font-semibold text-slate-800">
                          {e.action}
                        </p>
                        <p className="truncate text-xs text-slate-500">
                          {e.actor_email || "system"}
                        </p>
                      </div>
                    </div>
                    <p className="mt-3 text-xs text-slate-500">
                      {new Date(e.created_at)
                        .toISOString()
                        .replace("T", " ")
                        .slice(0, 19)}{" "}
                      UTC
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {e.resource_type && (
                        <Chip tone="indigo">
                          {e.resource_type} #{e.resource_id}
                        </Chip>
                      )}
                      {e.ip_address && <Chip>{e.ip_address}</Chip>}
                    </div>
                    <button
                      type="button"
                      className="mt-3 self-start text-xs underline"
                      aria-expanded={expanded === e.id}
                      onClick={() =>
                        setExpanded(expanded === e.id ? null : e.id)
                      }
                    >
                      Details
                    </button>
                    {expanded === e.id && (
                      <pre className="mt-2 overflow-x-auto rounded-lg bg-black/30 p-2 text-xs">
                        {JSON.stringify(
                          { request_id: e.request_id, changes: e.changes },
                          null,
                          2,
                        )}
                      </pre>
                    )}
                  </Card3D>
                ))}
              </CardGrid>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-slate-300 text-slate-600">
                    <tr>
                      <th className="py-2">Time (UTC)</th>
                      <th>Action</th>
                      <th>Actor</th>
                      <th>Resource</th>
                      <th>IP</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {q.data.results.map((e) => (
                      <Fragment key={e.id}>
                        <tr className="border-b border-slate-100">
                          <td className="py-2">
                            {new Date(e.created_at)
                              .toISOString()
                              .replace("T", " ")
                              .slice(0, 19)}
                          </td>
                          <td className="font-mono">{e.action}</td>
                          <td>{e.actor_email || "—"}</td>
                          <td>
                            {e.resource_type
                              ? `${e.resource_type} #${e.resource_id}`
                              : "—"}
                          </td>
                          <td>{e.ip_address ?? "—"}</td>
                          <td>
                            <button
                              type="button"
                              className="text-xs underline"
                              aria-expanded={expanded === e.id}
                              onClick={() =>
                                setExpanded(expanded === e.id ? null : e.id)
                              }
                            >
                              Details
                            </button>
                          </td>
                        </tr>
                        {expanded === e.id && (
                          <tr>
                            <td colSpan={6} className="bg-slate-50 p-3">
                              <pre className="overflow-x-auto text-xs">
                                {JSON.stringify(
                                  {
                                    request_id: e.request_id,
                                    changes: e.changes,
                                  },
                                  null,
                                  2,
                                )}
                              </pre>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="mt-3 flex items-center gap-3 text-sm">
              <Button
                variant="secondary"
                disabled={!q.data.previous}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>
              <span>
                Page {page} · {q.data.count} entries
              </span>
              <Button
                variant="secondary"
                disabled={!q.data.next}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
