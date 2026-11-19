import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { BehaviorProfile, Me, TransactionBehavior } from "../api/types";
import { AuthContext, type AuthValue } from "../auth/AuthContext";
import { BehaviorPanel } from "../components/behavior/BehaviorPanel";
import AccountBehaviorPage from "./AccountBehaviorPage";

afterEach(() => vi.unstubAllGlobals());

const me: Me = {
  id: 1,
  email: "a@example.com",
  full_name: "A",
  role: "financial_analyst",
  role_label: "Analyst",
  is_active: true,
  last_login: null,
  created_at: "2026-01-01T00:00:00Z",
  permissions: ["behavior.read"],
};
const auth: AuthValue = {
  status: "authenticated",
  user: me,
  login: vi.fn(),
  logout: vi.fn(),
  can: () => true,
};
const ok = (body: unknown) =>
  ({ ok: true, status: 200, json: async () => body }) as Response;

function renderIn(
  ui: React.ReactNode,
  fetchMock: ReturnType<typeof vi.fn>,
  path = "/",
) {
  vi.stubGlobal("fetch", fetchMock);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthContext.Provider value={auth}>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/accounts/:id/behavior" element={ui} />
            <Route path="/" element={ui} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

const profile = (over: Partial<BehaviorProfile> = {}): BehaviorProfile => ({
  account: 5,
  account_ref: "C-DEMO",
  as_of: "2026-03-01T00:00:00Z",
  window_days: 90,
  direction: "out",
  profile_version: "b1",
  tx_count: 26,
  sufficient_history: true,
  avg_amount: 800,
  median_amount: 790,
  std_amount: 60,
  p95_amount: 900,
  mad_amount: 40,
  tx_per_day: 0.4,
  unique_counterparties: 4,
  hour_histogram: Array.from({ length: 24 }, (_, h) => (h === 10 ? 26 : 0)),
  merchant_category_dist: null,
  aggregates: {
    daily: [{ period: "2026-02-01", count: 1, total: 800 }],
    weekly: [{ period: "2026-01-26", count: 3, total: 2400 }],
    monthly: [{ period: "2026-02", count: 12, total: 9600 }],
  },
  recent_7d: { count: 3, total: 2400, avg: 800 },
  ...over,
});

describe("AccountBehaviorPage", () => {
  it("shows statistics, trend, hour chart and says merchant categories are unavailable", async () => {
    renderIn(
      <AccountBehaviorPage />,
      vi.fn(async () => ok(profile())),
      "/accounts/5/behavior",
    );
    expect(await screen.findByText("C-DEMO")).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /transactions by hour/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /daily total amount/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/not available in this dataset/i),
    ).toBeInTheDocument();
    expect(screen.getByText("Last 7 days")).toBeInTheDocument();
  });
  it("explains an empty window and a thin history instead of showing zeros", async () => {
    const empty = vi.fn(async () =>
      ok(profile({ tx_count: 0, sufficient_history: false, avg_amount: null })),
    );
    const { unmount } = renderIn(
      <AccountBehaviorPage />,
      empty,
      "/accounts/5/behavior",
    );
    expect(await screen.findByText(/no profile to show/i)).toBeInTheDocument();
    unmount();
    renderIn(
      <AccountBehaviorPage />,
      vi.fn(async () =>
        ok(profile({ tx_count: 2, sufficient_history: false })),
      ),
      "/accounts/5/behavior",
    );
    expect(await screen.findByText(/too little history/i)).toBeInTheDocument();
  });
});

const behavior = (
  over: Partial<TransactionBehavior> = {},
): TransactionBehavior => ({
  transaction: 9,
  account: 5,
  profile_version: "b1",
  status: "scored",
  deviation_score: 83.9,
  coverage: 1,
  history_count: 30,
  components: {
    amount: {
      available: true,
      score: 100,
      detail: { amount: 40000, median: 800, mad: 40 },
    },
    burst: {
      available: true,
      score: 86,
      detail: { transactions_in_window: 5, window_minutes: 10 },
    },
    hour: {
      available: false,
      score: null,
      reason: "needs 20 prior transactions for an hour-of-day profile",
    },
  },
  ...over,
});

describe("BehaviorPanel", () => {
  it("shows the score with per-signal evidence and unavailable signals with their reason", async () => {
    renderIn(
      <BehaviorPanel transactionId={9} />,
      vi.fn(async () => ok(behavior())),
    );
    expect(await screen.findByText("83.9")).toBeInTheDocument();
    expect(
      screen.getByText(/5 transaction\(s\) in 10 min/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Unavailable — needs 20 prior transactions/),
    ).toBeInTheDocument();
  });
  it("states cold start explicitly rather than showing a zero score", async () => {
    renderIn(
      <BehaviorPanel transactionId={9} />,
      vi.fn(async () =>
        ok(
          behavior({
            status: "unavailable_cold_start",
            deviation_score: null,
            coverage: 0,
            history_count: 1,
            components: {},
          }),
        ),
      ),
    );
    expect(
      await screen.findByText(/only 1 earlier transaction/),
    ).toBeInTheDocument();
    expect(screen.queryByText("0.0")).not.toBeInTheDocument();
  });
});
