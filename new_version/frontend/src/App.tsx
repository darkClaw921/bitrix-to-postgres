import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import DashboardPage from './pages/DashboardPage'
import ConfigPage from './pages/ConfigPage'
import MonitoringPage from './pages/MonitoringPage'
import ValidationPage from './pages/ValidationPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="config" element={<ConfigPage />} />
        <Route path="monitoring" element={<MonitoringPage />} />
        <Route path="validation" element={<ValidationPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
