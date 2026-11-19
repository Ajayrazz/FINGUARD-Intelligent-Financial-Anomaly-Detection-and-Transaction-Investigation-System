import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ImportJob, Me } from "../api/types";
import { AuthContext, type AuthValue } from "../auth/AuthContext";
import { ToastProvider } from "../components/ui/Toast";
import { FIELDS, mappingProblems, toApiMapping } from "../lib/importMapping";
import ImportDetailPage from "./ImportDetailPage";
import ImportsPage from "./ImportsPage";
import ImportWizardPage from "./ImportWizardPage";

afterEach(() => vi.unstubAllGlobals());

const job = (over: Partial<ImportJob> = {}): ImportJob => ({
  id: 5,
  dataset: 1,
  dataset_name: "MOCK ds",
  source: "file",
  file_name: "tx.csv",
  file_size: 10,
  file_sha256: "abc",
  status: "completed",
  dup_policy: "reject",
  rows_total: 100,
  rows_processed: 100,
  rows_accepted: 97,
  rows_rejected: 3,
  rows_duplicate: 0,
  error_summary: "",
  created_by_email: "a@example.com",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: new Date().toISOString(),
  started_at: "2026-01-01T00:00:01Z",
  finished_at: "2026-01-01T00:00:09Z",
  ...over,
});
const me = (permissions: string[]): Me => ({
  id: 1,
  email: "a@example.com",
  full_name: "A",
  role: "financial_analyst",
  role_label: "Analyst",
  is_active: true,
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
  ({ ok: true, status: 200, json: async () => body }) as Response;

function renderAt(
  path: string,
  routePath: string,
  element: React.ReactNode,
  perms: string[],
  fetchMock: ReturnType<typeof vi.fn>,
) {
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal(
    "WebSocket",
    class {
      close() {}
    },
  );
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <AuthContext.Provider value={auth(perms)}>
          <MemoryRouter initialEntries={[path]}>
            <Routes>
              <Route path={routePath} element={element} />
            </Routes>
          </MemoryRouter>
        </AuthContext.Provider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("mapping helpers", () => {
  it("requires sender, amount and a time reference", () => {
    expect(mappingProblems({ a: "sender" }).length).toBe(2);
    expect(mappingProblems({ a: "sender", b: "amount", c: "step" })).toEqual(
      [],
    );
    expect(
      mappingProblems({ a: "sender", b: "amount", c: "occurred_at" }),
    ).toEqual([]);
  });
  it("flags two columns mapped to the same field", () => {
    expect(
      mappingProblems({
        a: "sender",
        b: "sender",
        c: "amount",
        d: "step",
      }).join(" "),
    ).toContain("More than one");
  });
  it("serialises only mapped columns and non-empty options", () => {
    const json = JSON.parse(
      toApiMapping(
        { a: "sender", b: "" },
        { merchant_prefix: "M", customer_prefix: "" },
      ),
    );
    expect(json).toEqual({
      columns: { a: "sender" },
      options: { merchant_prefix: "M" },
    });
  });
  it("exposes every canonical field exactly once", () => {
    expect(new Set(FIELDS.map((f) => f.key)).size).toBe(FIELDS.length);
  });
});

describe("ImportsPage", () => {
  it("lists imports with status and counts, and offers New import only with permission", async () => {
    const fetchMock = vi.fn(async () =>
      ok({
        count: 1,
        next: null,
        previous: null,
        results: [job({ status: "completed_with_errors" })],
      }),
    );
    renderAt(
      "/imports",
      "/imports",
      <ImportsPage />,
      ["imports.read", "imports.create"],
      fetchMock,
    );
    expect(
      await screen.findByText("Completed with errors"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "New import" }),
    ).toBeInTheDocument();
  });
  it("hides New import for read-only roles and shows the empty state", async () => {
    renderAt(
      "/imports",
      "/imports",
      <ImportsPage />,
      ["imports.read"],
      vi.fn(async () =>
        ok({ count: 0, next: null, previous: null, results: [] }),
      ),
    );
    expect(await screen.findByText("No imports yet")).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "New import" }),
    ).not.toBeInTheDocument();
  });
});

describe("ImportDetailPage", () => {
  const route = "/imports/:id";
  it("shows progress, counters and the rejected rows with a download button", async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.includes("/errors/")
        ? ok({
            count: 1,
            next: null,
            previous: null,
            results: [
              {
                id: 1,
                row_number: 7,
                error_code: "invalid_amount",
                message: "Amount is not a number",
                raw: {},
              },
            ],
          })
        : ok(job()),
    );
    renderAt(
      "/imports/5",
      route,
      <ImportDetailPage />,
      ["imports.read", "imports.create"],
      fetchMock,
    );
    expect(await screen.findByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "100",
    );
    expect(await screen.findByText("invalid_amount")).toBeInTheDocument();
    expect(screen.getByText("97")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Download CSV" }),
    ).toBeInTheDocument();
  });
  it("offers resume for failed jobs and posts to the resume endpoint", async () => {
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) =>
      init?.method === "POST"
        ? ok(job({ status: "pending" }))
        : ok(
            job({
              status: "failed",
              rows_rejected: 0,
              rows_processed: 50,
              error_summary: "RuntimeError: boom",
            }),
          ),
    );
    renderAt(
      "/imports/5",
      route,
      <ImportDetailPage />,
      ["imports.read", "imports.create"],
      fetchMock,
    );
    expect(await screen.findByText("RuntimeError: boom")).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: /Resume from row 50/ }),
    );
    expect(
      fetchMock.mock.calls.some(
        (c) =>
          String(c[0]).endsWith("/imports/5/resume/") &&
          (c[1] as RequestInit).method === "POST",
      ),
    ).toBe(true);
  });
  it("does not show actions to roles without imports.create", async () => {
    renderAt(
      "/imports/5",
      route,
      <ImportDetailPage />,
      ["imports.read"],
      vi.fn(async () => ok(job({ status: "failed", rows_rejected: 0 }))),
    );
    await screen.findByText("Import #5");
    expect(
      screen.queryByRole("button", { name: /Resume/ }),
    ).not.toBeInTheDocument();
  });
  it("offers a forced resume when an active job has made no progress for a minute", async () => {
    const stale = new Date(Date.now() - 5 * 60_000).toISOString();
    renderAt(
      "/imports/5",
      route,
      <ImportDetailPage />,
      ["imports.read", "imports.create"],
      vi.fn(async () =>
        ok(job({ status: "running", rows_rejected: 0, updated_at: stale })),
      ),
    );
    expect(
      await screen.findByRole("button", {
        name: /No progress for over a minute/,
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Cancel" }),
    ).not.toBeInTheDocument();
  });
});

describe("ImportWizardPage", () => {
  const previewBody = {
    file_name: "p.csv",
    format: "csv",
    columns: ["id", "who", "amt"],
    rows: [["1", "C1", "10"]],
    estimated_rows: 1,
    presets: ["paysim"],
    suggested_mapping: {
      columns: { id: "transaction_id" },
      options: {},
      preset: null,
    },
  };
  it("blocks the import until required fields are mapped, then enables it", async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.endsWith("/datasets/")
        ? ok([
            {
              id: 1,
              name: "DS",
              source_type: "custom",
              is_synthetic: true,
              description: "",
              row_count: 0,
              created_at: "",
            },
          ])
        : ok(previewBody),
    );
    renderAt(
      "/imports/new",
      "/imports/new",
      <ImportWizardPage />,
      ["imports.create", "datasets.create"],
      fetchMock,
    );
    const input = await screen.findByLabelText(/File \(/);
    await userEvent.upload(
      input,
      new File(["id,who,amt\n1,C1,10\n"], "p.csv", { type: "text/csv" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Preview file" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Sender account",
    );
    expect(screen.getByRole("button", { name: "Start import" })).toBeDisabled();
    await userEvent.selectOptions(
      screen.getByLabelText("Target for who"),
      "sender",
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Target for amt"),
      "amount",
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Target for id"),
      "step",
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start import" })).toBeEnabled();
  });
  it("tells users without imports.create that they cannot import", async () => {
    renderAt(
      "/imports/new",
      "/imports/new",
      <ImportWizardPage />,
      [],
      vi.fn(async () => ok([])),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "cannot start imports",
    );
  });
});
