import { useState, useEffect } from 'react'
import { useTranslation } from '../../i18n'
import { dashboardsApi, schemaApi } from '../../services/api'
import type {
  DashboardSelector,
  DashboardChart,
  SelectorCreateRequest,
  SelectorUpdateRequest,
  SelectorMappingRequest,
  SelectorOption,
  TableInfo,
} from '../../services/api'

const SELECTOR_TYPES = [
  { value: 'dropdown', defaultOp: 'equals' },
  { value: 'multi_select', defaultOp: 'in' },
  { value: 'date_range', defaultOp: 'between' },
  { value: 'single_date', defaultOp: 'equals' },
  { value: 'text', defaultOp: 'like' },
] as const

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

function Hint({ text }: { text: string }) {
  return <p className="text-xs text-gray-400 mt-0.5">{text}</p>
}

export default function SelectorModal({
  dashboardId,
  charts,
  selector,
  onClose,
  onSave,
  saving,
}: Props) {
  const { t } = useTranslation()
  const isEdit = !!selector

  // Step state
  const [step, setStep] = useState(1)

  // Step 1: Basic settings
  const [selectorType, setSelectorType] = useState(selector?.selector_type || 'dropdown')
  const [name, setName] = useState(selector?.name || '')
  const [label, setLabel] = useState(selector?.label || '')
  const [operator, setOperator] = useState(selector?.operator || 'equals')
  const [isRequired, setIsRequired] = useState(selector?.is_required || false)

  // Step 2: Data source
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
  const [previewOptions, setPreviewOptions] = useState<SelectorOption[]>([])
  const [previewLoading, setPreviewLoading] = useState(false)

  // Schema tables (for dropdowns in Step 2)
  const [schemaTables, setSchemaTables] = useState<TableInfo[]>([])
  const [schemaLoading, setSchemaLoading] = useState(false)

  // Step 3: Mappings
  const [mappings, setMappings] = useState<Record<number, { enabled: boolean; target_column: string; target_table: string; operator_override: string }>>(
    () => {
      const initial: Record<number, { enabled: boolean; target_column: string; target_table: string; operator_override: string }> = {}
      if (selector?.mappings) {
        for (const m of selector.mappings) {
          initial[m.dashboard_chart_id] = {
            enabled: true,
            target_column: m.target_column,
            target_table: m.target_table || '',
            operator_override: m.operator_override || '',
          }
        }
      }
      return initial
    },
  )
  const [chartColumns, setChartColumns] = useState<Record<number, string[]>>({})
  const [chartTables, setChartTables] = useState<Record<number, string[]>>({})

  // Auto-set operator on type change
  useEffect(() => {
    if (!isEdit) {
      const typeInfo = SELECTOR_TYPES.find((t) => t.value === selectorType)
      if (typeInfo) setOperator(typeInfo.defaultOp)
    }
  }, [selectorType, isEdit])

  // Load schema tables on mount (for Step 2 data source)
  useEffect(() => {
    setSchemaLoading(true)
    schemaApi.tables()
      .then((res) => setSchemaTables(res.tables || []))
      .catch(() => setSchemaTables([]))
      .finally(() => setSchemaLoading(false))
  }, [])

  // Helper: get columns for a selected schema table
  const getTableColumns = (tableName: string): string[] => {
    const table = schemaTables.find((t) => t.table_name === tableName)
    return table ? table.columns.map((c) => c.name) : []
  }

  // Load chart columns and tables for enabled charts
  const loadChartMeta = async (dcId: number) => {
    if (!chartColumns[dcId]) {
      dashboardsApi.getChartColumns(dashboardId, dcId)
        .then((cols) => setChartColumns((prev) => ({ ...prev, [dcId]: cols })))
        .catch(() => setChartColumns((prev) => ({ ...prev, [dcId]: [] })))
    }
    if (!chartTables[dcId]) {
      dashboardsApi.getChartTables(dashboardId, dcId)
        .then((tables) => setChartTables((prev) => ({ ...prev, [dcId]: tables })))
        .catch(() => setChartTables((prev) => ({ ...prev, [dcId]: [] })))
    }
  }

  const showStep2 = selectorType === 'dropdown' || selectorType === 'multi_select'
  const totalSteps = showStep2 ? 3 : 2

  const handleFinish = () => {
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

    const mappingsList: SelectorMappingRequest[] = Object.entries(mappings)
      .filter(([, m]) => m.enabled && m.target_column)
      .map(([dcId, m]) => ({
        dashboard_chart_id: Number(dcId),
        target_column: m.target_column,
        target_table: m.target_table || undefined,
        operator_override: m.operator_override || undefined,
      }))

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

  const handlePreview = async () => {
    if (!sourceTable || !sourceColumn) return
    setPreviewLoading(true)
    try {
      if (selector?.id) {
        const opts = await dashboardsApi.getSelectorOptions(dashboardId, selector.id)
        setPreviewOptions(opts)
      }
    } catch {
      setPreviewOptions([])
    }
    setPreviewLoading(false)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold">
            {isEdit ? t('selectors.editSelector') : t('selectors.addSelector')}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
        </div>

        {/* Step indicator */}
        <div className="flex px-4 pt-3 gap-2">
          {Array.from({ length: totalSteps }, (_, i) => i + 1).map((s) => {
            const stepNum = showStep2 ? s : (s === 1 ? 1 : 3)
            const stepLabel =
              stepNum === 1 ? t('selectors.step1Title') :
              stepNum === 2 ? t('selectors.step2Title') :
              t('selectors.step3Title')
            return (
              <div
                key={s}
                className={`flex-1 text-center text-xs py-1 rounded ${
                  step === s ? 'bg-blue-100 text-blue-700 font-medium' : 'bg-gray-100 text-gray-400'
                }`}
              >
                {s}. {stepLabel}
              </div>
            )
          })}
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          {/* Step 1 */}
          {step === 1 && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('selectors.selectorType')}</label>
                <Hint text={t('selectors.selectorTypeHint')} />
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mt-2">
                  {SELECTOR_TYPES.map((st) => (
                    <button
                      key={st.value}
                      onClick={() => setSelectorType(st.value)}
                      className={`p-3 border rounded-lg text-left text-sm transition-colors ${
                        selectorType === st.value
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="font-medium">{t(`selectors.type${st.value.charAt(0).toUpperCase() + st.value.slice(1).replace(/_(\w)/g, (_, c) => c.toUpperCase())}` as keyof typeof t)}</div>
                      <div className="text-xs text-gray-400 mt-0.5">{t(`selectors.type${st.value.charAt(0).toUpperCase() + st.value.slice(1).replace(/_(\w)/g, (_, c) => c.toUpperCase())}Desc` as keyof typeof t)}</div>
                    </button>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('selectors.selectorLabel')}</label>
                  <input
                    className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
                    value={label}
                    onChange={(e) => setLabel(e.target.value)}
                    placeholder="e.g. Status"
                  />
                  <Hint text={t('selectors.selectorLabelHint')} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('selectors.selectorName')}</label>
                  <input
                    className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm font-mono"
                    value={name}
                    onChange={(e) => setName(e.target.value.replace(/[^a-zA-Z0-9_]/g, ''))}
                    placeholder="e.g. status_filter"
                  />
                  <Hint text={t('selectors.selectorNameHint')} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('selectors.operator')}</label>
                  <select
                    className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
                    value={operator}
                    onChange={(e) => setOperator(e.target.value)}
                  >
                    {OPERATORS.map((op) => (
                      <option key={op} value={op}>
                        {t(`selectors.op${op.charAt(0).toUpperCase() + op.slice(1)}` as keyof typeof t)}
                      </option>
                    ))}
                  </select>
                  <Hint text={t('selectors.operatorHint')} />
                </div>
                <div className="flex flex-col justify-end">
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={isRequired}
                      onChange={(e) => setIsRequired(e.target.checked)}
                      className="rounded"
                    />
                    {t('selectors.required')}
                  </label>
                  <Hint text={t('selectors.requiredHint')} />
                </div>
              </div>
            </>
          )}

          {/* Step 2 — Data source (dropdown/multi_select only) */}
          {step === 2 && showStep2 && (
            <>
              <div className="flex gap-3">
                <label className={`flex items-center gap-2 px-3 py-2 border rounded cursor-pointer text-sm ${dataSourceMode === 'static' ? 'border-blue-500 bg-blue-50' : 'border-gray-200'}`}>
                  <input type="radio" checked={dataSourceMode === 'static'} onChange={() => setDataSourceMode('static')} />
                  <div>
                    <div>{t('selectors.staticValues')}</div>
                    <div className="text-xs text-gray-400">{t('selectors.staticValuesHint')}</div>
                  </div>
                </label>
                <label className={`flex items-center gap-2 px-3 py-2 border rounded cursor-pointer text-sm ${dataSourceMode === 'database' ? 'border-blue-500 bg-blue-50' : 'border-gray-200'}`}>
                  <input type="radio" checked={dataSourceMode === 'database'} onChange={() => setDataSourceMode('database')} />
                  <div>
                    <div>{t('selectors.fromDatabase')}</div>
                    <div className="text-xs text-gray-400">{t('selectors.fromDatabaseHint')}</div>
                  </div>
                </label>
              </div>

              {dataSourceMode === 'static' && (
                <div className="space-y-2">
                  {staticValues.map((sv, i) => (
                    <div key={i} className="flex gap-2">
                      <input
                        className="flex-1 border border-gray-300 rounded px-2 py-1 text-sm"
                        placeholder="value"
                        value={sv.value}
                        onChange={(e) => {
                          const copy = [...staticValues]
                          copy[i] = { ...copy[i], value: e.target.value }
                          setStaticValues(copy)
                        }}
                      />
                      <input
                        className="flex-1 border border-gray-300 rounded px-2 py-1 text-sm"
                        placeholder="label"
                        value={sv.label}
                        onChange={(e) => {
                          const copy = [...staticValues]
                          copy[i] = { ...copy[i], label: e.target.value }
                          setStaticValues(copy)
                        }}
                      />
                      <button
                        className="text-red-400 hover:text-red-600 text-sm px-1"
                        onClick={() => setStaticValues(staticValues.filter((_, j) => j !== i))}
                      >
                        &times;
                      </button>
                    </div>
                  ))}
                  <button
                    className="text-blue-600 text-sm hover:underline"
                    onClick={() => setStaticValues([...staticValues, { value: '', label: '' }])}
                  >
                    + {t('selectors.addValue')}
                  </button>
                </div>
              )}

              {dataSourceMode === 'database' && (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">{t('selectors.sourceTable')}</label>
                      <select
                        className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm"
                        value={sourceTable}
                        onChange={(e) => { setSourceTable(e.target.value); setSourceColumn('') }}
                        disabled={schemaLoading}
                      >
                        <option value="">--</option>
                        {schemaTables.map((tbl) => (
                          <option key={tbl.table_name} value={tbl.table_name}>{tbl.table_name}</option>
                        ))}
                      </select>
                      <Hint text={t('selectors.sourceTableHint')} />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">{t('selectors.sourceColumn')}</label>
                      <select
                        className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm"
                        value={sourceColumn}
                        onChange={(e) => setSourceColumn(e.target.value)}
                        disabled={!sourceTable}
                      >
                        <option value="">--</option>
                        {getTableColumns(sourceTable).map((col) => (
                          <option key={col} value={col}>{col}</option>
                        ))}
                      </select>
                      <Hint text={t('selectors.sourceColumnHint')} />
                    </div>
                  </div>

                  <div>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={showLabels}
                        onChange={(e) => setShowLabels(e.target.checked)}
                        className="rounded"
                      />
                      {t('selectors.showLabelsFrom')}
                    </label>
                    <Hint text={t('selectors.showLabelsHint')} />
                  </div>

                  {showLabels && (
                    <div className="grid grid-cols-3 gap-2 pl-6">
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">{t('selectors.labelTable')}</label>
                        <select
                          className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                          value={labelTable}
                          onChange={(e) => { setLabelTable(e.target.value); setLabelColumn(''); setLabelValueColumn('') }}
                          disabled={schemaLoading}
                        >
                          <option value="">--</option>
                          {schemaTables.map((tbl) => (
                            <option key={tbl.table_name} value={tbl.table_name}>{tbl.table_name}</option>
                          ))}
                        </select>
                        <Hint text={t('selectors.labelTableHint')} />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">{t('selectors.labelColumn')}</label>
                        <select
                          className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                          value={labelColumn}
                          onChange={(e) => setLabelColumn(e.target.value)}
                          disabled={!labelTable}
                        >
                          <option value="">--</option>
                          {getTableColumns(labelTable).map((col) => (
                            <option key={col} value={col}>{col}</option>
                          ))}
                        </select>
                        <Hint text={t('selectors.labelColumnHint')} />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">{t('selectors.labelValueColumn')}</label>
                        <select
                          className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                          value={labelValueColumn}
                          onChange={(e) => setLabelValueColumn(e.target.value)}
                          disabled={!labelTable}
                        >
                          <option value="">--</option>
                          {getTableColumns(labelTable).map((col) => (
                            <option key={col} value={col}>{col}</option>
                          ))}
                        </select>
                        <Hint text={t('selectors.labelValueColumnHint')} />
                      </div>
                    </div>
                  )}

                  {isEdit && selector?.id && (
                    <div>
                      <button
                        className="text-blue-600 text-sm hover:underline"
                        onClick={handlePreview}
                        disabled={previewLoading}
                      >
                        {previewLoading ? '...' : t('selectors.previewOptions')}
                      </button>
                      {previewOptions.length > 0 && (
                        <div className="mt-2 max-h-32 overflow-auto border rounded">
                          <table className="w-full text-xs">
                            <thead className="bg-gray-50">
                              <tr>
                                <th className="px-2 py-1 text-left">value</th>
                                <th className="px-2 py-1 text-left">label</th>
                              </tr>
                            </thead>
                            <tbody>
                              {previewOptions.slice(0, 20).map((o, i) => (
                                <tr key={i} className="border-t">
                                  <td className="px-2 py-0.5 font-mono">{String(o.value)}</td>
                                  <td className="px-2 py-0.5">{o.label}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {/* Step 3 (or Step 2 if no data source step) — Chart mappings */}
          {((showStep2 && step === 3) || (!showStep2 && step === 2)) && (
            <div className="space-y-3">
              <div>
                <p className="text-sm font-medium text-gray-700">{t('selectors.selectCharts')}</p>
                <Hint text={t('selectors.selectChartsHint')} />
              </div>
              {charts.map((dc) => {
                const mapping = mappings[dc.id] || { enabled: false, target_column: '', target_table: '', operator_override: '' }
                const tables = chartTables[dc.id] || []
                return (
                  <div key={dc.id} className={`border rounded-lg p-3 transition-colors ${mapping.enabled ? 'border-blue-300 bg-blue-50/30' : 'border-gray-200'}`}>
                    <label className="flex items-center gap-2 text-sm font-medium cursor-pointer">
                      <input
                        type="checkbox"
                        checked={mapping.enabled}
                        onChange={(e) => {
                          setMappings((prev) => ({
                            ...prev,
                            [dc.id]: { ...mapping, enabled: e.target.checked },
                          }))
                          if (e.target.checked) loadChartMeta(dc.id)
                        }}
                        className="rounded"
                      />
                      {dc.title_override || dc.chart_title || `Chart #${dc.chart_id}`}
                    </label>
                    {mapping.enabled && (
                      <div className="grid grid-cols-3 gap-2 mt-2 pl-6">
                        <div>
                          <label className="block text-xs text-gray-500 mb-1">{t('selectors.targetColumn')}</label>
                          {chartColumns[dc.id] ? (
                            <select
                              className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                              value={mapping.target_column}
                              onChange={(e) =>
                                setMappings((prev) => ({
                                  ...prev,
                                  [dc.id]: { ...mapping, target_column: e.target.value },
                                }))
                              }
                            >
                              <option value="">--</option>
                              {chartColumns[dc.id].map((col) => (
                                <option key={col} value={col}>{col}</option>
                              ))}
                            </select>
                          ) : (
                            <div className="text-xs text-gray-400 py-1">...</div>
                          )}
                          <Hint text={t('selectors.targetColumnHint')} />
                        </div>
                        <div>
                          <label className="block text-xs text-gray-500 mb-1">{t('selectors.targetTable')}</label>
                          {tables.length > 0 ? (
                            <select
                              className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                              value={mapping.target_table}
                              onChange={(e) =>
                                setMappings((prev) => ({
                                  ...prev,
                                  [dc.id]: { ...mapping, target_table: e.target.value },
                                }))
                              }
                            >
                              <option value="">--</option>
                              {tables.map((tbl) => (
                                <option key={tbl} value={tbl}>{tbl}</option>
                              ))}
                            </select>
                          ) : chartTables[dc.id] !== undefined ? (
                            <div className="text-xs text-gray-400 py-1">{t('selectors.noTablesInQuery')}</div>
                          ) : (
                            <div className="text-xs text-gray-400 py-1">...</div>
                          )}
                          <Hint text={t('selectors.targetTableHint')} />
                        </div>
                        <div>
                          <label className="block text-xs text-gray-500 mb-1">{t('selectors.operatorOverride')}</label>
                          <select
                            className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                            value={mapping.operator_override}
                            onChange={(e) =>
                              setMappings((prev) => ({
                                ...prev,
                                [dc.id]: { ...mapping, operator_override: e.target.value },
                              }))
                            }
                          >
                            <option value="">-- ({t(`selectors.op${operator.charAt(0).toUpperCase() + operator.slice(1)}` as keyof typeof t)})</option>
                            {OPERATORS.map((op) => (
                              <option key={op} value={op}>
                                {t(`selectors.op${op.charAt(0).toUpperCase() + op.slice(1)}` as keyof typeof t)}
                              </option>
                            ))}
                          </select>
                          <Hint text={t('selectors.operatorOverrideHint')} />
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t">
          <div>
            {step > 1 && (
              <button
                onClick={() => setStep(step - 1)}
                className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded hover:bg-gray-50"
              >
                {t('selectors.previous')}
              </button>
            )}
          </div>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded hover:bg-gray-50"
            >
              {t('common.cancel')}
            </button>
            {step < totalSteps ? (
              <button
                onClick={() => setStep(step + 1)}
                className="px-4 py-2 text-sm text-white bg-blue-600 rounded hover:bg-blue-700"
                disabled={!name || !label}
              >
                {t('selectors.next')}
              </button>
            ) : (
              <button
                onClick={handleFinish}
                className="px-4 py-2 text-sm text-white bg-blue-600 rounded hover:bg-blue-700"
                disabled={saving || !name || !label}
              >
                {saving ? t('common.saving') : t('selectors.finish')}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
