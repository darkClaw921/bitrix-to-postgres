import { useCallback, useEffect, useState } from 'react'
import {
  plansApi,
  type NumericFieldInfo,
  type PlanCreateRequest,
  type PlanDraft,
  type PlanManagerInfo,
  type PlanTableInfo,
} from '../../services/api'
import PlanDraftsTable, { defaultsForPeriodType } from './PlanDraftsTable'
import type { PlanPeriodType } from '../../services/api'

interface AIGeneratePlansModalProps {
  open: boolean
  onClose: () => void
  /** Called after drafts are saved via batchCreate so the caller can refetch. */
  onSuccess: () => void
  /** Optional prefetched managers list — used by PlanDraftsTable for name resolution. */
  managers?: PlanManagerInfo[]
}

function getErrorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'response' in error) {
    const axiosError = error as {
      response?: { status?: number; data?: { detail?: string } }
    }
    const status = axiosError.response?.status
    const detail = axiosError.response?.data?.detail
    if (status === 502 || status === 503) {
      return detail || 'AI-сервис временно недоступен. Попробуйте позже.'
    }
    if (detail) return detail
  }
  if (error instanceof Error) return error.message
  return 'Произошла неизвестная ошибка'
}

/**
 * Convert a `PlanDraft` into a `PlanCreateRequest` payload for
 * `plansApi.batchCreate`. Invalid (no plan_value) drafts are filtered
 * by the caller before this is called.
 */
interface BulkPeriodBarProps {
  onApply: (patch: {
    period_type: PlanPeriodType
    period_value: string | null
    date_from: string | null
    date_to: string | null
  }) => void
}

/**
 * Compact bar above drafts table: pick a period_type + value, click
 * "Применить ко всем" — pushes the patch into every row at once.
 */
function BulkPeriodBar({ onApply }: BulkPeriodBarProps) {
  const [type, setType] = useState<PlanPeriodType>('month')
  const today = new Date()
  const defaultMonth = `${today.getFullYear()}-${String(
    today.getMonth() + 1,
  ).padStart(2, '0')}`
  const [month, setMonth] = useState(defaultMonth)
  const [year, setYear] = useState(String(today.getFullYear()))
  const [quarter, setQuarter] = useState(
    String(Math.floor(today.getMonth() / 3) + 1),
  )
  const [dateFrom, setDateFrom] = useState(`${today.getFullYear()}-01-01`)
  const [dateTo, setDateTo] = useState(`${today.getFullYear()}-12-31`)

  const handleApply = () => {
    if (type === 'month') {
      onApply({
        period_type: 'month',
        period_value: month,
        date_from: null,
        date_to: null,
      })
    } else if (type === 'quarter') {
      onApply({
        period_type: 'quarter',
        period_value: `${year}-Q${quarter}`,
        date_from: null,
        date_to: null,
      })
    } else if (type === 'year') {
      onApply({
        period_type: 'year',
        period_value: year,
        date_from: null,
        date_to: null,
      })
    } else {
      onApply({
        period_type: 'custom',
        period_value: null,
        date_from: dateFrom || null,
        date_to: dateTo || null,
      })
    }
  }

  return (
    <div className="flex items-end gap-2 text-xs bg-gray-50 border border-gray-200 rounded p-2">
      <div>
        <label className="block text-gray-500 mb-0.5">Период всем</label>
        <select
          value={type}
          onChange={(e) => {
            const next = e.target.value as PlanPeriodType
            setType(next)
            // Reset to defaults via helper (keeps consistency with cell editor).
            const d = defaultsForPeriodType(next)
            if (next === 'month' && d.period_value) setMonth(d.period_value)
            if (next === 'quarter' && d.period_value) {
              const [y, q] = d.period_value.split('-Q')
              setYear(y)
              setQuarter(q)
            }
            if (next === 'year' && d.period_value) setYear(d.period_value)
            if (next === 'custom') {
              if (d.date_from) setDateFrom(d.date_from)
            }
          }}
          className="px-2 py-1 border border-gray-300 rounded"
        >
          <option value="month">Месяц</option>
          <option value="quarter">Квартал</option>
          <option value="year">Год</option>
          <option value="custom">Произвольный</option>
        </select>
      </div>
      {type === 'month' && (
        <input
          type="month"
          value={month}
          onChange={(e) => setMonth(e.target.value)}
          className="px-2 py-1 border border-gray-300 rounded"
        />
      )}
      {type === 'quarter' && (
        <>
          <input
            type="number"
            min="2000"
            max="2100"
            value={year}
            onChange={(e) => setYear(e.target.value)}
            className="w-20 px-2 py-1 border border-gray-300 rounded"
          />
          <select
            value={quarter}
            onChange={(e) => setQuarter(e.target.value)}
            className="px-2 py-1 border border-gray-300 rounded"
          >
            <option value="1">Q1</option>
            <option value="2">Q2</option>
            <option value="3">Q3</option>
            <option value="4">Q4</option>
          </select>
        </>
      )}
      {type === 'year' && (
        <input
          type="number"
          min="2000"
          max="2100"
          value={year}
          onChange={(e) => setYear(e.target.value)}
          className="w-24 px-2 py-1 border border-gray-300 rounded"
        />
      )}
      {type === 'custom' && (
        <>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="px-2 py-1 border border-gray-300 rounded"
          />
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="px-2 py-1 border border-gray-300 rounded"
          />
        </>
      )}
      <button
        type="button"
        onClick={handleApply}
        className="px-2 py-1 bg-primary-600 text-white rounded hover:bg-primary-700"
      >
        Применить ко всем
      </button>
    </div>
  )
}

function draftToCreateRequest(draft: PlanDraft): PlanCreateRequest {
  return {
    table_name: draft.table_name,
    field_name: draft.field_name,
    assigned_by_id: draft.assigned_by_id,
    period_type: draft.period_type,
    period_value: draft.period_value ?? null,
    date_from: draft.date_from ?? null,
    date_to: draft.date_to ?? null,
    plan_value:
      typeof draft.plan_value === 'string'
        ? Number(draft.plan_value)
        : (draft.plan_value as number),
    description: draft.description ?? null,
  }
}

export default function AIGeneratePlansModal({
  open,
  onClose,
  onSuccess,
  managers,
}: AIGeneratePlansModalProps) {
  // Stage: idle (editing prompt) → generating → preview → saving
  const [description, setDescription] = useState('')
  const [hintsOpen, setHintsOpen] = useState(false)
  const [tableName, setTableName] = useState('')
  const [fieldName, setFieldName] = useState('')
  const [tables, setTables] = useState<PlanTableInfo[]>([])
  const [fields, setFields] = useState<NumericFieldInfo[]>([])
  const [fieldsLoading, setFieldsLoading] = useState(false)

  const [drafts, setDrafts] = useState<PlanDraft[]>([])
  const [warnings, setWarnings] = useState<string[]>([])
  const [generating, setGenerating] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  // Reset state when modal opens/closes.
  useEffect(() => {
    if (!open) return
    setDescription('')
    setHintsOpen(false)
    setTableName('')
    setFieldName('')
    setFields([])
    setDrafts([])
    setWarnings([])
    setError(null)
    setSuccessMsg(null)
  }, [open])

  // Load tables once when hints panel is opened.
  useEffect(() => {
    if (!open || !hintsOpen || tables.length > 0) return
    plansApi
      .getTables()
      .then(setTables)
      .catch((err) =>
        setError(`Не удалось загрузить список таблиц: ${getErrorMessage(err)}`),
      )
  }, [open, hintsOpen, tables.length])

  // Load numeric fields when a table hint is picked.
  useEffect(() => {
    if (!tableName) {
      setFields([])
      setFieldName('')
      return
    }
    let cancelled = false
    setFieldsLoading(true)
    plansApi
      .getNumericFields(tableName)
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
  }, [tableName])

  const handleGenerate = useCallback(async () => {
    setError(null)
    setWarnings([])
    setDrafts([])
    setSuccessMsg(null)
    if (description.trim().length < 5) {
      setError('Описание должно содержать минимум 5 символов')
      return
    }
    setGenerating(true)
    try {
      const resp = await plansApi.aiGenerate({
        description: description.trim(),
        table_name: tableName || null,
        field_name: fieldName || null,
      })
      setDrafts(resp.plans ?? [])
      setWarnings(resp.warnings ?? [])
      if (!resp.plans || resp.plans.length === 0) {
        setError(
          'AI не смог сгенерировать ни одного плана. Уточните описание.',
        )
      }
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setGenerating(false)
    }
  }, [description, tableName, fieldName])

  const validDrafts = drafts.filter((d) => {
    const v = d.plan_value
    if (v === null || v === undefined || v === '') return false
    return !Number.isNaN(Number(v))
  })

  const handleSave = useCallback(async () => {
    setError(null)
    setSuccessMsg(null)
    if (validDrafts.length === 0) {
      setError('Нет валидных строк для сохранения (укажите суммы).')
      return
    }
    setSaving(true)
    try {
      const payload = {
        plans: validDrafts.map(draftToCreateRequest),
      }
      const created = await plansApi.batchCreate(payload)
      setSuccessMsg(`Создано планов: ${created.length}`)
      onSuccess()
      // Give the toast a moment to be visible before closing.
      setTimeout(() => {
        onClose()
      }, 700)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }, [validDrafts, onSuccess, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-5xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b px-6 py-4">
          <div>
            <h3 className="text-lg font-semibold">Сгенерировать планы через AI</h3>
            <p className="text-sm text-gray-500 mt-1">
              Опишите нужные планы человеческим языком — AI подготовит черновики, которые можно отредактировать перед сохранением.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
            aria-label="Закрыть"
            disabled={generating || saving}
          >
            ×
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
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
          {warnings.length > 0 && (
            <div className="p-3 bg-yellow-50 border border-yellow-200 rounded text-sm text-yellow-800">
              <div className="font-medium mb-1">Предупреждения AI:</div>
              <ul className="list-disc list-inside space-y-0.5">
                {warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Prompt */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Описание
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={5}
              placeholder="Например: план на всех менеджеров по opportunity на май 2026, 500к каждому"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              disabled={generating || saving}
            />
            <p className="text-xs text-gray-500 mt-1">
              Минимум 5 символов, максимум 4000.
            </p>
          </div>

          {/* Hints (collapsible) */}
          <div className="border border-gray-200 rounded">
            <button
              type="button"
              onClick={() => setHintsOpen((v) => !v)}
              className="w-full text-left px-3 py-2 text-sm text-gray-700 flex items-center justify-between hover:bg-gray-50"
            >
              <span>
                {hintsOpen ? '▼' : '▶'} Подсказки для AI (опционально)
              </span>
              {(tableName || fieldName) && (
                <span className="text-xs text-primary-600">
                  {tableName}
                  {fieldName ? `.${fieldName}` : ''}
                </span>
              )}
            </button>
            {hintsOpen && (
              <div className="border-t border-gray-200 px-3 py-3 grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">
                    Таблица
                  </label>
                  <select
                    value={tableName}
                    onChange={(e) => setTableName(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    disabled={generating || saving}
                  >
                    <option value="">— не указано —</option>
                    {tables.map((t) => (
                      <option key={t.name} value={t.name}>
                        {t.label ? `${t.label} (${t.name})` : t.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">
                    Поле
                  </label>
                  <select
                    value={fieldName}
                    onChange={(e) => setFieldName(e.target.value)}
                    disabled={!tableName || fieldsLoading || generating || saving}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm disabled:bg-gray-100"
                  >
                    <option value="">
                      {fieldsLoading
                        ? 'Загрузка…'
                        : tableName
                        ? '— не указано —'
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
          </div>

          {/* Generate button */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleGenerate}
              className="btn btn-primary disabled:opacity-50"
              disabled={
                generating ||
                saving ||
                description.trim().length < 5
              }
            >
              {generating ? 'Генерация… (до 5 мин)' : '✨ Сгенерировать'}
            </button>
            {generating && (
              <span className="text-sm text-gray-500">
                LLM анализирует описание и собирает данные о менеджерах…
              </span>
            )}
          </div>

          {/* Drafts preview */}
          {drafts.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="text-sm font-medium text-gray-700">
                  Черновики (редактируемые): {drafts.length} шт., валидных:{' '}
                  {validDrafts.length}
                </div>
                <BulkPeriodBar
                  onApply={(patch) =>
                    setDrafts((prev) => prev.map((d) => ({ ...d, ...patch })))
                  }
                />
              </div>
              <PlanDraftsTable
                drafts={drafts}
                onChange={setDrafts}
                managers={managers}
                readOnlyFields={['table_name', 'field_name']}
              />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="btn btn-secondary"
            disabled={generating || saving}
          >
            Отмена
          </button>
          <button
            type="button"
            onClick={handleSave}
            className="btn btn-primary disabled:opacity-50"
            disabled={saving || generating || validDrafts.length === 0}
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
