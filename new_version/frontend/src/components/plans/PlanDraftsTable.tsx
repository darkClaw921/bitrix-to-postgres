import { useCallback, useMemo } from 'react'
import type {
  PlanDraft,
  PlanManagerInfo,
  PlanPeriodType,
} from '../../services/api'

/**
 * Read-only policy for cells. When a field name is listed here the cell
 * renders as plain text instead of an editable input.
 */
export type PlanDraftField =
  | 'table_name'
  | 'field_name'
  | 'period'
  | 'assigned_by'
  | 'plan_value'
  | 'description'

export interface PlanDraftsTableProps {
  drafts: PlanDraft[]
  onChange: (updated: PlanDraft[]) => void
  onRemove?: (index: number) => void
  /** Optional lookup for assigned_by_id -> readable name. */
  managers?: PlanManagerInfo[]
  /** If provided, these fields are rendered as read-only text. */
  readOnlyFields?: PlanDraftField[]
  /** Empty-state label, defaults to 'Нет данных'. */
  emptyLabel?: string
}

const MONTHS_RU = [
  'Январь',
  'Февраль',
  'Март',
  'Апрель',
  'Май',
  'Июнь',
  'Июль',
  'Август',
  'Сентябрь',
  'Октябрь',
  'Ноябрь',
  'Декабрь',
]

function formatPeriod(draft: PlanDraft): string {
  const { period_type, period_value, date_from, date_to } = draft
  if (period_type === 'custom' || (!period_value && (date_from || date_to))) {
    return `${date_from ?? '…'} — ${date_to ?? '…'}`
  }
  if (period_type === 'month' && period_value) {
    const [y, m] = period_value.split('-')
    const idx = parseInt(m, 10) - 1
    if (!Number.isNaN(idx) && idx >= 0 && idx < 12) {
      return `${MONTHS_RU[idx]} ${y}`
    }
    return period_value
  }
  if (period_type === 'quarter' && period_value) {
    return period_value.replace('-Q', ' — Q')
  }
  if (period_type === 'year' && period_value) return period_value
  return period_value ?? '—'
}

const PERIOD_TYPE_OPTIONS: { value: PlanPeriodType; label: string }[] = [
  { value: 'month', label: 'Месяц' },
  { value: 'quarter', label: 'Квартал' },
  { value: 'year', label: 'Год' },
  { value: 'custom', label: 'Произвольный' },
]

/** Build a fresh period patch when ``period_type`` changes. */
export function defaultsForPeriodType(
  next: PlanPeriodType,
): Pick<PlanDraft, 'period_type' | 'period_value' | 'date_from' | 'date_to'> {
  const today = new Date()
  const y = today.getFullYear()
  const m = String(today.getMonth() + 1).padStart(2, '0')
  if (next === 'month') {
    return {
      period_type: 'month',
      period_value: `${y}-${m}`,
      date_from: null,
      date_to: null,
    }
  }
  if (next === 'quarter') {
    const q = Math.floor(today.getMonth() / 3) + 1
    return {
      period_type: 'quarter',
      period_value: `${y}-Q${q}`,
      date_from: null,
      date_to: null,
    }
  }
  if (next === 'year') {
    return {
      period_type: 'year',
      period_value: `${y}`,
      date_from: null,
      date_to: null,
    }
  }
  return {
    period_type: 'custom',
    period_value: null,
    date_from: `${y}-${m}-01`,
    date_to: null,
  }
}

interface PeriodEditorProps {
  draft: PlanDraft
  onChange: (
    patch: Partial<
      Pick<PlanDraft, 'period_type' | 'period_value' | 'date_from' | 'date_to'>
    >,
  ) => void
}

function PeriodEditor({ draft, onChange }: PeriodEditorProps) {
  const { period_type, period_value, date_from, date_to } = draft
  const quarterYear = period_value?.split('-Q')[0] ?? ''
  const quarterN = period_value?.split('-Q')[1] ?? ''
  return (
    <div className="flex flex-col gap-1">
      <select
        value={period_type ?? 'month'}
        onChange={(e) =>
          onChange(defaultsForPeriodType(e.target.value as PlanPeriodType))
        }
        className="px-2 py-1 border border-gray-300 rounded text-xs focus:ring-1 focus:ring-primary-500 focus:border-primary-500"
      >
        {PERIOD_TYPE_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {period_type === 'month' && (
        <input
          type="month"
          value={period_value ?? ''}
          onChange={(e) =>
            onChange({ period_value: e.target.value || null })
          }
          className="px-2 py-1 border border-gray-300 rounded text-xs"
        />
      )}
      {period_type === 'quarter' && (
        <div className="flex gap-1">
          <input
            type="number"
            min="2000"
            max="2100"
            step="1"
            value={quarterYear}
            onChange={(e) => {
              const y = e.target.value
              const q = quarterN || '1'
              onChange({ period_value: y ? `${y}-Q${q}` : null })
            }}
            placeholder="YYYY"
            className="w-20 px-2 py-1 border border-gray-300 rounded text-xs"
          />
          <select
            value={quarterN || '1'}
            onChange={(e) => {
              const y = quarterYear || String(new Date().getFullYear())
              onChange({ period_value: `${y}-Q${e.target.value}` })
            }}
            className="px-2 py-1 border border-gray-300 rounded text-xs"
          >
            <option value="1">Q1</option>
            <option value="2">Q2</option>
            <option value="3">Q3</option>
            <option value="4">Q4</option>
          </select>
        </div>
      )}
      {period_type === 'year' && (
        <input
          type="number"
          min="2000"
          max="2100"
          step="1"
          value={period_value ?? ''}
          onChange={(e) =>
            onChange({ period_value: e.target.value || null })
          }
          placeholder="YYYY"
          className="w-24 px-2 py-1 border border-gray-300 rounded text-xs"
        />
      )}
      {period_type === 'custom' && (
        <div className="flex flex-col gap-1">
          <input
            type="date"
            value={date_from ?? ''}
            onChange={(e) =>
              onChange({ date_from: e.target.value || null })
            }
            className="px-2 py-1 border border-gray-300 rounded text-xs"
          />
          <input
            type="date"
            value={date_to ?? ''}
            onChange={(e) => onChange({ date_to: e.target.value || null })}
            className="px-2 py-1 border border-gray-300 rounded text-xs"
          />
        </div>
      )}
    </div>
  )
}

function managerLabel(
  draft: PlanDraft,
  managerMap: Map<string, string>,
): string {
  if (!draft.assigned_by_id) {
    return draft.assigned_by_name || 'Общий план'
  }
  const fromMap = managerMap.get(draft.assigned_by_id)
  if (fromMap) return fromMap
  if (draft.assigned_by_name) return draft.assigned_by_name
  return `id: ${draft.assigned_by_id}`
}

export default function PlanDraftsTable({
  drafts,
  onChange,
  onRemove,
  managers,
  readOnlyFields,
  emptyLabel = 'Нет данных',
}: PlanDraftsTableProps) {
  const readOnly = useMemo(
    () => new Set<PlanDraftField>(readOnlyFields ?? []),
    [readOnlyFields],
  )

  const managerMap = useMemo(() => {
    const map = new Map<string, string>()
    ;(managers ?? []).forEach((m) => {
      const label =
        `${m.name ?? ''} ${m.last_name ?? ''}`.trim() || m.bitrix_id
      map.set(m.bitrix_id, label)
    })
    return map
  }, [managers])

  const updateCell = useCallback(
    (index: number, patch: Partial<PlanDraft>) => {
      const next = drafts.map((d, i) => (i === index ? { ...d, ...patch } : d))
      onChange(next)
    },
    [drafts, onChange],
  )

  const handleRemove = useCallback(
    (index: number) => {
      if (onRemove) {
        onRemove(index)
        return
      }
      onChange(drafts.filter((_, i) => i !== index))
    },
    [drafts, onChange, onRemove],
  )

  if (drafts.length === 0) {
    return (
      <div className="py-6 text-center text-sm text-gray-500 border border-dashed border-gray-300 rounded">
        {emptyLabel}
      </div>
    )
  }

  return (
    <div className="overflow-x-auto border border-gray-200 rounded">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
              Менеджер
            </th>
            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
              Таблица
            </th>
            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
              Поле
            </th>
            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
              Период
            </th>
            <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">
              Сумма
            </th>
            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
              Описание
            </th>
            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
              ⚠
            </th>
            <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase w-10">
              {/* удалить */}
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {drafts.map((draft, index) => {
            const hasWarnings = draft.warnings && draft.warnings.length > 0
            const planValueStr =
              draft.plan_value === null || draft.plan_value === undefined
                ? ''
                : String(draft.plan_value)
            const planValueInvalid =
              planValueStr === '' || Number.isNaN(Number(planValueStr))
            const rowClass = planValueInvalid
              ? 'bg-red-50'
              : hasWarnings
              ? 'bg-yellow-50'
              : ''
            return (
              <tr key={index} className={rowClass}>
                {/* Manager */}
                <td className="px-3 py-2 text-sm text-gray-700 whitespace-nowrap">
                  {managerLabel(draft, managerMap)}
                </td>

                {/* Table */}
                <td className="px-3 py-2 text-sm text-gray-700">
                  {readOnly.has('table_name') ? (
                    <span>{draft.table_name || '—'}</span>
                  ) : (
                    <input
                      type="text"
                      value={draft.table_name}
                      onChange={(e) =>
                        updateCell(index, { table_name: e.target.value })
                      }
                      className="w-full px-2 py-1 border border-gray-300 rounded text-sm focus:ring-1 focus:ring-primary-500 focus:border-primary-500"
                    />
                  )}
                </td>

                {/* Field */}
                <td className="px-3 py-2 text-sm text-gray-700">
                  {readOnly.has('field_name') ? (
                    <span>{draft.field_name || '—'}</span>
                  ) : (
                    <input
                      type="text"
                      value={draft.field_name}
                      onChange={(e) =>
                        updateCell(index, { field_name: e.target.value })
                      }
                      className="w-full px-2 py-1 border border-gray-300 rounded text-sm focus:ring-1 focus:ring-primary-500 focus:border-primary-500"
                    />
                  )}
                </td>

                {/* Period — inline editor (type + value). */}
                <td className="px-3 py-2 text-sm text-gray-700 whitespace-nowrap">
                  {readOnly.has('period') ? (
                    <span>{formatPeriod(draft)}</span>
                  ) : (
                    <PeriodEditor
                      draft={draft}
                      onChange={(patch) => updateCell(index, patch)}
                    />
                  )}
                </td>

                {/* Plan value */}
                <td className="px-3 py-2 text-right">
                  {readOnly.has('plan_value') ? (
                    <span className="text-sm font-medium">
                      {planValueStr || '—'}
                    </span>
                  ) : (
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={planValueStr}
                      onChange={(e) =>
                        updateCell(index, {
                          plan_value:
                            e.target.value === '' ? null : e.target.value,
                        })
                      }
                      className={`w-32 px-2 py-1 border rounded text-sm text-right focus:ring-1 ${
                        planValueInvalid
                          ? 'border-red-300 focus:ring-red-500 focus:border-red-500'
                          : 'border-gray-300 focus:ring-primary-500 focus:border-primary-500'
                      }`}
                    />
                  )}
                </td>

                {/* Description */}
                <td className="px-3 py-2 text-sm text-gray-700">
                  {readOnly.has('description') ? (
                    <span>{draft.description ?? ''}</span>
                  ) : (
                    <input
                      type="text"
                      value={draft.description ?? ''}
                      onChange={(e) =>
                        updateCell(index, {
                          description: e.target.value || null,
                        })
                      }
                      placeholder="—"
                      className="w-full px-2 py-1 border border-gray-300 rounded text-sm focus:ring-1 focus:ring-primary-500 focus:border-primary-500"
                    />
                  )}
                </td>

                {/* Warnings */}
                <td className="px-3 py-2 text-sm">
                  {hasWarnings ? (
                    <span
                      title={draft.warnings.join('\n')}
                      className="inline-block cursor-help text-yellow-600"
                      aria-label="Предупреждения"
                    >
                      ⚠
                    </span>
                  ) : null}
                </td>

                {/* Remove */}
                <td className="px-3 py-2 text-right">
                  <button
                    type="button"
                    onClick={() => handleRemove(index)}
                    className="text-red-500 hover:text-red-700"
                    aria-label="Удалить строку"
                    title="Удалить"
                  >
                    ✕
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
