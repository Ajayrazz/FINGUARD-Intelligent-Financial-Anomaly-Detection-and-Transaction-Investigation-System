import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { ProtectedRoute } from './auth/guards'
import { ToastProvider } from './components/ui/Toast'
import AppLayout from './layout/AppLayout'
import CaseDetailPage from './pages/CaseDetailPage'
import CasesPage from './pages/CasesPage'
import AlertsPage from './pages/AlertsPage'
import AccountBehaviorPage from './pages/AccountBehaviorPage'
import AccountPage from './pages/AccountPage'
import AnomalyDetectionPage from './pages/AnomalyDetectionPage'
import AuditLogsPage from './pages/AuditLogsPage'
import DetectionRunPage from './pages/DetectionRunPage'
import DuplicatesPage from './pages/DuplicatesPage'
import GraphOverviewPage from './pages/GraphOverviewPage'
import ImportDetailPage from './pages/ImportDetailPage'
import ImportsPage from './pages/ImportsPage'
import ImportWizardPage from './pages/ImportWizardPage'
import LoginPage from './pages/LoginPage'
import ModelPerformancePage from './pages/ModelPerformancePage'
import RelationshipGraphPage from './pages/RelationshipGraphPage'
import RiskAnalysisPage from './pages/RiskAnalysisPage'
import StatusPage from './pages/StatusPage'
import TransactionDetailPage from './pages/TransactionDetailPage'
import TransactionsPage from './pages/TransactionsPage'
import UsersPage from './pages/UsersPage'

export default function App() {
  const [queryClient] = useState(
    () => new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } } }),
  )
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route element={<ProtectedRoute />}>
                <Route element={<AppLayout />}>
                  <Route index element={<StatusPage />} />
                  <Route element={<ProtectedRoute permission="transactions.read" />}>
                    <Route path="transactions" element={<TransactionsPage />} />
                    <Route path="transactions/:id" element={<TransactionDetailPage />} />
                  </Route>
                  <Route element={<ProtectedRoute permission="imports.read" />}>
                    <Route path="imports" element={<ImportsPage />} />
                    <Route path="imports/:id" element={<ImportDetailPage />} />
                  </Route>
                  <Route element={<ProtectedRoute permission="imports.create" />}>
                    <Route path="imports/new" element={<ImportWizardPage />} />
                  </Route>
                  <Route element={<ProtectedRoute permission="detection.read" />}>
                    <Route path="detection" element={<AnomalyDetectionPage />} />
                    <Route path="detection/:id" element={<DetectionRunPage />} />
                  </Route>
                  <Route element={<ProtectedRoute permission="graph.read" />}>
                    <Route path="graph" element={<GraphOverviewPage />} />
                    <Route path="accounts/:id/graph" element={<RelationshipGraphPage />} />
                  </Route>
                  <Route element={<ProtectedRoute permission="duplicates.read" />}>
                    <Route path="duplicates" element={<DuplicatesPage />} />
                  </Route>
                  <Route element={<ProtectedRoute permission="cases.read" />}>
                    <Route path="cases" element={<CasesPage />} />
                    <Route path="cases/:id" element={<CaseDetailPage />} />
                  </Route>
                  <Route element={<ProtectedRoute permission="alerts.read" />}>
                    <Route path="alerts" element={<AlertsPage />} />
                  </Route>
                  <Route element={<ProtectedRoute permission="risk.read" />}>
                    <Route path="risk" element={<RiskAnalysisPage />} />
                  </Route>
                  <Route element={<ProtectedRoute permission="models.read" />}>
                    <Route path="models" element={<ModelPerformancePage />} />
                  </Route>
                  <Route element={<ProtectedRoute permission="accounts.read" />}>
                    <Route path="accounts/:id" element={<AccountPage />} />
                  </Route>
                  <Route element={<ProtectedRoute permission="behavior.read" />}>
                    <Route path="accounts/:id/behavior" element={<AccountBehaviorPage />} />
                  </Route>
                  <Route element={<ProtectedRoute permission="users.read" />}>
                    <Route path="users" element={<UsersPage />} />
                  </Route>
                  <Route element={<ProtectedRoute permission="audit.read" />}>
                    <Route path="audit" element={<AuditLogsPage />} />
                  </Route>
                  <Route path="*" element={<p className="p-8">Page not found.</p>} />
                </Route>
              </Route>
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  )
}
