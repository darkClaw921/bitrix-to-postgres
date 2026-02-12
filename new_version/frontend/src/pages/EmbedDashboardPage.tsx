import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams } from 'react-router-dom'
import ChartRenderer from '../components/charts/ChartRenderer'
import ExportButtons from '../components/charts/ExportButtons'
import { getCardStyleClasses, getCardInlineStyle, getTitleSizeClass } from '../components/charts/cardStyleUtils'
import PasswordGate from '../components/dashboards/PasswordGate'
import SelectorBar from '../components/selectors/SelectorBar'
import { useTranslation } from '../i18n'
import { publicApi } from '../services/api'
import type { Dashboard, DashboardChart, DashboardSelector, ChartSpec, ChartDataResponse, ChartDisplayConfig, FilterValue } from '../services/api'

const SESSION_KEY_PREFIX = 'dashboard_token_'

interface TabData {
  dashboard: Dashboard
  chartData: Record<number, ChartDataResponse>
}

function useIsMobile(breakpoint = 768) {
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth <= breakpoint : false,
  )

  useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${breakpoint}px)`)
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches)
    mql.addEventListener('change', handler)
    setIsMobile(mql.matches)
    return () => mql.removeEventListener('change', handler)
  }, [breakpoint])

  return isMobile
}

export default function EmbedDashboardPage() {
  const { slug } = useParams<{ slug: string }>()
  const { t } = useTranslation()
  const isMobile = useIsMobile()
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

  // Tab state
  const [activeTab, setActiveTab] = useState<string>('main')
  const [linkedCache, setLinkedCache] = useState<Record<string, TabData>>({})
  const [linkedLoading, setLinkedLoading] = useState(false)

  // Filter state — per-dashboard filter values (keyed by dashboard slug or 'main')
  const [filterValues, setFilterValues] = useState<Record<string, Record<string, unknown>>>({})
  const filterValuesRef = useRef(filterValues)
  filterValuesRef.current = filterValues

  const setActiveFilterValues = useCallback(
    (values: Record<string, unknown>) => {
      const key = activeTab === 'main' ? 'main' : activeTab
      setFilterValues((prev) => ({ ...prev, [key]: values }))
    },
    [activeTab],
  )

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

  // Build filter array from current values
  const buildFilterArray = useCallback((values: Record<string, unknown>): FilterValue[] => {
    const filters: FilterValue[] = []
    for (const [name, value] of Object.entries(values)) {
      if (value !== null && value !== '' && value !== undefined && !(Array.isArray(value) && value.length === 0)) {
        filters.push({ name, value })
      }
    }
    return filters
  }, [])

  const fetchAllChartData = useCallback(
    async (dash: Dashboard, authToken: string, currentFilters?: Record<string, unknown>) => {
      if (!slug) return
      if (refreshingRef.current) return
      refreshingRef.current = true
      setRefreshing(true)

      const filtersToUse = currentFilters ?? filterValuesRef.current['main'] ?? {}
      const filterArray = buildFilterArray(filtersToUse)
      const hasFilters = filterArray.length > 0

      try {
        const promises = dash.charts.map((c) => {
          const fetcher = hasFilters
            ? publicApi.getDashboardChartDataFiltered(slug, c.id, authToken, filterArray)
            : publicApi.getDashboardChartData(slug, c.id, authToken)

          return fetcher
            .then((data) => ({ dcId: c.id, data }))
            .catch((err) => {
              const axiosErr = err as { response?: { status?: number } }
              if (axiosErr?.response?.status === 401) {
                throw err
              }
              return { dcId: c.id, data: null }
            })
        })
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
    [slug, buildFilterArray],
  )

  const fetchLinkedChartData = useCallback(
    async (
      linkedSlug: string,
      dash: Dashboard,
      authToken: string,
      currentFilters?: Record<string, unknown>,
    ): Promise<Record<number, ChartDataResponse>> => {
      if (!slug) return {}

      const filtersToUse = currentFilters ?? filterValuesRef.current[linkedSlug] ?? {}
      const filterArray = buildFilterArray(filtersToUse)
      const hasFilters = filterArray.length > 0

      const promises = dash.charts.map((c) => {
        const fetcher = hasFilters
          ? publicApi.getLinkedDashboardChartDataFiltered(slug, linkedSlug, c.id, authToken, filterArray)
          : publicApi.getLinkedDashboardChartData(slug, linkedSlug, c.id, authToken)

        return fetcher
          .then((data) => ({ dcId: c.id, data }))
          .catch((err) => {
            const axiosErr = err as { response?: { status?: number } }
            if (axiosErr?.response?.status === 401) {
              throw err
            }
            return { dcId: c.id, data: null }
          })
      })
      const results = await Promise.all(promises)
      const dataMap: Record<number, ChartDataResponse> = {}
      for (const r of results) {
        if (r.data) dataMap[r.dcId] = r.data
      }
      return dataMap
    },
    [slug, buildFilterArray],
  )

  const handleTabClick = useCallback(
    async (tabSlug: string) => {
      if (tabSlug === activeTab) return
      setActiveTab(tabSlug)

      // Main tab: data already loaded
      if (tabSlug === 'main') return

      // Already cached
      if (linkedCache[tabSlug]) return

      // Fetch linked dashboard
      if (!slug || !token) return
      setLinkedLoading(true)
      try {
        const linkedDash = await publicApi.getLinkedDashboard(slug, tabSlug, token)
        const linkedData = await fetchLinkedChartData(tabSlug, linkedDash, token)
        setLinkedCache((prev) => ({
          ...prev,
          [tabSlug]: { dashboard: linkedDash, chartData: linkedData },
        }))
      } catch (err) {
        const axiosErr = err as { response?: { status?: number } }
        if (axiosErr?.response?.status === 401) {
          sessionStorage.removeItem(SESSION_KEY_PREFIX + slug)
          setToken(null)
        }
      } finally {
        setLinkedLoading(false)
      }
    },
    [activeTab, linkedCache, slug, token, fetchLinkedChartData],
  )

  // Apply filters: re-fetch active tab's chart data
  const handleApplyFilters = useCallback(() => {
    if (!token || !slug) return

    if (activeTab === 'main' && dashboard) {
      const currentFilters = filterValuesRef.current['main'] || {}
      fetchAllChartData(dashboard, token, currentFilters)
    } else {
      const cached = linkedCache[activeTab]
      if (cached) {
        const currentFilters = filterValuesRef.current[activeTab] || {}
        fetchLinkedChartData(activeTab, cached.dashboard, token, currentFilters).then(
          (freshData) => {
            setLinkedCache((prev) => ({
              ...prev,
              [activeTab]: { ...prev[activeTab], chartData: freshData },
            }))
            setLastUpdatedAt(new Date())
          },
        ).catch(() => {})
      }
    }
  }, [activeTab, dashboard, linkedCache, token, slug, fetchAllChartData, fetchLinkedChartData])

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
          setError(t('embed.dashboardNotFound'))
        }
      })
      .finally(() => setLoading(false))
  }, [slug, token, fetchAllChartData])

  // Auto-refresh interval — refreshes active tab's charts with current filters
  useEffect(() => {
    if (!dashboard || !token || !slug) return

    const intervalMs = dashboard.refresh_interval_minutes * 60 * 1000
    const timer = setInterval(async () => {
      if (activeTab === 'main') {
        fetchAllChartData(dashboard, token)
      } else {
        const cached = linkedCache[activeTab]
        if (cached) {
          try {
            const freshData = await fetchLinkedChartData(activeTab, cached.dashboard, token)
            setLinkedCache((prev) => ({
              ...prev,
              [activeTab]: { ...prev[activeTab], chartData: freshData },
            }))
            setLastUpdatedAt(new Date())
          } catch {}
        }
      }
    }, intervalMs)

    return () => clearInterval(timer)
  }, [dashboard, token, slug, activeTab, linkedCache, fetchAllChartData, fetchLinkedChartData])

  if (!token) {
    return <PasswordGate onAuthenticated={handleAuthenticated} onSubmit={handleAuth} />
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-gray-400">{t('embed.loadingDashboard')}</div>
      </div>
    )
  }

  if (error || !dashboard) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-red-500">{error || t('embed.dashboardNotFound')}</div>
      </div>
    )
  }

  const linkedDashboards = dashboard.linked_dashboards || []
  const hasTabs = linkedDashboards.length > 0

  // Determine active charts and selectors to display
  let activeCharts: DashboardChart[] = dashboard.charts
  let activeChartData: Record<number, ChartDataResponse> = chartData
  let activeSelectors: DashboardSelector[] = dashboard.selectors || []
  let activeFilterKey = 'main'

  if (activeTab !== 'main' && linkedCache[activeTab]) {
    activeCharts = linkedCache[activeTab].dashboard.charts
    activeChartData = linkedCache[activeTab].chartData
    activeSelectors = linkedCache[activeTab].dashboard.selectors || []
    activeFilterKey = activeTab
  }

  const currentFilterValues = filterValues[activeFilterKey] || {}

  return (
    <div className="min-h-screen bg-gray-50 p-3 md:p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row md:items-center justify-between mb-2 gap-2">
          <h1 className="text-xl md:text-2xl font-bold text-gray-800">{dashboard.title}</h1>
          <div className="flex items-center space-x-3 text-xs text-gray-400">
            {refreshing && (
              <span className="flex items-center space-x-1">
                <svg className="animate-spin h-3 w-3 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                <span>{t('embed.refreshing')}</span>
              </span>
            )}
            {lastUpdatedAt && (
              <span>
                {t('embed.updated')} {lastUpdatedAt.toLocaleTimeString()}
              </span>
            )}
            <span className="text-gray-300">|</span>
            <span>{t('embed.autoRefresh')} {dashboard.refresh_interval_minutes} min</span>
          </div>
        </div>
        {dashboard.description && (
          <p className="text-gray-500 mb-4">{dashboard.description}</p>
        )}

        {/* Tab bar */}
        {hasTabs && (
          <div className="flex space-x-1 border-b border-gray-200 mb-4">
            <TabButton
              label={dashboard.title}
              isActive={activeTab === 'main'}
              onClick={() => handleTabClick('main')}
            />
            {linkedDashboards.map((link) => (
              <TabButton
                key={link.id}
                label={link.label || link.linked_title || 'Tab'}
                isActive={activeTab === link.linked_slug}
                onClick={() => link.linked_slug && handleTabClick(link.linked_slug)}
              />
            ))}
          </div>
        )}

        {!hasTabs && <div className="mb-4" />}

        {/* Selector bar */}
        {activeSelectors.length > 0 && token && slug && (
          <SelectorBar
            selectors={activeSelectors}
            filterValues={currentFilterValues}
            onFilterChange={setActiveFilterValues}
            onApply={handleApplyFilters}
            slug={slug}
            token={token}
          />
        )}

        {linkedLoading ? (
          <div className="flex items-center justify-center h-64 text-gray-400">
            {t('embed.loadingTab')}
          </div>
        ) : (
          <div
            className="grid gap-4"
            style={{
              gridTemplateColumns: isMobile ? '1fr' : 'repeat(12, 1fr)',
            }}
          >
            {activeCharts.map((dc) => (
              <DashboardChartCard
                key={dc.id}
                dc={dc}
                data={activeChartData[dc.id] || null}
                isMobile={isMobile}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function TabButton({
  label,
  isActive,
  onClick,
}: {
  label: string
  isActive: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
        isActive
          ? 'border-blue-500 text-blue-600'
          : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
      }`}
    >
      {label}
    </button>
  )
}

function DashboardChartCard({
  dc,
  data,
  isMobile,
}: {
  dc: DashboardChart
  data: ChartDataResponse | null
  isMobile?: boolean
}) {
  const { t } = useTranslation()
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
    indicator: config?.indicator,
    table: config?.table,
    funnel: config?.funnel,
    horizontal_bar: config?.horizontal_bar,
    general: config?.general,
    designLayout: config?.designLayout,
  }

  const cardClasses = config?.cardStyle
    ? getCardStyleClasses(config.cardStyle)
    : 'bg-white rounded-lg shadow-sm border border-gray-200 p-4'
  const cardInline = getCardInlineStyle(config?.cardStyle)
  const titleClass = getTitleSizeClass(config?.general?.titleFontSize)

  const gridStyle = isMobile ? undefined : {
    gridColumn: `${dc.layout_x + 1} / span ${dc.layout_w}`,
    gridRow: `${dc.layout_y + 1} / span ${dc.layout_h}`,
  }

  return (
    <div
      className={cardClasses}
      style={{ ...gridStyle, ...cardInline }}
    >
      <div className="flex items-start justify-between mb-1">
        <h3
          className={`font-semibold text-gray-700 ${titleClass}`}
          style={
            config?.designLayout?.title
              ? { transform: `translate(${config.designLayout.title.dx ?? 0}px, ${config.designLayout.title.dy ?? 0}px)` }
              : undefined
          }
        >
          {title}
        </h3>
        {data && <ExportButtons data={data.data} title={title} />}
      </div>
      {description && (
        <p className="text-xs text-gray-400 mb-2">{description}</p>
      )}
      <div className="flex-1">
        {data ? (
          <ChartRenderer spec={spec} data={data.data} height={isMobile ? 250 : dc.layout_h * 80} />
        ) : (
          <div className="flex items-center justify-center h-32 text-gray-400 text-sm">
            {t('embed.loadingChartData')}
          </div>
        )}
      </div>
    </div>
  )
}
