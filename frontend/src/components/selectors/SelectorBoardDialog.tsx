import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import {
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  useNodesState,
  useEdgesState,
  useUpdateNodeInternals,
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

export default function SelectorBoardDialog(props: Props) {
  // useUpdateNodeInternals (and other React Flow hooks that talk to the
  // internal store) require a ReactFlowProvider somewhere up the tree.
  // Wrapping the inner component here keeps the public API unchanged.
  return (
    <ReactFlowProvider>
      <SelectorBoardDialogInner {...props} />
    </ReactFlowProvider>
  )
}

function SelectorBoardDialogInner({
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

  // AI regeneration of a single mapping (per edge)
  const [aiRegenPrompt, setAiRegenPrompt] = useState('')
  const [aiRegenLoading, setAiRegenLoading] = useState(false)
  const [aiRegenError, setAiRegenError] = useState<string | null>(null)
  // Last AI response for display in popup so user sees what was applied even
  // when fields look unchanged (AI may pick the same target_column).
  const [aiRegenResult, setAiRegenResult] = useState<{
    target_column: string
    target_table?: string | null
    operator_override?: string | null
    post_filter_resolve_table?: string | null
    post_filter_resolve_column?: string | null
    post_filter_resolve_id_column?: string | null
  } | null>(null)

  // Node types (memoized to prevent re-renders)
  const nodeTypes: NodeTypes = useMemo(() => ({
    selectorNode: SelectorNode,
    chartNode: ChartNode,
  }), [])

  // AI-generated mappings often reference columns that are NOT in the chart's
  // SELECT output (e.g. a `date_range` filter targeting `date_create` on the
  // underlying table even though the chart only SELECTs aggregates). The
  // backend applies such filters via ChartService.apply_filters regardless,
  // but the visual board can only render an edge when a matching target
  // <Handle> exists. To make existing mappings visible, we augment each
  // chart's column list with any extra columns coming from saved mappings —
  // the handle gets created and the edge attaches.
  const getColumnsForChart = useCallback(
    (dcId: number): { columns: string[]; extras: Set<string> } => {
      const fromSelect = chartColumnsCache[dcId] || []
      const extras = new Set<string>()
      if (selector?.mappings) {
        for (const m of selector.mappings) {
          if (m.dashboard_chart_id === dcId && !fromSelect.includes(m.target_column)) {
            extras.add(m.target_column)
          }
        }
      }
      return {
        columns: extras.size > 0 ? [...fromSelect, ...extras] : fromSelect,
        extras,
      }
    },
    [chartColumnsCache, selector?.mappings],
  )

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

    const chartNodes: Node[] = charts.map((dc, i) => {
      const { columns, extras } = getColumnsForChart(dc.id)
      return {
        id: `chart-${dc.id}`,
        type: 'chartNode',
        position: { x: 500, y: 30 + i * 220 },
        data: {
          chartTitle: dc.title_override || dc.chart_title || `Chart #${dc.chart_id}`,
          dcId: dc.id,
          columns,
          extraColumns: extras,
          loading: !chartColumnsCache[dc.id],
        },
      }
    })

    return [selectorNode, ...chartNodes]
  }, [charts, label, selectorType, operator, chartColumnsCache, getColumnsForChart])

  // Edges start empty. We populate them from `selector.mappings` only after
  // the referenced charts have loaded their columns — otherwise ReactFlow
  // tries to attach edges to handles that don't exist yet (the chart node
  // renders "Loading..." with zero <Handle> elements) and silently drops the
  // edges, so the user sees no connections at all.
  const [nodes, setNodes, onNodesChange] = useNodesState(buildInitialNodes())
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])

  // Force ReactFlow to re-measure node handles when chart columns load.
  // Without this, handles added dynamically (after node mount) are not
  // registered in ReactFlow's internal store, so edges silently fail to
  // attach to them and the canvas appears empty.
  const updateNodeInternals = useUpdateNodeInternals()

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

  // Update chart nodes when columns load (or when mappings-derived extras change)
  useEffect(() => {
    const refreshedNodeIds: string[] = []
    setNodes((nds) =>
      nds.map((n) => {
        if (n.type === 'chartNode') {
          const dcId = (n.data as { dcId: number }).dcId
          const cached = chartColumnsCache[dcId]
          if (!cached) return n
          const { columns, extras } = getColumnsForChart(dcId)
          const prevCols = ((n.data as { columns?: string[] }).columns) || []
          const changed =
            prevCols.length !== columns.length ||
            prevCols.some((c, i) => c !== columns[i])
          if (changed || (n.data as { loading?: boolean }).loading !== false) {
            refreshedNodeIds.push(n.id)
            return {
              ...n,
              data: { ...n.data, columns, extraColumns: extras, loading: false },
            }
          }
        }
        return n
      }),
    )
    // Tell ReactFlow about the newly-rendered <Handle> elements; otherwise
    // edges built from saved mappings don't find them and stay invisible.
    if (refreshedNodeIds.length > 0) {
      // Defer one frame so the DOM commit (with the new handles) lands
      // before ReactFlow re-measures the node.
      requestAnimationFrame(() => {
        refreshedNodeIds.forEach((id) => updateNodeInternals(id))
      })
    }
  }, [chartColumnsCache, setNodes, updateNodeInternals, getColumnsForChart])

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
    setAiRegenPrompt('')
    setAiRegenError(null)
    setAiRegenResult(null)
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

    // Force ReactFlow to re-measure each referenced chart node so the
    // freshly-rendered <Handle> elements get registered in the internal
    // store. Without this, edges added to dynamically-created handles are
    // silently dropped and the canvas appears empty.
    requestAnimationFrame(() => {
      referencedChartIds.forEach((id) => updateNodeInternals(`chart-${id}`))
    })
  }, [
    chartColumnsCache,
    selector?.mappings,
    setEdges,
    handleDeleteEdge,
    handleConfigureEdge,
    updateNodeInternals,
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

  // AI regenerate the current edge's mapping. The target_column may change,
  // so we rebuild the edge id + targetHandle and ensure the chart node has a
  // matching <Handle> for the (possibly new) column.
  const handleAiRegenerate = async () => {
    if (!configEdgeId) return
    const edge = edges.find((e) => e.id === configEdgeId)
    if (!edge) return
    const dcIdStr = edge.target.replace('chart-', '')
    const dcId = Number(dcIdStr)
    if (!dcId) return

    setAiRegenLoading(true)
    setAiRegenError(null)
    setAiRegenResult(null)
    try {
      const ed = edge.data as {
        targetColumn?: string
        targetTable?: string
        operatorOverride?: string
        postFilterResolveTable?: string
        postFilterResolveColumn?: string
        postFilterResolveIdColumn?: string
      } | undefined
      const res = await dashboardsApi.regenerateMapping(dashboardId, {
        dc_id: dcId,
        selector_name: name || 'selector',
        selector_label: label || name || 'Filter',
        selector_type: selectorType,
        operator: operator,
        user_request: aiRegenPrompt.trim() || undefined,
        current_target_column: ed?.targetColumn || undefined,
        current_target_table: ed?.targetTable || undefined,
        current_operator_override: ed?.operatorOverride || undefined,
        current_post_filter_resolve_table: ed?.postFilterResolveTable || undefined,
        current_post_filter_resolve_column: ed?.postFilterResolveColumn || undefined,
        current_post_filter_resolve_id_column: ed?.postFilterResolveIdColumn || undefined,
      })

      const newCol = res.target_column

      // Make sure the chart node exposes the new column as a <Handle> target,
      // otherwise the edge silently drops in ReactFlow.
      const refreshIds: string[] = []
      setNodes((nds) =>
        nds.map((n) => {
          if (n.type !== 'chartNode') return n
          if ((n.data as { dcId: number }).dcId !== dcId) return n
          const cols: string[] = (n.data as { columns?: string[] }).columns || []
          if (cols.includes(newCol)) return n
          const prevExtras = (n.data as { extraColumns?: Set<string> }).extraColumns
          const extras = new Set<string>(prevExtras ?? [])
          extras.add(newCol)
          refreshIds.push(n.id)
          return {
            ...n,
            data: { ...n.data, columns: [...cols, newCol], extraColumns: extras },
          }
        }),
      )

      const newEdgeId = `edge-${dcIdStr}-${newCol}`
      setEdges((eds) =>
        eds.map((e) =>
          e.id === configEdgeId
            ? {
                ...e,
                id: newEdgeId,
                targetHandle: `${dcIdStr}-${newCol}`,
                data: {
                  ...e.data,
                  targetColumn: newCol,
                  targetTable: res.target_table || '',
                  operatorOverride: res.operator_override || '',
                  postFilterResolveTable: res.post_filter_resolve_table || '',
                  postFilterResolveColumn: res.post_filter_resolve_column || '',
                  postFilterResolveIdColumn: res.post_filter_resolve_id_column || '',
                },
              }
            : e,
        ),
      )
      setConfigEdgeId(newEdgeId)
      setAiRegenResult(res)

      if (refreshIds.length > 0) {
        requestAnimationFrame(() => {
          refreshIds.forEach((id) => updateNodeInternals(id))
        })
      }
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string }
      setAiRegenError(err?.response?.data?.detail || err?.message || 'Ошибка регенерации')
    } finally {
      setAiRegenLoading(false)
    }
  }

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

                  {/* AI regeneration of this single mapping */}
                  <div className="border-t pt-2 mt-2">
                    <div className="text-xs font-semibold text-gray-600 mb-1">
                      AI-регенерация
                    </div>
                    <p className="text-[10px] text-gray-400 mb-2">
                      Опишите что нужно (можно сослаться на другой график по
                      названию — например «как у графика Конверсия»). Поле можно
                      оставить пустым.
                    </p>
                    <textarea
                      className="w-full border border-gray-300 rounded px-2 py-1 text-xs"
                      rows={3}
                      placeholder="посмотри как сделан фильтр у графика «Воронка продаж» и сделай так же"
                      value={aiRegenPrompt}
                      onChange={(e) => setAiRegenPrompt(e.target.value)}
                      disabled={aiRegenLoading}
                    />
                    {aiRegenError && (
                      <p className="text-[10px] text-red-600 mt-1">{aiRegenError}</p>
                    )}
                    <button
                      onClick={handleAiRegenerate}
                      disabled={aiRegenLoading}
                      className="w-full mt-2 text-xs text-white bg-purple-600 rounded py-1 hover:bg-purple-700 disabled:bg-purple-300 transition-colors"
                    >
                      {aiRegenLoading ? 'Генерирую…' : '🪄 Перегенерировать через AI'}
                    </button>
                    {aiRegenResult && (
                      <div className="mt-2 p-2 bg-purple-50 border border-purple-200 rounded text-[10px] text-gray-700 space-y-0.5">
                        <div className="font-semibold text-purple-700 mb-1">AI применил:</div>
                        <div>
                          <span className="text-gray-500">target_column:</span>{' '}
                          <span className="font-mono">{aiRegenResult.target_column}</span>
                        </div>
                        <div>
                          <span className="text-gray-500">target_table:</span>{' '}
                          <span className="font-mono">{aiRegenResult.target_table || '—'}</span>
                        </div>
                        <div>
                          <span className="text-gray-500">operator_override:</span>{' '}
                          <span className="font-mono">{aiRegenResult.operator_override || '—'}</span>
                        </div>
                        <div>
                          <span className="text-gray-500">post_filter:</span>{' '}
                          {aiRegenResult.post_filter_resolve_table ? (
                            <span className="font-mono">
                              {aiRegenResult.post_filter_resolve_table}.
                              {aiRegenResult.post_filter_resolve_column}
                              {' (id: '}
                              {aiRegenResult.post_filter_resolve_id_column || 'id'}
                              {')'}
                            </span>
                          ) : (
                            <span className="text-gray-400">—</span>
                          )}
                        </div>
                      </div>
                    )}
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
