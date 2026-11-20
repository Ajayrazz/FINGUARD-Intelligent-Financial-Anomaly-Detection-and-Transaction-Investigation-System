import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Me } from "../api/types";
import { AuthContext, type AuthValue } from "../auth/AuthContext";
import { ToastProvider } from "../components/ui/Toast";
import AnalyticsPage from "./AnalyticsPage";

vi.mock("../components/charts/EChart", () => ({
  EChart: ({ label }: { label: string }) => (
    <div role="img" aria-label={label} />
  ),
}));
afterEach(() => vi.unstubAllGlobals());

const me = (permissions: string[]): Me => ({
  id: 1,
  email: "m@example.com",
  full_name: "M",
  role: "management",
  role_label: "Management",
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

function fetchMock() {
  return vi.fn(async (url: string) => {
    if (url.includes("/analytics/datasets/"))
      return ok([{ id: 3, name: "DEMO" }]);
    if (url.includes("/analytics/overview/"))
      return ok({
        transactions: 1234,
        value: "5000.00",
        flagged: 7,
        high_risk_transactions: 2,
        open_alerts: 4,
        open_cases: 1,
        datasets: 1,
        refreshed_at: "2026-01-02T03:04:05Z",
      });
    if (url.includes("/analytics/volume/"))
      return ok({
        granularity: "day",
        series: [
          { period: "2026-01-01", transactions: 5, value: "10.00", flagged: 1 },
        ],
      });
    if (url.includes("/analytics/risk-distribution/"))
      return ok({ counts: { low: 3, high: 1 }, total: 4, runs: [1] });
    if (url.includes("/analytics/accounts/high-risk/"))
      return ok([
        {
          account: 9,
          account_ref: "C-9",
          dataset: 3,
          max_score: 88.5,
          assessments: 2,
          high_or_critical: 1,
        },
      ]);
    if (url.includes("/analytics/recent-suspicious/")) return ok([]);
    if (url.includes("/analytics/investigations/summary/"))
      return ok({
        total: 0,
        by_status: {},
        by_priority: {},
        by_outcome: {},
        resolved: 0,
        resolution_hours: { mean: null, median: null, max: null },
      });
    if (url.includes("/analytics/false-positives/"))
      return ok({
        investigated: {
          alerts: { false_positive: 1, true_positive: 3, rate: 0.25 },
          cases: { false_positive: 0, confirmed_suspicious: 0, rate: null },
        },
        labelled: {
          runs: [],
          tp: 0,
          fp: 0,
          fn: 0,
          tn: 0,
          precision: null,
          recall: null,
          false_positive_rate: null,
        },
      });
    if (url.includes("/analytics/detection-performance/")) return ok([]);
    return ok({});
  });
}

function renderPage(perms: string[], f = fetchMock()) {
  vi.stubGlobal("fetch", f);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <AuthContext.Provider value={auth(perms)}>
        <ToastProvider>
          <MemoryRouter>
            <AnalyticsPage />
          </MemoryRouter>
        </ToastProvider>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
  return f;
}

describe("AnalyticsPage", () => {
  it("shows the numbers from the API, the dataset filter, and empty states for missing data", async () => {
    renderPage(["analytics.read"]);
    expect(
      await screen.findByRole("heading", { name: "Analytics", level: 1 }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("option", { name: "DEMO" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("C-9")).toBeInTheDocument();
    expect(await screen.findByText(/Rollup refreshed/)).toBeInTheDocument();
    expect(
      await screen.findByText("Nothing high-risk yet."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("No registered models with test results."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Download CSV" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Rebuild rollup" }),
    ).not.toBeInTheDocument();
  });

  it("sends the chosen dataset with every request and offers export and rebuild only with the permissions", async () => {
    const f = renderPage([
      "analytics.read",
      "analytics.export",
      "analytics.refresh",
    ]);
    await screen.findByRole("option", { name: "DEMO" });
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Dataset" }),
      "3",
    );
    await screen.findByRole("button", { name: "Download CSV" });
    expect(
      screen.getByRole("button", { name: "Rebuild rollup" }),
    ).toBeInTheDocument();
    await vi.waitFor(() =>
      expect(
        f.mock.calls.some(([u]) =>
          String(u).includes("/analytics/overview/?dataset=3"),
        ),
      ).toBe(true),
    );
  });
});
