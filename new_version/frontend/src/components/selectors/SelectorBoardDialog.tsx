import { useState, useEffect, useCallback, useMemo } from 'react'
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
import SelectorConfigPanel from './SelectorConfigPanel'
import SqlPreviewPanel from './SqlPreviewPanel'
import SelectorNode from './nodes/SelectorNode'
import ChartNode from './nodes/ChartNode'
import MappingEdge from './nodes/MappingEdge'

const OPERATORS = ['equals', 'in', 'between', 'like', 'gt', 'lt', 'gte', 'lte'] as const

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

  // Build initial edges from existing mappings
  const buildInitialEdges = useCallback((): Edge[] => {
    if (!selector?.mappings) return []
    return selector.mappings.map((m) => ({
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
        onDelete: handleDeleteEdge,
        onConfigure: handleConfigureEdge,
      },
    }))
  }, [selector?.mappings])

  const [nodes, setNodes, onNodesChange] = useNodesState(buildInitialNodes())
  const [edges, setEdges, onEdgesChange] = useEdgesState(buildInitialEdges())

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

  // Update edge callbacks whenever edges change
  useEffect(() => {
    setEdges((eds) =>
      eds.map((e) => ({
        ...e,
        data: {
          ...e.data,
          onDelete: handleDeleteEdge,
          onConfigure: handleConfigureEdge,
        },
      })),
    )
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

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

    // Build mappings from edges
    const mappingsList: SelectorMappingRequest[] = edges.map((e) => {
      const dcIdStr = e.target.replace('chart-', '')
      const d = e.data as { targetColumn?: string; operatorOverride?: string; targetTable?: string } | undefined
      return {
        dashboard_chart_id: Number(dcIdStr),
        target_column: d?.targetColumn || '',
        target_table: d?.targetTable || undefined,
        operator_override: d?.operatorOverride || undefined,
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
  const configEdgeData = configEdge?.data as { operatorOverride?: string; targetTable?: string; targetColumn?: string } | undefined

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
          {/* Left panel: config */}
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
              <div className="absolute top-4 right-4 bg-white border border-gray-300 rounded-lg shadow-lg p-3 w-[240px] z-10">
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
                      onChange={(e) => {
                        const val = e.target.value
                        setEdges((eds) =>
                          eds.map((ed) =>
                            ed.id === configEdgeId
                              ? { ...ed, data: { ...ed.data, operatorOverride: val } }
                              : ed,
                          ),
                        )
                      }}
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
                      onChange={(e) => {
                        const val = e.target.value
                        setEdges((eds) =>
                          eds.map((ed) =>
                            ed.id === configEdgeId
                              ? { ...ed, data: { ...ed.data, targetTable: val } }
                              : ed,
                          ),
                        )
                      }}
                    />
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
