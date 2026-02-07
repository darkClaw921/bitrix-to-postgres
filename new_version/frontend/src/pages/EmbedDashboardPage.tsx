import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams } from 'react-router-dom'
import ChartRenderer from '../components/charts/ChartRenderer'
import PasswordGate from '../components/dashboards/PasswordGate'
import { publicApi } from '../services/api'
import type { Dashboard, DashboardChart, ChartSpec, ChartDataResponse, ChartDisplayConfig } from '../services/api'

const SESSION_KEY_PREFIX = 'dashboard_token_'

export default function EmbedDashboardPage() {
  const { slug } = useParams<{ slug: string }>()
  const [token, setToken] = useState<string | null>(() => {
    if (!slug) return null
    return sessionStorage.getItem(SESSION_KEY_PREFIX + slug)
  })
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [chartData, setChartData] = useState<Record<number, ChartDataResponse>>({})
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const refreshingRef = useRef(false)

  const handleAuth = useCallback(
    async (password: string): Promise<string> => {
      if (!slug) throw new Error('No slug')
      const res = await publicApi.authenticateDashboard(slug, password)
      sessionStorage.setItem(SESSION_KEY_PREFIX + slug, res.token)
      return res.token
    },
    [slug],
  )

  const handleAuthenticated = useCallback((t: string) => {
    setToken(t)
  }, [])

  const fetchAllChartData = useCallback(
    async (dash: Dashboard, authToken: string) => {
      if (!slug) return
      if (refreshingRef.current) return
      refreshingRef.current = true
      setRefreshing(true)

      try {
        const promises = dash.charts.map((c) =>
          publicApi
            .getDashboardChartData(slug, c.id, authToken)
            .then((data) => ({ dcId: c.id, data }))
            .catch((err) => {
              const axiosErr = err as { response?: { status?: number } }
              if (axiosErr?.response?.status === 401) {
                throw err
              }
              return { dcId: c.id, data: null }
            }),
        )
        const results = await Promise.all(promises)
        const dataMap: Record<number, ChartDataResponse> = {}
        for (const r of results) {
          if (r.data) dataMap[r.dcId] = r.data
        }
        setChartData(dataMap)
        setLastUpdatedAt(new Date())
      } catch (err) {
        const axiosErr = err as { response?: { status?: number } }
        if (axiosErr?.response?.status === 401) {
          sessionStorage.removeItem(SESSION_KEY_PREFIX + slug)
          setToken(null)
        }
      } finally {
        refreshingRef.current = false
        setRefreshing(false)
      }
    },
    [slug],
  )

  // Load dashboard once authenticated
  useEffect(() => {
    if (!slug || !token) return

    setLoading(true)
    publicApi
      .getDashboard(slug, token)
      .then((d) => {
        setDashboard(d)
        return fetchAllChartData(d, token)
      })
      .catch((err) => {
        const axiosErr = err as { response?: { status?: number } }
        if (axiosErr?.response?.status === 401) {
          sessionStorage.removeItem(SESSION_KEY_PREFIX + slug)
          setToken(null)
        } else {
          setError('Failed to load dashboard')
        }
      })
      .finally(() => setLoading(false))
  }, [slug, token, fetchAllChartData])

  // Auto-refresh interval
  useEffect(() => {
    if (!dashboard || !token || !slug) return

    const intervalMs = dashboard.refresh_interval_minutes * 60 * 1000
    const timer = setInterval(() => {
      fetchAllChartData(dashboard, token)
    }, intervalMs)

    return () => clearInterval(timer)
  }, [dashboard, token, slug, fetchAllChartData])

  if (!token) {
    return <PasswordGate onAuthenticated={handleAuthenticated} onSubmit={handleAuth} />
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-gray-400">Loading dashboard...</div>
      </div>
    )
  }

  if (error || !dashboard) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-red-500">{error || 'Dashboard not found'}</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-2">
          <h1 className="text-2xl font-bold text-gray-800">{dashboard.title}</h1>
          <div className="flex items-center space-x-3 text-xs text-gray-400">
            {refreshing && (
              <span className="flex items-center space-x-1">
                <svg className="animate-spin h-3 w-3 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                <span>Refreshing...</span>
              </span>
            )}
            {lastUpdatedAt && (
              <span>
                Updated: {lastUpdatedAt.toLocaleTimeString()}
              </span>
            )}
            <span className="text-gray-300">|</span>
            <span>Auto-refresh: {dashboard.refresh_interval_minutes} min</span>
          </div>
        </div>
        {dashboard.description && (
          <p className="text-gray-500 mb-6">{dashboard.description}</p>
        )}

        <div
          className="grid gap-4"
          style={{
            gridTemplateColumns: 'repeat(12, 1fr)',
          }}
        >
          {dashboard.charts.map((dc) => (
            <DashboardChartCard
              key={dc.id}
              dc={dc}
              data={chartData[dc.id] || null}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

function DashboardChartCard({
  dc,
  data,
}: {
  dc: DashboardChart
  data: ChartDataResponse | null
}) {
  const title = dc.title_override || dc.chart_title || 'Chart'
  const description = dc.description_override || dc.chart_description

  const config = dc.chart_config as unknown as ChartDisplayConfig | null

  const spec: ChartSpec = {
    title,
    chart_type: (dc.chart_type || 'bar') as ChartSpec['chart_type'],
    sql_query: '',
    data_keys: { x: config?.x || 'x', y: config?.y || 'y' },
    colors: config?.colors,
    description,
    legend: config?.legend,
    grid: config?.grid,
    xAxis: config?.xAxis,
    yAxis: config?.yAxis,
    line: config?.line,
    area: config?.area,
    pie: config?.pie,
  }

  return (
    <div
      className="bg-white rounded-lg shadow-sm border border-gray-200 p-4"
      style={{
        gridColumn: `${dc.layout_x + 1} / span ${dc.layout_w}`,
        gridRow: `${dc.layout_y + 1} / span ${dc.layout_h}`,
        minHeight: `${dc.layout_h * 100}px`,
      }}
    >
      <h3 className="text-sm font-semibold text-gray-700 mb-1">{title}</h3>
      {description && (
        <p className="text-xs text-gray-400 mb-2">{description}</p>
      )}
      <div className="flex-1">
        {data ? (
          <ChartRenderer spec={spec} data={data.data} height={dc.layout_h * 80} />
        ) : (
          <div className="flex items-center justify-center h-32 text-gray-400 text-sm">
            Loading...
          </div>
        )}
      </div>
    </div>
  )
}
