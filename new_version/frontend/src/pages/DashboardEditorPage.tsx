import { useState, useCallback, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useParams, useNavigate } from 'react-router-dom'
import ReactGridLayout, { useContainerWidth } from 'react-grid-layout'
import type { Layout } from 'react-grid-layout'
import 'react-grid-layout/css/styles.css'
import 'react-resizable/css/styles.css'
import ChartRenderer from '../components/charts/ChartRenderer'
import ChartSettingsPanel from '../components/charts/ChartSettingsPanel'
import DesignModeOverlay from '../components/charts/DesignModeOverlay'
import DesignModeToolbar from '../components/charts/design/DesignModeToolbar'
import SelectorEditorSection from '../components/selectors/SelectorEditorSection'
import HeadingItem from '../components/dashboards/HeadingItem'
import { useDesignMode } from '../hooks/useDesignMode'
import { useTvMode } from '../hooks/useTvMode'
import { useElementSize } from '../hooks/useElementSize'
import { useUpdateChartConfig } from '../hooks/useCharts'
import {
  useDashboard,
  useDashboardList,
  useUpdateDashboard,
  useUpdateDashboardLayout,
  useUpdateChartOverride,
  useRemoveChartFromDashboard,
  useChangeDashboardPassword,
  useAddDashboardLink,
  useRemoveDashboardLink,
  useUpdateDashboardLinks,
  useAddDashboardHeading,
  useUpdateDashboardHeading,
} from '../hooks/useDashboards'
import { chartsApi } from '../services/api'
import { copyToClipboard } from '../utils/clipboard'
import { useTranslation } from '../i18n'
import type { DashboardChart, DashboardLink, ChartSpec, ChartDataResponse, ChartDisplayConfig, HeadingConfig } from '../services/api'

const GRID_COLS = 12
const ROW_HEIGHT = 120

const GRID_PRESETS = [1, 2, 3, 4] as const

function detectGridPreset(layout: Layout): number | null {
  if (layout.length === 0) return null
  const firstW = layout[0].w
  const allSame = layout.every((item) => item.w === firstW)
  if (!allSame) return null
  const colMap: Record<number, number> = { 12: 1, 6: 2, 4: 3, 3: 4 }
  return colMap[firstW] ?? null
}

function GridPresetIcon({ columns, active }: { columns: number; active: boolean }) {
  const cells = Array.from({ length: columns }, (_, i) => i)
  return (
    <div
      className={`inline-flex gap-px p-1 rounded border-2 ${
        active ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-white'
      }`}
    >
      {cells.map((i) => (
        <div
          key={i}
          className={`rounded-sm ${active ? 'bg-blue-400' : 'bg-gray-300'}`}
          style={{ width: `${Math.max(20 / columns, 4)}px`, height: 14 }}
        />
      ))}
    </div>
  )
}

export default function DashboardEditorPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const dashboardId = Number(id)
  const { t } = useTranslation()

  const { data: dashboard, isLoading, refetch } = useDashboard(dashboardId)
  const { data: allDashboards } = useDashboardList(1, 100)
  const updateDashboard = useUpdateDashboard()
  const updateLayout = useUpdateDashboardLayout()
  const updateOverride = useUpdateChartOverride()
  const removeChart = useRemoveChartFromDashboard()
  const changePassword = useChangeDashboardPassword()
  const addLink = useAddDashboardLink()
  const removeLink = useRemoveDashboardLink()
  const updateLinks = useUpdateDashboardLinks()
  const addHeading = useAddDashboardHeading()
  const updateHeading = useUpdateDashboardHeading()

  const [editingTitle, setEditingTitle] = useState(false)
  const [titleValue, setTitleValue] = useState('')
  const [descValue, setDescValue] = useState('')
  const [refreshInterval, setRefreshInterval] = useState(10)
  const [chartData, setChartData] = useState<Record<number, ChartDataResponse>>({})
  const [newPassword, setNewPassword] = useState<string | null>(null)
  const [copiedLink, setCopiedLink] = useState(false)

  // Grid layout state
  const [gridLayout, setGridLayout] = useState<Layout>([])
  const [layoutDirty, setLayoutDirty] = useState(false)

  // TV mode — relaxes min-size constraints and enables font auto-scaling inside chart cards
  const { tvMode, setTvMode } = useTvMode()

  // react-grid-layout v2 container width (used in non-TV mode where the page sits
  // inside Layout's <main className="max-w-7xl"> and the actual width depends on
  // the column constraint).
  const { containerRef, width: measuredContainerWidth, mounted, measureWidth } = useContainerWidth()

  // Direct viewport width for TV mode. Bypasses useContainerWidth's measurement
  // entirely because in TV mode the editor is rendered through a portal directly
  // into document.body, so we know the grid is always the full viewport width
  // minus the root div's p-2 padding (8px each side = 16px total). Reading from
  // window.innerWidth on mount + updating on resize is more reliable than
  // racing react-grid-layout's hardcoded 1280px initial state on page refresh
  // with ?tv=1.
  const [viewportWidth, setViewportWidth] = useState<number>(() =>
    typeof window !== 'undefined' ? window.innerWidth : 1280,
  )
  useEffect(() => {
    if (typeof window === 'undefined') return
    const handler = (): void => setViewportWidth(window.innerWidth)
    window.addEventListener('resize', handler)
    return () => window.removeEventListener('resize', handler)
  }, [])

  // Effective grid width: in TV mode, viewport minus padding (p-2 = 8px each
  // side); otherwise the width measured against Layout's max-w-7xl container.
  const containerWidth = tvMode ? Math.max(0, viewportWidth - 16) : measuredContainerWidth

  // Stable ref to measureWidth so the re-measure effect below doesn't loop
  const measureWidthRef = useRef(measureWidth)
  useEffect(() => {
    measureWidthRef.current = measureWidth
  }, [measureWidth])

  // Re-measure non-TV grid width when TV mode toggles off — the page transitions
  // back from fullscreen overlay to the Layout-bound container and ReactGridLayout
  // needs a fresh width to reposition charts inside the max-w-7xl frame.
  useEffect(() => {
    if (tvMode) return
    const timer = setTimeout(() => {
      measureWidthRef.current?.()
    }, 50)
    return () => clearTimeout(timer)
  }, [tvMode])

  useEffect(() => {
    if (dashboard) {
      setTitleValue(dashboard.title)
      setDescValue(dashboard.description || '')
      setRefreshInterval(dashboard.refresh_interval_minutes)
      setGridLayout(
        dashboard.charts.map((c) => ({
          i: String(c.id),
          x: c.layout_x,
          y: c.layout_y,
          w: c.layout_w,
          h: c.layout_h,
          minW: 2,
          minH: c.item_type === 'heading' ? 1 : 2,
          maxH: c.item_type === 'heading' ? 4 : undefined,
        })),
      )

      // Load chart data
      for (const dc of dashboard.charts) {
        if (dc.item_type !== 'chart' || dc.chart_id == null) continue
        const cid = dc.chart_id
        if (!chartData[cid]) {
          chartsApi.getData(cid).then((data) => {
            setChartData((prev) => ({ ...prev, [cid]: data }))
          }).catch(() => {})
        }
      }
    }
  }, [dashboard])

  const handleSaveTitle = () => {
    if (!titleValue.trim()) return
    updateDashboard.mutate(
      {
        id: dashboardId,
        data: {
          title: titleValue.trim(),
          description: descValue.trim() || undefined,
          refresh_interval_minutes: refreshInterval,
        },
      },
      { onSuccess: () => { setEditingTitle(false); refetch() } },
    )
  }

  const handleSaveLayout = () => {
    const layouts = gridLayout.map((item, idx) => ({
      id: Number(item.i),
      x: item.x,
      y: item.y,
      w: item.w,
      h: item.h,
      sort_order: idx,
    }))
    updateLayout.mutate(
      { id: dashboardId, data: { layouts } },
      { onSuccess: () => { setLayoutDirty(false); refetch() } },
    )
  }

  const handleLayoutChange = useCallback((newLayout: Layout) => {
    setGridLayout(newLayout)
    setLayoutDirty(true)
  }, [])

  const handleGridPreset = useCallback((columns: number) => {
    const colWidth = GRID_COLS / columns
    const defaultH = 3
    setGridLayout((prev) => {
      const sorted = [...prev].sort((a, b) => {
        if (a.y !== b.y) return a.y - b.y
        return a.x - b.x
      })
      return sorted.map((item, idx) => ({
        ...item,
        w: colWidth,
        h: item.h || defaultH,
        x: (idx % columns) * colWidth,
        y: Math.floor(idx / columns) * (item.h || defaultH),
      }))
    })
    setLayoutDirty(true)
  }, [])

  const handleChangePassword = () => {
    changePassword.mutate(dashboardId, {
      onSuccess: (data) => setNewPassword(data.password),
    })
  }

  const handleCopyLink = () => {
    if (!dashboard) return
    const url = `${window.location.origin}/embed/dashboard/${dashboard.slug}`
    copyToClipboard(url).then((ok) => {
      if (!ok) return
      setCopiedLink(true)
      setTimeout(() => setCopiedLink(false), 2000)
    })
  }

  const handleRemoveChart = (dcId: number) => {
    if (!confirm(t('editor.confirmRemoveChart'))) return
    removeChart.mutate(
      { dashboardId, dcId },
      { onSuccess: () => refetch() },
    )
  }

  const handleUpdateOverride = useCallback(
    (dcId: number, field: 'title_override' | 'description_override', value: string) => {
      updateOverride.mutate(
        { dashboardId, dcId, data: { [field]: value || null } },
        { onSuccess: () => refetch() },
      )
    },
    [dashboardId, updateOverride, refetch],
  )

  const handleAddHeading = () => {
    addHeading.mutate(
      {
        dashboardId,
        data: {
          heading: {
            text: t('editor.headingPlaceholder'),
            level: 2,
            align: 'left',
            divider: false,
          },
          layout_x: 0,
          layout_y: 9999,
          layout_w: 12,
          layout_h: 1,
        },
      },
      { onSuccess: () => refetch() },
    )
  }

  const handleUpdateHeading = useCallback(
    (dcId: number, heading: HeadingConfig) => {
      updateHeading.mutate(
        { dashboardId, dcId, data: { heading } },
        { onSuccess: () => refetch() },
      )
    },
    [dashboardId, updateHeading, refetch],
  )

  if (isLoading) {
    return <div className="flex items-center justify-center h-64 text-gray-500">{t('common.loading')}</div>
  }

  if (!dashboard) {
    return <div className="text-center text-gray-500 py-12">{t('embed.dashboardNotFound')}</div>
  }

  // In TV mode we render the editor through a portal directly into document.body.
  // The default route is wrapped in <main className="max-w-7xl mx-auto …"> from
  // Layout.tsx which constrains the available width. `position: fixed` alone is
  // not enough on initial mount with `?tv=1` (page refresh) because react-grid-
  // layout's first width measurement can lock to the parent-constrained width
  // before the fixed positioning settles, leaving a permanent right margin.
  // The portal moves the DOM out from under <main> entirely so containerWidth
  // is always measured against the viewport.
  const editorTree = (
    <div className={tvMode ? 'fixed inset-0 z-40 bg-gray-50 overflow-auto p-2 space-y-2' : 'space-y-6'}>
      {/* Header */}
      <div className={tvMode ? 'card py-2 px-3' : 'card'}>
        <div className="flex justify-between items-start">
          <div className="flex-1">
            {editingTitle ? (
              <div className="space-y-2">
                <input
                  type="text"
                  value={titleValue}
                  onChange={(e) => setTitleValue(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-lg font-semibold"
                />
                <textarea
                  value={descValue}
                  onChange={(e) => setDescValue(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  rows={2}
                  placeholder={t('editor.descriptionOptional')}
                />
                <div className="flex items-center space-x-2">
                  <label className="text-sm text-gray-600">{t('editor.autoRefresh')}</label>
                  <select
                    value={refreshInterval}
                    onChange={(e) => setRefreshInterval(Number(e.target.value))}
                    className="px-2 py-1 border border-gray-300 rounded text-sm"
                  >
                    <option value={1}>{t('editor.min1')}</option>
                    <option value={5}>{t('editor.min5')}</option>
                    <option value={10}>{t('editor.min10')}</option>
                    <option value={15}>{t('editor.min15')}</option>
                    <option value={30}>{t('editor.min30')}</option>
                    <option value={60}>{t('editor.min60')}</option>
                  </select>
                </div>
                <div className="flex space-x-2">
                  <button onClick={handleSaveTitle} className="btn btn-primary text-sm">
                    {t('common.save')}
                  </button>
                  <button onClick={() => setEditingTitle(false)} className="btn btn-secondary text-sm">
                    {t('common.cancel')}
                  </button>
                </div>
              </div>
            ) : (
              <div>
                <h2
                  className="text-xl font-bold cursor-pointer hover:text-blue-600"
                  onClick={() => setEditingTitle(true)}
                  title={t('editor.clickToEdit')}
                >
                  {dashboard.title}
                </h2>
                {dashboard.description && (
                  <p className="text-gray-500 mt-1">{dashboard.description}</p>
                )}
                <p className="text-xs text-gray-400 mt-1">
                  {`${t('editor.autoRefresh')} ${dashboard.refresh_interval_minutes} min`}
                </p>
              </div>
            )}
          </div>

          <div className="flex items-center space-x-2 ml-4">
            {dashboard.charts.length > 0 && (
              <div className="flex items-center space-x-1 mr-2">
                <span className="text-xs text-gray-500 mr-1">{t('editor.gridFormat')}:</span>
                {GRID_PRESETS.map((cols) => {
                  const active = detectGridPreset(gridLayout) === cols
                  const labels = {
                    1: t('editor.columns1'),
                    2: t('editor.columns2'),
                    3: t('editor.columns3'),
                    4: t('editor.columns4'),
                  } as const
                  return (
                    <button
                      key={cols}
                      onClick={() => handleGridPreset(cols)}
                      className="p-0.5 rounded hover:bg-gray-100 transition-colors"
                      title={labels[cols]}
                    >
                      <GridPresetIcon columns={cols} active={active} />
                    </button>
                  )
                })}
              </div>
            )}
            <button
              onClick={handleAddHeading}
              disabled={addHeading.isPending}
              className="btn btn-secondary text-sm"
            >
              {addHeading.isPending ? t('common.saving') : t('editor.addHeading')}
            </button>
            <button onClick={handleCopyLink} className="btn btn-secondary text-sm">
              {copiedLink ? t('common.copied') : t('editor.copyLink')}
            </button>
            <button onClick={handleChangePassword} className="btn btn-secondary text-sm">
              {t('editor.changePassword')}
            </button>
            <label className="flex items-center space-x-1 text-sm text-gray-600 cursor-pointer select-none ml-2">
              <input
                type="checkbox"
                checked={tvMode}
                onChange={(e) => setTvMode(e.target.checked)}
                className="h-4 w-4 cursor-pointer"
              />
              <span>{t('embed.tvMode')}</span>
            </label>
            {layoutDirty && (
              <button onClick={handleSaveLayout} className="btn btn-primary text-sm">
                {updateLayout.isPending ? t('common.saving') : t('editor.saveLayout')}
              </button>
            )}
          </div>
        </div>

        {newPassword && (
          <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded">
            <p className="text-sm text-green-700">
              {t('editor.newPassword')} <span className="font-mono font-bold">{newPassword}</span>
            </p>
            <p className="text-xs text-green-500 mt-1">{t('editor.newPasswordHelp')}</p>
          </div>
        )}

        {dashboard.charts.length > 0 && (
          <p className="mt-3 text-xs text-gray-400">
            {t('editor.dragHelp')}
          </p>
        )}
      </div>

      {/* Draggable/Resizable Grid */}
      <div ref={containerRef as React.RefObject<HTMLDivElement>} className="min-h-[200px]">
        {mounted && dashboard.charts.length > 0 && (
          <ReactGridLayout
            layout={
              tvMode
                ? gridLayout.map((item) => ({ ...item, minW: 1, minH: 1, maxH: undefined }))
                : gridLayout
            }
            onLayoutChange={handleLayoutChange}
            width={containerWidth}
            gridConfig={{
              cols: GRID_COLS,
              rowHeight: tvMode ? Math.max(20, Math.floor(ROW_HEIGHT / 3)) : ROW_HEIGHT,
              margin: tvMode ? ([8, 8] as const) : ([16, 16] as const),
              containerPadding: [0, 0] as const,
              maxRows: Infinity,
            }}
            dragConfig={{ enabled: true, bounded: false, threshold: 3 }}
            resizeConfig={{ enabled: true, handles: ['se'] }}
          >
            {dashboard.charts.map((dc) => (
              <div key={String(dc.id)} className="overflow-visible">
                {dc.item_type === 'heading' ? (
                  <EditorHeadingCard
                    dc={dc}
                    onRemove={() => handleRemoveChart(dc.id)}
                    onUpdateHeading={(h) => handleUpdateHeading(dc.id, h)}
                    tvMode={tvMode}
                  />
                ) : (
                  <EditorChartCard
                    dc={dc}
                    data={dc.chart_id != null ? chartData[dc.chart_id] || null : null}
                    onRemove={() => handleRemoveChart(dc.id)}
                    onUpdateOverride={handleUpdateOverride}
                    tvMode={tvMode}
                  />
                )}
              </div>
            ))}
          </ReactGridLayout>
        )}
      </div>

      {dashboard.charts.length === 0 && (
        <div className="card text-center text-gray-400 py-12">
          {t('editor.noCharts')}
        </div>
      )}

      {/* Selectors Section */}
      <SelectorEditorSection dashboardId={dashboardId} charts={dashboard.charts} />

      {/* Linked Dashboards Section */}
      <LinkedDashboardsSection
        dashboardId={dashboardId}
        linkedDashboards={dashboard.linked_dashboards || []}
        allDashboards={allDashboards?.dashboards || []}
        onAddLink={(linkedId, label) => {
          addLink.mutate(
            { dashboardId, data: { linked_dashboard_id: linkedId, label } },
            { onSuccess: () => refetch() },
          )
        }}
        onRemoveLink={(linkId) => {
          removeLink.mutate(
            { dashboardId, linkId },
            { onSuccess: () => refetch() },
          )
        }}
        onUpdateOrder={(links) => {
          updateLinks.mutate(
            { dashboardId, links },
            { onSuccess: () => refetch() },
          )
        }}
        isAdding={addLink.isPending}
      />

      <div className="flex justify-start">
        <button onClick={() => navigate('/charts')} className="btn btn-secondary">
          {t('editor.backToCharts')}
        </button>
      </div>
    </div>
  )

  return tvMode ? createPortal(editorTree, document.body) : editorTree
}

// Chart types that support design mode (SVG-based)
const DESIGN_MODE_CHART_TYPES = new Set(['bar', 'line', 'area', 'pie', 'scatter', 'funnel', 'horizontal_bar'])

function EditorChartCard({
  dc,
  data,
  onRemove,
  onUpdateOverride,
  tvMode,
}: {
  dc: DashboardChart
  data: ChartDataResponse | null
  onRemove: () => void
  onUpdateOverride: (dcId: number, field: 'title_override' | 'description_override', value: string) => void
  tvMode?: boolean
}) {
  const { t } = useTranslation()
  const [editTitle, setEditTitle] = useState(false)
  const [titleVal, setTitleVal] = useState(dc.title_override || '')
  const [editDesc, setEditDesc] = useState(false)
  const [descVal, setDescVal] = useState(dc.description_override || '')
  const [showSettings, setShowSettings] = useState(false)
  const [settingsPos, setSettingsPos] = useState({ x: 0, y: 0 })
  const settingsDragRef = useRef<{ startX: number; startY: number; origX: number; origY: number } | null>(null)
  const updateConfig = useUpdateChartConfig()
  const chartContainerRef = useRef<HTMLDivElement>(null)

  // TV mode font scaling — measures the chart body container and derives a scale factor.
  // Tables use a width-only formula so vertical stretching just exposes more rows
  // instead of inflating the text (mirrors TvCellMeasurer in TvModeGrid).
  const { ref: chartBodyRef, width: chartBodyWidth, height: chartBodyHeight } = useElementSize<HTMLDivElement>()
  const isTableChart = (dc.chart_type || 'bar') === 'table'
  const fontScale = tvMode
    ? isTableChart
      ? Math.max(0.4, Math.min(2.5, Math.sqrt(Math.max(1, chartBodyWidth) / 350)))
      : Math.max(0.4, Math.min(2.5, Math.sqrt(Math.max(1, chartBodyWidth * chartBodyHeight)) / 350))
    : undefined

  const title = dc.title_override || dc.chart_title || 'Chart'
  const description = dc.description_override || dc.chart_description

  const config = dc.chart_config as unknown as ChartDisplayConfig | null
  const chartType = dc.chart_type || 'bar'
  const supportsDesign = DESIGN_MODE_CHART_TYPES.has(chartType)

  const designMode = useDesignMode(config?.designLayout)

  const spec: ChartSpec = {
    title,
    chart_type: chartType as ChartSpec['chart_type'],
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
  }

  const handleConfigUpdate = (patch: Partial<ChartDisplayConfig>) => {
    if (dc.chart_id == null) return
    updateConfig.mutate({ chartId: dc.chart_id, config: patch })
  }

  const handleDesignApply = () => {
    if (dc.chart_id == null) return
    const layoutToSave = designMode.applyLayout()
    updateConfig.mutate(
      { chartId: dc.chart_id, config: { designLayout: layoutToSave } },
      { onSuccess: () => designMode.deactivate() },
    )
  }

  const handleMarginChange = (side: 'top' | 'right' | 'bottom' | 'left', value: number) => {
    designMode.updateDraft({
      margins: {
        ...designMode.draftLayout.margins,
        [side]: value,
      },
    })
  }

  return (
    <div
      className="h-full bg-white rounded-lg border border-gray-200 shadow-sm p-3 flex flex-col"
      style={{ position: 'relative' }}
      ref={chartContainerRef}
      data-design-card=""
    >
      <div className="flex justify-between items-start mb-2">
        <div className="flex-1 min-w-0">
          {editTitle ? (
            <div className="flex items-center space-x-2">
              <input
                type="text"
                value={titleVal}
                onChange={(e) => setTitleVal(e.target.value)}
                className="flex-1 px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder={t('editor.customTitle')}
                onMouseDown={(e) => e.stopPropagation()}
              />
              <button
                onClick={() => {
                  onUpdateOverride(dc.id, 'title_override', titleVal)
                  setEditTitle(false)
                }}
                className="text-xs text-blue-600 hover:text-blue-800"
              >
                {t('common.save')}
              </button>
              <button onClick={() => setEditTitle(false)} className="text-xs text-gray-400">
                {t('common.cancel')}
              </button>
            </div>
          ) : (
            <h3
              className="text-sm font-semibold cursor-pointer hover:text-blue-600 truncate"
              onClick={() => !designMode.isActive && setEditTitle(true)}
              title={t('editor.clickToEditTitle')}
              style={
                designMode.isActive && designMode.draftLayout.title
                  ? { transform: `translate(${designMode.draftLayout.title.dx ?? 0}px, ${designMode.draftLayout.title.dy ?? 0}px)` }
                  : undefined
              }
            >
              {title}
            </h3>
          )}

          {editDesc ? (
            <div className="flex items-center space-x-2 mt-1">
              <input
                type="text"
                value={descVal}
                onChange={(e) => setDescVal(e.target.value)}
                className="flex-1 px-2 py-1 border border-gray-300 rounded text-xs"
                placeholder={t('editor.customDescription')}
                onMouseDown={(e) => e.stopPropagation()}
              />
              <button
                onClick={() => {
                  onUpdateOverride(dc.id, 'description_override', descVal)
                  setEditDesc(false)
                }}
                className="text-xs text-blue-600"
              >
                {t('common.save')}
              </button>
              <button onClick={() => setEditDesc(false)} className="text-xs text-gray-400">
                {t('common.cancel')}
              </button>
            </div>
          ) : (
            <p
              className="text-xs text-gray-500 mt-0.5 cursor-pointer hover:text-blue-500 truncate"
              onClick={() => !designMode.isActive && setEditDesc(true)}
              title={t('editor.clickToEditDesc')}
            >
              {description || t('editor.addDescription')}
            </p>
          )}
        </div>

        <div className="flex space-x-1 ml-2 flex-shrink-0">
          {supportsDesign && !designMode.isActive && (
            <button
              onClick={() => designMode.activate()}
              onMouseDown={(e) => e.stopPropagation()}
              className="p-1 rounded text-xs bg-purple-50 text-purple-600 hover:bg-purple-100"
              title={t('designMode.designMode')}
            >
              {t('editor.design')}
            </button>
          )}
          <button
            onClick={(e) => {
              if (!showSettings) {
                const rect = e.currentTarget.getBoundingClientRect()
                setSettingsPos({
                  x: Math.min(rect.left, window.innerWidth - 440),
                  y: Math.min(rect.bottom + 4, window.innerHeight - 400),
                })
              }
              setShowSettings(!showSettings)
            }}
            onMouseDown={(e) => e.stopPropagation()}
            className={`p-1 rounded text-xs ${
              showSettings
                ? 'bg-blue-100 text-blue-700'
                : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
            }`}
            title={t('charts.chartSettings')}
          >
            {t('charts.settings')}
          </button>
          <button
            onClick={onRemove}
            className="p-1 rounded text-xs bg-red-50 text-red-500 hover:bg-red-100"
            title={t('editor.removeFromDashboard')}
          >
            {t('editor.removeChart')}
          </button>
        </div>
      </div>

      {designMode.isActive && (
        <div onMouseDown={(e) => e.stopPropagation()}>
          <DesignModeToolbar
            selectedElement={designMode.selectedElement}
            draftLayout={designMode.draftLayout}
            onResetElement={designMode.resetElement}
            onResetAll={designMode.resetAll}
            onApply={handleDesignApply}
            onCancel={designMode.deactivate}
            isSaving={updateConfig.isPending}
            chartType={chartType}
          />
        </div>
      )}

      {showSettings && !designMode.isActive && createPortal(
        <div
          onMouseDown={(e) => e.stopPropagation()}
          style={{
            position: 'fixed',
            left: settingsPos.x,
            top: settingsPos.y,
            zIndex: 50000,
            width: 420,
            maxHeight: '80vh',
          }}
          className="bg-white rounded-xl shadow-2xl border border-gray-300 overflow-hidden"
        >
          <div
            className="flex items-center justify-between px-4 py-2 bg-gray-100 border-b border-gray-200 cursor-move select-none"
            onMouseDown={(e) => {
              e.preventDefault()
              const startX = e.clientX
              const startY = e.clientY
              settingsDragRef.current = { startX, startY, origX: settingsPos.x, origY: settingsPos.y }

              const onMove = (ev: MouseEvent) => {
                if (!settingsDragRef.current) return
                setSettingsPos({
                  x: settingsDragRef.current.origX + (ev.clientX - settingsDragRef.current.startX),
                  y: settingsDragRef.current.origY + (ev.clientY - settingsDragRef.current.startY),
                })
              }
              const onUp = () => {
                settingsDragRef.current = null
                document.removeEventListener('mousemove', onMove)
                document.removeEventListener('mouseup', onUp)
              }
              document.addEventListener('mousemove', onMove)
              document.addEventListener('mouseup', onUp)
            }}
          >
            <span className="text-sm font-semibold text-gray-700">{t('charts.chartSettings')}</span>
            <button
              onClick={() => setShowSettings(false)}
              className="text-gray-400 hover:text-gray-600 text-lg leading-none"
            >
              &times;
            </button>
          </div>
          <div className="overflow-y-auto" style={{ maxHeight: 'calc(80vh - 40px)' }}>
            <ChartSettingsPanel
              chartType={chartType}
              config={config || { x: 'x', y: 'y' }}
              onApply={handleConfigUpdate}
              isSaving={updateConfig.isPending}
            />
          </div>
        </div>,
        document.body,
      )}

      <div
        ref={chartBodyRef}
        className="flex-1 min-h-0"
        onMouseDown={designMode.isActive ? (e) => e.stopPropagation() : undefined}
      >
        {data ? (
          <ChartRenderer
            spec={spec}
            data={data.data}
            height="100%"
            designLayout={designMode.isActive ? designMode.draftLayout : config?.designLayout}
            fontScale={fontScale}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">
            {t('embed.loadingChartData')}
          </div>
        )}
      </div>

      {designMode.isActive && data && (
        <DesignModeOverlay
          containerRef={chartContainerRef}
          selectedElement={designMode.selectedElement}
          draftLayout={designMode.draftLayout}
          chartType={chartType}
          onSelectElement={designMode.selectElement}
          onDragStart={designMode.onDragStart}
          onDragMove={designMode.onDragMove}
          onDragEnd={designMode.onDragEnd}
          onMarginChange={handleMarginChange}
          isDragging={designMode.isDragging}
        />
      )}
    </div>
  )
}

function EditorHeadingCard({
  dc,
  onRemove,
  onUpdateHeading,
  tvMode,
}: {
  dc: DashboardChart
  onRemove: () => void
  onUpdateHeading: (heading: HeadingConfig) => void
  tvMode?: boolean
}) {
  const { t } = useTranslation()
  const { ref: headingRef, width: headingWidth, height: headingHeight } = useElementSize<HTMLDivElement>()
  const fontScale = tvMode
    ? Math.max(0.4, Math.min(2.5, Math.sqrt(Math.max(1, headingWidth * headingHeight)) / 350))
    : undefined
  const heading: HeadingConfig =
    (dc.heading_config as HeadingConfig) || {
      text: '',
      level: 2,
      align: 'left',
      divider: false,
    }
  return (
    <div
      ref={headingRef}
      className="h-full bg-white rounded-lg border border-gray-200 shadow-sm p-3 relative group"
    >
      <button
        onClick={onRemove}
        onMouseDown={(e) => e.stopPropagation()}
        className="absolute top-1 right-1 z-10 px-1.5 py-0.5 text-xs rounded bg-red-50 text-red-500 hover:bg-red-100 opacity-0 group-hover:opacity-100"
        title={t('editor.removeHeading')}
      >
        ×
      </button>
      <HeadingItem heading={heading} editable onChange={onUpdateHeading} fontScale={fontScale} />
    </div>
  )
}

function LinkedDashboardsSection({
  dashboardId,
  linkedDashboards,
  allDashboards,
  onAddLink,
  onRemoveLink,
  onUpdateOrder,
  isAdding,
}: {
  dashboardId: number
  linkedDashboards: DashboardLink[]
  allDashboards: { id: number; title: string; slug: string }[]
  onAddLink: (linkedId: number, label?: string) => void
  onRemoveLink: (linkId: number) => void
  onUpdateOrder: (links: { id: number; sort_order: number }[]) => void
  isAdding: boolean
}) {
  const { t } = useTranslation()
  const [selectedId, setSelectedId] = useState<number | ''>('')
  const [labelValue, setLabelValue] = useState('')

  // Filter out self + already linked dashboards
  const linkedIds = new Set(linkedDashboards.map((l) => l.linked_dashboard_id))
  const availableDashboards = allDashboards.filter(
    (d) => d.id !== dashboardId && !linkedIds.has(d.id),
  )

  const handleAdd = () => {
    if (!selectedId) return
    onAddLink(selectedId as number, labelValue.trim() || undefined)
    setSelectedId('')
    setLabelValue('')
  }

  const handleMoveUp = (index: number) => {
    if (index === 0) return
    const newLinks = [...linkedDashboards]
    const updated = newLinks.map((link, i) => ({
      id: link.id,
      sort_order: i === index ? index - 1 : i === index - 1 ? index : i,
    }))
    onUpdateOrder(updated)
  }

  const handleMoveDown = (index: number) => {
    if (index >= linkedDashboards.length - 1) return
    const newLinks = [...linkedDashboards]
    const updated = newLinks.map((link, i) => ({
      id: link.id,
      sort_order: i === index ? index + 1 : i === index + 1 ? index : i,
    }))
    onUpdateOrder(updated)
  }

  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-3">{t('editor.linkedDashboards')}</h3>
      <p className="text-xs text-gray-400 mb-4">
        {t('editor.linkedDescription')}
      </p>

      {/* Existing links */}
      {linkedDashboards.length > 0 && (
        <div className="space-y-2 mb-4">
          {linkedDashboards.map((link, index) => (
            <div
              key={link.id}
              className="flex items-center justify-between bg-gray-50 rounded px-3 py-2"
            >
              <div className="flex items-center space-x-3">
                <span className="text-xs text-gray-400 w-6">{index + 1}.</span>
                <span className="text-sm font-medium">
                  {link.label || link.linked_title || 'Untitled'}
                </span>
                {link.label && link.linked_title && (
                  <span className="text-xs text-gray-400">({link.linked_title})</span>
                )}
              </div>
              <div className="flex items-center space-x-1">
                <button
                  onClick={() => handleMoveUp(index)}
                  disabled={index === 0}
                  className="p-1 text-xs text-gray-400 hover:text-gray-600 disabled:opacity-30"
                  title={t('editor.moveUp')}
                >
                  &uarr;
                </button>
                <button
                  onClick={() => handleMoveDown(index)}
                  disabled={index >= linkedDashboards.length - 1}
                  className="p-1 text-xs text-gray-400 hover:text-gray-600 disabled:opacity-30"
                  title={t('editor.moveDown')}
                >
                  &darr;
                </button>
                <button
                  onClick={() => onRemoveLink(link.id)}
                  className="p-1 text-xs text-red-500 hover:text-red-700"
                  title={t('editor.removeLink')}
                >
                  {t('common.remove')}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add new link */}
      {availableDashboards.length > 0 && (
        <div className="flex items-end space-x-2">
          <div className="flex-1">
            <label className="block text-xs text-gray-500 mb-1">{t('editor.dashboard')}</label>
            <select
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value ? Number(e.target.value) : '')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            >
              <option value="">{t('editor.selectDashboard')}</option>
              {availableDashboards.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.title}
                </option>
              ))}
            </select>
          </div>
          <div className="w-48">
            <label className="block text-xs text-gray-500 mb-1">{t('editor.tabLabel')}</label>
            <input
              type="text"
              value={labelValue}
              onChange={(e) => setLabelValue(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
              placeholder={t('editor.customLabel')}
            />
          </div>
          <button
            onClick={handleAdd}
            disabled={!selectedId || isAdding}
            className="btn btn-primary text-sm"
          >
            {isAdding ? t('editor.adding') : t('common.add')}
          </button>
        </div>
      )}

      {availableDashboards.length === 0 && linkedDashboards.length === 0 && (
        <p className="text-sm text-gray-400">
          {t('editor.noLinkedDashboards')}
        </p>
      )}
    </div>
  )
}

