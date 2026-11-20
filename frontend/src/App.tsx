import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { ProtectedRoute } from "./auth/guards";
import { LoadingState } from "./components/ui/states";
import { ToastProvider } from "./components/ui/Toast";
import AppLayout from "./layout/AppLayout";

// Pages load on demand (route-level code splitting keeps the first load small).
const CaseDetailPage = lazy(() => import("./pages/CaseDetailPage"));
const CasesPage = lazy(() => import("./pages/CasesPage"));
const AlertsPage = lazy(() => import("./pages/AlertsPage"));
const AnalyticsPage = lazy(() => import("./pages/AnalyticsPage"));
const AccountBehaviorPage = lazy(() => import("./pages/AccountBehaviorPage"));
const AccountPage = lazy(() => import("./pages/AccountPage"));
const AnomalyDetectionPage = lazy(() => import("./pages/AnomalyDetectionPage"));
const AuditLogsPage = lazy(() => import("./pages/AuditLogsPage"));
const DetectionRunPage = lazy(() => import("./pages/DetectionRunPage"));
const DuplicatesPage = lazy(() => import("./pages/DuplicatesPage"));
const GraphOverviewPage = lazy(() => import("./pages/GraphOverviewPage"));
const ImportDetailPage = lazy(() => import("./pages/ImportDetailPage"));
const ImportsPage = lazy(() => import("./pages/ImportsPage"));
const ImportWizardPage = lazy(() => import("./pages/ImportWizardPage"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const ModelPerformancePage = lazy(() => import("./pages/ModelPerformancePage"));
const RelationshipGraphPage = lazy(
  () => import("./pages/RelationshipGraphPage"),
);
const RiskAnalysisPage = lazy(() => import("./pages/RiskAnalysisPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const LandingPage = lazy(() => import("./pages/LandingPage"));
const TransactionDetailPage = lazy(
  () => import("./pages/TransactionDetailPage"),
);
const TransactionsPage = lazy(() => import("./pages/TransactionsPage"));
const UsersPage = lazy(() => import("./pages/UsersPage"));

export default function App() {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: false, refetchOnWindowFocus: false },
        },
      }),
  );
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthProvider>
          <BrowserRouter>
            <Suspense fallback={<LoadingState />}>
              <Routes>
                <Route path="/" element={<LandingPage />} />
                <Route path="/login" element={<LoginPage />} />
                <Route element={<ProtectedRoute />}>
                  <Route element={<AppLayout />}>
                    <Route path="dashboard" element={<DashboardPage />} />
                    <Route
                      element={<ProtectedRoute permission="analytics.read" />}
                    >
                      <Route path="analytics" element={<AnalyticsPage />} />
                    </Route>
                    <Route
                      element={
                        <ProtectedRoute permission="transactions.read" />
                      }
                    >
                      <Route
                        path="transactions"
                        element={<TransactionsPage />}
                      />
                      <Route
                        path="transactions/:id"
                        element={<TransactionDetailPage />}
                      />
                    </Route>
                    <Route
                      element={<ProtectedRoute permission="imports.read" />}
                    >
                      <Route path="imports" element={<ImportsPage />} />
                      <Route
                        path="imports/:id"
                        element={<ImportDetailPage />}
                      />
                    </Route>
                    <Route
                      element={<ProtectedRoute permission="imports.create" />}
                    >
                      <Route
                        path="imports/new"
                        element={<ImportWizardPage />}
                      />
                    </Route>
                    <Route
                      element={<ProtectedRoute permission="detection.read" />}
                    >
                      <Route
                        path="detection"
                        element={<AnomalyDetectionPage />}
                      />
                      <Route
                        path="detection/:id"
                        element={<DetectionRunPage />}
                      />
                    </Route>
                    <Route element={<ProtectedRoute permission="graph.read" />}>
                      <Route path="graph" element={<GraphOverviewPage />} />
                      <Route
                        path="accounts/:id/graph"
                        element={<RelationshipGraphPage />}
                      />
                    </Route>
                    <Route
                      element={<ProtectedRoute permission="duplicates.read" />}
                    >
                      <Route path="duplicates" element={<DuplicatesPage />} />
                    </Route>
                    <Route element={<ProtectedRoute permission="cases.read" />}>
                      <Route path="cases" element={<CasesPage />} />
                      <Route path="cases/:id" element={<CaseDetailPage />} />
                    </Route>
                    <Route
                      element={<ProtectedRoute permission="alerts.read" />}
                    >
                      <Route path="alerts" element={<AlertsPage />} />
                    </Route>
                    <Route element={<ProtectedRoute permission="risk.read" />}>
                      <Route path="risk" element={<RiskAnalysisPage />} />
                    </Route>
                    <Route
                      element={<ProtectedRoute permission="models.read" />}
                    >
                      <Route path="models" element={<ModelPerformancePage />} />
                    </Route>
                    <Route
                      element={<ProtectedRoute permission="accounts.read" />}
                    >
                      <Route path="accounts/:id" element={<AccountPage />} />
                    </Route>
                    <Route
                      element={<ProtectedRoute permission="behavior.read" />}
                    >
                      <Route
                        path="accounts/:id/behavior"
                        element={<AccountBehaviorPage />}
                      />
                    </Route>
                    <Route element={<ProtectedRoute permission="users.read" />}>
                      <Route path="users" element={<UsersPage />} />
                    </Route>
                    <Route element={<ProtectedRoute permission="audit.read" />}>
                      <Route path="audit" element={<AuditLogsPage />} />
                    </Route>
                    <Route
                      path="*"
                      element={<p className="p-8">Page not found.</p>}
                    />
                  </Route>
                </Route>
              </Routes>
            </Suspense>
          </BrowserRouter>
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}
