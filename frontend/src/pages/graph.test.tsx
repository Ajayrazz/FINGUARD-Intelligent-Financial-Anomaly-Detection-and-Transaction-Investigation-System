import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type {
  GraphFinding,
  GraphSnapshot,
  Me,
  Neighborhood,
  SyncStatus,
} from "../api/types";
import { AuthContext, type AuthValue } from "../auth/AuthContext";
import { ToastProvider } from "../components/ui/Toast";
import { ringLayout } from "../lib/graphLayout";
import GraphOverviewPage from "./GraphOverviewPage";
import RelationshipGraphPage from "./RelationshipGraphPage";

// The diagram itself needs a real layout engine; the data table under it carries the same information.
vi.mock("@xyflow/react", () => ({
  ReactFlow: ({ nodes, edges }: { nodes: unknown[]; edges: unknown[] }) => (
    <div data-testid="flow">
      {nodes.length} nodes / {edges.length} edges
    </div>
  ),
  Background: () => null,
  Controls: () => null,
  MarkerType: { ArrowClosed: "arrowclosed" },
}));
vi.mock("@xyflow/react/dist/style.css", () => ({}));

afterEach(() => vi.unstubAllGlobals());

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

const snap = (over: Partial<GraphSnapshot> = {}): GraphSnapshot => ({
  id: 4,
  dataset: 2,
  dataset_name: "DEMO graph",
  is_mock_data: true,
  as_of: "2026-02-01T00:00:00Z",
  window_days: null,
  status: "succeeded",
  node_count: 180,
  edge_count: 420,
  finding_count: 6,
  truncated: {},
  error_message: "",
  created_by_email: "a@example.com",
  created_at: "2026-02-01T00:00:00Z",
  built_at: "2026-02-01T00:00:05Z",
  ...over,
});
const finding: GraphFinding = {
  id: 1,
  snapshot: 4,
  finding_type: "cycle",
  score: 91.5,
  account_ids: [11, 12, 13],
  accounts: [
    { id: 11, account_ref: "A1" },
    { id: 12, account_ref: "A2" },
    { id: 13, account_ref: "A3" },
  ],
  transaction_ids: [1, 2, 3],
  evidence: { length: 3, span_s: 18000 },
  detected_at: "2026-02-01T00:00:05Z",
};
const sync = (over: Partial<SyncStatus> = {}): SyncStatus => ({
  dataset: 2,
  status: "synced",
  last_tx_id: 10,
  edges_synced: 420,
  last_error: "",
  updated_at: null,
  drift: {
    postgres: { nodes: 180, edges: 420 },
    neo4j: { nodes: 180, edges: 420 },
    in_sync: true,
    error: null,
  },
  ...over,
});

function overviewFetch(syncBody: SyncStatus) {
  return vi.fn(async (url: string) => {
    if (url.includes("/datasets/") && url.includes("/sync/"))
      return ok(syncBody);
    if (url.includes("/datasets/"))
      return ok([
        {
          id: 2,
          name: "DEMO graph",
          source_type: "custom",
          is_synthetic: true,
          description: "",
          row_count: 420,
          created_at: "",
        },
      ]);
    if (url.includes("/graph/snapshots/"))
      return ok({ count: 1, next: null, previous: null, results: [snap()] });
    if (url.includes("/graph/findings/"))
      return ok({ count: 1, next: null, previous: null, results: [finding] });
    return ok({});
  });
}

describe("GraphOverviewPage", () => {
  // these tests exercise the accessible Table view; the Cards view is the default for users
  beforeEach(() => {
    localStorage.setItem("fg-view-graph-snaps", "table");
    localStorage.setItem("fg-view-graph-findings", "table");
  });

  it("lists snapshots and findings with links to account networks, and shows the sync state", async () => {
    renderAt(
      "/graph",
      "/graph",
      <GraphOverviewPage />,
      ["graph.read", "graph.run"],
      overviewFetch(sync()),
    );
    expect(
      await screen.findByText("DEMO graph", { selector: "td" }),
    ).toBeInTheDocument();
    await screen.findByRole("option", { name: /DEMO graph \(420 rows\)/ });
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /dataset/i }),
      "2",
    );
    expect(
      await screen.findByRole("cell", { name: "Circular flow" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "A1" })).toHaveAttribute(
      "href",
      "/accounts/11/graph",
    );
    expect(await screen.findByText(/in sync/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /rebuild projection/i }),
    ).toBeInTheDocument();
  });
  it("says when Neo4j is down and that views fall back to PostgreSQL; hides actions without graph.run", async () => {
    const down = sync({
      status: "failed",
      drift: {
        postgres: { nodes: 180, edges: 420 },
        neo4j: null,
        in_sync: null,
        error: "Neo4j unavailable: ServiceUnavailable",
      },
    });
    renderAt(
      "/graph",
      "/graph",
      <GraphOverviewPage />,
      ["graph.read"],
      overviewFetch(down),
    );
    await screen.findByRole("option", { name: /DEMO graph \(420 rows\)/ });
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /dataset/i }),
      "2",
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /fall back to PostgreSQL/,
    );
    expect(
      screen.queryByRole("button", { name: /rebuild projection/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /build graph analysis/i }),
    ).not.toBeInTheDocument();
  });
});

const hood = (over: Partial<Neighborhood> = {}): Neighborhood => ({
  center: 11,
  source: "neo4j",
  depth: 1,
  truncated: false,
  snapshot: 4,
  nodes: [
    {
      id: 11,
      account_ref: "A1",
      account_type: "customer",
      depth: 0,
      graph_risk_score: 80,
      in_finding: true,
    },
    {
      id: 12,
      account_ref: "A2",
      account_type: "customer",
      depth: 1,
      graph_risk_score: null,
      in_finding: false,
    },
  ],
  edges: [
    {
      source: 11,
      target: 12,
      count: 2,
      total: 99000,
      first_at: "2026-01-10T00:00:00Z",
      last_at: "2026-01-11T00:00:00Z",
      transaction_ids: [7, 8],
    },
  ],
  ...over,
});

describe("RelationshipGraphPage", () => {
  it("shows the data source, a connections table and the edge detail with its transaction", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url.includes("/neighborhood/")) return ok(hood());
      if (url.includes("/timeline/")) return ok({ events: [] });
      if (url.includes("/graph/edges/"))
        return ok({
          transaction_id: 7,
          external_id: "G00007",
          sender: { id: 11, account_ref: "A1" },
          receiver: { id: 12, account_ref: "A2" },
          amount: "50000.00",
          currency: "INR",
          tx_type: "TRANSFER",
          occurred_at: "2026-01-10T00:00:00Z",
          status: "completed",
        });
      return ok({});
    });
    renderAt(
      "/accounts/11/graph",
      "/accounts/:id/graph",
      <RelationshipGraphPage />,
      ["graph.read"],
      fetchMock,
    );
    expect(
      await screen.findByText("Neo4j", { selector: "strong" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("flow")).toHaveTextContent("2 nodes / 1 edges");
    await userEvent.click(screen.getByRole("button", { name: "Details" }));
    expect(await screen.findByRole("link", { name: "G00007" })).toHaveAttribute(
      "href",
      "/transactions/7",
    );
  });
  it("warns when results are truncated and labels a PostgreSQL fallback", async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.includes("/neighborhood/")
        ? ok(hood({ truncated: true, source: "postgres" }))
        : ok({ events: [] }),
    );
    renderAt(
      "/accounts/11/graph",
      "/accounts/:id/graph",
      <RelationshipGraphPage />,
      ["graph.read"],
      fetchMock,
    );
    expect(
      await screen.findByText("PostgreSQL", { selector: "strong" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/Truncated/);
  });
});

describe("ringLayout", () => {
  it("puts the centre at the origin and every other node on a ring by depth", () => {
    const pos = ringLayout([
      {
        id: 1,
        account_ref: "a",
        account_type: "x",
        depth: 0,
        graph_risk_score: null,
        in_finding: false,
      },
      {
        id: 2,
        account_ref: "b",
        account_type: "x",
        depth: 1,
        graph_risk_score: null,
        in_finding: false,
      },
      {
        id: 3,
        account_ref: "c",
        account_type: "x",
        depth: 2,
        graph_risk_score: null,
        in_finding: false,
      },
    ]);
    expect(pos[1]).toEqual({ x: 0, y: 0 });
    expect(Math.hypot(pos[2]!.x, pos[2]!.y)).toBeCloseTo(190, 0);
    expect(Math.hypot(pos[3]!.x, pos[3]!.y)).toBeCloseTo(380, 0);
  });
});
