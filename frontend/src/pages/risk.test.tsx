import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  Me,
  RiskAssessment,
  RiskAssessmentDetail,
  RiskComponent,
  RiskConfig,
  RiskRun,
} from "../api/types";
import { AuthContext, type AuthValue } from "../auth/AuthContext";
import { RiskPanel } from "../components/risk/RiskPanel";
import { ToastProvider } from "../components/ui/Toast";
import RiskAnalysisPage from "./RiskAnalysisPage";

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
const notFound = () =>
  ({
    ok: false,
    status: 404,
    statusText: "Not Found",
    json: async () => ({
      error: {
        code: "not_found",
        message: "This transaction has not been scored.",
      },
    }),
  }) as Response;

function renderUi(
  ui: React.ReactNode,
  perms: string[],
  fetchMock: ReturnType<typeof vi.fn>,
) {
  vi.stubGlobal("fetch", fetchMock);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <AuthContext.Provider value={auth(perms)}>
          <MemoryRouter>{ui}</MemoryRouter>
        </AuthContext.Provider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const comp = (over: Partial<RiskComponent> = {}): RiskComponent => ({
  available: true,
  value: 70,
  reason: "",
  source: {},
  weight: 0.2,
  contribution: 14,
  imputed: false,
  ...over,
});
const detail = (
  over: Partial<RiskAssessmentDetail> = {},
): RiskAssessmentDetail => ({
  id: 5,
  transaction: 9,
  external_id: "T9",
  amount: "40000.00",
  tx_type: "PAYMENT",
  occurred_at: "2026-01-01T00:00:00Z",
  account: 3,
  account_ref: "C1",
  overall_score: 71.2,
  category: "high",
  weight_coverage: 0.55,
  low_coverage: false,
  capped: false,
  policy: "renormalize",
  config_version: 2,
  run: 1,
  component_values: {},
  computed_at: "2026-01-02T00:00:00Z",
  algorithm_version: "r1",
  detection_run: 1,
  behavior_run: null,
  graph_snapshot: 2,
  components: {
    A: comp({ value: 88, weight: 0.25, contribution: 40 }),
    B: comp({
      available: false,
      value: null,
      reason: "cold start: 0 prior transactions, 5 needed",
      weight: 0.2,
      contribution: null,
    }),
    G: comp({ value: 0, weight: 0.2, contribution: 0 }),
    F: comp({
      available: false,
      value: null,
      reason: "cold start",
      weight: 0.15,
      contribution: null,
    }),
    D: comp({ value: 30, weight: 0.1, contribution: 5 }),
    H: comp({
      available: false,
      value: null,
      reason: "no earlier transactions for either account",
      weight: 0.1,
      contribution: null,
    }),
  },
  ...over,
});

describe("RiskPanel", () => {
  it("shows the score, coverage and a reason for every unavailable component instead of a zero", async () => {
    renderUi(
      <RiskPanel transactionId={9} />,
      ["risk.read"],
      vi.fn(async () => ok(detail())),
    );
    expect(await screen.findByText("71.2")).toBeInTheDocument();
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.getByText(/signal coverage 55%/)).toBeInTheDocument();
    expect(
      screen.getByText(/Unavailable — cold start: 0 prior transactions/),
    ).toBeInTheDocument();
    expect(screen.getAllByText("excluded")).toHaveLength(3);
    expect(
      screen.getByText(/not a finding of wrongdoing/i),
    ).toBeInTheDocument();
  });
  it("explains a low-coverage cap and an unscored transaction", async () => {
    const { unmount } = renderUi(
      <RiskPanel transactionId={9} />,
      ["risk.read"],
      vi.fn(async () =>
        ok(
          detail({
            low_coverage: true,
            capped: true,
            category: "high",
            weight_coverage: 0.25,
          }),
        ),
      ),
    );
    expect(await screen.findByRole("note")).toHaveTextContent(
      /held at High until an analyst reviews/,
    );
    unmount();
    renderUi(
      <RiskPanel transactionId={9} />,
      ["risk.read"],
      vi.fn(async () =>
        ok(
          detail({
            overall_score: null,
            category: "unscored",
            policy: "strict",
          }),
        ),
      ),
    );
    expect(
      await screen.findByText(/strict policy refuses to guess/),
    ).toBeInTheDocument();
  });
  it("says a transaction has not been scored when the API returns 404", async () => {
    renderUi(
      <RiskPanel transactionId={9} />,
      ["risk.read"],
      vi.fn(async () => notFound()),
    );
    expect(
      await screen.findByText(/has not been scored yet/),
    ).toBeInTheDocument();
  });
});

const cfg = (over: Partial<RiskConfig> = {}): RiskConfig => ({
  id: 1,
  version: 1,
  weights: { A: 0.25, B: 0.2, G: 0.2, F: 0.15, D: 0.1, H: 0.1 },
  thresholds: { medium: 30, high: 60, critical: 80 },
  missing_signal_policy: "renormalize",
  min_coverage: 0.5,
  model_version: null,
  model_version_name: null,
  is_active: true,
  source: "default",
  notes: "",
  created_by_email: null,
  created_at: "2026-01-01T00:00:00Z",
  used_by_assessments: false,
  ...over,
});
const run: RiskRun = {
  id: 1,
  dataset: 2,
  dataset_name: "DEMO",
  config: 1,
  config_version: 1,
  status: "succeeded",
  params: {},
  rows_total: 100,
  rows_scored: 100,
  category_counts: { low: 90, medium: 6, high: 3, critical: 1 },
  coverage_summary: { "0.55": 100 },
  error_message: "",
  created_by_email: "a@example.com",
  created_at: "2026-01-01T00:00:00Z",
  finished_at: "2026-01-01T00:00:10Z",
};
const row: RiskAssessment = {
  id: 5,
  transaction: 9,
  external_id: "T9",
  amount: "40000.00",
  tx_type: "PAYMENT",
  occurred_at: "2026-01-01T00:00:00Z",
  account: 3,
  account_ref: "C1",
  overall_score: 71.2,
  category: "high",
  weight_coverage: 0.55,
  low_coverage: false,
  capped: false,
  policy: "renormalize",
  config_version: 1,
  run: 1,
  component_values: { A: 88, G: 0, D: 30 },
  computed_at: "",
};
const pageFetch = (posts: { url: string; body: unknown }[] = []) =>
  vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      posts.push({ url, body: JSON.parse(String(init.body ?? "null")) });
      return ok(cfg({ id: 2, version: 2, is_active: false }));
    }
    if (url.includes("/risk/config/"))
      return ok([
        cfg(),
        cfg({
          id: 2,
          version: 2,
          is_active: false,
          source: "calibrated",
          notes: "calibrated",
        }),
      ]);
    if (url.includes("/risk/runs/"))
      return ok({ count: 1, next: null, previous: null, results: [run] });
    if (url.match(/risk\/assessments\/\d+\//)) return ok(detail());
    if (url.includes("/risk/assessments/"))
      return ok({ count: 1, next: null, previous: null, results: [row] });
    if (url.includes("/datasets/"))
      return ok([
        {
          id: 2,
          name: "DEMO",
          source_type: "custom",
          is_synthetic: true,
          description: "",
          row_count: 100,
          created_at: "",
        },
      ]);
    return ok({});
  });

describe("RiskAnalysisPage", () => {
  it("shows the active configuration, category distribution with counts, and a breakdown for a selected transaction", async () => {
    renderUi(<RiskAnalysisPage />, ["risk.read"], pageFetch());
    expect(await screen.findByText(/Version 1/)).toBeInTheDocument();
    await screen.findByRole("option", { name: /DEMO \(100 rows\)/ });
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /dataset/i }),
      "2",
    );
    const dist = await screen.findByRole("list", {
      name: /category distribution/i,
    });
    expect(dist).toHaveTextContent("Critical");
    expect(dist).toHaveTextContent("90");
    expect(
      screen.getByText(/Signal coverage in this run: 55% → 100/),
    ).toBeInTheDocument();
    await userEvent.click(await screen.findByRole("button", { name: "T9" }));
    expect(
      await screen.findByRole("region", { name: /assessment breakdown/i }),
    ).toHaveTextContent(/Unavailable — cold start/);
    expect(
      screen.queryByRole("button", {
        name: /score with active configuration/i,
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /activate version/i }),
    ).not.toBeInTheDocument();
  });
  it("lets an admin create a new version (client-side sum check) and activate another; blocks nothing for others", async () => {
    const posts: { url: string; body: unknown }[] = [];
    renderUi(
      <RiskAnalysisPage />,
      ["risk.read", "risk.run", "risk.configure"],
      pageFetch(posts),
    );
    expect(
      await screen.findByText("Weights sum to 1.00 (must be 1.00)"),
    ).toBeInTheDocument();
    const a = screen.getByLabelText("Model anomaly weight");
    await userEvent.clear(a);
    await userEvent.type(a, "0.5");
    expect(screen.getByText(/Weights sum to 1.25/)).toBeInTheDocument();
    await userEvent.clear(a);
    await userEvent.type(a, "0.25");
    await userEvent.click(
      screen.getByRole("button", { name: /create version/i }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: /activate version 2/i }),
    );
    expect(posts.map((p) => p.url.replace(/^.*\/api\/v1/, ""))).toEqual([
      "/risk/config/",
      "/risk/config/2/activate/",
    ]);
    expect(posts[0]!.body).toMatchObject({
      weights: { A: 0.25, B: 0.2 },
      missing_signal_policy: "renormalize",
      min_coverage: 0.5,
    });
  });
});
