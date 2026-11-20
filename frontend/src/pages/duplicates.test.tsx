import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type {
  DuplicateCandidate,
  DuplicateCandidateDetail,
  InvoiceRow,
  Me,
} from "../api/types";
import { AuthContext, type AuthValue } from "../auth/AuthContext";
import { ToastProvider } from "../components/ui/Toast";
import DuplicatesPage from "./DuplicatesPage";

afterEach(() => vi.unstubAllGlobals());

const me = (permissions: string[]): Me => ({
  id: 1,
  email: "a@example.com",
  full_name: "A",
  role: "financial_analyst",
  role_label: "Analyst",
  is_active: true,
  approval_status: "approved",
  email_verified: true,
  last_login: null,
  created_at: "2026-01-01T00:00:00Z",
  permissions,
});
const auth = (permissions: string[]): AuthValue => ({
  status: "authenticated",
  user: me(permissions),
  login: vi.fn(),
  logout: vi.fn(),
  can: (p) => permissions.includes(p),
});
const ok = (body: unknown) =>
  ({
    ok: true,
    status: 200,
    json: async () => body,
    blob: async () => new Blob(["x"], { type: "image/png" }),
  }) as Response;

function renderPage(perms: string[], fetchMock: ReturnType<typeof vi.fn>) {
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal(
    "URL",
    Object.assign(URL, {
      createObjectURL: () => "blob:x",
      revokeObjectURL: () => undefined,
    }),
  );
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <AuthContext.Provider value={auth(perms)}>
          <MemoryRouter>
            <DuplicatesPage />
          </MemoryRouter>
        </AuthContext.Provider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const cand = (over: Partial<DuplicateCandidate> = {}): DuplicateCandidate => ({
  id: 7,
  kind: "transaction",
  record_a_type: "transaction",
  record_a_id: 1,
  record_b_type: "transaction",
  record_b_id: 2,
  match_class: "strong_similar",
  similarity_score: 96.5,
  review_status: "pending",
  reviewed_by_email: null,
  reviewed_at: null,
  notes: "",
  created_at: "2026-01-01T00:00:00Z",
  ...over,
});
const detail = (
  over: Partial<DuplicateCandidateDetail> = {},
): DuplicateCandidateDetail => ({
  ...cand(),
  evidence: { gap_seconds: 600 },
  record_a: {
    type: "transaction",
    id: 1,
    transaction_id: "T1",
    sender: "C1",
    receiver: "M1",
    amount: "40000.00",
    tx_type: "PAYMENT",
    occurred_at: "2026-01-01T10:00:00Z",
    dataset: "d",
  },
  record_b: {
    type: "transaction",
    id: 2,
    transaction_id: "T2",
    sender: "C1",
    receiver: "M1",
    amount: "40000.00",
    tx_type: "PAYMENT",
    occurred_at: "2026-01-01T10:10:00Z",
    dataset: "d",
  },
  ...over,
});

const handler = (
  opts: {
    detail?: DuplicateCandidateDetail;
    onReview?: (b: unknown) => void;
  } = {},
) =>
  vi.fn(async (url: string, init?: RequestInit) => {
    if (url.includes("/review/")) {
      opts.onReview?.(JSON.parse(String(init?.body)));
      return ok(opts.detail ?? detail());
    }
    if (url.match(/candidates\/\d+\/$/)) return ok(opts.detail ?? detail());
    if (url.includes("/duplicates/candidates/"))
      return ok({ count: 1, next: null, previous: null, results: [cand()] });
    return ok({ count: 0, next: null, previous: null, results: [] });
  });

describe("DuplicatesPage", () => {
  // the Table view is the accessible fallback these tests exercise
  beforeEach(() => {
    localStorage.setItem("fg-view-dup-cands", "table");
    localStorage.setItem("fg-view-dup-invoices", "table");
  });
  it("lists candidates with class and score, and shows differing fields in a side-by-side comparison", async () => {
    renderPage(["duplicates.read"], handler());
    expect(
      await screen.findByRole("cell", { name: "Strong match" }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "7" }));
    const panel = await screen.findByRole("region", {
      name: /candidate details/i,
    });
    expect(panel).toHaveTextContent("Record A (#1)");
    expect(panel).toHaveTextContent("T1");
    expect(panel).toHaveTextContent(/evidence, not proof/i);
    expect(
      screen.queryByRole("button", { name: /confirm duplicate/i }),
    ).not.toBeInTheDocument(); // read-only role cannot decide
  });
  it("records a human decision with notes for a reviewer", async () => {
    const reviews: unknown[] = [];
    renderPage(
      ["duplicates.read", "duplicates.review"],
      handler({ onReview: (b) => reviews.push(b) }),
    );
    await userEvent.click(await screen.findByRole("button", { name: "7" }));
    await userEvent.type(
      await screen.findByLabelText("Notes"),
      "same purchase order",
    );
    await userEvent.click(
      screen.getByRole("button", { name: /confirm duplicate/i }),
    );
    expect(reviews).toEqual([
      { decision: "confirmed_duplicate", notes: "same purchase order" },
    ]);
  });
  it("shows who reviewed an already-reviewed candidate", async () => {
    const d = detail({
      review_status: "not_duplicate",
      reviewed_by_email: "r@example.com",
      notes: "two instalments",
    });
    renderPage(["duplicates.read"], handler({ detail: d }));
    await userEvent.click(await screen.findByRole("button", { name: "7" }));
    expect(
      await screen.findByText(/Reviewed by r@example.com/),
    ).toHaveTextContent("two instalments");
  });
});

const invoice = (over: Partial<InvoiceRow> = {}): InvoiceRow => ({
  id: 4,
  document_id: 9,
  original_name: "inv.png",
  status: "needs_review",
  ocr_confidence: 91.2,
  error_message: "",
  vendor_name: "Acme Supplies",
  invoice_number: "INV-1",
  amount: "1416.00",
  currency: "INR",
  invoice_date: "2026-03-12",
  extracted_fields: {},
  field_confidence: { vendor: 96, invoice_number: 80 },
  verified_by_email: null,
  verified_at: null,
  created_at: "2026-03-12T00:00:00Z",
  ...over,
});

describe("Invoices tab", () => {
  const invFetch = (patches: unknown[] = []) =>
    vi.fn(async (url: string, init?: RequestInit) => {
      if (url.includes("/fields/")) {
        patches.push(JSON.parse(String(init?.body)));
        return ok(invoice({ verified_by_email: "a@example.com" }));
      }
      if (url.includes("/file/")) return ok({});
      if (url.includes("/invoices/"))
        return ok({
          count: 1,
          next: null,
          previous: null,
          results: [invoice()],
        });
      return ok({ count: 0, next: null, previous: null, results: [] });
    });
  it("shows OCR confidence per field, says the fields are unverified, and saves a human correction", async () => {
    const patches: unknown[] = [];
    renderPage(
      ["duplicates.read", "duplicates.create", "duplicates.review"],
      invFetch(patches),
    );
    await userEvent.click(await screen.findByRole("tab", { name: "invoices" }));
    await userEvent.click(await screen.findByRole("button", { name: "4" }));
    expect(
      await screen.findByText(/not yet verified by a person/),
    ).toBeInTheDocument();
    expect(screen.getByText("OCR 96%")).toBeInTheDocument();
    expect(screen.getAllByText("not found").length).toBe(3); // a field the OCR did not find is labelled, not blank
    const number = screen.getByLabelText("Invoice number");
    await userEvent.clear(number);
    await userEvent.type(number, "INV-2");
    await userEvent.click(
      screen.getByRole("button", { name: /verify and save/i }),
    );
    expect(patches[0]).toMatchObject({
      invoice_number: "INV-2",
      vendor_name: "Acme Supplies",
      amount: "1416.00",
    });
  });
  it("hides upload and editing without the permissions", async () => {
    renderPage(["duplicates.read"], invFetch());
    await userEvent.click(await screen.findByRole("tab", { name: "invoices" }));
    expect(
      screen.queryByLabelText(/upload an invoice/i),
    ).not.toBeInTheDocument();
    await userEvent.click(await screen.findByRole("button", { name: "4" }));
    expect(await screen.findByLabelText("Vendor")).toBeDisabled();
    expect(
      screen.queryByRole("button", { name: /verify and save/i }),
    ).not.toBeInTheDocument();
  });
});
