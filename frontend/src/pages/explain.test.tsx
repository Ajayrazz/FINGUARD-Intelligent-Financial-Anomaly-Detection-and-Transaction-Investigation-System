import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Explanation, Me } from "../api/types";
import { AuthContext, type AuthValue } from "../auth/AuthContext";
import { AttributionChart } from "../components/explain/AttributionChart";
import { ExplanationPanel } from "../components/explain/ExplanationPanel";
import { ToastProvider } from "../components/ui/Toast";

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
  ({ ok: true, status: 200, json: async () => body }) as Response;

function renderPanel(perms: string[], fetchMock: ReturnType<typeof vi.fn>) {
  vi.stubGlobal("fetch", fetchMock);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <AuthContext.Provider value={auth(perms)}>
          <ExplanationPanel transactionId={9} />
        </AuthContext.Provider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const features = [
  {
    name: "log_amount",
    label: "transaction amount",
    value: 10.6,
    display: "40,000.00",
    contribution: 2.1,
  },
  {
    name: "receiver_is_merchant",
    label: "receiver is a merchant account",
    value: 0,
    display: "no",
    contribution: -0.4,
  },
];
const exp = (
  method: Explanation["method"],
  over: Partial<Explanation> = {},
  payload: Explanation["payload"] = {},
): Explanation => ({
  id: 1,
  transaction: 9,
  method,
  prediction: 5,
  assessment: null,
  model_version: 3,
  model_version_name: "xgb_paysim_core paysim-s42-abc",
  payload,
  narrative: `${method} narrative`,
  generator_version: "x1",
  generated_at: "2026-01-02T00:00:00Z",
  current: true,
  stale_reason: "",
  note: "",
  disclaimer: "",
  ...over,
});
const full = (over: Partial<Explanation> = {}): Explanation[] => [
  exp(
    "shap",
    { narrative: "The XGBoost model gave a score of 0.91.", ...over },
    { features },
  ),
  exp(
    "lime",
    { id: 2, ...over },
    {
      features,
      note: "LIME samples randomly: weights vary a little between runs.",
      background: "500 transactions sampled",
    },
  ),
  exp(
    "summary",
    { id: 3, ...over },
    {
      sections: [
        { title: "Prediction", text: "P-text" },
        { title: "Indicator", text: "I-text" },
        { title: "Evidence", text: "E-text" },
        { title: "Assessment", text: "A-text" },
        { title: "Outcome", text: "No analyst outcome has been recorded yet." },
      ],
      timeline: [
        {
          transaction_id: 9,
          external_id: "T9",
          occurred_at: "2026-01-01T10:00:00Z",
          amount: "40000.00",
          tx_type: "PAYMENT",
          sender: "C1",
          receiver: "N1",
          is_this_transaction: true,
        },
      ],
    },
  ),
];

describe("ExplanationPanel", () => {
  it("shows the five sections, the exact model version, contribution bars with values, LIME caveat and the non-proof note", async () => {
    renderPanel(
      ["explain.read"],
      vi.fn(async () => ok(full())),
    );
    expect(await screen.findByText("Prediction")).toBeInTheDocument();
    for (const t of ["Indicator", "Evidence", "Assessment", "Outcome"])
      expect(screen.getByText(t)).toBeInTheDocument();
    expect(
      screen.getByText(/xgb_paysim_core paysim-s42-abc/),
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole("list", { name: /feature contributions/i }),
    ).toHaveLength(2);
    expect(screen.getAllByText(/raises \+2.100/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/lowers -0.400/).length).toBeGreaterThan(0);
    expect(
      screen.getByText(/weights vary a little between runs/),
    ).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(
      /not proof of wrongdoing/,
    );
    expect(
      screen.queryByRole("button", { name: /generate|regenerate/i }),
    ).not.toBeInTheDocument();
  });
  it("warns loudly when an explanation was built from a superseded prediction", async () => {
    renderPanel(
      ["explain.read", "explain.generate"],
      vi.fn(async () =>
        ok(
          full({
            current: false,
            stale_reason:
              "The same model version (xgb_x) has been run again since; this explains an older prediction.",
          }),
        ),
      ),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /Out of date: .*run again since/,
    );
    expect(
      screen.getByRole("button", { name: /regenerate/i }),
    ).toBeInTheDocument();
  });
  it("offers generation when none exists and reports why a method was skipped", async () => {
    let posted = 0;
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        posted += 1;
        return ok({
          id: 4,
          status: "pending",
          result: { created: [], skipped: {} },
          error_message: "",
        });
      }
      if (url.includes("/explanation-jobs/"))
        return ok({
          id: 4,
          status: "succeeded",
          result: {
            created: ["summary"],
            skipped: {
              shap: "no detection prediction exists for this transaction",
            },
          },
          error_message: "",
        });
      return ok([]);
    });
    renderPanel(["explain.read", "explain.generate"], fetchMock);
    expect(
      await screen.findByText(/No explanation has been generated/),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: /generate explanation/i }),
    );
    expect(
      await screen.findByText(/not produced: no detection prediction exists/),
    ).toBeInTheDocument();
    expect(posted).toBe(1);
  });
  it("shows a failed job message", async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST")
        return ok({
          id: 4,
          status: "pending",
          result: { created: [], skipped: {} },
          error_message: "",
        });
      if (url.includes("/explanation-jobs/"))
        return ok({
          id: 4,
          status: "failed",
          result: { created: [], skipped: {} },
          error_message: "Unexpected error.",
        });
      return ok([]);
    });
    renderPanel(["explain.read", "explain.generate"], fetchMock);
    await userEvent.click(
      await screen.findByRole("button", { name: /generate explanation/i }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /Explanation failed: Unexpected error/,
    );
  });
});

it("mentions a later run by another model without calling the explanation out of date", async () => {
  renderPanel(
    ["explain.read"],
    vi.fn(async () =>
      ok(
        full({
          note: "A later run by another model (rf_x) also scored this transaction; this explains xgb_x.",
        }),
      ),
    ),
  );
  expect(
    await screen.findByText(/later run by another model \(rf_x\)/),
  ).toBeInTheDocument();
  expect(screen.queryByText(/Out of date/)).not.toBeInTheDocument();
});

describe("AttributionChart", () => {
  it("prints direction and value for each bar so colour is never the only cue", () => {
    render(<AttributionChart rows={features} />);
    expect(screen.getByText(/raises \+2.100/)).toBeInTheDocument();
    expect(screen.getByText(/lowers -0.400/)).toBeInTheDocument();
    expect(screen.getByText("transaction amount")).toBeInTheDocument();
  });
});
