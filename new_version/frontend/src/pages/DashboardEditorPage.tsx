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
import { useDesignMode } from '../hooks/useDesignMode'
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
} from '../hooks/useDashboards'
import {
  useCreateSelector,
  useDeleteSelector,
  useAddSelectorMapping,
  useRemoveSelectorMapping,
  useChartColumns,
  useGenerateSelectors,
} from '../hooks/useSelectors'
import { useSchemaTables } from '../hooks/useCharts'
import { chartsApi } from '../services/api'
import { useTranslation } from '../i18n'
import type { DashboardChart, DashboardLink, DashboardSelector, SelectorMapping, ChartSpec, ChartDataResponse, ChartDisplayConfig } from '../services/api'

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

  // react-grid-layout v2 container width
  const { containerRef, width: containerWidth, mounted } = useContainerWidth()

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
          minH: 2,
        })),
      )

      // Load chart data
      for (const dc of dashboard.charts) {
        if (!chartData[dc.chart_id]) {
          chartsApi.getData(dc.chart_id).then((data) => {
            setChartData((prev) => ({ ...prev, [dc.chart_id]: data }))
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
    navigator.clipboard.writeText(url).then(() => {
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

  if (isLoading) {
    return <div className="flex items-center justify-center h-64 text-gray-500">{t('common.loading')}</div>
  }

  if (!dashboard) {
    return <div className="text-center text-gray-500 py-12">{t('embed.dashboardNotFound')}</div>
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="card">
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
            <button onClick={handleCopyLink} className="btn btn-secondary text-sm">
              {copiedLink ? t('common.copied') : t('editor.copyLink')}
            </button>
            <button onClick={handleChangePassword} className="btn btn-secondary text-sm">
              {t('editor.changePassword')}
            </button>
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
            layout={gridLayout}
            onLayoutChange={handleLayoutChange}
            width={containerWidth}
            gridConfig={{
              cols: GRID_COLS,
              rowHeight: ROW_HEIGHT,
              margin: [16, 16] as const,
              containerPadding: [0, 0] as const,
              maxRows: Infinity,
            }}
            dragConfig={{ enabled: true, bounded: false, threshold: 3 }}
            resizeConfig={{ enabled: true, handles: ['se'] }}
          >
            {dashboard.charts.map((dc) => (
              <div key={String(dc.id)} className="overflow-visible">
                <EditorChartCard
                  dc={dc}
                  data={chartData[dc.chart_id] || null}
                  onRemove={() => handleRemoveChart(dc.id)}
                  onUpdateOverride={handleUpdateOverride}
                />
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
      <SelectorsSection
        dashboardId={dashboardId}
        selectors={dashboard.selectors || []}
        charts={dashboard.charts}
        onRefetch={refetch}
      />

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
}

// Chart types that support design mode (SVG-based)
const DESIGN_MODE_CHART_TYPES = new Set(['bar', 'line', 'area', 'pie', 'scatter', 'funnel', 'horizontal_bar'])

function EditorChartCard({
  dc,
  data,
  onRemove,
  onUpdateOverride,
}: {
  dc: DashboardChart
  data: ChartDataResponse | null
  onRemove: () => void
  onUpdateOverride: (dcId: number, field: 'title_override' | 'description_override', value: string) => void
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
    updateConfig.mutate({ chartId: dc.chart_id, config: patch })
  }

  const handleDesignApply = () => {
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
        className="flex-1 min-h-0"
        onMouseDown={designMode.isActive ? (e) => e.stopPropagation() : undefined}
      >
        {data ? (
          <ChartRenderer
            spec={spec}
            data={data.data}
            height="100%"
            designLayout={designMode.isActive ? designMode.draftLayout : config?.designLayout}
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

const SELECTOR_TYPES = [
  { value: 'date_range', label: 'Date Range' },
  { value: 'single_date', label: 'Single Date' },
  { value: 'dropdown', label: 'Dropdown' },
  { value: 'multi_select', label: 'Multi Select' },
  { value: 'text', label: 'Text' },
]

const OPERATORS = [
  { value: 'equals', label: '=' },
  { value: 'not_equals', label: '!=' },
  { value: 'in', label: 'IN' },
  { value: 'not_in', label: 'NOT IN' },
  { value: 'between', label: 'BETWEEN' },
  { value: 'gt', label: '>' },
  { value: 'lt', label: '<' },
  { value: 'gte', label: '>=' },
  { value: 'lte', label: '<=' },
  { value: 'like', label: 'LIKE' },
  { value: 'not_like', label: 'NOT LIKE' },
]

function SelectorsSection({
  dashboardId,
  selectors,
  charts,
  onRefetch,
}: {
  dashboardId: number
  selectors: DashboardSelector[]
  charts: DashboardChart[]
  onRefetch: () => void
}) {
  const { t } = useTranslation()
  const createSelector = useCreateSelector()
  const deleteSelector = useDeleteSelector()
  const addMapping = useAddSelectorMapping()
  const removeMapping = useRemoveSelectorMapping()
  const generateSelectors = useGenerateSelectors()
  const { data: tablesData } = useSchemaTables()

  // New selector form
  const [showForm, setShowForm] = useState(false)
  const [formName, setFormName] = useState('')
  const [formLabel, setFormLabel] = useState('')
  const [formType, setFormType] = useState('date_range')
  const [formOperator, setFormOperator] = useState('between')
  const [formSourceTable, setFormSourceTable] = useState('')
  const [formSourceColumn, setFormSourceColumn] = useState('')
  const [formRequired, setFormRequired] = useState(false)
  const [sourceTableMode, setSourceTableMode] = useState<'select' | 'manual'>('select')
  const [sourceColumnMode, setSourceColumnMode] = useState<'select' | 'manual'>('select')

  // Label join config
  const [formLabelTable, setFormLabelTable] = useState('')
  const [formLabelColumn, setFormLabelColumn] = useState('')
  const [formLabelValueColumn, setFormLabelValueColumn] = useState('')
  const [labelTableMode, setLabelTableMode] = useState<'select' | 'manual'>('select')
  const [labelColumnMode, setLabelColumnMode] = useState<'select' | 'manual'>('select')
  const [labelValueColumnMode, setLabelValueColumnMode] = useState<'select' | 'manual'>('select')

  // Mapping form state
  const [addingMappingFor, setAddingMappingFor] = useState<number | null>(null)
  const [mappingChartId, setMappingChartId] = useState<number | ''>('')
  const [mappingColumn, setMappingColumn] = useState('')
  const [mappingColumnMode, setMappingColumnMode] = useState<'select' | 'manual'>('select')

  const handleCreate = () => {
    if (!formName.trim() || !formLabel.trim()) return

    const config: Record<string, unknown> = {}
    if (formSourceTable.trim()) config.source_table = formSourceTable.trim()
    if (formSourceColumn.trim()) config.source_column = formSourceColumn.trim()
    if (formLabelTable.trim()) config.label_table = formLabelTable.trim()
    if (formLabelColumn.trim()) config.label_column = formLabelColumn.trim()
    if (formLabelValueColumn.trim()) config.label_value_column = formLabelValueColumn.trim()

    createSelector.mutate(
      {
        dashboardId,
        data: {
          name: formName.trim(),
          label: formLabel.trim(),
          selector_type: formType,
          operator: formOperator,
          config: Object.keys(config).length > 0 ? config : undefined,
          is_required: formRequired,
        },
      },
      {
        onSuccess: () => {
          setShowForm(false)
          setFormName('')
          setFormLabel('')
          setFormType('date_range')
          setFormOperator('between')
          setFormSourceTable('')
          setFormSourceColumn('')
          setFormRequired(false)
          setSourceTableMode('select')
          setSourceColumnMode('select')
          setFormLabelTable('')
          setFormLabelColumn('')
          setFormLabelValueColumn('')
          setLabelTableMode('select')
          setLabelColumnMode('select')
          setLabelValueColumnMode('select')
          onRefetch()
        },
      },
    )
  }

  const handleDelete = (selectorId: number) => {
    if (!confirm(t('editor.confirmDeleteSelector'))) return
    deleteSelector.mutate(
      { dashboardId, selectorId },
      { onSuccess: () => onRefetch() },
    )
  }

  const handleAddMapping = (selectorId: number) => {
    if (!mappingChartId || !mappingColumn.trim()) return
    addMapping.mutate(
      {
        dashboardId,
        selectorId,
        data: {
          dashboard_chart_id: mappingChartId as number,
          target_column: mappingColumn.trim(),
        },
      },
      {
        onSuccess: () => {
          setAddingMappingFor(null)
          setMappingChartId('')
          setMappingColumn('')
          onRefetch()
        },
      },
    )
  }

  const handleRemoveMapping = (selectorId: number, mappingId: number) => {
    removeMapping.mutate(
      { dashboardId, selectorId, mappingId },
      { onSuccess: () => onRefetch() },
    )
  }

  const handleGenerate = () => {
    generateSelectors.mutate(dashboardId, {
      onSuccess: () => onRefetch(),
    })
  }

  // Auto-set operator based on selector type
  useEffect(() => {
    if (formType === 'date_range') setFormOperator('between')
    else if (formType === 'multi_select') setFormOperator('in')
    else if (formType === 'dropdown') setFormOperator('equals')
    else if (formType === 'text') setFormOperator('like')
    else if (formType === 'single_date') setFormOperator('equals')
  }, [formType])

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold">{t('editor.selectorsFilters')}</h3>
        <div className="flex space-x-2">
          <button
            onClick={handleGenerate}
            disabled={generateSelectors.isPending || charts.length === 0}
            className="btn btn-secondary text-sm"
            title="Generate selectors with AI based on chart queries"
          >
            {generateSelectors.isPending ? t('common.generating') : t('editor.generateWithAi')}
          </button>
          <button
            onClick={() => setShowForm(!showForm)}
            className="btn btn-primary text-sm"
          >
            {showForm ? t('common.cancel') : t('editor.addSelector')}
          </button>
        </div>
      </div>
      {generateSelectors.isError && (
        <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-600">
          {(generateSelectors.error as Error)?.message || t('editor.failedToGenerateSelectors')}
        </div>
      )}
      <p className="text-xs text-gray-400 mb-4">
        {t('editor.selectorDescription')}
      </p>

      {/* Create form */}
      {showForm && (
        <div className="mb-4 p-4 bg-gray-50 rounded-lg border border-gray-200 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t('editor.internalName')}</label>
              <input
                type="text"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                placeholder="e.g. date_filter"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t('editor.displayLabel')}</label>
              <input
                type="text"
                value={formLabel}
                onChange={(e) => setFormLabel(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                placeholder="e.g. Period"
              />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t('editor.selectorType')}</label>
              <select
                value={formType}
                onChange={(e) => setFormType(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
              >
                {SELECTOR_TYPES.map((st) => (
                  <option key={st.value} value={st.value}>
                    {st.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">{t('editor.operator')}</label>
              <select
                value={formOperator}
                onChange={(e) => setFormOperator(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
              >
                {OPERATORS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-end">
              <label className="flex items-center text-sm text-gray-600">
                <input
                  type="checkbox"
                  checked={formRequired}
                  onChange={(e) => setFormRequired(e.target.checked)}
                  className="mr-2"
                />
                {t('common.required')}
              </label>
            </div>
          </div>

          {(formType === 'dropdown' || formType === 'multi_select') && (
            <>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs text-gray-500">{t('editor.sourceTable')}</label>
                  <button
                    type="button"
                    onClick={() => {
                      setSourceTableMode(sourceTableMode === 'select' ? 'manual' : 'select')
                      setFormSourceTable('')
                      setFormSourceColumn('')
                    }}
                    className="text-[10px] text-blue-500 hover:text-blue-700"
                  >
                    {sourceTableMode === 'select' ? t('editor.typeManually') : t('editor.pickFromList')}
                  </button>
                </div>
                {sourceTableMode === 'manual' ? (
                  <input
                    type="text"
                    value={formSourceTable}
                    onChange={(e) => setFormSourceTable(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    placeholder="e.g. crm_deals"
                  />
                ) : (
                  <select
                    value={formSourceTable}
                    onChange={(e) => {
                      setFormSourceTable(e.target.value)
                      setFormSourceColumn('')
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  >
                    <option value="">{t('editor.selectTable')}</option>
                    {(tablesData?.tables || []).map((tbl) => (
                      <option key={tbl.table_name} value={tbl.table_name}>
                        {tbl.table_name}
                      </option>
                    ))}
                  </select>
                )}
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs text-gray-500">{t('editor.sourceColumn')}</label>
                  <button
                    type="button"
                    onClick={() => {
                      setSourceColumnMode(sourceColumnMode === 'select' ? 'manual' : 'select')
                      setFormSourceColumn('')
                    }}
                    className="text-[10px] text-blue-500 hover:text-blue-700"
                  >
                    {sourceColumnMode === 'select' ? t('editor.typeManually') : t('editor.pickFromList')}
                  </button>
                </div>
                {sourceColumnMode === 'manual' ? (
                  <input
                    type="text"
                    value={formSourceColumn}
                    onChange={(e) => setFormSourceColumn(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    placeholder="e.g. stage_id"
                  />
                ) : (
                  <select
                    value={formSourceColumn}
                    onChange={(e) => setFormSourceColumn(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    disabled={!formSourceTable}
                  >
                    <option value="">{formSourceTable ? t('editor.selectColumn') : t('editor.selectTableFirst')}</option>
                    {formSourceTable &&
                      (tablesData?.tables || [])
                        .find((tbl) => tbl.table_name === formSourceTable)
                        ?.columns.map((col) => (
                          <option key={col.name} value={col.name}>
                            {col.name} ({col.data_type})
                          </option>
                        ))}
                  </select>
                )}
              </div>
            </div>

            {/* Label join config (optional) */}
            <div className="grid grid-cols-3 gap-3">
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs text-gray-500">{t('editor.labelTable')}</label>
                  <button
                    type="button"
                    onClick={() => {
                      setLabelTableMode(labelTableMode === 'select' ? 'manual' : 'select')
                      setFormLabelTable('')
                      setFormLabelColumn('')
                      setFormLabelValueColumn('')
                    }}
                    className="text-[10px] text-blue-500 hover:text-blue-700"
                  >
                    {labelTableMode === 'select' ? t('editor.typeManually') : t('editor.pickFromList')}
                  </button>
                </div>
                {labelTableMode === 'manual' ? (
                  <input
                    type="text"
                    value={formLabelTable}
                    onChange={(e) => setFormLabelTable(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    placeholder="e.g. ref_crm_statuses"
                  />
                ) : (
                  <select
                    value={formLabelTable}
                    onChange={(e) => {
                      setFormLabelTable(e.target.value)
                      setFormLabelColumn('')
                      setFormLabelValueColumn('')
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  >
                    <option value="">{t('editor.selectTable')}</option>
                    {(tablesData?.tables || []).map((tbl) => (
                      <option key={tbl.table_name} value={tbl.table_name}>
                        {tbl.table_name}
                      </option>
                    ))}
                  </select>
                )}
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs text-gray-500">{t('editor.labelColumn')}</label>
                  <button
                    type="button"
                    onClick={() => {
                      setLabelColumnMode(labelColumnMode === 'select' ? 'manual' : 'select')
                      setFormLabelColumn('')
                    }}
                    className="text-[10px] text-blue-500 hover:text-blue-700"
                  >
                    {labelColumnMode === 'select' ? t('editor.typeManually') : t('editor.pickFromList')}
                  </button>
                </div>
                {labelColumnMode === 'manual' ? (
                  <input
                    type="text"
                    value={formLabelColumn}
                    onChange={(e) => setFormLabelColumn(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    placeholder="e.g. name"
                  />
                ) : (
                  <select
                    value={formLabelColumn}
                    onChange={(e) => setFormLabelColumn(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    disabled={!formLabelTable}
                  >
                    <option value="">{formLabelTable ? t('editor.selectColumn') : t('editor.selectLabelTableFirst')}</option>
                    {formLabelTable &&
                      (tablesData?.tables || [])
                        .find((tbl) => tbl.table_name === formLabelTable)
                        ?.columns.map((col) => (
                          <option key={col.name} value={col.name}>
                            {col.name} ({col.data_type})
                          </option>
                        ))}
                  </select>
                )}
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs text-gray-500">{t('editor.labelValueColumn')}</label>
                  <button
                    type="button"
                    onClick={() => {
                      setLabelValueColumnMode(labelValueColumnMode === 'select' ? 'manual' : 'select')
                      setFormLabelValueColumn('')
                    }}
                    className="text-[10px] text-blue-500 hover:text-blue-700"
                  >
                    {labelValueColumnMode === 'select' ? t('editor.typeManually') : t('editor.pickFromList')}
                  </button>
                </div>
                {labelValueColumnMode === 'manual' ? (
                  <input
                    type="text"
                    value={formLabelValueColumn}
                    onChange={(e) => setFormLabelValueColumn(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    placeholder="e.g. status_id"
                  />
                ) : (
                  <select
                    value={formLabelValueColumn}
                    onChange={(e) => setFormLabelValueColumn(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    disabled={!formLabelTable}
                  >
                    <option value="">{formLabelTable ? t('editor.selectColumn') : t('editor.selectLabelTableFirst')}</option>
                    {formLabelTable &&
                      (tablesData?.tables || [])
                        .find((tbl) => tbl.table_name === formLabelTable)
                        ?.columns.map((col) => (
                          <option key={col.name} value={col.name}>
                            {col.name} ({col.data_type})
                          </option>
                        ))}
                  </select>
                )}
              </div>
            </div>
            </>
          )}

          <button
            onClick={handleCreate}
            disabled={!formName.trim() || !formLabel.trim() || createSelector.isPending}
            className="btn btn-primary text-sm"
          >
            {createSelector.isPending ? t('editor.creating') : t('editor.createSelector')}
          </button>
        </div>
      )}

      {/* Existing selectors */}
      {selectors.length > 0 && (
        <div className="space-y-3">
          {selectors.map((sel) => (
            <div key={sel.id} className="bg-gray-50 rounded-lg border border-gray-200 p-3">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <span className="text-sm font-medium">{sel.label}</span>
                  <span className="text-xs text-gray-400 ml-2">({sel.name})</span>
                  <span className="text-xs text-gray-400 ml-2">
                    {SELECTOR_TYPES.find((st) => st.value === sel.selector_type)?.label || sel.selector_type}
                  </span>
                  <span className="text-xs text-gray-400 ml-2">
                    [{OPERATORS.find((o) => o.value === sel.operator)?.label || sel.operator}]
                  </span>
                  {sel.is_required && (
                    <span className="text-xs text-red-400 ml-2">{t('common.required')}</span>
                  )}
                </div>
                <button
                  onClick={() => handleDelete(sel.id)}
                  className="text-xs text-red-500 hover:text-red-700"
                >
                  {t('editor.deleteSelector')}
                </button>
              </div>

              {/* Mappings */}
              <div className="pl-4 space-y-1">
                <p className="text-xs text-gray-500 font-medium">{t('editor.chartMappings')}</p>
                {sel.mappings.length === 0 && (
                  <p className="text-xs text-gray-400 italic">{t('editor.noMappings')}</p>
                )}
                {sel.mappings.map((m: SelectorMapping) => {
                  const chart = charts.find((c) => c.id === m.dashboard_chart_id)
                  const chartName = chart
                    ? chart.title_override || chart.chart_title || `Chart #${chart.chart_id}`
                    : `DC #${m.dashboard_chart_id}`
                  return (
                    <div key={m.id} className="flex items-center justify-between text-xs">
                      <span>
                        <span className="text-gray-700">{chartName}</span>
                        <span className="text-gray-400"> → </span>
                        <span className="font-mono text-blue-600">{m.target_column}</span>
                        {m.target_table && (
                          <span className="text-gray-400"> ({m.target_table})</span>
                        )}
                      </span>
                      <button
                        onClick={() => handleRemoveMapping(sel.id, m.id)}
                        className="text-red-400 hover:text-red-600"
                      >
                        {t('common.remove')}
                      </button>
                    </div>
                  )
                })}

                {/* Add mapping */}
                {addingMappingFor === sel.id ? (
                  <div className="flex items-end space-x-2 mt-2 flex-wrap gap-y-2">
                    <div>
                      <label className="block text-xs text-gray-500 mb-0.5">Chart</label>
                      <select
                        value={mappingChartId}
                        onChange={(e) => {
                          setMappingChartId(e.target.value ? Number(e.target.value) : '')
                          setMappingColumn('')
                          setMappingColumnMode('select')
                        }}
                        className="px-2 py-1 border border-gray-300 rounded text-xs"
                      >
                        <option value="">{t('editor.selectChart')}</option>
                        {charts
                          .filter((c) => !sel.mappings.some((m: SelectorMapping) => m.dashboard_chart_id === c.id))
                          .map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.title_override || c.chart_title || `Chart #${c.chart_id}`}
                            </option>
                          ))}
                      </select>
                    </div>
                    <div>
                      <div className="flex items-center justify-between mb-0.5">
                        <label className="text-xs text-gray-500">{t('editor.targetColumn')}</label>
                        <button
                          type="button"
                          onClick={() => {
                            setMappingColumnMode(mappingColumnMode === 'select' ? 'manual' : 'select')
                            setMappingColumn('')
                          }}
                          className="text-[10px] text-blue-500 hover:text-blue-700"
                        >
                          {mappingColumnMode === 'select' ? t('editor.typeManually') : t('editor.pickFromList')}
                        </button>
                      </div>
                      {mappingColumnMode === 'manual' ? (
                        <input
                          type="text"
                          value={mappingColumn}
                          onChange={(e) => setMappingColumn(e.target.value)}
                          className="px-2 py-1 border border-gray-300 rounded text-xs w-40"
                          placeholder="e.g. date_create"
                        />
                      ) : (
                        <ColumnPicker
                          dashboardId={dashboardId}
                          dcId={mappingChartId as number}
                          value={mappingColumn}
                          onChange={setMappingColumn}
                        />
                      )}
                    </div>
                    <button
                      onClick={() => handleAddMapping(sel.id)}
                      disabled={!mappingChartId || !mappingColumn.trim()}
                      className="text-xs text-blue-600 hover:text-blue-800"
                    >
                      {t('common.add')}
                    </button>
                    <button
                      onClick={() => {
                        setAddingMappingFor(null)
                        setMappingChartId('')
                        setMappingColumn('')
                        setMappingColumnMode('select')
                      }}
                      className="text-xs text-gray-400"
                    >
                      {t('common.cancel')}
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setAddingMappingFor(sel.id)}
                    className="text-xs text-blue-500 hover:text-blue-700 mt-1"
                  >
                    {t('editor.addMapping')}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {selectors.length === 0 && !showForm && (
        <p className="text-sm text-gray-400">
          {t('editor.noSelectors')}
        </p>
      )}
    </div>
  )
}

function ColumnPicker({
  dashboardId,
  dcId,
  value,
  onChange,
}: {
  dashboardId: number
  dcId: number
  value: string
  onChange: (v: string) => void
}) {
  const { t } = useTranslation()
  const { data, isLoading } = useChartColumns(dashboardId, dcId)
  const columns = data?.columns || []

  if (!dcId) {
    return (
      <select disabled className="px-2 py-1 border border-gray-300 rounded text-xs w-40 text-gray-400">
        <option>{t('editor.selectChartFirst')}</option>
      </select>
    )
  }

  if (isLoading) {
    return (
      <select disabled className="px-2 py-1 border border-gray-300 rounded text-xs w-40 text-gray-400">
        <option>{t('editor.loadingColumns')}</option>
      </select>
    )
  }

  if (columns.length === 0) {
    return (
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="px-2 py-1 border border-gray-300 rounded text-xs w-40"
        placeholder="e.g. date_create"
      />
    )
  }

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="px-2 py-1 border border-gray-300 rounded text-xs w-40"
    >
      <option value="">{t('editor.selectColumn')}</option>
      {columns.map((col) => (
        <option key={col} value={col}>
          {col}
        </option>
      ))}
    </select>
  )
}
