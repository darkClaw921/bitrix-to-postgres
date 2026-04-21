import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from '../../i18n'
import {
  useDashboardSelectors,
  useCreateSelector,
  useUpdateSelector,
  useDeleteSelector,
} from '../../hooks/useSelectors'
import { dashboardsApi, schemaApi } from '../../services/api'
import type { DashboardSelector, DashboardChart, SelectorCreateRequest, SelectorUpdateRequest, SelectorMapping, TableInfo } from '../../services/api'
import SelectorBoardDialog from './SelectorBoardDialog'

const TYPE_ICONS: Record<string, string> = {
  dropdown: '\u25BC',
  multi_select: '\u2611',
  date_range: '\u2194',
  single_date: '\u{1F4C5}',
  text: 'Aa',
}

interface Props {
  dashboardId: number
  charts: DashboardChart[]
}

// ──────────────────────────────────────────────────────────────
// Inline mapping panel state per selector
// ──────────────────────────────────────────────────────────────
interface AddMappingState {
  selectedChartId: number | null
  /** Columns from the chart's DB tables (schema-based, not SELECT output) */
  columns: string[]
  loadingCols: boolean
  /** Final value — filled by dropdown pick OR manual input */
  columnValue: string
  saving: boolean
}

const EMPTY_ADD_MAPPING: AddMappingState = {
  selectedChartId: null,
  columns: [],
  loadingCols: false,
  columnValue: '',
  saving: false,
}

export default function SelectorEditorSection({ dashboardId, charts }: Props) {
  const { t } = useTranslation()
  const { data: selectors, refetch } = useDashboardSelectors(dashboardId)
  const createSelector = useCreateSelector()
  const updateSelector = useUpdateSelector()
  const deleteSelector = useDeleteSelector()

  const [modalOpen, setModalOpen] = useState(false)
  const [editingSelector, setEditingSelector] = useState<DashboardSelector | null>(null)

  // Which selector has the mapping panel open
  const [expandedMappingSelectorId, setExpandedMappingSelectorId] = useState<number | null>(null)
  // Add-mapping form state (one form at a time)
  const [addMapping, setAddMapping] = useState<AddMappingState>(EMPTY_ADD_MAPPING)
  // Used to cancel in-flight column load when chart changes
  const colLoadAbortRef = useRef<AbortController | null>(null)
  // Schema tables cache (loaded once when first mapping panel is opened)
  const schemaCacheRef = useRef<TableInfo[] | null>(null)

  // AI generation preview
  const [aiPreview, setAiPreview] = useState<SelectorCreateRequest[] | null>(null)
  const [aiLoading, setAiLoading] = useState(false)
  const [aiError, setAiError] = useState<string | null>(null)
  const [acceptedSet, setAcceptedSet] = useState<Set<number>>(new Set())
  const [aiPanelOpen, setAiPanelOpen] = useState(false)
  const [aiUserRequest, setAiUserRequest] = useState('')
  const [aiSelectedChartIds, setAiSelectedChartIds] = useState<Set<number>>(new Set())

  // Only real charts are eligible for AI selector generation (headings are excluded).
  const eligibleCharts = useMemo(
    () => charts.filter((c) => c.item_type !== 'heading'),
    [charts],
  )

  // When the AI panel opens or the list of eligible charts changes,
  // default to "all charts selected".
  useEffect(() => {
    if (aiPanelOpen) {
      setAiSelectedChartIds(new Set(eligibleCharts.map((c) => c.id)))
    }
  }, [aiPanelOpen, eligibleCharts])

  const toggleAiChart = (dcId: number) => {
    setAiSelectedChartIds((prev) => {
      const next = new Set(prev)
      if (next.has(dcId)) next.delete(dcId)
      else next.add(dcId)
      return next
    })
  }

  const selectAllAiCharts = () =>
    setAiSelectedChartIds(new Set(eligibleCharts.map((c) => c.id)))
  const clearAllAiCharts = () => setAiSelectedChartIds(new Set())

  const handleCreate = () => {
    setEditingSelector(null)
    setModalOpen(true)
  }

  const handleEdit = (sel: DashboardSelector) => {
    setEditingSelector(sel)
    setModalOpen(true)
  }

  const handleDelete = (sel: DashboardSelector) => {
    if (!confirm(t('selectors.confirmDelete'))) return
    deleteSelector.mutate(
      { dashboardId, selectorId: sel.id },
      { onSuccess: () => refetch() },
    )
  }

  const handleSave = (data: SelectorCreateRequest | SelectorUpdateRequest) => {
    if (editingSelector) {
      updateSelector.mutate(
        { dashboardId, selectorId: editingSelector.id, data: data as SelectorUpdateRequest },
        {
          onSuccess: () => {
            setModalOpen(false)
            refetch()
          },
        },
      )
    } else {
      createSelector.mutate(
        { dashboardId, data: data as SelectorCreateRequest },
        {
          onSuccess: () => {
            setModalOpen(false)
            refetch()
          },
        },
      )
    }
  }

  const handleMoveUp = (sel: DashboardSelector, index: number) => {
    if (index === 0 || !selectors) return
    const prev = selectors[index - 1]
    updateSelector.mutate(
      { dashboardId, selectorId: sel.id, data: { sort_order: prev.sort_order } },
      { onSuccess: () => {
        updateSelector.mutate(
          { dashboardId, selectorId: prev.id, data: { sort_order: sel.sort_order } },
          { onSuccess: () => refetch() },
        )
      }},
    )
  }

  const handleAiGenerate = async () => {
    if (aiSelectedChartIds.size === 0) {
      setAiError('Выберите хотя бы один чарт для генерации селекторов')
      return
    }
    setAiLoading(true)
    setAiError(null)
    setAiPreview(null)
    try {
      // If user selected all eligible charts, omit chart_ids — backend will use all.
      const allSelected =
        eligibleCharts.length > 0 &&
        aiSelectedChartIds.size === eligibleCharts.length
      const chartIds = allSelected ? undefined : Array.from(aiSelectedChartIds)
      const res = await dashboardsApi.generateSelectors(
        dashboardId,
        aiUserRequest.trim() || undefined,
        chartIds,
      )
      setAiPreview(res.selectors || [])
      setAcceptedSet(new Set(res.selectors?.map((_, i) => i) || []))
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string }
      setAiError(err?.response?.data?.detail || err?.message || 'Ошибка генерации')
    } finally {
      setAiLoading(false)
    }
  }

  const toggleAccepted = (idx: number) => {
    setAcceptedSet((prev) => {
      const next = new Set(prev)
      if (next.has(idx)) next.delete(idx)
      else next.add(idx)
      return next
    })
  }

  const handleAcceptAi = async () => {
    if (!aiPreview) return
    const accepted = aiPreview.filter((_, i) => acceptedSet.has(i))
    for (const sel of accepted) {
      await new Promise<void>((resolve, reject) => {
        createSelector.mutate(
          { dashboardId, data: sel },
          { onSuccess: () => resolve(), onError: (err) => reject(err) },
        )
      })
    }
    setAiPreview(null)
    setAcceptedSet(new Set())
    refetch()
  }

  // ── Inline mapping handlers ────────────────────────────────
  const toggleMappingPanel = (selId: number) => {
    setExpandedMappingSelectorId((prev) => (prev === selId ? null : selId))
    setAddMapping(EMPTY_ADD_MAPPING)
    // Pre-load schema on first open
    if (schemaCacheRef.current === null) {
      schemaApi.tables().then((res) => { schemaCacheRef.current = res.tables }).catch(() => {})
    }
  }

  const handleChartPickForMapping = async (dcId: number) => {
    // Cancel previous column load
    colLoadAbortRef.current?.abort()
    const ac = new AbortController()
    colLoadAbortRef.current = ac

    setAddMapping({ selectedChartId: dcId, columns: [], loadingCols: true, columnValue: '', saving: false })
    try {
      // Get the tables used in the chart's SQL
      const chartTables = await dashboardsApi.getChartTables(dashboardId, dcId)
      if (ac.signal.aborted) return

      // Load schema if not yet cached
      if (schemaCacheRef.current === null) {
        const res = await schemaApi.tables()
        schemaCacheRef.current = res.tables
      }
      if (ac.signal.aborted) return

      // Collect all columns from tables used in this chart
      const tableSet = new Set(chartTables)
      const cols: string[] = []
      for (const tbl of schemaCacheRef.current) {
        if (tableSet.has(tbl.table_name)) {
          for (const col of tbl.columns) {
            cols.push(col.name)
          }
        }
      }

      setAddMapping((prev) => ({ ...prev, columns: cols, loadingCols: false }))
    } catch {
      if (!ac.signal.aborted) {
        setAddMapping((prev) => ({ ...prev, columns: [], loadingCols: false }))
      }
    }
  }

  const handleConfirmAddMapping = (sel: DashboardSelector) => {
    const { selectedChartId, columnValue } = addMapping
    if (!selectedChartId || !columnValue.trim()) return

    // Build the updated mappings list (keep all existing + append new)
    const existingMappings = sel.mappings.map((m: SelectorMapping) => ({
      dashboard_chart_id: m.dashboard_chart_id,
      target_column: m.target_column,
      target_table: m.target_table,
      operator_override: m.operator_override,
      post_filter_resolve_table: m.post_filter_resolve_table,
      post_filter_resolve_column: m.post_filter_resolve_column,
      post_filter_resolve_id_column: m.post_filter_resolve_id_column,
    }))

    setAddMapping((prev) => ({ ...prev, saving: true }))
    updateSelector.mutate(
      {
        dashboardId,
        selectorId: sel.id,
        data: {
          mappings: [...existingMappings, { dashboard_chart_id: selectedChartId, target_column: columnValue.trim() }],
        },
      },
      {
        onSuccess: () => {
          setAddMapping(EMPTY_ADD_MAPPING)
          refetch()
        },
        onError: () => setAddMapping((prev) => ({ ...prev, saving: false })),
      },
    )
  }

  const handleDeleteMappingInline = (sel: DashboardSelector, mappingId: number) => {
    if (!confirm(t('selectors.confirmDeleteMapping'))) return
    const newMappings = sel.mappings
      .filter((m: SelectorMapping) => m.id !== mappingId)
      .map((m: SelectorMapping) => ({
        dashboard_chart_id: m.dashboard_chart_id,
        target_column: m.target_column,
        target_table: m.target_table,
        operator_override: m.operator_override,
        post_filter_resolve_table: m.post_filter_resolve_table,
        post_filter_resolve_column: m.post_filter_resolve_column,
        post_filter_resolve_id_column: m.post_filter_resolve_id_column,
      }))
    updateSelector.mutate(
      { dashboardId, selectorId: sel.id, data: { mappings: newMappings } },
      { onSuccess: () => refetch() },
    )
  }

  const handleMoveDown = (sel: DashboardSelector, index: number) => {
    if (!selectors || index >= selectors.length - 1) return
    const next = selectors[index + 1]
    updateSelector.mutate(
      { dashboardId, selectorId: sel.id, data: { sort_order: next.sort_order } },
      { onSuccess: () => {
        updateSelector.mutate(
          { dashboardId, selectorId: next.id, data: { sort_order: sel.sort_order } },
          { onSuccess: () => refetch() },
        )
      }},
    )
  }

  return (
    <div className="mt-8">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold">{t('selectors.title')}</h3>
        <div className="flex gap-2">
          <button
            onClick={() => setAiPanelOpen((v) => !v)}
            disabled={charts.length === 0}
            className="px-3 py-1.5 text-sm bg-purple-600 text-white rounded hover:bg-purple-700 transition-colors disabled:opacity-50"
            title="Сгенерировать селекторы через AI на основе чартов дашборда"
          >
            {aiPanelOpen ? 'AI: скрыть' : 'AI: сгенерировать'}
          </button>
          <button
            onClick={handleCreate}
            className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
          >
            + {t('selectors.addSelector')}
          </button>
        </div>
      </div>

      {aiPanelOpen && (
        <div className="mb-3 border border-purple-200 bg-purple-50 rounded-lg p-3">
          <label className="block text-xs font-semibold text-purple-700 mb-1">
            Опишите, какие селекторы нужны (опционально)
          </label>
          <textarea
            value={aiUserRequest}
            onChange={(e) => setAiUserRequest(e.target.value)}
            placeholder="Например: фильтр по диапазону дат создания сделки, фильтр по ответственному менеджеру (multi-select), фильтр по стадии воронки"
            rows={3}
            maxLength={2000}
            className="w-full px-2 py-1.5 text-sm border border-purple-300 rounded focus:outline-none focus:ring-1 focus:ring-purple-500 bg-white"
          />

          <div className="mt-3">
            <div className="flex items-center justify-between mb-1">
              <label className="block text-xs font-semibold text-purple-700">
                Чарты для генерации селекторов
              </label>
              <div className="flex items-center gap-2 text-[11px]">
                <button
                  type="button"
                  onClick={selectAllAiCharts}
                  className="text-purple-700 hover:underline"
                >
                  Выбрать все
                </button>
                <span className="text-gray-300">|</span>
                <button
                  type="button"
                  onClick={clearAllAiCharts}
                  className="text-purple-700 hover:underline"
                >
                  Снять все
                </button>
              </div>
            </div>
            {eligibleCharts.length === 0 ? (
              <div className="text-[11px] text-gray-500 px-2 py-1.5 bg-white border border-purple-200 rounded">
                В дашборде нет чартов, доступных для генерации
              </div>
            ) : (
              <div className="max-h-[180px] overflow-y-auto bg-white border border-purple-200 rounded p-2 space-y-1">
                {eligibleCharts.map((c) => {
                  const checked = aiSelectedChartIds.has(c.id)
                  const title = c.title_override || c.chart_title || `Chart #${c.id}`
                  return (
                    <label
                      key={c.id}
                      className="flex items-center gap-2 text-xs cursor-pointer hover:bg-purple-50 px-1 py-0.5 rounded"
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleAiChart(c.id)}
                      />
                      <span className="truncate flex-1" title={title}>
                        {title}
                      </span>
                      {c.chart_type && (
                        <span className="text-[10px] text-gray-400 uppercase">
                          {c.chart_type}
                        </span>
                      )}
                    </label>
                  )
                })}
              </div>
            )}
            <div className="text-[11px] text-gray-500 mt-1">
              По умолчанию выбраны все чарты. Выбрано: {aiSelectedChartIds.size} / {eligibleCharts.length}
            </div>
          </div>

          <div className="flex items-center justify-between mt-2">
            <div className="text-[11px] text-gray-500">
              Если оставить пустым — AI сам подберёт наиболее полезные фильтры. {aiUserRequest.length}/2000
            </div>
            <button
              onClick={handleAiGenerate}
              disabled={aiLoading || aiSelectedChartIds.size === 0}
              className="px-3 py-1.5 text-sm bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50"
            >
              {aiLoading ? 'Генерация...' : 'Сгенерировать'}
            </button>
          </div>
        </div>
      )}

      {aiError && (
        <div className="mb-3 px-3 py-2 bg-red-50 border border-red-200 text-red-600 text-sm rounded">
          {aiError}
        </div>
      )}

      {aiPreview && (
        <div className="mb-4 border border-purple-200 bg-purple-50 rounded-lg p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm font-semibold text-purple-700">
              AI предложил {aiPreview.length} селектор(ов)
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleAcceptAi}
                disabled={acceptedSet.size === 0 || createSelector.isPending}
                className="px-3 py-1 text-xs bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50"
              >
                Сохранить выбранные ({acceptedSet.size})
              </button>
              <button
                onClick={() => { setAiPreview(null); setAcceptedSet(new Set()) }}
                className="px-3 py-1 text-xs text-gray-600 border border-gray-300 rounded hover:bg-gray-100"
              >
                Отмена
              </button>
            </div>
          </div>
          <div className="space-y-2 max-h-[260px] overflow-y-auto">
            {aiPreview.map((sel, idx) => (
              <label
                key={idx}
                className="flex items-start gap-2 bg-white border border-gray-200 rounded p-2 cursor-pointer hover:bg-gray-50"
              >
                <input
                  type="checkbox"
                  checked={acceptedSet.has(idx)}
                  onChange={() => toggleAccepted(idx)}
                  className="mt-0.5"
                />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">
                    {sel.label} <span className="text-xs text-gray-400">({sel.name})</span>
                  </div>
                  <div className="text-xs text-gray-500">
                    {sel.selector_type} · {sel.operator} · маппингов: {sel.mappings?.length || 0}
                  </div>
                  {Boolean((sel.config as { default_value?: unknown } | undefined)?.default_value) && (
                    <div className="text-[11px] text-purple-600 font-mono">
                      default: {JSON.stringify((sel.config as { default_value?: unknown }).default_value)}
                    </div>
                  )}
                </div>
              </label>
            ))}
          </div>
        </div>
      )}

      {(!selectors || selectors.length === 0) ? (
        <div className="text-gray-400 text-sm py-4 text-center border border-dashed border-gray-200 rounded">
          {t('selectors.noSelectors')}
        </div>
      ) : (
        <div className="space-y-2">
          {selectors.map((sel, index) => {
            const isMappingOpen = expandedMappingSelectorId === sel.id
            return (
              <div key={sel.id} className="border border-gray-200 rounded-lg bg-white overflow-hidden">
                {/* Selector row */}
                <div className="flex items-center gap-3 px-4 py-2">
                  <span className="text-lg w-6 text-center" title={sel.selector_type}>
                    {TYPE_ICONS[sel.selector_type] || '?'}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm truncate">{sel.label}</div>
                    <div className="text-xs text-gray-400">
                      {sel.selector_type} &middot; {sel.mappings.length} {t('selectors.mappedCharts')}
                      {sel.is_required && <span className="text-red-500 ml-1">*</span>}
                    </div>
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => toggleMappingPanel(sel.id)}
                      className={`px-2 py-1 text-xs rounded border transition-colors ${
                        isMappingOpen
                          ? 'border-blue-400 bg-blue-50 text-blue-700'
                          : 'border-gray-200 text-gray-500 hover:border-gray-400'
                      }`}
                      title={t('selectors.addChartMapping')}
                    >
                      {t('selectors.addChartMapping')} {isMappingOpen ? '▲' : '▼'}
                    </button>
                    <button
                      onClick={() => handleMoveUp(sel, index)}
                      disabled={index === 0}
                      className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-30"
                      title={t('selectors.moveUp')}
                    >
                      &uarr;
                    </button>
                    <button
                      onClick={() => handleMoveDown(sel, index)}
                      disabled={index >= selectors.length - 1}
                      className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-30"
                      title={t('selectors.moveDown')}
                    >
                      &darr;
                    </button>
                    <button
                      onClick={() => handleEdit(sel)}
                      className="p-1 text-blue-500 hover:text-blue-700 text-sm"
                      title={t('common.edit')}
                    >
                      {t('common.edit')}
                    </button>
                    <button
                      onClick={() => handleDelete(sel)}
                      className="p-1 text-red-400 hover:text-red-600 text-sm"
                      title={t('common.delete')}
                    >
                      {t('common.delete')}
                    </button>
                  </div>
                </div>

                {/* Inline mapping panel */}
                {isMappingOpen && (
                  <div className="border-t border-gray-100 bg-gray-50 px-4 py-3 space-y-3">
                    {/* Existing mappings */}
                    {sel.mappings.length > 0 ? (
                      <div className="space-y-1">
                        {sel.mappings.map((m: SelectorMapping) => {
                          const chartName = eligibleCharts.find((c) => c.id === m.dashboard_chart_id)
                            ?.title_override
                            || eligibleCharts.find((c) => c.id === m.dashboard_chart_id)?.chart_title
                            || `#${m.dashboard_chart_id}`
                          return (
                            <div key={m.id} className="flex items-center gap-2 text-xs bg-white border border-gray-200 rounded px-2 py-1">
                              <span className="truncate flex-1 text-gray-700">
                                <span className="font-medium">{chartName}</span>
                                <span className="text-gray-400 mx-1">→</span>
                                <span className="font-mono text-blue-700">{m.target_column}</span>
                                {m.target_table && (
                                  <span className="text-gray-400 ml-1">({m.target_table})</span>
                                )}
                              </span>
                              <button
                                onClick={() => handleDeleteMappingInline(sel, m.id)}
                                className="text-red-400 hover:text-red-600 shrink-0"
                                title={t('selectors.deleteMapping')}
                              >
                                &times;
                              </button>
                            </div>
                          )
                        })}
                      </div>
                    ) : (
                      <p className="text-xs text-gray-400">{t('selectors.noMappings')}</p>
                    )}

                    {/* Add-mapping form */}
                    <div className="space-y-1.5 border-t border-gray-200 pt-2">
                      <div className="text-[10px] text-gray-400 font-medium uppercase tracking-wide">
                        Добавить привязку
                      </div>

                      {/* Row 1: chart picker */}
                      <select
                        className="w-full border border-gray-300 rounded px-2 py-1 text-xs"
                        value={addMapping.selectedChartId ?? ''}
                        onChange={(e) => {
                          const dcId = Number(e.target.value)
                          if (dcId) handleChartPickForMapping(dcId)
                          else setAddMapping(EMPTY_ADD_MAPPING)
                        }}
                      >
                        <option value="">{t('selectors.selectChart')}</option>
                        {eligibleCharts.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.title_override || c.chart_title || `#${c.id}`}
                          </option>
                        ))}
                      </select>

                      {/* Row 2: field — always visible */}
                      <div className="flex items-center gap-1.5">
                        {/* Suggestion dropdown — only when columns loaded */}
                        {addMapping.selectedChartId && (
                          <select
                            className="border border-gray-300 rounded px-2 py-1 text-xs bg-white"
                            value=""
                            onChange={(e) => {
                              if (e.target.value) {
                                setAddMapping((prev) => ({ ...prev, columnValue: e.target.value }))
                              }
                            }}
                            disabled={addMapping.loadingCols}
                            title="Поля из таблиц чарта"
                          >
                            <option value="">
                              {addMapping.loadingCols ? '...' : '— выбрать поле —'}
                            </option>
                            {addMapping.columns.map((col) => (
                              <option key={col} value={col}>{col}</option>
                            ))}
                          </select>
                        )}

                        {/* Manual input — always visible */}
                        <input
                          type="text"
                          className="flex-1 min-w-0 border border-gray-300 rounded px-2 py-1 text-xs font-mono"
                          placeholder="поле (напр. date_create)"
                          value={addMapping.columnValue}
                          onChange={(e) => setAddMapping((prev) => ({ ...prev, columnValue: e.target.value }))}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && !addMapping.saving) handleConfirmAddMapping(sel)
                          }}
                        />

                        <button
                          onClick={() => handleConfirmAddMapping(sel)}
                          disabled={!addMapping.selectedChartId || !addMapping.columnValue.trim() || addMapping.saving}
                          className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 shrink-0"
                        >
                          {addMapping.saving ? '...' : t('selectors.addMapping')}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {modalOpen && (
        <SelectorBoardDialog
          dashboardId={dashboardId}
          charts={charts}
          selector={editingSelector}
          onClose={() => setModalOpen(false)}
          onSave={handleSave}
          saving={createSelector.isPending || updateSelector.isPending}
        />
      )}
    </div>
  )
}
