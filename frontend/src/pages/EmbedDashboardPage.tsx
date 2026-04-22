import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams } from 'react-router-dom'
import ChartRenderer from '../components/charts/ChartRenderer'
import ExportButtons from '../components/charts/ExportButtons'
import { getCardStyleClasses, getCardInlineStyle, getTitleSizeStyle } from '../components/charts/cardStyleUtils'
import PasswordGate from '../components/dashboards/PasswordGate'
import HeadingItem from '../components/dashboards/HeadingItem'
import { TvModeGrid } from '../components/dashboards/TvModeGrid'
import { useTvMode } from '../hooks/useTvMode'
import SelectorBar from '../components/selectors/SelectorBar'
import { useTranslation } from '../i18n'
import { publicApi } from '../services/api'
import type { Dashboard, DashboardChart, FilterValue, ChartSpec, ChartDataResponse, ChartDisplayConfig, HeadingConfig } from '../services/api'
import { UI_VERSION } from '../version'

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

  // Per-tab filter state. Key is 'main' or a linked dashboard slug, so each
  // tab keeps its own selector values across switches (mirrors how the JS
  // dashboard guide treats `tabs[*].selectors`).
  const [filterValuesByTab, setFilterValuesByTab] = useState<Record<string, Record<string, unknown>>>({})

  // Tab state
  const [activeTab, setActiveTab] = useState<string>('main')
  const [linkedCache, setLinkedCache] = useState<Record<string, TabData>>({})
  const [linkedLoading, setLinkedLoading] = useState(false)

  // TV mode (?tv=1). `tvKey` is incremented by the "Reset layout" button to
  // remount TvModeGrid so it picks up the cleared localStorage state.
  const { tvMode, setTvMode } = useTvMode()
  const [tvKey, setTvKey] = useState(0)
  // Per-linked-tab storageKey: each tab persists its own RGL layout under a
  // distinct key, mirroring how `filterValuesByTab` keeps tab-scoped filters.
  const tvStorageKey = activeTab === 'main' ? (slug ?? '') : activeTab
  // Resets the persisted TV layout for the active tab and remounts the grid
  // (via tvKey++) so it re-seeds defaults. Wrapped in try/catch because
  // localStorage can throw in privacy mode / when storage is disabled.
  const handleTvReset = (): void => {
    try {
      localStorage.removeItem('tv_layout_' + tvStorageKey)
    } catch {
      /* private mode / disabled storage — silently skip */
    }
    setTvKey((k) => k + 1)
  }

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
    async (dash: Dashboard, authToken: string, filters?: Record<string, unknown>) => {
      if (!slug) return
      if (refreshingRef.current) return
      refreshingRef.current = true
      setRefreshing(true)

      const activeFilters = filters || {}
      const hasFilters = Object.keys(activeFilters).length > 0
      const filterList: FilterValue[] = hasFilters
        ? Object.entries(activeFilters).map(([name, value]) => ({ name, value }))
        : []

      try {
        const promises = dash.charts
          .filter((c) => c.item_type !== 'heading' && c.chart_id != null)
          .map((c) => {
            const fetcher = hasFilters
              ? publicApi.getDashboardChartDataFiltered(slug, c.id, authToken, filterList)
              : publicApi.getDashboardChartData(slug, c.id, authToken)
            return fetcher
              .then((data) => {
                setChartData((prev) => ({ ...prev, [c.id]: data }))
                return { dcId: c.id, data }
              })
              .catch((err) => {
                const axiosErr = err as { response?: { status?: number } }
                if (axiosErr?.response?.status === 401) {
                  throw err
                }
                return { dcId: c.id, data: null }
              })
          })
        await Promise.all(promises)
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

  const fetchLinkedChartData = useCallback(
    async (
      linkedSlug: string,
      dash: Dashboard,
      authToken: string,
      filters?: Record<string, unknown>,
    ): Promise<Record<number, ChartDataResponse>> => {
      if (!slug) return {}

      const activeFilters = filters || {}
      const hasFilters = Object.keys(activeFilters).length > 0
      const filterList: FilterValue[] = hasFilters
        ? Object.entries(activeFilters).map(([name, value]) => ({ name, value }))
        : []

      const promises = dash.charts
        .filter((c) => c.item_type !== 'heading' && c.chart_id != null)
        .map((c) => {
          const fetcher = hasFilters
            ? publicApi.getLinkedDashboardChartDataFiltered(slug, linkedSlug, c.id, authToken, filterList)
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
    [slug],
  )

  // Apply filters for the *active* tab (main or a linked dashboard slug).
  // The SelectorBar fires this whenever its draft changes (auto-apply with
  // debounce — see SelectorBar.tsx).
  const handleFilterApply = useCallback(
    (tabId: string, values: Record<string, unknown>) => {
      setFilterValuesByTab((prev) => ({ ...prev, [tabId]: values }))

      if (!token) return
      if (tabId === 'main') {
        if (dashboard) fetchAllChartData(dashboard, token, values)
        return
      }

      const cached = linkedCache[tabId]
      if (!cached) return
      fetchLinkedChartData(tabId, cached.dashboard, token, values)
        .then((freshData) => {
          setLinkedCache((prev) => ({
            ...prev,
            [tabId]: { ...prev[tabId], chartData: freshData },
          }))
          setLastUpdatedAt(new Date())
        })
        .catch(() => {})
    },
    [dashboard, token, fetchAllChartData, fetchLinkedChartData, linkedCache],
  )

  const handleTabClick = useCallback(
    async (tabSlug: string) => {
      if (tabSlug === activeTab) return
      setActiveTab(tabSlug)
      // Per-tab filters: do NOT clear — each tab remembers its own state.

      // Main tab: data already loaded
      if (tabSlug === 'main') return

      // Already cached
      if (linkedCache[tabSlug]) return

      // Fetch linked dashboard
      if (!slug || !token) return
      setLinkedLoading(true)
      try {
        const linkedDash = await publicApi.getLinkedDashboard(slug, tabSlug, token)
        // Use this tab's filters if any (will be initialized by SelectorBar
        // defaults shortly after the dashboard renders).
        const tabFilters = filterValuesByTab[tabSlug] || {}
        const linkedData = await fetchLinkedChartData(tabSlug, linkedDash, token, tabFilters)
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
    [activeTab, linkedCache, slug, token, fetchLinkedChartData, filterValuesByTab],
  )

  // Load dashboard once authenticated
  useEffect(() => {
    if (!slug || !token) return

    setLoading(true)
    publicApi
      .getDashboard(slug, token)
      .then((d) => {
        setDashboard(d)
        setLoading(false)
        fetchAllChartData(d, token)
      })
      .catch((err) => {
        const axiosErr = err as { response?: { status?: number } }
        if (axiosErr?.response?.status === 401) {
          sessionStorage.removeItem(SESSION_KEY_PREFIX + slug)
          setToken(null)
        } else {
          setError(t('embed.dashboardNotFound'))
        }
        setLoading(false)
      })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug, token])

  // Auto-refresh interval — re-runs the active tab with its current filters.
  useEffect(() => {
    if (!dashboard || !token || !slug) return

    const intervalMs = dashboard.refresh_interval_minutes * 60 * 1000
    const timer = setInterval(async () => {
      const tabFilters = filterValuesByTab[activeTab] || {}
      if (activeTab === 'main') {
        fetchAllChartData(dashboard, token, tabFilters)
      } else {
        const cached = linkedCache[activeTab]
        if (cached) {
          try {
            const freshData = await fetchLinkedChartData(activeTab, cached.dashboard, token, tabFilters)
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
  }, [dashboard, token, slug, activeTab, linkedCache, filterValuesByTab, fetchAllChartData, fetchLinkedChartData])

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
  let activeSelectors = dashboard.selectors || []

  if (activeTab !== 'main' && linkedCache[activeTab]) {
    activeCharts = linkedCache[activeTab].dashboard.charts
    activeChartData = linkedCache[activeTab].chartData
    activeSelectors = linkedCache[activeTab].dashboard.selectors || []
  }

  const activeFilterValues = filterValuesByTab[activeTab] || {}

  /**
   * TV-mode chart cell renderer. Mirrors `DashboardChartCard` but:
   *  - drops the CSS-grid `gridStyle` (RGL positions the cell itself);
   *  - uses `h-full flex flex-col` so the chart fills the RGL cell;
   *  - applies inline `fontSize` to the title (Tailwind class loses to inline);
   *  - forwards `fontScale` and `chartHeight` from `TvCellMeasurer` into the
   *    chart so axes/legend/values scale with cell size.
   *
   * Closure access to `activeChartData` keeps it in sync with the active tab
   * without having to thread the map through `TvModeGrid` props twice.
   */
  const renderTvChartCard = (
    dc: DashboardChart,
    fontScale: number,
    _chartHeight: number,
  ): React.ReactNode => {
    const data = activeChartData[dc.id] || null
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

    const titleTransformStyle: React.CSSProperties | undefined = config?.designLayout?.title
      ? {
          transform: `translate(${config.designLayout.title.dx ?? 0}px, ${config.designLayout.title.dy ?? 0}px)`,
        }
      : undefined

    // Title size in TV mode is taken as-is from the editor slider
    // (`title_font_size_override`) or the legacy preset (`general.titleFontSize`).
    // We intentionally do NOT multiply by `fontScale` — the user configures the
    // exact size in the editor and TV mode must honour it verbatim.
    const effectiveTitleSize = dc.title_font_size_override || config?.general?.titleFontSize
    const titleStyle: React.CSSProperties = {
      ...getTitleSizeStyle(effectiveTitleSize),
      ...titleTransformStyle,
    }

    return (
      <div className={`${cardClasses} h-full flex flex-col group relative`} style={cardInline}>
        {!dc.hide_title && (
          <div className="flex items-start mb-1 flex-shrink-0">
            <h3 className="font-semibold text-gray-700 truncate flex-1 min-w-0" style={titleStyle}>
              {title}
            </h3>
          </div>
        )}
        {data && (
          <div className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity duration-150 z-10">
            <ExportButtons data={data.data} title={title} />
          </div>
        )}
        <div className="flex-1 min-h-0 overflow-hidden">
          {data ? (
            // Pass "100%" so ResponsiveContainer measures the actual flex
            // child height instead of using the pre-computed `chartHeight`
            // (which subtracts a fixed 44px title row — wrong when the TV
            // title font is larger and pushes the content down beyond the
            // card's `overflow:hidden` boundary, clipping the legend).
            // `chartHeight` is still forwarded for the `fillHeight` logic
            // used by the indicator renderer, which needs a concrete pixel
            // value. Non-indicator charts ignore it under "100%".
            <ChartRenderer
              spec={spec}
              data={data.data}
              height="100%"
              fontScale={fontScale}
              fillHeight
            />
          ) : (
            <div className="animate-pulse h-full w-full bg-gray-100 rounded" />
          )}
        </div>
      </div>
    )
  }

  /**
   * TV-mode heading cell renderer. Wraps `HeadingItem` so it fills the RGL
   * cell and forwards `fontScale` so the heading scales with the cell size.
   */
  const renderTvHeading = (dc: DashboardChart, fontScale: number): React.ReactNode => {
    const heading: HeadingConfig =
      (dc.heading_config as HeadingConfig) || {
        text: '',
        level: 2,
        align: 'left',
        divider: false,
      }
    return (
      <div className="h-full w-full">
        <HeadingItem heading={heading} fontScale={fontScale} />
      </div>
    )
  }
  return (
    <div className={tvMode ? 'min-h-screen bg-gray-50 p-2' : 'min-h-screen bg-gray-50 p-3 md:p-6'}>
      <div className={tvMode ? 'w-full' : 'max-w-7xl mx-auto'}>
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
            <span className="text-gray-300">|</span>
            <label className="flex items-center space-x-1 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={tvMode}
                onChange={(e) => setTvMode(e.target.checked)}
                className="h-3 w-3 cursor-pointer"
              />
              <span>{t('embed.tvMode')}</span>
            </label>
            {tvMode && (
              <button
                type="button"
                onClick={handleTvReset}
                className="px-2 py-0.5 text-xs text-gray-500 border border-gray-300 rounded hover:bg-gray-100 hover:text-gray-700 transition-colors"
              >
                {t('embed.tvModeReset')}
              </button>
            )}
          </div>
        </div>
        {dashboard.description && !tvMode && (
          <p className="text-gray-500 mb-4">{dashboard.description}</p>
        )}

        {/* Tab bar */}
        {hasTabs && (
          <div className="flex space-x-1 border-b border-gray-200 mb-4">
            <TabButton
              label={dashboard.tab_label || dashboard.title}
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

        {/* Selector bar — per-tab selectors. Each linked dashboard has its
            own selectors loaded together with its dashboard payload. The
            linkedSlug prop tells the bar to fetch options via the linked
            endpoint so the JWT (issued for the main slug) stays valid. */}
        {activeSelectors.length > 0 && token && slug && (
          <SelectorBar
            // Force a fresh instance per tab so internal draft state resets
            // and default values re-initialize for the new selector list.
            key={activeTab}
            selectors={activeSelectors}
            slug={slug}
            linkedSlug={activeTab === 'main' ? undefined : activeTab}
            token={token}
            filterValues={activeFilterValues}
            onApply={(values) => handleFilterApply(activeTab, values)}
          />
        )}

        {linkedLoading ? (
          <div className="flex items-center justify-center h-64 text-gray-400">
            {t('embed.loadingTab')}
          </div>
        ) : tvMode ? (
          <TvModeGrid
            key={`${tvKey}_${tvStorageKey}`}
            storageKey={tvStorageKey}
            charts={activeCharts}
            chartData={activeChartData}
            renderChart={renderTvChartCard}
            renderHeading={renderTvHeading}
          />
        ) : (
          <div
            className="grid gap-4"
            style={{
              gridTemplateColumns: isMobile ? '1fr' : 'repeat(12, 1fr)',
            }}
          >
            {activeCharts.map((dc) => {
              if (dc.item_type === 'heading') {
                const heading: HeadingConfig =
                  (dc.heading_config as HeadingConfig) || {
                    text: '',
                    level: 2,
                    align: 'left',
                    divider: false,
                  }
                const gridStyle = isMobile
                  ? undefined
                  : {
                      gridColumn: `${dc.layout_x + 1} / span ${dc.layout_w}`,
                      gridRow: `${dc.layout_y + 1} / span ${dc.layout_h}`,
                    }
                return (
                  <div key={dc.id} style={gridStyle}>
                    <HeadingItem heading={heading} />
                  </div>
                )
              }
              return (
                <DashboardChartCard
                  key={dc.id}
                  dc={dc}
                  data={activeChartData[dc.id] || null}
                  isMobile={isMobile}
                />
              )
            })}
          </div>
        )}

        {/* Footer */}
        <div className="mt-6 pt-3 border-t border-gray-200 flex justify-end">
          <span className="text-xs text-gray-300">{t('footer.version')} {UI_VERSION}</span>
        </div>
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
  const effectiveTitleSize = dc.title_font_size_override || config?.general?.titleFontSize

  const gridStyle = isMobile ? undefined : {
    gridColumn: `${dc.layout_x + 1} / span ${dc.layout_w}`,
    gridRow: `${dc.layout_y + 1} / span ${dc.layout_h}`,
  }

  return (
    <div
      className={`${cardClasses} group relative`}
      style={{ ...gridStyle, ...cardInline }}
    >
      {!dc.hide_title && (
        <div className="flex items-start mb-1">
          <h3
            className="font-semibold text-gray-700 flex-1 min-w-0"
            style={{
              ...getTitleSizeStyle(effectiveTitleSize),
              ...(config?.designLayout?.title
                ? { transform: `translate(${config.designLayout.title.dx ?? 0}px, ${config.designLayout.title.dy ?? 0}px)` }
                : {}),
            }}
          >
            {title}
          </h3>
        </div>
      )}
      {data && (
        <div className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity duration-150 z-10">
          <ExportButtons data={data.data} title={title} />
        </div>
      )}
      {description && (
        <p className="text-xs text-gray-400 mb-2">{description}</p>
      )}
      <div className="flex-1">
        {data ? (
          <ChartRenderer spec={spec} data={data.data} height={isMobile ? 250 : dc.layout_h * 80} />
        ) : (
          <div className="animate-pulse h-32 w-full bg-gray-100 rounded" />
        )}
      </div>
    </div>
  )
}
