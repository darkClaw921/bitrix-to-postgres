import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  departmentsApi,
  plansApi,
  type DepartmentTreeNode,
  type NumericFieldInfo,
  type Plan,
  type PlanCreateRequest,
  type PlanManagerInfo,
  type PlanPeriodType,
  type PlanTableInfo,
} from '../../services/api'

/**
 * Assignment mode — drives how a single form submission fans out into one or
 * many `POST /plans` (or `POST /plans/batch`) calls.
 *
 * - `single` — old behaviour, pick one manager (or null for "all"). Used for
 *   editing too, since backend only allows one `assigned_by_id` per row.
 * - `multi` — pick several managers, save as N plans via batch.
 * - `department` — pick a department + "include sub-departments" → resolve to
 *   managers via `departmentsApi.getManagers`, then batch-create.
 * - `global` — single row with `assigned_by_id=null` (company-wide plan).
 */
export type PlanFormAssignMode = 'single' | 'multi' | 'department' | 'global'

interface BitrixUser {
  bitrix_id: string
  name: string
  last_name: string
}

interface PlanFormModalProps {
  mode: 'create' | 'edit'
  plan: Plan | null
  tables: PlanTableInfo[]
  users: BitrixUser[]
  usersLoading: boolean
  onClose: () => void
  onSaved: () => void
}

type PeriodMode = 'fixed' | 'custom'

interface PlanFormState {
  table_name: string
  field_name: string
  assigned_by_id: string // '' means "all"
  period_mode: PeriodMode
  period_type: 'month' | 'quarter' | 'year'
  period_value: string
  date_from: string
  date_to: string
  plan_value: string
  description: string
}

function emptyFormState(): PlanFormState {
  const now = new Date()
  const month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  return {
    table_name: '',
    field_name: '',
    assigned_by_id: '',
    period_mode: 'fixed',
    period_type: 'month',
    period_value: month,
    date_from: '',
    date_to: '',
    plan_value: '',
    description: '',
  }
}

function planToFormState(plan: Plan): PlanFormState {
  const base = emptyFormState()
  return {
    ...base,
    table_name: plan.table_name,
    field_name: plan.field_name,
    assigned_by_id: plan.assigned_by_id ?? '',
    period_mode: plan.period_type === 'custom' ? 'custom' : 'fixed',
    period_type:
      plan.period_type === 'quarter' || plan.period_type === 'year'
        ? plan.period_type
        : 'month',
    period_value: plan.period_value ?? '',
    date_from: plan.date_from ?? '',
    date_to: plan.date_to ?? '',
    plan_value: String(plan.plan_value ?? ''),
    description: plan.description ?? '',
  }
}

function todayYear(): number {
  return new Date().getFullYear()
}

function getErrorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'response' in error) {
    const axiosError = error as { response?: { data?: { detail?: string } } }
    if (axiosError.response?.data?.detail) return axiosError.response.data.detail
  }
  if (error instanceof Error) return error.message
  return 'Произошла неизвестная ошибка'
}

/** Flatten department tree into flat option list with indent prefixes. */
function flattenDepartments(
  tree: DepartmentTreeNode[],
  depth = 0,
): Array<{ id: string; label: string }> {
  const out: Array<{ id: string; label: string }> = []
  const prefix = depth > 0 ? '\u00A0\u00A0'.repeat(depth) + '└ ' : ''
  tree.forEach((n) => {
    out.push({
      id: n.id,
      label: `${prefix}${n.name ?? `id:${n.id}`}`,
    })
    if (n.children && n.children.length > 0) {
      out.push(...flattenDepartments(n.children, depth + 1))
    }
  })
  return out
}

export default function PlanFormModal({
  mode,
  plan,
  tables,
  users,
  usersLoading,
  onClose,
  onSaved,
}: PlanFormModalProps) {
  const isEdit = mode === 'edit'

  // Assignment mode (only create flow — edit is always "single" and hidden).
  const [assignMode, setAssignMode] = useState<PlanFormAssignMode>(() => {
    if (!isEdit) return 'single'
    if (plan && plan.assigned_by_id === null) return 'global'
    return 'single'
  })

  const [form, setForm] = useState<PlanFormState>(() =>
    plan ? planToFormState(plan) : emptyFormState(),
  )

  // Multi-select: bitrix_ids of selected managers
  const [multiIds, setMultiIds] = useState<string[]>([])

  // Department mode state
  const [tree, setTree] = useState<DepartmentTreeNode[]>([])
  const [deptId, setDeptId] = useState<string>('')
  const [recursive, setRecursive] = useState(true)
  const [deptManagers, setDeptManagers] = useState<PlanManagerInfo[]>([])
  const [deptPreviewLoading, setDeptPreviewLoading] = useState(false)

  const [numericFields, setNumericFields] = useState<NumericFieldInfo[]>([])
  const [fieldsLoading, setFieldsLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const deptOptions = useMemo(() => flattenDepartments(tree), [tree])

  // Load numeric fields whenever table_name changes
  useEffect(() => {
    if (!form.table_name) {
      setNumericFields([])
      return
    }
    let cancelled = false
    setFieldsLoading(true)
    plansApi
      .getNumericFields(form.table_name)
      .then((fields) => {
        if (!cancelled) setNumericFields(fields)
      })
      .catch((err) => {
        if (!cancelled) {
          setNumericFields([])
          setError(getErrorMessage(err))
        }
      })
      .finally(() => {
        if (!cancelled) setFieldsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [form.table_name])

  // Load department tree on mount for department mode.
  useEffect(() => {
    if (isEdit) return
    departmentsApi
      .getTree()
      .then((resp) => setTree(resp.tree))
      .catch(() => setTree([]))
  }, [isEdit])

  // Preview managers for chosen department.
  useEffect(() => {
    if (assignMode !== 'department' || !deptId) {
      setDeptManagers([])
      return
    }
    let cancelled = false
    setDeptPreviewLoading(true)
    departmentsApi
      .getManagers(deptId, { recursive, active_only: true })
      .then((resp) => {
        if (!cancelled) setDeptManagers(resp.managers)
      })
      .catch(() => {
        if (!cancelled) setDeptManagers([])
      })
      .finally(() => {
        if (!cancelled) setDeptPreviewLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [assignMode, deptId, recursive])

  const updateField = useCallback(
    <K extends keyof PlanFormState>(key: K, value: PlanFormState[K]) => {
      setForm((prev) => ({ ...prev, [key]: value }))
    },
    [],
  )

  // Reset assignment-related state when switching modes.
  const switchAssignMode = (next: PlanFormAssignMode) => {
    setAssignMode(next)
    setError(null)
    if (next !== 'single') updateField('assigned_by_id', '')
    if (next !== 'multi') setMultiIds([])
    if (next !== 'department') {
      setDeptId('')
      setDeptManagers([])
    }
  }

  const buildBasePayload = (): Omit<PlanCreateRequest, 'assigned_by_id'> => {
    return form.period_mode === 'fixed'
      ? {
          table_name: form.table_name,
          field_name: form.field_name,
          period_type: form.period_type,
          period_value: form.period_value,
          date_from: null,
          date_to: null,
          plan_value: Number(form.plan_value),
          description: form.description || null,
        }
      : {
          table_name: form.table_name,
          field_name: form.field_name,
          period_type: 'custom' as PlanPeriodType,
          period_value: null,
          date_from: form.date_from,
          date_to: form.date_to,
          plan_value: Number(form.plan_value),
          description: form.description || null,
        }
  }

  const validateCommonFields = (): string | null => {
    const planValueNum = Number(form.plan_value)
    if (!form.plan_value || Number.isNaN(planValueNum)) {
      return 'Укажите корректное числовое значение плана'
    }
    if (planValueNum < 0) {
      return 'Значение плана не может быть отрицательным'
    }
    if (!form.table_name) return 'Выберите таблицу'
    if (!form.field_name) return 'Выберите числовое поле'
    if (form.period_mode === 'fixed' && !form.period_value) {
      return 'Укажите значение периода'
    }
    if (form.period_mode === 'custom' && (!form.date_from || !form.date_to)) {
      return 'Укажите даты начала и окончания периода'
    }
    return null
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    const common = validateCommonFields()
    if (common) {
      setError(common)
      return
    }

    const base = buildBasePayload()

    setSubmitting(true)
    try {
      if (isEdit && plan) {
        // Edit flow is always a single update — no assignMode branching.
        await plansApi.update(plan.id, {
          ...base,
          assigned_by_id: form.assigned_by_id || null,
        })
      } else {
        // Create flow branches by assignMode.
        if (assignMode === 'single') {
          await plansApi.create({
            ...base,
            assigned_by_id: form.assigned_by_id || null,
          })
        } else if (assignMode === 'global') {
          await plansApi.create({ ...base, assigned_by_id: null })
        } else if (assignMode === 'multi') {
          if (multiIds.length === 0) {
            setError('Выберите хотя бы одного менеджера')
            return
          }
          await plansApi.batchCreate({
            plans: multiIds.map((id) => ({ ...base, assigned_by_id: id })),
          })
        } else if (assignMode === 'department') {
          if (!deptId) {
            setError('Выберите отдел')
            return
          }
          if (deptManagers.length === 0) {
            setError('В выбранном отделе нет активных менеджеров')
            return
          }
          await plansApi.batchCreate({
            plans: deptManagers.map((m) => ({
              ...base,
              assigned_by_id: m.bitrix_id,
            })),
          })
        }
      }
      onSaved()
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  const periodInputType =
    form.period_type === 'month'
      ? 'month'
      : form.period_type === 'year'
      ? 'number'
      : 'text'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h3 className="text-lg font-semibold">
            {isEdit ? 'Редактировать план' : 'Добавить план'}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
            aria-label="Закрыть"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-4">
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Assignment mode tabs (create only) */}
          {!isEdit && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Назначение
              </label>
              <div className="grid grid-cols-4 gap-1 bg-gray-100 rounded-lg p-1">
                {(
                  [
                    ['single', 'Один менеджер'],
                    ['multi', 'Несколько'],
                    ['department', 'Отдел'],
                    ['global', 'Общий'],
                  ] as Array<[PlanFormAssignMode, string]>
                ).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => switchAssignMode(value)}
                    className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                      assignMode === value
                        ? 'bg-white text-primary-700 shadow-sm'
                        : 'text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Table */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Таблица
            </label>
            <select
              value={form.table_name}
              onChange={(e) => {
                updateField('table_name', e.target.value)
                updateField('field_name', '')
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 disabled:bg-gray-100"
            >
              <option value="">— выберите таблицу —</option>
              {tables.map((t) => (
                <option key={t.name} value={t.name}>
                  {t.label ? `${t.label} (${t.name})` : t.name}
                </option>
              ))}
            </select>
          </div>

          {/* Field */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Поле (числовое)
            </label>
            <select
              value={form.field_name}
              onChange={(e) => updateField('field_name', e.target.value)}
              disabled={!form.table_name || fieldsLoading}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 disabled:bg-gray-100"
            >
              <option value="">
                {fieldsLoading
                  ? 'Загрузка полей…'
                  : form.table_name
                  ? '— выберите поле —'
                  : 'Сначала выберите таблицу'}
              </option>
              {numericFields.map((f) => (
                <option key={f.name} value={f.name}>
                  {f.name} ({f.data_type})
                </option>
              ))}
            </select>
          </div>

          {/* Assignment details — depends on mode */}
          {(isEdit || assignMode === 'single') && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Менеджер
              </label>
              <select
                value={form.assigned_by_id}
                onChange={(e) => updateField('assigned_by_id', e.target.value)}
                disabled={usersLoading}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 disabled:bg-gray-100"
              >
                <option value="">
                  {usersLoading
                    ? 'Загрузка пользователей…'
                    : 'Общий план (все менеджеры)'}
                </option>
                {users.map((u) => {
                  const label =
                    `${u.name ?? ''} ${u.last_name ?? ''}`.trim() ||
                    u.bitrix_id
                  return (
                    <option key={u.bitrix_id} value={u.bitrix_id}>
                      {label} (id: {u.bitrix_id})
                    </option>
                  )
                })}
              </select>
            </div>
          )}

          {!isEdit && assignMode === 'multi' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Менеджеры ({multiIds.length} выбрано)
              </label>
              <select
                multiple
                value={multiIds}
                onChange={(e) => {
                  const ids = Array.from(e.target.selectedOptions).map(
                    (o) => o.value,
                  )
                  setMultiIds(ids)
                }}
                disabled={usersLoading}
                size={Math.min(10, Math.max(4, users.length))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 disabled:bg-gray-100"
              >
                {users.map((u) => {
                  const label =
                    `${u.name ?? ''} ${u.last_name ?? ''}`.trim() ||
                    u.bitrix_id
                  return (
                    <option key={u.bitrix_id} value={u.bitrix_id}>
                      {label} (id: {u.bitrix_id})
                    </option>
                  )
                })}
              </select>
              <p className="text-xs text-gray-500 mt-1">
                Ctrl/Cmd + клик для выбора нескольких. Будет создано{' '}
                {multiIds.length} планов.
              </p>
            </div>
          )}

          {!isEdit && assignMode === 'department' && (
            <div className="space-y-2">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Отдел
                </label>
                <select
                  value={deptId}
                  onChange={(e) => setDeptId(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                >
                  <option value="">— выберите отдел —</option>
                  {deptOptions.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.label}
                    </option>
                  ))}
                </select>
              </div>
              <label className="inline-flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={recursive}
                  onChange={(e) => setRecursive(e.target.checked)}
                />
                Включая подотделы
              </label>
              {deptId && (
                <div className="text-xs text-gray-600 bg-gray-50 border border-gray-200 rounded p-2">
                  {deptPreviewLoading
                    ? 'Загрузка менеджеров отдела…'
                    : deptManagers.length === 0
                    ? 'В отделе нет активных менеджеров.'
                    : `Будет создано ${deptManagers.length} планов (по одному на менеджера).`}
                  {deptManagers.length > 0 && (
                    <ul className="mt-1 max-h-28 overflow-y-auto list-disc list-inside">
                      {deptManagers.slice(0, 10).map((m) => {
                        const name =
                          `${m.name ?? ''} ${m.last_name ?? ''}`.trim() ||
                          m.bitrix_id
                        return <li key={m.bitrix_id}>{name}</li>
                      })}
                      {deptManagers.length > 10 && (
                        <li>…и ещё {deptManagers.length - 10}</li>
                      )}
                    </ul>
                  )}
                </div>
              )}
            </div>
          )}

          {!isEdit && assignMode === 'global' && (
            <div className="p-3 bg-blue-50 border border-blue-200 rounded text-sm text-blue-700">
              Создастся один общий план без привязки к менеджеру.
            </div>
          )}

          {/* Period mode */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Период
            </label>
            <div className="flex items-center gap-4 mb-3">
              <label className="inline-flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  name="period_mode"
                  value="fixed"
                  checked={form.period_mode === 'fixed'}
                  onChange={() => updateField('period_mode', 'fixed')}
                />
                Фиксированный
              </label>
              <label className="inline-flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  name="period_mode"
                  value="custom"
                  checked={form.period_mode === 'custom'}
                  onChange={() => updateField('period_mode', 'custom')}
                />
                Произвольный
              </label>
            </div>

            {form.period_mode === 'fixed' ? (
              <div className="grid grid-cols-2 gap-3">
                <select
                  value={form.period_type}
                  onChange={(e) => {
                    const pt = e.target.value as 'month' | 'quarter' | 'year'
                    updateField('period_type', pt)
                    const y = todayYear()
                    const m = String(new Date().getMonth() + 1).padStart(2, '0')
                    updateField(
                      'period_value',
                      pt === 'month'
                        ? `${y}-${m}`
                        : pt === 'quarter'
                        ? `${y}-Q1`
                        : `${y}`,
                    )
                  }}
                  className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 disabled:bg-gray-100"
                >
                  <option value="month">Месяц</option>
                  <option value="quarter">Квартал</option>
                  <option value="year">Год</option>
                </select>

                {form.period_type === 'quarter' ? (
                  <select
                    value={form.period_value}
                    onChange={(e) => updateField('period_value', e.target.value)}
                    className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 disabled:bg-gray-100"
                  >
                    {[todayYear() - 1, todayYear(), todayYear() + 1].flatMap((y) =>
                      ['Q1', 'Q2', 'Q3', 'Q4'].map((q) => (
                        <option key={`${y}-${q}`} value={`${y}-${q}`}>
                          {y} — {q}
                        </option>
                      )),
                    )}
                  </select>
                ) : (
                  <input
                    type={periodInputType}
                    value={form.period_value}
                    onChange={(e) => updateField('period_value', e.target.value)}
                    placeholder={
                      form.period_type === 'month' ? '2026-04' : '2026'
                    }
                    className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 disabled:bg-gray-100"
                  />
                )}
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">С</label>
                  <input
                    type="date"
                    value={form.date_from}
                    onChange={(e) => updateField('date_from', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 disabled:bg-gray-100"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">По</label>
                  <input
                    type="date"
                    value={form.date_to}
                    onChange={(e) => updateField('date_to', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 disabled:bg-gray-100"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Plan value */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Плановое значение
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={form.plan_value}
              onChange={(e) => updateField('plan_value', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              required
            />
            {!isEdit && (assignMode === 'multi' || assignMode === 'department') && (
              <p className="text-xs text-gray-500 mt-1">
                Это значение будет использовано для КАЖДОГО из{' '}
                {assignMode === 'multi' ? multiIds.length : deptManagers.length}{' '}
                создаваемых планов.
              </p>
            )}
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Описание
            </label>
            <textarea
              value={form.description}
              onChange={(e) => updateField('description', e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder="Необязательно"
            />
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t">
            <button
              type="button"
              onClick={onClose}
              className="btn btn-secondary"
              disabled={submitting}
            >
              Отмена
            </button>
            <button
              type="submit"
              className="btn btn-primary disabled:opacity-50"
              disabled={submitting}
            >
              {submitting
                ? 'Сохранение…'
                : isEdit
                ? 'Сохранить'
                : 'Создать'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export type { BitrixUser }
