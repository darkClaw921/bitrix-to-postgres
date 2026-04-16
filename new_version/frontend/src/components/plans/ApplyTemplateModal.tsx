import { useCallback, useEffect, useState } from 'react'
import {
  plansApi,
  type NumericFieldInfo,
  type PlanDraft,
  type PlanManagerInfo,
  type PlanTableInfo,
  type PlanTemplate,
} from '../../services/api'
import PlanDraftsTable from './PlanDraftsTable'

interface ApplyTemplateModalProps {
  open: boolean
  onClose: () => void
  templateId: number | null
  onSuccess: () => void
  /** Optional list for PlanDraftsTable manager name resolution. */
  managers?: PlanManagerInfo[]
}

function getErrorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'response' in error) {
    const axiosError = error as { response?: { data?: { detail?: string } } }
    if (axiosError.response?.data?.detail) return axiosError.response.data.detail
  }
  if (error instanceof Error) return error.message
  return 'Произошла неизвестная ошибка'
}

export default function ApplyTemplateModal({
  open,
  onClose,
  templateId,
  onSuccess,
  managers,
}: ApplyTemplateModalProps) {
  const [template, setTemplate] = useState<PlanTemplate | null>(null)
  const [loadingTpl, setLoadingTpl] = useState(false)

  const [tables, setTables] = useState<PlanTableInfo[]>([])
  const [fields, setFields] = useState<NumericFieldInfo[]>([])
  const [fieldsLoading, setFieldsLoading] = useState(false)

  const [tableOverride, setTableOverride] = useState('')
  const [fieldOverride, setFieldOverride] = useState('')
  const [periodOverride, setPeriodOverride] = useState('')
  const [bulkValue, setBulkValue] = useState('')

  const [drafts, setDrafts] = useState<PlanDraft[]>([])
  const [expanding, setExpanding] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  // Reset and load template when opened.
  useEffect(() => {
    if (!open || !templateId) {
      setTemplate(null)
      setDrafts([])
      return
    }
    setError(null)
    setSuccessMsg(null)
    setDrafts([])
    setTableOverride('')
    setFieldOverride('')
    setPeriodOverride('')
    setBulkValue('')
    setLoadingTpl(true)
    plansApi
      .getTemplate(templateId)
      .then((tpl) => {
        setTemplate(tpl)
        if (tpl.default_plan_value !== null && tpl.default_plan_value !== undefined) {
          setBulkValue(String(tpl.default_plan_value))
        }
      })
      .catch((err) => setError(getErrorMessage(err)))
      .finally(() => setLoadingTpl(false))
  }, [open, templateId])

  // Load tables only when override is needed.
  const needsTargetOverride = !!template && !template.table_name
  useEffect(() => {
    if (!open || !needsTargetOverride || tables.length > 0) return
    plansApi
      .getTables()
      .then(setTables)
      .catch(() => setTables([]))
  }, [open, needsTargetOverride, tables.length])

  // Load numeric fields when table override changes.
  useEffect(() => {
    if (!tableOverride) {
      setFields([])
      setFieldOverride('')
      return
    }
    let cancelled = false
    setFieldsLoading(true)
    plansApi
      .getNumericFields(tableOverride)
      .then((list) => {
        if (!cancelled) setFields(list)
      })
      .catch(() => {
        if (!cancelled) setFields([])
      })
      .finally(() => {
        if (!cancelled) setFieldsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [tableOverride])

  const canExpand = !!template && (!needsTargetOverride || (tableOverride && fieldOverride))

  const handleExpand = useCallback(async () => {
    if (!template) return
    setError(null)
    setSuccessMsg(null)
    setExpanding(true)
    try {
      const overrides: Parameters<typeof plansApi.expandTemplate>[1] = {}
      if (tableOverride) overrides.table_name = tableOverride
      if (fieldOverride) overrides.field_name = fieldOverride
      if (periodOverride) overrides.period_value = periodOverride
      const list = await plansApi.expandTemplate(template.id, overrides)
      // Apply default bulk value if provided and drafts don't already have one.
      if (bulkValue && list.length > 0) {
        const numeric = Number(bulkValue)
        if (!Number.isNaN(numeric)) {
          list.forEach((d) => {
            if (d.plan_value === null || d.plan_value === undefined || d.plan_value === '') {
              d.plan_value = numeric
            }
          })
        }
      }
      setDrafts(list)
      if (list.length === 0) {
        setError(
          'Шаблон развернулся в пустой список (возможно, нет активных менеджеров для выбранного отдела).',
        )
      }
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setExpanding(false)
    }
  }, [template, tableOverride, fieldOverride, periodOverride, bulkValue])

  const applyBulkValue = useCallback(() => {
    const num = Number(bulkValue)
    if (Number.isNaN(num)) {
      setError('Укажите корректное числовое значение для массового заполнения')
      return
    }
    setError(null)
    setDrafts((prev) => prev.map((d) => ({ ...d, plan_value: num })))
  }, [bulkValue])

  const validDrafts = drafts.filter((d) => {
    const v = d.plan_value
    if (v === null || v === undefined || v === '') return false
    return !Number.isNaN(Number(v))
  })

  const handleSave = useCallback(async () => {
    if (!template) return
    setError(null)
    if (validDrafts.length === 0) {
      setError('Нет валидных строк для сохранения (укажите суммы).')
      return
    }
    setSaving(true)
    try {
      const payload = {
        template_id: template.id,
        table_name: tableOverride || null,
        field_name: fieldOverride || null,
        period_value_override: periodOverride || null,
        entries: validDrafts.map((d) => ({
          ...d,
          plan_value:
            typeof d.plan_value === 'string'
              ? Number(d.plan_value)
              : d.plan_value,
        })),
      }
      const created = await plansApi.applyTemplate(template.id, payload)
      setSuccessMsg(`Создано планов: ${created.length}`)
      onSuccess()
      setTimeout(() => {
        onClose()
      }, 700)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }, [template, tableOverride, fieldOverride, periodOverride, validDrafts, onSuccess, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[55] flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-5xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between border-b px-6 py-4">
          <div>
            <h3 className="text-lg font-semibold">
              Применить шаблон{template?.name ? `: ${template.name}` : ''}
            </h3>
            {template?.description && (
              <p className="text-sm text-gray-500 mt-1">{template.description}</p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
            aria-label="Закрыть"
            disabled={expanding || saving}
          >
            ×
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {loadingTpl && (
            <div className="py-6 text-center text-sm text-gray-500">
              Загрузка шаблона…
            </div>
          )}
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
              {error}
            </div>
          )}
          {successMsg && (
            <div className="p-3 bg-green-50 border border-green-200 rounded text-sm text-green-700">
              {successMsg}
            </div>
          )}

          {template && (
            <>
              {/* Target override */}
              {needsTargetOverride && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Таблица <span className="text-red-500">*</span>
                    </label>
                    <select
                      value={tableOverride}
                      onChange={(e) => setTableOverride(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    >
                      <option value="">— выберите таблицу —</option>
                      {tables.map((t) => (
                        <option key={t.name} value={t.name}>
                          {t.label ? `${t.label} (${t.name})` : t.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Поле <span className="text-red-500">*</span>
                    </label>
                    <select
                      value={fieldOverride}
                      onChange={(e) => setFieldOverride(e.target.value)}
                      disabled={!tableOverride || fieldsLoading}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg disabled:bg-gray-100"
                    >
                      <option value="">
                        {fieldsLoading
                          ? 'Загрузка…'
                          : tableOverride
                          ? '— выберите поле —'
                          : 'Сначала выберите таблицу'}
                      </option>
                      {fields.map((f) => (
                        <option key={f.name} value={f.name}>
                          {f.name} ({f.data_type})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              )}

              {/* Optional period override — useful for builtin 'current_month' etc. */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Переопределить период (необязательно)
                </label>
                <input
                  type="text"
                  value={periodOverride}
                  onChange={(e) => setPeriodOverride(e.target.value)}
                  placeholder={
                    template.period_mode === 'current_month'
                      ? '2026-04 — пусто для авто-расчёта'
                      : template.period_mode === 'current_quarter'
                      ? '2026-Q2 — пусто для авто-расчёта'
                      : template.period_mode === 'current_year'
                      ? '2026 — пусто для авто-расчёта'
                      : 'Период из шаблона'
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Оставьте пустым — backend сам вычислит период по правилам шаблона.
                </p>
              </div>

              {/* Bulk plan value */}
              <div className="grid grid-cols-[1fr_auto] gap-2 items-end">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Сумма по умолчанию (необязательно)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={bulkValue}
                    onChange={(e) => setBulkValue(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    placeholder="Например, 500000"
                  />
                </div>
                <button
                  type="button"
                  onClick={applyBulkValue}
                  className="btn btn-secondary"
                  disabled={drafts.length === 0 || !bulkValue}
                >
                  Заполнить всем
                </button>
              </div>

              {/* Expand */}
              <div>
                <button
                  type="button"
                  onClick={handleExpand}
                  className="btn btn-primary disabled:opacity-50"
                  disabled={!canExpand || expanding || saving}
                >
                  {expanding ? 'Подготовка…' : 'Подготовить превью'}
                </button>
              </div>

              {/* Drafts preview */}
              {drafts.length > 0 && (
                <div className="space-y-2">
                  <div className="text-sm font-medium text-gray-700">
                    Черновики: {drafts.length} шт., валидных: {validDrafts.length}
                  </div>
                  <PlanDraftsTable
                    drafts={drafts}
                    onChange={setDrafts}
                    managers={managers}
                    readOnlyFields={['table_name', 'field_name']}
                  />
                </div>
              )}
            </>
          )}
        </div>

        <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="btn btn-secondary"
            disabled={expanding || saving}
          >
            Отмена
          </button>
          <button
            type="button"
            onClick={handleSave}
            className="btn btn-primary disabled:opacity-50"
            disabled={saving || expanding || validDrafts.length === 0}
          >
            {saving
              ? 'Сохранение…'
              : validDrafts.length > 0
              ? `Сохранить все (${validDrafts.length})`
              : 'Сохранить все'}
          </button>
        </div>
      </div>
    </div>
  )
}
