import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import DashboardPage from './pages/DashboardPage'
import ConfigPage from './pages/ConfigPage'
import MonitoringPage from './pages/MonitoringPage'
import ValidationPage from './pages/ValidationPage'
import ChartsPage from './pages/ChartsPage'
import SchemaPage from './pages/SchemaPage'
import EmbedChartPage from './pages/EmbedChartPage'
import EmbedDashboardPage from './pages/EmbedDashboardPage'
import DashboardEditorPage from './pages/DashboardEditorPage'

function App() {
  return (
    <Routes>
      {/* Embed routes — outside Layout, no nav */}
      <Route path="/embed/chart/:chartId" element={<EmbedChartPage />} />
      <Route path="/embed/dashboard/:slug" element={<EmbedDashboardPage />} />

      {/* App routes — inside Layout */}
      <Route path="/" element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="config" element={<ConfigPage />} />
        <Route path="monitoring" element={<MonitoringPage />} />
        <Route path="validation" element={<ValidationPage />} />
        <Route path="charts" element={<ChartsPage />} />
        <Route path="schema" element={<SchemaPage />} />
        <Route path="dashboards/:id/edit" element={<DashboardEditorPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
