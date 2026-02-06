import { useState, useCallback, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ReactGridLayout, { useContainerWidth } from 'react-grid-layout'
import type { Layout, LayoutItem } from 'react-grid-layout'
import 'react-grid-layout/css/styles.css'
import 'react-resizable/css/styles.css'
import ChartRenderer from '../components/charts/ChartRenderer'
import {
  useDashboard,
  useUpdateDashboard,
  useUpdateDashboardLayout,
  useUpdateChartOverride,
  useRemoveChartFromDashboard,
  useChangeDashboardPassword,
} from '../hooks/useDashboards'
import { chartsApi } from '../services/api'
import type { DashboardChart, ChartSpec, ChartDataResponse, ChartDisplayConfig } from '../services/api'

const GRID_COLS = 12
const ROW_HEIGHT = 120

export default function DashboardEditorPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const dashboardId = Number(id)

  const { data: dashboard, isLoading, refetch } = useDashboard(dashboardId)
  const updateDashboard = useUpdateDashboard()
  const updateLayout = useUpdateDashboardLayout()
  const updateOverride = useUpdateChartOverride()
  const removeChart = useRemoveChartFromDashboard()
  const changePassword = useChangeDashboardPassword()

  const [editingTitle, setEditingTitle] = useState(false)
  const [titleValue, setTitleValue] = useState('')
  const [descValue, setDescValue] = useState('')
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
      { id: dashboardId, data: { title: titleValue.trim(), description: descValue.trim() || undefined } },
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
