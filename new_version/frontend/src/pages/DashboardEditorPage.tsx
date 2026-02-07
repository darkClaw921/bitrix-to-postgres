import { useState, useCallback, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ReactGridLayout, { useContainerWidth } from 'react-grid-layout'
import type { Layout, LayoutItem } from 'react-grid-layout'
import 'react-grid-layout/css/styles.css'
import 'react-resizable/css/styles.css'
import ChartRenderer from '../components/charts/ChartRenderer'
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
import { chartsApi } from '../services/api'
import type { DashboardChart, DashboardLink, ChartSpec, ChartDataResponse, ChartDisplayConfig } from '../services/api'

const GRID_COLS = 12
const ROW_HEIGHT = 120

export default function DashboardEditorPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const dashboardId = Number(id)

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
    if (!confirm('Remove this chart from the dashboard?')) return
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
    return <div className="flex items-center justify-center h-64 text-gray-500">Loading...</div>
  }

  if (!dashboard) {
    return <div className="text-center text-gray-500 py-12">Dashboard not found</div>
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
                  placeholder="Description (optional)"
                />
                <div className="flex items-center space-x-2">
                  <label className="text-sm text-gray-600">Auto-refresh:</label>
                  <select
                    value={refreshInterval}
                    onChange={(e) => setRefreshInterval(Number(e.target.value))}
                    className="px-2 py-1 border border-gray-300 rounded text-sm"
                  >
                    <option value={1}>1 min</option>
                    <option value={5}>5 min</option>
                    <option value={10}>10 min</option>
                    <option value={15}>15 min</option>
                    <option value={30}>30 min</option>
                    <option value={60}>60 min</option>
                  </select>
                </div>
                <div className="flex space-x-2">
                  <button onClick={handleSaveTitle} className="btn btn-primary text-sm">
                    Save
                  </button>
                  <button onClick={() => setEditingTitle(false)} className="btn btn-secondary text-sm">
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div>
                <h2
                  className="text-xl font-bold cursor-pointer hover:text-blue-600"
                  onClick={() => setEditingTitle(true)}
                  title="Click to edit"
                >
                  {dashboard.title}
                </h2>
                {dashboard.description && (
                  <p className="text-gray-500 mt-1">{dashboard.description}</p>
                )}
                <p className="text-xs text-gray-400 mt-1">
                  Auto-refresh: {dashboard.refresh_interval_minutes} min
                </p>
              </div>
            )}
          </div>

          <div className="flex space-x-2 ml-4">
            <button onClick={handleCopyLink} className="btn btn-secondary text-sm">
              {copiedLink ? 'Copied!' : 'Copy Link'}
            </button>
            <button onClick={handleChangePassword} className="btn btn-secondary text-sm">
              Change Password
            </button>
            {layoutDirty && (
              <button onClick={handleSaveLayout} className="btn btn-primary text-sm">
                {updateLayout.isPending ? 'Saving...' : 'Save Layout'}
              </button>
            )}
          </div>
        </div>

        {newPassword && (
          <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded">
            <p className="text-sm text-green-700">
              New password: <span className="font-mono font-bold">{newPassword}</span>
            </p>
            <p className="text-xs text-green-500 mt-1">Save this — it won't be shown again</p>
          </div>
        )}

        {dashboard.charts.length > 0 && (
          <p className="mt-3 text-xs text-gray-400">
            Drag charts to reposition. Resize by dragging the handle at bottom-right corner.
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
            {dashboard.charts.map((dc) => {
              const layoutItem = gridLayout.find((l) => l.i === String(dc.id))
              return (
                <div key={String(dc.id)} className="overflow-hidden">
                  <EditorChartCard
                    dc={dc}
                    data={chartData[dc.chart_id] || null}
                    layout={layoutItem}
                    onRemove={() => handleRemoveChart(dc.id)}
                    onUpdateOverride={handleUpdateOverride}
                  />
                </div>
              )
            })}
          </ReactGridLayout>
        )}
      </div>

      {dashboard.charts.length === 0 && (
        <div className="card text-center text-gray-400 py-12">
          No charts in this dashboard. Add charts when publishing.
        </div>
      )}

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
          Back to Charts
        </button>
      </div>
    </div>
  )
}

function EditorChartCard({
  dc,
  data,
  layout,
  onRemove,
  onUpdateOverride,
}: {
  dc: DashboardChart
  data: ChartDataResponse | null
  layout?: LayoutItem
  onRemove: () => void
  onUpdateOverride: (dcId: number, field: 'title_override' | 'description_override', value: string) => void
}) {
  const [editTitle, setEditTitle] = useState(false)
  const [titleVal, setTitleVal] = useState(dc.title_override || '')
  const [editDesc, setEditDesc] = useState(false)
  const [descVal, setDescVal] = useState(dc.description_override || '')

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

  // Calculate chart height from grid layout
  const chartHeight = layout ? Math.max(layout.h * ROW_HEIGHT - 100, 120) : 200

  return (
    <div className="h-full bg-white rounded-lg border border-gray-200 shadow-sm p-3 flex flex-col">
      <div className="flex justify-between items-start mb-2">
        <div className="flex-1 min-w-0">
          {editTitle ? (
            <div className="flex items-center space-x-2">
              <input
                type="text"
                value={titleVal}
                onChange={(e) => setTitleVal(e.target.value)}
                className="flex-1 px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="Custom title"
                onMouseDown={(e) => e.stopPropagation()}
              />
              <button
                onClick={() => {
                  onUpdateOverride(dc.id, 'title_override', titleVal)
                  setEditTitle(false)
                }}
                className="text-xs text-blue-600 hover:text-blue-800"
              >
                Save
              </button>
              <button onClick={() => setEditTitle(false)} className="text-xs text-gray-400">
                Cancel
              </button>
            </div>
          ) : (
            <h3
              className="text-sm font-semibold cursor-pointer hover:text-blue-600 truncate"
              onClick={() => setEditTitle(true)}
              title="Click to edit title"
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
                placeholder="Custom description"
                onMouseDown={(e) => e.stopPropagation()}
              />
              <button
                onClick={() => {
                  onUpdateOverride(dc.id, 'description_override', descVal)
                  setEditDesc(false)
                }}
                className="text-xs text-blue-600"
              >
                Save
              </button>
              <button onClick={() => setEditDesc(false)} className="text-xs text-gray-400">
                Cancel
              </button>
            </div>
          ) : (
            <p
              className="text-xs text-gray-500 mt-0.5 cursor-pointer hover:text-blue-500 truncate"
              onClick={() => setEditDesc(true)}
              title="Click to edit description"
            >
              {description || 'Add description...'}
            </p>
          )}
        </div>

        <button
          onClick={onRemove}
          className="p-1 rounded text-xs bg-red-50 text-red-500 hover:bg-red-100 ml-2 flex-shrink-0"
          title="Remove from dashboard"
        >
          Remove
        </button>
      </div>

      <div className="flex-1 min-h-0">
        {data ? (
          <ChartRenderer spec={spec} data={data.data} height={chartHeight} />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">
            Loading chart data...
          </div>
        )}
      </div>
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
      <h3 className="text-lg font-semibold mb-3">Linked Dashboards (Tabs)</h3>
      <p className="text-xs text-gray-400 mb-4">
        Link other dashboards to display as tabs on the public embed page.
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
                  title="Move up"
                >
                  &uarr;
                </button>
                <button
                  onClick={() => handleMoveDown(index)}
                  disabled={index >= linkedDashboards.length - 1}
                  className="p-1 text-xs text-gray-400 hover:text-gray-600 disabled:opacity-30"
                  title="Move down"
                >
                  &darr;
                </button>
                <button
                  onClick={() => onRemoveLink(link.id)}
                  className="p-1 text-xs text-red-500 hover:text-red-700"
                  title="Remove link"
                >
                  Remove
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
            <label className="block text-xs text-gray-500 mb-1">Dashboard</label>
            <select
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value ? Number(e.target.value) : '')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            >
              <option value="">Select dashboard...</option>
              {availableDashboards.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.title}
                </option>
              ))}
            </select>
          </div>
          <div className="w-48">
            <label className="block text-xs text-gray-500 mb-1">Tab label (optional)</label>
            <input
              type="text"
              value={labelValue}
              onChange={(e) => setLabelValue(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
              placeholder="Custom label"
            />
          </div>
          <button
            onClick={handleAdd}
            disabled={!selectedId || isAdding}
            className="btn btn-primary text-sm"
          >
            {isAdding ? 'Adding...' : 'Add'}
          </button>
        </div>
      )}

      {availableDashboards.length === 0 && linkedDashboards.length === 0 && (
        <p className="text-sm text-gray-400">
          No other published dashboards available to link.
        </p>
      )}
    </div>
  )
}
