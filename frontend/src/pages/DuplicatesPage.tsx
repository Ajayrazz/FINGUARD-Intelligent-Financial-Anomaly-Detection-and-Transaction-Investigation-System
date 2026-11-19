import { PageHero } from "../components/scenes/PageHero";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError, downloadFile } from "../api/client";
import type {
  DuplicateCandidate,
  DuplicateCandidateDetail,
  InvoiceRow,
  MatchClass,
  Paginated,
  ReviewStatus,
} from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { AuthImage } from "../components/duplicates/AuthImage";
import { CLASS_LABEL, STATUS_LABEL } from "../components/duplicates/labels";
import { Button } from "../components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/states";
import { useToast } from "../components/ui/Toast";

const RECORD_FIELDS = [
  "transaction_id",
  "dataset",
  "sender",
  "receiver",
  "vendor",
  "invoice_number",
  "amount",
  "currency",
  "tx_type",
  "invoice_date",
  "occurred_at",
];

function CandidatePanel({
  id,
  onChanged,
}: {
  id: number;
  onChanged: () => void;
}) {
  const { can } = useAuth();
  const toast = useToast();
  const [notes, setNotes] = useState("");
  const q = useQuery({
    queryKey: ["dup-candidate", id],
    queryFn: ({ signal }) =>
      api.get<DuplicateCandidateDetail>(
        `/duplicates/candidates/${id}/`,
        signal,
      ),
  });
  const review = useMutation({
    mutationFn: (decision: ReviewStatus) =>
      api.post(`/duplicates/candidates/${id}/review/`, { decision, notes }),
    onSuccess: () => {
      toast("success", "Review recorded");
      void q.refetch();
      onChanged();
    },
    onError: (e: unknown) =>
      toast("error", e instanceof ApiError ? e.message : "Review failed"),
  });
  if (q.isPending) return <LoadingState />;
  if (q.isError) return <ErrorState message={q.error.message} />;
  const c = q.data;
  const a = c.record_a;
  const b = c.record_b;
  const keys = RECORD_FIELDS.filter(
    (k) => a?.[k] !== undefined || b?.[k] !== undefined,
  );
  const isInvoice = c.kind === "invoice";
  return (
    <div
      role="region"
      aria-label="Candidate details"
      className="mt-4 space-y-3 rounded-md border border-slate-300 p-4"
    >
      <h3 className="font-semibold">
        {CLASS_LABEL[c.match_class]} · score {c.similarity_score.toFixed(1)} /
        100 ·{" "}
        <span className="font-normal">{STATUS_LABEL[c.review_status]}</span>
      </h3>
      <p className="text-xs text-slate-600">
        The score ranks candidates for review. It is evidence, not proof; only a
        reviewer's decision counts.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-300 text-slate-600">
            <tr>
              <th className="py-1">Field</th>
              <th>Record A (#{c.record_a_id})</th>
              <th>Record B (#{c.record_b_id})</th>
            </tr>
          </thead>
          <tbody>
            {keys.map((k) => {
              const same = String(a?.[k]) === String(b?.[k]);
              return (
                <tr key={k} className="border-b border-slate-100">
                  <td className="py-1 text-slate-600">
                    {k.replace(/_/g, " ")}
                  </td>
                  <td className={same ? "" : "font-semibold text-amber-800"}>
                    {String(a?.[k] ?? "—")}
                  </td>
                  <td className={same ? "" : "font-semibold text-amber-800"}>
                    {String(b?.[k] ?? "—")}
                    {!same && <span className="sr-only"> (differs)</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {isInvoice && (
        <div className="grid gap-3 sm:grid-cols-2">
          {a?.document_id && (
            <AuthImage
              path={`/invoices/${a.id}/file/`}
              alt={`Invoice A #${a.id}`}
            />
          )}
          {b?.document_id && (
            <AuthImage
              path={`/invoices/${b.id}/file/`}
              alt={`Invoice B #${b.id}`}
            />
          )}
        </div>
      )}
      <details>
        <summary className="cursor-pointer text-sm font-medium">
          Evidence
        </summary>
        <pre className="mt-1 max-h-64 overflow-auto rounded bg-slate-50 p-2 text-xs">
          {JSON.stringify(c.evidence, null, 2)}
        </pre>
      </details>
      {c.reviewed_by_email && (
        <p className="text-sm">
          Reviewed by {c.reviewed_by_email}
          {c.notes ? `: “${c.notes}”` : ""}
        </p>
      )}
      <div className="flex flex-wrap items-end gap-2">
        {can("duplicates.review") && (
          <>
            <label className="text-sm">
              <span className="block">Notes</span>
              <input
                className="w-64 rounded border border-slate-300 p-1.5"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </label>
            <Button
              disabled={review.isPending}
              onClick={() => review.mutate("confirmed_duplicate")}
            >
              Confirm duplicate
            </Button>
            <Button
              variant="secondary"
              disabled={review.isPending}
              onClick={() => review.mutate("not_duplicate")}
            >
              Not a duplicate
            </Button>
            <Button
              variant="secondary"
              disabled={review.isPending}
              onClick={() => review.mutate("legitimate_repeat")}
            >
              Legitimate repeat
            </Button>
          </>
        )}
        <Button
          variant="secondary"
          onClick={() =>
            void downloadFile(
              `/duplicates/candidates/${id}/report/`,
              `duplicate-candidate-${id}.pdf`,
            ).catch(() => toast("error", "Download failed"))
          }
        >
          PDF report
        </Button>
      </div>
    </div>
  );
}

function CandidatesTab() {
  const qc = useQueryClient();
  const [kind, setKind] = useState("");
  const [cls, setCls] = useState("");
  const [status, setStatus] = useState("pending");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number | null>(null);
  const qs = `page=${page}${kind ? `&kind=${kind}` : ""}${cls ? `&match_class=${cls}` : ""}${status ? `&review_status=${status}` : ""}`;
  const q = useQuery({
    queryKey: ["dup-candidates", qs],
    queryFn: ({ signal }) =>
      api.get<Paginated<DuplicateCandidate>>(
        `/duplicates/candidates/?${qs}`,
        signal,
      ),
  });
  const sel =
    (set: (v: string) => void) => (e: React.ChangeEvent<HTMLSelectElement>) => {
      set(e.target.value);
      setPage(1);
    };
  return (
    <div>
      <div className="flex flex-wrap gap-4 text-sm">
        <label>
          Kind{" "}
          <select
            className="rounded border border-slate-300 p-1"
            value={kind}
            onChange={sel(setKind)}
          >
            <option value="">All</option>
            <option value="transaction">Transactions</option>
            <option value="invoice">Invoices</option>
          </select>
        </label>
        <label>
          Class{" "}
          <select
            className="rounded border border-slate-300 p-1"
            value={cls}
            onChange={sel(setCls)}
          >
            <option value="">All</option>
            {(Object.keys(CLASS_LABEL) as MatchClass[]).map((k) => (
              <option key={k} value={k}>
                {CLASS_LABEL[k]}
              </option>
            ))}
          </select>
        </label>
        <label>
          Review{" "}
          <select
            className="rounded border border-slate-300 p-1"
            value={status}
            onChange={sel(setStatus)}
          >
            <option value="">All</option>
            {(Object.keys(STATUS_LABEL) as ReviewStatus[]).map((k) => (
              <option key={k} value={k}>
                {STATUS_LABEL[k]}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="mt-3">
        {q.isPending && <LoadingState />}
        {q.isError && (
          <ErrorState
            message={q.error.message}
            onRetry={() => void q.refetch()}
          />
        )}
        {q.data && q.data.results.length === 0 && (
          <EmptyState
            title="No candidates match these filters"
            hint="Run a scan or upload invoices to find some."
          />
        )}
        {q.data && q.data.results.length > 0 && (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-300 text-slate-600">
                  <tr>
                    <th className="py-1">#</th>
                    <th>Kind</th>
                    <th>Class</th>
                    <th className="text-right">Score</th>
                    <th>Records</th>
                    <th>Review</th>
                  </tr>
                </thead>
                <tbody>
                  {q.data.results.map((c) => (
                    <tr
                      key={c.id}
                      className={`border-b border-slate-100 ${selected === c.id ? "bg-slate-100" : ""}`}
                    >
                      <td className="py-1">
                        <button
                          className="text-blue-700 hover:underline"
                          onClick={() => setSelected(c.id)}
                        >
                          {c.id}
                        </button>
                      </td>
                      <td className="capitalize">{c.kind}</td>
                      <td>{CLASS_LABEL[c.match_class]}</td>
                      <td className="text-right tabular-nums">
                        {c.similarity_score.toFixed(1)}
                      </td>
                      <td>
                        #{c.record_a_id} ~ #{c.record_b_id}
                      </td>
                      <td>{STATUS_LABEL[c.review_status]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3 flex items-center gap-3 text-sm">
              <Button
                variant="secondary"
                disabled={!q.data.previous}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>
              <span>
                Page {page} · {q.data.count} candidates
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
      {selected && (
        <CandidatePanel
          key={selected}
          id={selected}
          onChanged={() =>
            void qc.invalidateQueries({ queryKey: ["dup-candidates"] })
          }
        />
      )}
    </div>
  );
}

const FIELD_ROWS: {
  key:
    "vendor_name" | "invoice_number" | "amount" | "currency" | "invoice_date";
  label: string;
  ocr: string;
  type?: string;
}[] = [
  { key: "vendor_name", label: "Vendor", ocr: "vendor" },
  { key: "invoice_number", label: "Invoice number", ocr: "invoice_number" },
  { key: "invoice_date", label: "Date (YYYY-MM-DD)", ocr: "invoice_date" },
  { key: "amount", label: "Amount", ocr: "amount" },
  { key: "currency", label: "Currency", ocr: "currency" },
];

function InvoicePanel({
  inv,
  onSaved,
}: {
  inv: InvoiceRow;
  onSaved: () => void;
}) {
  const { can } = useAuth();
  const toast = useToast();
  const [vals, setVals] = useState<Record<string, string>>({
    vendor_name: inv.vendor_name,
    invoice_number: inv.invoice_number,
    amount: inv.amount ?? "",
    currency: inv.currency,
    invoice_date: inv.invoice_date ?? "",
  });
  const save = useMutation({
    mutationFn: () =>
      api.patch<InvoiceRow>(`/invoices/${inv.id}/fields/`, {
        ...vals,
        amount: vals.amount === "" ? null : vals.amount,
        invoice_date: vals.invoice_date === "" ? null : vals.invoice_date,
      }),
    onSuccess: () => {
      toast("success", "Fields verified and saved");
      onSaved();
    },
    onError: (e: unknown) =>
      toast(
        "error",
        e instanceof ApiError
          ? Object.values(e.details).flat().join(" ") || e.message
          : "Save failed",
      ),
  });
  return (
    <div
      role="region"
      aria-label="Invoice details"
      className="mt-4 grid gap-4 rounded-md border border-slate-300 p-4 sm:grid-cols-2"
    >
      <div>
        {inv.document_id && (
          <AuthImage
            path={`/invoices/${inv.id}/file/`}
            alt={`Invoice ${inv.id}`}
          />
        )}
      </div>
      <div>
        <h3 className="font-semibold">
          Extracted fields{" "}
          {inv.verified_by_email ? (
            <span className="font-normal text-green-800">
              · verified by {inv.verified_by_email}
            </span>
          ) : (
            <span className="font-normal text-amber-800">
              · not yet verified by a person
            </span>
          )}
        </h3>
        {inv.status === "failed" && (
          <p role="alert" className="text-sm text-red-700">
            {inv.error_message}
          </p>
        )}
        <div className="overflow-x-auto">
          <table className="mt-1 w-full text-sm">
            <tbody>
              {FIELD_ROWS.map((f) => (
                <tr key={f.key}>
                  <td className="py-1 pr-2 text-slate-600">
                    <label htmlFor={`f-${f.key}`}>{f.label}</label>
                  </td>
                  <td>
                    <input
                      id={`f-${f.key}`}
                      className="w-full rounded border border-slate-300 p-1"
                      value={vals[f.key] ?? ""}
                      disabled={!can("duplicates.review")}
                      onChange={(e) =>
                        setVals({ ...vals, [f.key]: e.target.value })
                      }
                    />
                  </td>
                  <td className="pl-2 text-xs text-slate-500">
                    {inv.field_confidence[f.ocr] !== undefined
                      ? `OCR ${inv.field_confidence[f.ocr]!.toFixed(0)}%`
                      : "not found"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {can("duplicates.review") && (
          <Button
            className="mt-2"
            disabled={save.isPending}
            onClick={() => save.mutate()}
          >
            Verify and save
          </Button>
        )}
      </div>
    </div>
  );
}

function InvoicesTab() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const [selected, setSelected] = useState<number | null>(null);
  const q = useQuery({
    queryKey: ["invoices"],
    queryFn: ({ signal }) =>
      api.get<Paginated<InvoiceRow>>("/invoices/", signal),
    refetchInterval: (query) =>
      query.state.data?.results.some(
        (i) => i.status === "uploaded" || i.status === "ocr_done",
      )
        ? 2500
        : false,
  });
  const upload = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return api.post<InvoiceRow>("/invoices/upload/", fd);
    },
    onSuccess: () => {
      toast("success", "Uploaded; reading the invoice…");
      void qc.invalidateQueries({ queryKey: ["invoices"] });
    },
    onError: (e: unknown) =>
      toast("error", e instanceof ApiError ? e.message : "Upload failed"),
  });
  const current = q.data?.results.find((i) => i.id === selected);
  return (
    <div>
      {can("duplicates.create") && (
        <label className="block text-sm">
          <span className="font-medium">
            Upload an invoice (PNG, JPEG or PDF, up to 10 MB)
          </span>
          <input
            className="mt-1 block"
            type="file"
            accept="image/png,image/jpeg,application/pdf"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) upload.mutate(f);
              e.target.value = "";
            }}
          />
        </label>
      )}
      <div className="mt-3">
        {q.isPending && <LoadingState />}
        {q.isError && (
          <ErrorState
            message={q.error.message}
            onRetry={() => void q.refetch()}
          />
        )}
        {q.data && q.data.results.length === 0 && (
          <EmptyState
            title="No invoices yet"
            hint={can("duplicates.create") ? "Upload one above." : undefined}
          />
        )}
        {q.data && q.data.results.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-300 text-slate-600">
                <tr>
                  <th className="py-1">#</th>
                  <th>File</th>
                  <th>Vendor</th>
                  <th>Number</th>
                  <th className="text-right">Amount</th>
                  <th>Date</th>
                  <th>Status</th>
                  <th className="text-right">OCR</th>
                </tr>
              </thead>
              <tbody>
                {q.data.results.map((i) => (
                  <tr
                    key={i.id}
                    className={`border-b border-slate-100 ${selected === i.id ? "bg-slate-100" : ""}`}
                  >
                    <td className="py-1">
                      <button
                        className="text-blue-700 hover:underline"
                        onClick={() => setSelected(i.id)}
                      >
                        {i.id}
                      </button>
                    </td>
                    <td>{i.original_name}</td>
                    <td>{i.vendor_name || "—"}</td>
                    <td>{i.invoice_number || "—"}</td>
                    <td className="text-right tabular-nums">
                      {i.amount ?? "—"}
                    </td>
                    <td>{i.invoice_date ?? "—"}</td>
                    <td className="capitalize">{i.status.replace("_", " ")}</td>
                    <td className="text-right tabular-nums">
                      {i.ocr_confidence !== null ? `${i.ocr_confidence}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {current && (
        <InvoicePanel
          key={`${current.id}-${current.verified_at}`}
          inv={current}
          onSaved={() => void qc.invalidateQueries({ queryKey: ["invoices"] })}
        />
      )}
    </div>
  );
}

export default function DuplicatesPage() {
  const { can } = useAuth();
  const toast = useToast();
  const qc = useQueryClient();
  const [tab, setTab] = useState<"candidates" | "invoices">("candidates");
  const scan = useMutation({
    mutationFn: (kind: "invoice" | "transaction") =>
      api.post("/duplicates/scan/", { kind }),
    onSuccess: () => {
      toast("success", "Scan started");
      setTimeout(
        () => void qc.invalidateQueries({ queryKey: ["dup-candidates"] }),
        4000,
      );
    },
    onError: (e: unknown) =>
      toast("error", e instanceof ApiError ? e.message : "Scan failed"),
  });
  return (
    <section className="space-y-4">
      <PageHero
        eyebrow="Detect"
        title="Duplicate Detection"
        tone="amber"
        scene="merge"
      />
      <p className="text-sm text-slate-600">
        Repeated payments and duplicate invoices. Review each candidate before
        it counts: scores are evidence, not proof.
      </p>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div role="tablist" className="flex gap-2">
          {(["candidates", "invoices"] as const).map((t) => (
            <button
              key={t}
              role="tab"
              aria-selected={tab === t}
              onClick={() => setTab(t)}
              className={`rounded-md px-3 py-1 text-sm capitalize ${tab === t ? "bg-slate-900 text-white" : "border border-slate-300"}`}
            >
              {t}
            </button>
          ))}
        </div>
        {can("duplicates.run") && (
          <div className="flex gap-2">
            <Button
              variant="secondary"
              disabled={scan.isPending}
              onClick={() => scan.mutate("transaction")}
            >
              Scan transactions
            </Button>
            <Button
              variant="secondary"
              disabled={scan.isPending}
              onClick={() => scan.mutate("invoice")}
            >
              Scan invoices
            </Button>
          </div>
        )}
      </div>
      {tab === "candidates" ? <CandidatesTab /> : <InvoicesTab />}
    </section>
  );
}
