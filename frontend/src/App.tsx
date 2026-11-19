import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { ProtectedRoute } from './auth/guards'
import { ToastProvider } from './components/ui/Toast'
import AppLayout from './layout/AppLayout'
import AuditLogsPage from './pages/AuditLogsPage'
import LoginPage from './pages/LoginPage'
import StatusPage from './pages/StatusPage'
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
