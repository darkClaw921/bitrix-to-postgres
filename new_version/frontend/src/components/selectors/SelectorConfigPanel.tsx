import { useState, useEffect } from 'react'
import { useTranslation } from '../../i18n'
import { schemaApi } from '../../services/api'
import type { TableInfo, SelectorOption } from '../../services/api'
import { dashboardsApi } from '../../services/api'

const SELECTOR_TYPES = [
  { value: 'dropdown', defaultOp: 'equals' },
  { value: 'multi_select', defaultOp: 'in' },
  { value: 'date_range', defaultOp: 'between' },
  { value: 'single_date', defaultOp: 'equals' },
  { value: 'text', defaultOp: 'like' },
] as const

const OPERATORS = ['equals', 'in', 'between', 'like', 'gt', 'lt', 'gte', 'lte'] as const

interface StaticValue {
  value: string
  label: string
}

interface Props {
  dashboardId: number
  selectorType: string
  name: string
  label: string
  operator: string
  isRequired: boolean
  dataSourceMode: 'static' | 'database'
  staticValues: StaticValue[]
  sourceTable: string
  sourceColumn: string
  showLabels: boolean
  labelTable: string
  labelColumn: string
  labelValueColumn: string
  isEdit: boolean
  selectorId?: number
  onSelectorTypeChange: (v: string) => void
  onNameChange: (v: string) => void
  onLabelChange: (v: string) => void
  onOperatorChange: (v: string) => void
  onIsRequiredChange: (v: boolean) => void
  onDataSourceModeChange: (v: 'static' | 'database') => void
  onStaticValuesChange: (v: StaticValue[]) => void
  onSourceTableChange: (v: string) => void
  onSourceColumnChange: (v: string) => void
  onShowLabelsChange: (v: boolean) => void
  onLabelTableChange: (v: string) => void
  onLabelColumnChange: (v: string) => void
  onLabelValueColumnChange: (v: string) => void
}

function Hint({ text }: { text: string }) {
  return <p className="text-xs text-gray-400 mt-0.5">{text}</p>
}

export default function SelectorConfigPanel({
  dashboardId,
  selectorType,
  name,
  label,
  operator,
  isRequired,
  dataSourceMode,
  staticValues,
  sourceTable,
  sourceColumn,
  showLabels,
  labelTable,
  labelColumn,
  labelValueColumn,
  isEdit,
  selectorId,
  onSelectorTypeChange,
  onNameChange,
  onLabelChange,
  onOperatorChange,
  onIsRequiredChange,
  onDataSourceModeChange,
  onStaticValuesChange,
  onSourceTableChange,
  onSourceColumnChange,
  onShowLabelsChange,
  onLabelTableChange,
  onLabelColumnChange,
  onLabelValueColumnChange,
}: Props) {
  const { t } = useTranslation()
  const [schemaTables, setSchemaTables] = useState<TableInfo[]>([])
  const [schemaLoading, setSchemaLoading] = useState(false)
  const [previewOptions, setPreviewOptions] = useState<SelectorOption[]>([])
  const [previewLoading, setPreviewLoading] = useState(false)

  useEffect(() => {
    setSchemaLoading(true)
    schemaApi.tables()
      .then((res) => setSchemaTables(res.tables || []))
      .catch(() => setSchemaTables([]))
      .finally(() => setSchemaLoading(false))
  }, [])

  // Auto-set operator on type change
  useEffect(() => {
    if (!isEdit) {
      const typeInfo = SELECTOR_TYPES.find((st) => st.value === selectorType)
      if (typeInfo) onOperatorChange(typeInfo.defaultOp)
    }
  }, [selectorType, isEdit])

  const getTableColumns = (tableName: string): string[] => {
    const table = schemaTables.find((t) => t.table_name === tableName)
    return table ? table.columns.map((c) => c.name) : []
  }

  const handlePreview = async () => {
    if (!sourceTable || !sourceColumn || !selectorId) return
    setPreviewLoading(true)
    try {
      const opts = await dashboardsApi.getSelectorOptions(dashboardId, selectorId)
      setPreviewOptions(opts)
    } catch {
      setPreviewOptions([])
    }
    setPreviewLoading(false)
  }

  const showStep2 = selectorType === 'dropdown' || selectorType === 'multi_select'

  return (
    <div className="w-[280px] min-w-[280px] border-r border-gray-200 overflow-y-auto p-4 space-y-4 bg-gray-50">
      <h3 className="text-sm font-semibold text-gray-700">{t('selectors.configPanel')}</h3>

      {/* Selector Type */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">{t('selectors.selectorType')}</label>
        <div className="space-y-1">
          {SELECTOR_TYPES.map((st) => (
            <button
              key={st.value}
              onClick={() => onSelectorTypeChange(st.value)}
              className={`w-full p-2 border rounded text-left text-xs transition-colors ${
                selectorType === st.value
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <div className="font-medium">{t(`selectors.type${st.value.charAt(0).toUpperCase() + st.value.slice(1).replace(/_(\w)/g, (_, c: string) => c.toUpperCase())}` as keyof typeof t)}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Name & Label */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">{t('selectors.selectorLabel')}</label>
        <input
          className="w-full border border-gray-300 rounded px-2 py-1.5 text-xs"
          value={label}
          onChange={(e) => onLabelChange(e.target.value)}
          placeholder="e.g. Status"
        />
        <Hint text={t('selectors.selectorLabelHint')} />
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">{t('selectors.selectorName')}</label>
        <input
          className="w-full border border-gray-300 rounded px-2 py-1.5 text-xs font-mono"
          value={name}
          onChange={(e) => onNameChange(e.target.value.replace(/[^a-zA-Z0-9_]/g, ''))}
          placeholder="e.g. status_filter"
        />
        <Hint text={t('selectors.selectorNameHint')} />
      </div>

      {/* Operator */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">{t('selectors.operator')}</label>
        <select
          className="w-full border border-gray-300 rounded px-2 py-1.5 text-xs"
          value={operator}
          onChange={(e) => onOperatorChange(e.target.value)}
        >
          {OPERATORS.map((op) => (
            <option key={op} value={op}>
              {t(`selectors.op${op.charAt(0).toUpperCase() + op.slice(1)}` as keyof typeof t)}
            </option>
          ))}
        </select>
      </div>

      {/* Required */}
      <label className="flex items-center gap-2 text-xs">
        <input
          type="checkbox"
          checked={isRequired}
          onChange={(e) => onIsRequiredChange(e.target.checked)}
          className="rounded"
        />
        {t('selectors.required')}
      </label>

      {/* Data Source (only for dropdown / multi_select) */}
      {showStep2 && (
        <>
          <hr className="border-gray-200" />
          <h4 className="text-xs font-semibold text-gray-600">{t('selectors.step2Title')}</h4>

          <div className="flex gap-2">
            <button
              onClick={() => onDataSourceModeChange('static')}
              className={`flex-1 text-xs py-1.5 border rounded ${dataSourceMode === 'static' ? 'border-blue-500 bg-blue-50' : 'border-gray-200'}`}
            >
              {t('selectors.staticValues')}
            </button>
            <button
              onClick={() => onDataSourceModeChange('database')}
              className={`flex-1 text-xs py-1.5 border rounded ${dataSourceMode === 'database' ? 'border-blue-500 bg-blue-50' : 'border-gray-200'}`}
            >
              {t('selectors.fromDatabase')}
            </button>
          </div>

          {dataSourceMode === 'static' && (
            <div className="space-y-1.5">
              {staticValues.map((sv, i) => (
                <div key={i} className="flex gap-1">
                  <input
                    className="flex-1 border border-gray-300 rounded px-2 py-1 text-xs"
                    placeholder="value"
                    value={sv.value}
                    onChange={(e) => {
                      const copy = [...staticValues]
                      copy[i] = { ...copy[i], value: e.target.value }
                      onStaticValuesChange(copy)
                    }}
                  />
                  <input
                    className="flex-1 border border-gray-300 rounded px-2 py-1 text-xs"
                    placeholder="label"
                    value={sv.label}
                    onChange={(e) => {
                      const copy = [...staticValues]
                      copy[i] = { ...copy[i], label: e.target.value }
                      onStaticValuesChange(copy)
                    }}
                  />
                  <button
                    className="text-red-400 hover:text-red-600 text-xs px-1"
                    onClick={() => onStaticValuesChange(staticValues.filter((_, j) => j !== i))}
                  >
                    &times;
                  </button>
                </div>
              ))}
              <button
                className="text-blue-600 text-xs hover:underline"
                onClick={() => onStaticValuesChange([...staticValues, { value: '', label: '' }])}
              >
                + {t('selectors.addValue')}
              </button>
            </div>
          )}

          {dataSourceMode === 'database' && (
            <div className="space-y-2">
              <div>
                <label className="block text-xs text-gray-500 mb-1">{t('selectors.sourceTable')}</label>
                <select
                  className="w-full border border-gray-300 rounded px-2 py-1 text-xs"
                  value={sourceTable}
                  onChange={(e) => { onSourceTableChange(e.target.value); onSourceColumnChange('') }}
                  disabled={schemaLoading}
                >
                  <option value="">--</option>
                  {schemaTables.map((tbl) => (
                    <option key={tbl.table_name} value={tbl.table_name}>{tbl.table_name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">{t('selectors.sourceColumn')}</label>
                <select
                  className="w-full border border-gray-300 rounded px-2 py-1 text-xs"
                  value={sourceColumn}
                  onChange={(e) => onSourceColumnChange(e.target.value)}
                  disabled={!sourceTable}
                >
                  <option value="">--</option>
                  {getTableColumns(sourceTable).map((col) => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>
              </div>

              <label className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={showLabels}
                  onChange={(e) => onShowLabelsChange(e.target.checked)}
                  className="rounded"
                />
                {t('selectors.showLabelsFrom')}
              </label>

              {showLabels && (
                <div className="space-y-1.5 pl-4">
                  <div>
                    <label className="block text-xs text-gray-500 mb-0.5">{t('selectors.labelTable')}</label>
                    <select
                      className="w-full border border-gray-300 rounded px-2 py-1 text-xs"
                      value={labelTable}
                      onChange={(e) => { onLabelTableChange(e.target.value); onLabelColumnChange(''); onLabelValueColumnChange('') }}
                      disabled={schemaLoading}
                    >
                      <option value="">--</option>
                      {schemaTables.map((tbl) => (
                        <option key={tbl.table_name} value={tbl.table_name}>{tbl.table_name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-0.5">{t('selectors.labelColumn')}</label>
                    <select
                      className="w-full border border-gray-300 rounded px-2 py-1 text-xs"
                      value={labelColumn}
                      onChange={(e) => onLabelColumnChange(e.target.value)}
                      disabled={!labelTable}
                    >
                      <option value="">--</option>
                      {getTableColumns(labelTable).map((col) => (
                        <option key={col} value={col}>{col}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-0.5">{t('selectors.labelValueColumn')}</label>
                    <select
                      className="w-full border border-gray-300 rounded px-2 py-1 text-xs"
                      value={labelValueColumn}
                      onChange={(e) => onLabelValueColumnChange(e.target.value)}
                      disabled={!labelTable}
                    >
                      <option value="">--</option>
                      {getTableColumns(labelTable).map((col) => (
                        <option key={col} value={col}>{col}</option>
                      ))}
                    </select>
                  </div>
                </div>
              )}

              {isEdit && selectorId && (
                <div>
                  <button
                    className="text-blue-600 text-xs hover:underline"
                    onClick={handlePreview}
                    disabled={previewLoading}
                  >
                    {previewLoading ? '...' : t('selectors.previewOptions')}
                  </button>
                  {previewOptions.length > 0 && (
                    <div className="mt-1 max-h-24 overflow-auto border rounded text-xs">
                      {previewOptions.slice(0, 15).map((o, i) => (
                        <div key={i} className="px-2 py-0.5 border-b border-gray-100 last:border-b-0">
                          <span className="font-mono">{String(o.value)}</span>
                          <span className="text-gray-400 ml-1">{o.label}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
