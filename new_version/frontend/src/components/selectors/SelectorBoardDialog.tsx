import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import {
  ReactFlow,
  addEdge,
  useNodesState,
  useEdgesState,
  Controls,
  Background,
  MarkerType,
  type OnConnect,
  type Node,
  type Edge,
  type NodeTypes,
  type EdgeTypes,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useTranslation } from '../../i18n'
import { dashboardsApi } from '../../services/api'
import type {
  DashboardSelector,
  DashboardChart,
  SelectorCreateRequest,
  SelectorUpdateRequest,
  SelectorMappingRequest,
  FilterPreviewResponse,
} from '../../services/api'
import { DATE_TOKENS, tokenLabel, type DateToken } from '../../utils/dateTokens'
import SelectorConfigPanel from './SelectorConfigPanel'
import SqlPreviewPanel from './SqlPreviewPanel'
import SelectorNode from './nodes/SelectorNode'
import ChartNode from './nodes/ChartNode'
import MappingEdge from './nodes/MappingEdge'

const OPERATORS = ['equals', 'in', 'between', 'like', 'gt', 'lt', 'gte', 'lte'] as const

// Token list for default-value dropdowns; "" means "no default".
const TOKEN_OPTIONS: Array<{ value: string; label: string }> = [
  { value: '', label: '— нет —' },
  ...DATE_TOKENS.map((tok) => ({ value: tok, label: `${tok} — ${tokenLabel(tok as DateToken)}` })),
]

interface Props {
  dashboardId: number
  charts: DashboardChart[]
  selector?: DashboardSelector | null
  onClose: () => void
  onSave: (data: SelectorCreateRequest | SelectorUpdateRequest) => void
  saving?: boolean
}

interface StaticValue {
  value: string
  label: string
}

const SELECTOR_NODE_ID = 'selector-node'

export default function SelectorBoardDialog({
  dashboardId,
  charts,
  selector,
  onClose,
  onSave,
  saving,
}: Props) {
  const { t } = useTranslation()
  const isEdit = !!selector

  // Config state (Step 1+2)
  const [selectorType, setSelectorType] = useState(selector?.selector_type || 'dropdown')
  const [name, setName] = useState(selector?.name || '')
  const [label, setLabel] = useState(selector?.label || '')
  const [operator, setOperator] = useState(selector?.operator || 'equals')
  const [isRequired, setIsRequired] = useState(selector?.is_required || false)
  const [dataSourceMode, setDataSourceMode] = useState<'static' | 'database'>(
    selector?.config?.static_values ? 'static' : 'database',
  )
  const [staticValues, setStaticValues] = useState<StaticValue[]>(
    (selector?.config?.static_values as StaticValue[]) || [{ value: '', label: '' }],
  )
  const [sourceTable, setSourceTable] = useState((selector?.config?.source_table as string) || '')
  const [sourceColumn, setSourceColumn] = useState((selector?.config?.source_column as string) || '')
  const [showLabels, setShowLabels] = useState(!!(selector?.config?.label_table))
  const [labelTable, setLabelTable] = useState((selector?.config?.label_table as string) || '')
  const [labelColumn, setLabelColumn] = useState((selector?.config?.label_column as string) || '')
  const [labelValueColumn, setLabelValueColumn] = useState((selector?.config?.label_value_column as string) || '')

  // Default value (for date selectors — token-based; for others — raw string)
  const initialDefault = (selector?.config?.default_value ?? null) as
    | string
    | { from?: string; to?: string }
    | null
  const [defaultValueFrom, setDefaultValueFrom] = useState<string>(
    typeof initialDefault === 'object' && initialDefault ? (initialDefault.from || '') : '',
  )
  const [defaultValueTo, setDefaultValueTo] = useState<string>(
    typeof initialDefault === 'object' && initialDefault ? (initialDefault.to || '') : '',
  )
  const [defaultValueScalar, setDefaultValueScalar] = useState<string>(
    typeof initialDefault === 'string' ? initialDefault : '',
  )

  // Chart columns cache
  const [chartColumnsCache, setChartColumnsCache] = useState<Record<number, string[]>>({})

  // SQL Preview state
  const [sqlPreview, setSqlPreview] = useState<FilterPreviewResponse | null>(null)
  const [sqlPreviewLoading, setSqlPreviewLoading] = useState(false)

  // Edge config popup
  const [configEdgeId, setConfigEdgeId] = useState<string | null>(null)

  // Node types (memoized to prevent re-renders)
  const nodeTypes: NodeTypes = useMemo(() => ({
    selectorNode: SelectorNode,
    chartNode: ChartNode,
  }), [])

  // Build initial nodes
  const buildInitialNodes = useCallback((): Node[] => {
    const selectorNode: Node = {
      id: SELECTOR_NODE_ID,
      type: 'selectorNode',
      position: { x: 50, y: 100 },
      data: {
        label: label || '—',
        selectorType: selectorType,
        operator: operator,
      },
    }

    const chartNodes: Node[] = charts.map((dc, i) => ({
      id: `chart-${dc.id}`,
      type: 'chartNode',
      position: { x: 500, y: 30 + i * 220 },
      data: {
        chartTitle: dc.title_override || dc.chart_title || `Chart #${dc.chart_id}`,
        dcId: dc.id,
        columns: chartColumnsCache[dc.id] || [],
        loading: !chartColumnsCache[dc.id],
      },
    }))

    return [selectorNode, ...chartNodes]
  }, [charts, label, selectorType, operator, chartColumnsCache])

  // Edges start empty. We populate them from `selector.mappings` only after
  // the referenced charts have loaded their columns — otherwise ReactFlow
  // tries to attach edges to handles that don't exist yet (the chart node
  // renders "Loading..." with zero <Handle> elements) and silently drops the
  // edges, so the user sees no connections at all.
  const [nodes, setNodes, onNodesChange] = useNodesState(buildInitialNodes())
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])

  // Edge type with callbacks
  const edgeTypesObj: EdgeTypes = useMemo(() => ({
    mappingEdge: MappingEdge,
  }), [])

  // Load all chart columns on mount
  useEffect(() => {
    charts.forEach((dc) => {
      if (!chartColumnsCache[dc.id]) {
        dashboardsApi.getChartColumns(dashboardId, dc.id)
          .then((cols) => {
            setChartColumnsCache((prev) => ({ ...prev, [dc.id]: cols }))
          })
          .catch(() => {
            setChartColumnsCache((prev) => ({ ...prev, [dc.id]: [] }))
          })
      }
    })
  }, [charts, dashboardId])

  // Update chart nodes when columns load
  useEffect(() => {
    setNodes((nds) =>
      nds.map((n) => {
        if (n.type === 'chartNode') {
          const dcId = (n.data as { dcId: number }).dcId
          const cols = chartColumnsCache[dcId]
          if (cols) {
            return {
              ...n,
              data: { ...n.data, columns: cols, loading: false },
            }
          }
        }
        return n
      }),
    )
  }, [chartColumnsCache, setNodes])

  // Update selector node when config changes
  useEffect(() => {
    setNodes((nds) =>
      nds.map((n) =>
        n.id === SELECTOR_NODE_ID
          ? { ...n, data: { ...n.data, label: label || '—', selectorType, operator } }
          : n,
      ),
    )
  }, [label, selectorType, operator, setNodes])

  // Edge callbacks — declared BEFORE the edge-building useEffect below so the
  // effect's dep array doesn't hit a temporal dead zone.
  const handleDeleteEdge = useCallback((edgeId: string) => {
    setEdges((eds) => eds.filter((e) => e.id !== edgeId))
    setConfigEdgeId(null)
    setSqlPreview(null)
  }, [setEdges])

  const handleConfigureEdge = useCallback((edgeId: string) => {
    setConfigEdgeId(edgeId)
    // Load SQL preview for this edge's chart
    setEdges((eds) => {
      const edge = eds.find((e) => e.id === edgeId)
      if (edge) {
        const dcIdStr = edge.target.replace('chart-', '')
        const dcId = Number(dcIdStr)
        const targetColumn = (edge.data as { targetColumn?: string })?.targetColumn || ''
        if (dcId && targetColumn) {
          setSqlPreviewLoading(true)
          dashboardsApi.previewFilter(dashboardId, dcId, {
            selector_name: name,
            selector_type: selectorType,
            operator: operator,
            target_column: targetColumn,
            target_table: (edge.data as { targetTable?: string })?.targetTable,
            sample_value: 'example',
          })
            .then((res) => setSqlPreview(res))
            .catch(() => setSqlPreview(null))
            .finally(() => setSqlPreviewLoading(false))
        }
      }
      return eds
    })
  }, [dashboardId, name, selectorType, operator, setEdges])

  // Build initial edges from saved mappings exactly once, after the columns
  // of every chart referenced by a mapping have loaded. ReactFlow needs the
  // matching <Handle> to exist before an edge can attach to it, so creating
  // edges synchronously at mount (when chart nodes are still in the loading
  // state) results in dropped edges and a visually empty canvas.
  const initialEdgesBuilt = useRef(false)
  useEffect(() => {
    if (initialEdgesBuilt.current) return
    if (!selector?.mappings || selector.mappings.length === 0) {
      initialEdgesBuilt.current = true
      return
    }
    const referencedChartIds = Array.from(
      new Set(selector.mappings.map((m) => m.dashboard_chart_id)),
    )
    const allLoaded = referencedChartIds.every(
      (id) => chartColumnsCache[id] !== undefined,
    )
    if (!allLoaded) return

    initialEdgesBuilt.current = true
    setEdges(
      selector.mappings.map((m) => ({
        id: `edge-${m.dashboard_chart_id}-${m.target_column}`,
        source: SELECTOR_NODE_ID,
        target: `chart-${m.dashboard_chart_id}`,
        targetHandle: `${m.dashboard_chart_id}-${m.target_column}`,
        type: 'mappingEdge',
        markerEnd: { type: MarkerType.ArrowClosed, color: '#94a3b8' },
        data: {
          targetColumn: m.target_column,
          operatorOverride: m.operator_override || '',
          targetTable: m.target_table || '',
          postFilterResolveTable: m.post_filter_resolve_table || '',
          postFilterResolveColumn: m.post_filter_resolve_column || '',
          postFilterResolveIdColumn: m.post_filter_resolve_id_column || '',
          onDelete: handleDeleteEdge,
          onConfigure: handleConfigureEdge,
        },
      })),
    )
  }, [
    chartColumnsCache,
    selector?.mappings,
    setEdges,
    handleDeleteEdge,
    handleConfigureEdge,
  ])

  // Handle new connection
  const onConnect: OnConnect = useCallback(
    (params) => {
      if (!params.targetHandle) return
      // Parse target handle: "{dcId}-{column}"
      const parts = params.targetHandle.split('-')
      if (parts.length < 2) return
      const targetColumn = parts.slice(1).join('-')

      // Prevent duplicate edges to the same column
      const exists = edges.some(
        (e) => e.target === params.target && e.targetHandle === params.targetHandle,
      )
      if (exists) return

      const newEdge: Edge = {
        ...params,
        id: `edge-${params.target?.replace('chart-', '')}-${targetColumn}`,
        type: 'mappingEdge',
        markerEnd: { type: MarkerType.ArrowClosed, color: '#94a3b8' },
        data: {
          targetColumn,
          operatorOverride: '',
          targetTable: '',
          postFilterResolveTable: '',
          postFilterResolveColumn: '',
          postFilterResolveIdColumn: '',
          onDelete: handleDeleteEdge,
          onConfigure: handleConfigureEdge,
        },
      } as Edge

      setEdges((eds) => addEdge(newEdge, eds))
    },
    [edges, setEdges, handleDeleteEdge, handleConfigureEdge],
  )

  // Handle save
  const handleFinish = () => {
    const showStep2 = selectorType === 'dropdown' || selectorType === 'multi_select'
    const config: Record<string, unknown> = {}

    if (showStep2) {
      if (dataSourceMode === 'static') {
        config.static_values = staticValues.filter((v) => v.value)
      } else {
        if (sourceTable) config.source_table = sourceTable
        if (sourceColumn) config.source_column = sourceColumn
        if (showLabels) {
          if (labelTable) config.label_table = labelTable
          if (labelColumn) config.label_column = labelColumn
          if (labelValueColumn) config.label_value_column = labelValueColumn
        }
      }
    }

    // Default value: tokens for date selectors, scalar for others.
    if (selectorType === 'date_range') {
      if (defaultValueFrom || defaultValueTo) {
        config.default_value = {
          from: defaultValueFrom || undefined,
          to: defaultValueTo || undefined,
        }
      }
    } else if (selectorType === 'single_date') {
      if (defaultValueScalar) {
        config.default_value = defaultValueScalar
      }
    } else {
      if (defaultValueScalar) {
        config.default_value = defaultValueScalar
      }
    }

    // Build mappings from edges, including optional post_filter triple.
    const mappingsList: SelectorMappingRequest[] = edges.map((e) => {
      const dcIdStr = e.target.replace('chart-', '')
      const d = e.data as
        | {
            targetColumn?: string
            operatorOverride?: string
            targetTable?: string
            postFilterResolveTable?: string
            postFilterResolveColumn?: string
            postFilterResolveIdColumn?: string
          }
        | undefined
      return {
        dashboard_chart_id: Number(dcIdStr),
        target_column: d?.targetColumn || '',
        target_table: d?.targetTable || undefined,
        operator_override: d?.operatorOverride || undefined,
        post_filter_resolve_table: d?.postFilterResolveTable || undefined,
        post_filter_resolve_column: d?.postFilterResolveColumn || undefined,
        post_filter_resolve_id_column: d?.postFilterResolveIdColumn || undefined,
      }
    }).filter((m) => m.target_column)

    const data: SelectorCreateRequest | SelectorUpdateRequest = {
      name,
      label,
      selector_type: selectorType,
      operator,
      config: Object.keys(config).length > 0 ? config : undefined,
      is_required: isRequired,
      mappings: mappingsList,
    }

    onSave(data)
  }

  // Edge config popup
  const configEdge = configEdgeId ? edges.find((e) => e.id === configEdgeId) : null
  const configEdgeData = configEdge?.data as
    | {
        operatorOverride?: string
        targetTable?: string
        targetColumn?: string
        postFilterResolveTable?: string
        postFilterResolveColumn?: string
        postFilterResolveIdColumn?: string
      }
    | undefined

  const updateEdgeField = (field: string, val: string) => {
    setEdges((eds) =>
      eds.map((ed) =>
        ed.id === configEdgeId ? { ...ed, data: { ...ed.data, [field]: val } } : ed,
      ),
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-6xl h-[85vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <h2 className="text-lg font-semibold">{t('selectors.boardTitle')}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
        </div>

        {/* Main area */}
        <div className="flex flex-1 min-h-0">
          {/* Left panel: config (wrapped to host the default-value section below) */}
          <div className="flex flex-col w-[320px] border-r overflow-y-auto">
          <SelectorConfigPanel
            dashboardId={dashboardId}
            selectorType={selectorType}
            name={name}
            label={label}
            operator={operator}
            isRequired={isRequired}
            dataSourceMode={dataSourceMode}
            staticValues={staticValues}
            sourceTable={sourceTable}
            sourceColumn={sourceColumn}
            showLabels={showLabels}
            labelTable={labelTable}
            labelColumn={labelColumn}
            labelValueColumn={labelValueColumn}
            isEdit={isEdit}
            selectorId={selector?.id}
            onSelectorTypeChange={setSelectorType}
            onNameChange={setName}
            onLabelChange={setLabel}
            onOperatorChange={setOperator}
            onIsRequiredChange={setIsRequired}
            onDataSourceModeChange={setDataSourceMode}
            onStaticValuesChange={setStaticValues}
            onSourceTableChange={setSourceTable}
            onSourceColumnChange={setSourceColumn}
            onShowLabelsChange={setShowLabels}
            onLabelTableChange={setLabelTable}
            onLabelColumnChange={setLabelColumn}
            onLabelValueColumnChange={setLabelValueColumn}
          />

          {/* Default value (resolved on every request — date selectors store
              tokens, others store a literal value). */}
          <div className="border-t px-4 py-3">
            <div className="text-xs font-semibold text-gray-700 mb-2">Default value</div>
            {selectorType === 'date_range' && (
              <div className="space-y-2">
                <div>
                  <label className="block text-[10px] text-gray-500 mb-0.5">from (token)</label>
                  <select
                    className="w-full border border-gray-300 rounded px-2 py-1 text-xs"
                    value={defaultValueFrom}
                    onChange={(e) => setDefaultValueFrom(e.target.value)}
                  >
                    {TOKEN_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] text-gray-500 mb-0.5">to (token)</label>
                  <select
                    className="w-full border border-gray-300 rounded px-2 py-1 text-xs"
                    value={defaultValueTo}
                    onChange={(e) => setDefaultValueTo(e.target.value)}
                  >
                    {TOKEN_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </div>
              </div>
            )}
            {selectorType === 'single_date' && (
              <select
                className="w-full border border-gray-300 rounded px-2 py-1 text-xs"
                value={defaultValueScalar}
                onChange={(e) => setDefaultValueScalar(e.target.value)}
              >
                {TOKEN_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            )}
            {(selectorType === 'dropdown' || selectorType === 'text') && (
              <input
                className="w-full border border-gray-300 rounded px-2 py-1 text-xs"
                placeholder="—"
                value={defaultValueScalar}
                onChange={(e) => setDefaultValueScalar(e.target.value)}
              />
            )}
            {selectorType === 'multi_select' && (
              <p className="text-[10px] text-gray-400">Default value не поддерживается для multi_select.</p>
            )}
          </div>
          </div>

          {/* Center: React Flow canvas */}
          <div className="flex-1 relative">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypesObj}
              defaultEdgeOptions={{
                type: 'mappingEdge',
                markerEnd: { type: MarkerType.ArrowClosed, color: '#94a3b8' },
              }}
              fitView
              fitViewOptions={{ padding: 0.3 }}
              proOptions={{ hideAttribution: true }}
            >
              <Controls position="bottom-right" />
              <Background gap={16} size={1} />
            </ReactFlow>

            {/* Hint overlay */}
            {edges.length === 0 && (
              <div className="absolute bottom-12 left-1/2 -translate-x-1/2 bg-blue-50 text-blue-600 text-xs px-3 py-1.5 rounded shadow-sm pointer-events-none">
                {t('selectors.dragToConnect')}
              </div>
            )}

            {/* Edge config popup */}
            {configEdge && configEdgeData && (
              <div className="absolute top-4 right-4 bg-white border border-gray-300 rounded-lg shadow-lg p-3 w-[280px] z-10 max-h-[80vh] overflow-y-auto">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-gray-700">
                    {configEdgeData.targetColumn}
                  </span>
                  <button
                    onClick={() => setConfigEdgeId(null)}
                    className="text-gray-400 hover:text-gray-600 text-sm"
                  >
                    &times;
                  </button>
                </div>

                <div className="space-y-2">
                  <div>
                    <label className="block text-xs text-gray-500 mb-0.5">{t('selectors.operatorOverride')}</label>
                    <select
                      className="w-full border border-gray-300 rounded px-2 py-1 text-xs"
                      value={configEdgeData.operatorOverride || ''}
                      onChange={(e) => updateEdgeField('operatorOverride', e.target.value)}
                    >
                      <option value="">-- ({t(`selectors.op${operator.charAt(0).toUpperCase() + operator.slice(1)}` as keyof typeof t)})</option>
                      {OPERATORS.map((op) => (
                        <option key={op} value={op}>
                          {t(`selectors.op${op.charAt(0).toUpperCase() + op.slice(1)}` as keyof typeof t)}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs text-gray-500 mb-0.5">{t('selectors.targetTable')}</label>
                    <input
                      className="w-full border border-gray-300 rounded px-2 py-1 text-xs font-mono"
                      value={configEdgeData.targetTable || ''}
                      placeholder="optional"
                      onChange={(e) => updateEdgeField('targetTable', e.target.value)}
                    />
                  </div>

                  {/* Two-step (post_filter) section */}
                  <div className="border-t pt-2 mt-2">
                    <div className="text-xs font-semibold text-gray-600 mb-1">
                      Двухшаговая фильтрация (опц.)
                    </div>
                    <p className="text-[10px] text-gray-400 mb-2">
                      Когда колонки нет в SELECT чарта: значение селектора резолвится через
                      связную таблицу, ID подставляется в target_column.
                    </p>
                    <div className="space-y-1.5">
                      <div>
                        <label className="block text-[10px] text-gray-500 mb-0.5">resolve_table</label>
                        <input
                          className="w-full border border-gray-300 rounded px-2 py-1 text-xs font-mono"
                          value={configEdgeData.postFilterResolveTable || ''}
                          placeholder="crm_deals"
                          onChange={(e) => updateEdgeField('postFilterResolveTable', e.target.value)}
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] text-gray-500 mb-0.5">resolve_column</label>
                        <input
                          className="w-full border border-gray-300 rounded px-2 py-1 text-xs font-mono"
                          value={configEdgeData.postFilterResolveColumn || ''}
                          placeholder="assigned_by_id"
                          onChange={(e) => updateEdgeField('postFilterResolveColumn', e.target.value)}
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] text-gray-500 mb-0.5">resolve_id_column</label>
                        <input
                          className="w-full border border-gray-300 rounded px-2 py-1 text-xs font-mono"
                          value={configEdgeData.postFilterResolveIdColumn || ''}
                          placeholder="id"
                          onChange={(e) => updateEdgeField('postFilterResolveIdColumn', e.target.value)}
                        />
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={() => handleDeleteEdge(configEdgeId!)}
                    className="w-full text-xs text-red-500 hover:text-red-700 border border-red-200 rounded py-1 hover:bg-red-50 transition-colors"
                  >
                    {t('selectors.deleteMapping')}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* SQL Preview */}
        <SqlPreviewPanel preview={sqlPreview} loading={sqlPreviewLoading} />

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded hover:bg-gray-50"
          >
            {t('common.cancel')}
          </button>
          <button
            onClick={handleFinish}
            className="px-4 py-2 text-sm text-white bg-blue-600 rounded hover:bg-blue-700"
            disabled={saving || !name || !label}
          >
            {saving ? t('common.saving') : t('common.save')}
          </button>
        </div>
      </div>
    </div>
  )
}
