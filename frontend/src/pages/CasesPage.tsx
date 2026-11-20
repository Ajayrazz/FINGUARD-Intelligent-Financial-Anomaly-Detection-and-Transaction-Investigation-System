import { PageHero } from "../components/scenes/PageHero";
import {
  Card3D,
  CardGrid,
  Chip,
  useViewMode,
  ViewToggle,
} from "../components/ui/cards";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type {
  CasePriority,
  CaseRow,
  CaseSummary,
  Paginated,
} from "../api/types";
import { useAuth } from "../auth/AuthContext";
import {
  CaseStatusBadge,
  OUTCOME_LABEL,
  PriorityBadge,
} from "../components/cases/CaseBadges";
import { Button } from "../components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/states";
import { useToast } from "../components/ui/Toast";
import { formatDateTime } from "../lib/format";

export default function CasesPage() {
  const { can } = useAuth();
  const nav = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const [status, setStatus] = useState("open");
  const [priority, setPriority] = useState("");
  const [assignee, setAssignee] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [view, setView] = useViewMode("cases");
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [newPriority, setNewPriority] = useState<CasePriority>("medium");
  const qs = `page=${page}${status === "open" ? "&open=true" : status ? `&status=${status}` : ""}${priority ? `&priority=${priority}` : ""}${assignee ? `&assignee=${assignee}` : ""}${search.trim() ? `&search=${encodeURIComponent(search.trim())}` : ""}`;
  const list = useQuery({
    queryKey: ["cases", qs],
    queryFn: ({ signal }) =>
      api.get<Paginated<CaseRow>>(`/cases/?${qs}`, signal),
  });
  const summary = useQuery({
    queryKey: ["cases-summary"],
    queryFn: ({ signal }) => api.get<CaseSummary>("/cases/summary/", signal),
  });
  const create = useMutation({
    mutationFn: () =>
      api.post<CaseRow>("/cases/", {
        title,
        description,
        priority: newPriority,
      }),
    onSuccess: (c) => {
      toast("success", `Case ${c.case_ref} opened`);
      void qc.invalidateQueries({ queryKey: ["cases"] });
      nav(`/cases/${c.id}`);
    },
    onError: (e: unknown) =>
      toast(
        "error",
        e instanceof ApiError ? e.message : "Could not create the case",
      ),
  });
  const sel =
    (set: (v: string) => void) => (e: React.ChangeEvent<HTMLSelectElement>) => {
      set(e.target.value);
      setPage(1);
    };
  return (
    <section className="space-y-4">
      <div className="relative [&>a]:absolute [&>a]:right-6 [&>a]:top-6 [&>a]:z-10 [&>button]:absolute [&>button]:right-6 [&>button]:top-6 [&>button]:z-10">
        <PageHero
          eyebrow="Respond"
          title="Investigations"
          tone="violet"
          scene="cube"
        />
        {can("cases.create") && (
          <Button variant="secondary" onClick={() => setCreating((v) => !v)}>
            {creating ? "Cancel" : "New case"}
          </Button>
        )}
      </div>
      <p className="text-sm text-slate-600">
        Cases are opened from alerts (automatically for critical ones) or by
        hand. Open cases come first, then by priority.
      </p>
      {summary.data && (
        <ul
          aria-label="Open cases by priority"
          className="flex flex-wrap gap-4 text-sm"
        >
          {(["critical", "high", "medium", "low"] as const).map((p) => (
            <li key={p} className="rounded border border-slate-200 px-3 py-1">
              <PriorityBadge priority={p} />{" "}
              <span className="tabular-nums">
                {summary.data.open_by_priority[p]}
              </span>
            </li>
          ))}
          <li className="rounded border border-slate-200 px-3 py-1">
            Unassigned open{" "}
            <span className="tabular-nums">{summary.data.unassigned_open}</span>
          </li>
        </ul>
      )}
      {creating && (
        <form
          className="space-y-2 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <label className="block">
            Title
            <input
              className="mt-1 block w-full rounded border border-slate-300 p-1.5"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          <label className="block">
            Description
            <textarea
              className="mt-1 block w-full rounded border border-slate-300 p-1.5"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </label>
          <label>
            Priority{" "}
            <select
              className="rounded border border-slate-300 p-1"
              value={newPriority}
              onChange={(e) => setNewPriority(e.target.value as CasePriority)}
            >
              {["low", "medium", "high", "critical"].map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </label>{" "}
          <Button type="submit" disabled={!title.trim() || create.isPending}>
            Open case
          </Button>
        </form>
      )}
      <div className="flex flex-wrap items-end gap-4 text-sm">
        <label>
          Search
          <input
            className="ml-1 w-56 rounded border border-slate-300 p-1"
            placeholder="case number, title or account"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </label>
        <label>
          Status
          <select
            className="ml-1 rounded border border-slate-300 p-1"
            value={status}
            onChange={sel(setStatus)}
          >
            <option value="open">Open</option>
            <option value="">All</option>
            {[
              "new",
              "under_review",
              "investigation",
              "escalated",
              "resolved",
              "closed",
            ].map((s) => (
              <option key={s} value={s}>
                {s.replace("_", " ")}
              </option>
            ))}
          </select>
        </label>
        <label>
          Priority
          <select
            className="ml-1 rounded border border-slate-300 p-1"
            value={priority}
            onChange={sel(setPriority)}
          >
            <option value="">All</option>
            {["critical", "high", "medium", "low"].map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </label>
        <label>
          Assigned
          <select
            className="ml-1 rounded border border-slate-300 p-1"
            value={assignee}
            onChange={sel(setAssignee)}
          >
            <option value="">Anyone</option>
            <option value="me">Me</option>
            <option value="none">Unassigned</option>
          </select>
        </label>
      </div>
      {list.isPending && <LoadingState />}
      {list.isError && (
        <ErrorState
          message={list.error.message}
          onRetry={() => void list.refetch()}
        />
      )}
      {list.data && list.data.results.length === 0 && (
        <EmptyState
          title="No cases match"
          hint="Open one from an alert, or use New case."
        />
      )}
      {list.data && list.data.results.length > 0 && (
        <>
          <div className="space-y-3">
            <ViewToggle mode={view} onChange={setView} />
            {view === "cards" ? (
              <CardGrid min="20rem">
                {list.data.results.map((c) => (
                  <Card3D
                    key={c.id}
                    tone={
                      c.priority === "critical"
                        ? "red"
                        : c.priority === "high"
                          ? "amber"
                          : c.priority === "medium"
                            ? "violet"
                            : "cyan"
                    }
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Link
                        className="font-mono text-blue-700 hover:underline"
                        to={`/cases/${c.id}`}
                      >
                        {c.case_ref}
                      </Link>
                      <div className="flex items-center gap-2">
                        <PriorityBadge priority={c.priority} />
                        <CaseStatusBadge status={c.status} />
                      </div>
                    </div>
                    <h2 className="mt-3 text-sm font-semibold text-slate-800">
                      {c.title}
                      {c.auto_created && (
                        <span className="ml-2">
                          <Chip>auto</Chip>
                        </span>
                      )}
                    </h2>
                    {c.outcome && (
                      <p className="mt-1 text-xs text-slate-600">
                        Outcome: {OUTCOME_LABEL[c.outcome]}
                      </p>
                    )}
                    <div className="mt-3 grid grid-cols-2 gap-2 text-center">
                      <div className="rounded-lg bg-white/5 p-2">
                        <p className="text-xl font-semibold tabular-nums">
                          {c.alert_count}
                        </p>
                        <p className="text-[10px] uppercase tracking-wider text-slate-500">
                          Alerts
                        </p>
                      </div>
                      <div className="rounded-lg bg-white/5 p-2">
                        <p className="text-xl font-semibold tabular-nums">
                          {c.transaction_count}
                        </p>
                        <p className="text-[10px] uppercase tracking-wider text-slate-500">
                          Transactions
                        </p>
                      </div>
                    </div>
                    <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-3 text-xs text-slate-500">
                      <span>
                        {c.assignee_email
                          ? `Assigned: ${c.assignee_email}`
                          : "Unassigned"}
                      </span>
                      <span>{formatDateTime(c.opened_at)}</span>
                    </div>
                  </Card3D>
                ))}
              </CardGrid>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-slate-300 text-slate-600">
                    <tr>
                      <th className="py-1">Case</th>
                      <th>Title</th>
                      <th>Priority</th>
                      <th>Status</th>
                      <th>Assigned</th>
                      <th className="text-right">Alerts</th>
                      <th className="text-right">Transactions</th>
                      <th>Opened</th>
                    </tr>
                  </thead>
                  <tbody>
                    {list.data.results.map((c) => (
                      <tr
                        key={c.id}
                        className="border-b border-slate-100 align-top"
                      >
                        <td className="py-1 font-mono">
                          <Link
                            className="text-blue-700 hover:underline"
                            to={`/cases/${c.id}`}
                          >
                            {c.case_ref}
                          </Link>
                        </td>
                        <td className="max-w-md">
                          {c.title}
                          {c.auto_created && (
                            <span className="ml-2 rounded bg-slate-100 px-1.5 text-xs text-slate-600">
                              auto
                            </span>
                          )}
                          {c.outcome && (
                            <span className="ml-2 text-xs text-slate-600">
                              ({OUTCOME_LABEL[c.outcome]})
                            </span>
                          )}
                        </td>
                        <td>
                          <PriorityBadge priority={c.priority} />
                        </td>
                        <td>
                          <CaseStatusBadge status={c.status} />
                        </td>
                        <td>{c.assignee_email ?? "—"}</td>
                        <td className="text-right tabular-nums">
                          {c.alert_count}
                        </td>
                        <td className="text-right tabular-nums">
                          {c.transaction_count}
                        </td>
                        <td className="whitespace-nowrap">
                          {formatDateTime(c.opened_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
          <div className="flex items-center gap-3 text-sm">
            <Button
              variant="secondary"
              disabled={!list.data.previous}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </Button>
            <span>
              Page {page} · {list.data.count.toLocaleString()} cases
            </span>
            <Button
              variant="secondary"
              disabled={!list.data.next}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </>
      )}
    </section>
  );
}
