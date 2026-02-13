import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import DashboardPage from './pages/DashboardPage'
import ConfigPage from './pages/ConfigPage'
import MonitoringPage from './pages/MonitoringPage'
import ValidationPage from './pages/ValidationPage'
import ChartsPage from './pages/ChartsPage'
import ReportsPage from './pages/ReportsPage'
import SchemaPage from './pages/SchemaPage'
import EmbedChartPage from './pages/EmbedChartPage'
import EmbedDashboardPage from './pages/EmbedDashboardPage'
import EmbedReportPage from './pages/EmbedReportPage'
import DashboardEditorPage from './pages/DashboardEditorPage'
import LoginPage from './pages/LoginPage'
import { useAuth } from './hooks/useAuth'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="text-gray-500">Loading...</div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

function App() {
  return (
    <Routes>
      {/* Login */}
      <Route path="/login" element={<LoginPage />} />

      {/* Embed routes — outside Layout, no nav */}
      <Route path="/embed/chart/:chartId" element={<EmbedChartPage />} />
      <Route path="/embed/dashboard/:slug" element={<EmbedDashboardPage />} />
      <Route path="/embed/report/:slug" element={<EmbedReportPage />} />

      {/* App routes — inside Layout, protected */}
      <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route index element={<DashboardPage />} />
        <Route path="config" element={<ConfigPage />} />
        <Route path="monitoring" element={<MonitoringPage />} />
        <Route path="validation" element={<ValidationPage />} />
        <Route path="ai/charts" element={<ChartsPage />} />
        <Route path="ai/reports" element={<ReportsPage />} />
        <Route path="ai" element={<Navigate to="/ai/charts" replace />} />
        <Route path="schema" element={<SchemaPage />} />
        <Route path="dashboards/:id/edit" element={<DashboardEditorPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
