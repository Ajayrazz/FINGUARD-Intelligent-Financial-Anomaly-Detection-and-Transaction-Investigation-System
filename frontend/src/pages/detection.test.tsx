import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DetectionRun, Me, ModelVersionRow } from "../api/types";
import { AuthContext, type AuthValue } from "../auth/AuthContext";
import { ToastProvider } from "../components/ui/Toast";
import AnomalyDetectionPage from "./AnomalyDetectionPage";
import DetectionRunPage from "./DetectionRunPage";
import ModelPerformancePage from "./ModelPerformancePage";

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

const version = (over: Partial<ModelVersionRow> = {}): ModelVersionRow => ({
  id: 1,
  model_name: "xgb_paysim_core",
  algorithm: "XGBoost",
  task_type: "supervised",
  version: "paysim-s42-abc",
  status: "candidate",
  dataset: "paysim",
  feature_set: "core",
  random_seed: 42,
  trained_at: null,
  scorable: true,
  test_metrics: {
    pr_auc: 0.417,
    pr_auc_ci95: [0.404, 0.431],
    roc_auc: 0.96,
    base_rate: 0.00436,
    positives: 4006,
    rows: 918617,
    recall_at_fpr_1pct: 0.695,
  },
  ...over,
});
const run = (over: Partial<DetectionRun> = {}): DetectionRun => ({
  id: 3,
  model_version: 1,
  model_name: "xgb_paysim_core",
  algorithm: "XGBoost",
  version: "v",
  dataset: 1,
  dataset_name: "MOCK demo",
  is_mock_data: true,
  threshold: 0.5,
  threshold_source: "registry: max F1 on validation, frozen",
  status: "succeeded",
  rows_scored: 100,
  rows_flagged: 2,
  score_summary: {
    min: 0,
    max: 1,
    mean: 0.1,
    quantiles: {},
    threshold: 0.5,
    histogram: { counts: [90, 8, 2], edges: [0, 0.33, 0.66, 1] },
  },
  error_message: "",
  created_by_email: "a@example.com",
  created_at: "2026-01-01T00:00:00Z",
  started_at: "2026-01-01T00:00:01Z",
  finished_at: "2026-01-01T00:00:05Z",
  ...over,
});

function renderAt(
  path: string,
  routePath: string,
  element: React.ReactNode,
  perms: string[],
  fetchMock: ReturnType<typeof vi.fn>,
) {
  vi.stubGlobal("fetch", fetchMock);
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

describe("ModelPerformancePage", () => {
  // these tests exercise the accessible Table view; the Cards view is the default for users
  beforeEach(() => {
    localStorage.setItem("fg-view-models", "table");
  });

  it("ranks by PR-AUC, shows intervals and warns about balance features", async () => {
    const fetchMock = vi.fn(async () =>
      ok([
        version({
          id: 1,
          model_name: "lr_paysim_core",
          algorithm: "LogisticRegression",
          test_metrics: { ...version().test_metrics!, pr_auc: 0.194 },
        }),
        version({ id: 2, model_name: "xgb_paysim_core" }),
      ]),
    );
    renderAt(
      "/models",
      "/models",
      <ModelPerformancePage />,
      ["models.read"],
      fetchMock,
    );
    expect(await screen.findByText("xgb_paysim_core")).toBeInTheDocument();
    const rows = screen.getAllByRole("row");
    expect(rows[1]).toHaveTextContent("xgb_paysim_core"); // best PR-AUC first
    expect(screen.getAllByText(/0.404, 0.431/).length).toBeGreaterThan(0);
    expect(screen.getByRole("note")).toHaveTextContent(/core\+balance/);
  });
});

describe("AnomalyDetectionPage", () => {
  // these tests exercise the accessible Table view
  beforeEach(() => {
    localStorage.setItem("fg-view-detection-runs", "table");
  });
  it("lists runs, flags mock data, and hides the start form without detection.run", async () => {
    const fetchMock = vi.fn(async () =>
      ok({ count: 1, next: null, previous: null, results: [run()] }),
    );
    renderAt(
      "/detection",
      "/detection",
      <AnomalyDetectionPage />,
      ["detection.read"],
      fetchMock,
    );
    expect(await screen.findByText("MOCK")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /run detection/i }),
    ).not.toBeInTheDocument();
  });
  it("offers only scorable models in the start form", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url.includes("/model-versions/"))
        return ok([
          version(),
          version({ id: 9, model_name: "xgb_creditcard", scorable: false }),
        ]);
      if (url.includes("/datasets/")) return ok([]);
      return ok({ count: 0, next: null, previous: null, results: [] });
    });
    renderAt(
      "/detection",
      "/detection",
      <AnomalyDetectionPage />,
      ["detection.read", "detection.run"],
      fetchMock,
    );
    expect(
      await screen.findByRole("option", { name: /xgb_paysim_core/ }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("option", { name: /xgb_creditcard/ }),
    ).not.toBeInTheDocument();
  });
});

describe("DetectionRunPage", () => {
  it("shows the failure reason of a failed run", async () => {
    const fetchMock = vi.fn(async () =>
      ok(
        run({
          status: "failed",
          error_message: "artifact hash does not match the registry",
          score_summary: {},
        }),
      ),
    );
    renderAt(
      "/detection/3",
      "/detection/:id",
      <DetectionRunPage />,
      ["detection.read"],
      fetchMock,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /hash does not match/,
    );
  });
  it("renders score distribution and flagged predictions for a finished run", async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.includes("/predictions/")
        ? ok({
            count: 1,
            next: null,
            previous: null,
            results: [
              {
                id: 1,
                transaction_id: 7,
                external_id: "T7",
                amount: "500.00",
                tx_type: "TRANSFER",
                occurred_at: "2026-01-01T00:00:00Z",
                sender: "C1",
                receiver: "C2",
                score: 0.9123,
                flagged: true,
              },
            ],
          })
        : ok(run()),
    );
    renderAt(
      "/detection/3",
      "/detection/:id",
      <DetectionRunPage />,
      ["detection.read"],
      fetchMock,
    );
    expect(await screen.findByText("0.9123")).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /score distribution/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/MOCK/);
  });
});
