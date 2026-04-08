import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  chartsApi,
  plansApi,
  type NumericFieldInfo,
  type Plan,
  type PlanCreateRequest,
  type PlanPeriodType,
  type PlanTableInfo,
  type PlanVsActual,
} from '../services/api'
import AISubTabs from '../components/ai/AISubTabs'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface BitrixUser {
  bitrix_id: string
  name: string
  last_name: string
}

function getErrorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'response' in error) {
    const axiosError = error as { response?: { data?: { detail?: string } } }
    if (axiosError.response?.data?.detail) return axiosError.response.data.detail
  }
  if (error instanceof Error) return error.message
  return 'Произошла неизвестная ошибка'
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

function formatPeriod(plan: Plan): string {
  const { period_type: pt, period_value: pv, date_from, date_to } = plan
  if (pt === 'custom' || (!pv && (date_from || date_to))) {
    return `${date_from ?? '…'} — ${date_to ?? '…'}`
  }
  if (pt === 'month' && pv) {
    const [y, m] = pv.split('-')
    const idx = parseInt(m, 10) - 1
    if (!Number.isNaN(idx) && idx >= 0 && idx < 12) {
      return `${MONTHS_RU[idx]} ${y}`
    }
    return pv
  }
  if (pt === 'quarter' && pv) return pv.replace('-Q', ' — Q') // 2026-Q2 -> 2026 — Q2
  if (pt === 'year' && pv) return pv
  return pv ?? '—'
}

function formatNumber(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const num = typeof value === 'number' ? value : Number(value)
  if (Number.isNaN(num)) return String(value)
  return num.toLocaleString('ru-RU', { maximumFractionDigits: 2 })
}

function formatVariance(vs: PlanVsActual | undefined): string {
  if (!vs) return '—'
  const variance = formatNumber(vs.variance)
  if (vs.variance_pct === null || vs.variance_pct === undefined) return variance
  const sign = vs.variance_pct >= 0 ? '+' : ''
  return `${variance} (${sign}${vs.variance_pct.toFixed(1)}%)`
}

function todayYear(): number {
  return new Date().getFullYear()
}

// ---------------------------------------------------------------------------
// Plan Form Modal
// ---------------------------------------------------------------------------

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

interface PlanFormModalProps {
  mode: 'create' | 'edit'
  plan: Plan | null
  tables: PlanTableInfo[]
  users: BitrixUser[]
  usersLoading: boolean
  onClose: () => void
  onSaved: () => void
}

function PlanFormModal({
  mode,
  plan,
  tables,
  users,
  usersLoading,
  onClose,
  onSaved,
}: PlanFormModalProps) {
  const [form, setForm] = useState<PlanFormState>(() =>
    plan ? planToFormState(plan) : emptyFormState(),
  )
  const [numericFields, setNumericFields] = useState<NumericFieldInfo[]>([])
  const [fieldsLoading, setFieldsLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isEdit = mode === 'edit'

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

  const updateField = useCallback(<K extends keyof PlanFormState>(
    key: K,
    value: PlanFormState[K],
  ) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    // Client-side validation
    const planValueNum = Number(form.plan_value)
    if (!form.plan_value || Number.isNaN(planValueNum)) {
      setError('Укажите корректное числовое значение плана')
      return
    }
    if (planValueNum < 0) {
      setError('Значение плана не может быть отрицательным')
      return
    }

    if (!form.table_name) {
      setError('Выберите таблицу')
      return
    }
    if (!form.field_name) {
      setError('Выберите числовое поле')
      return
    }
    if (form.period_mode === 'fixed' && !form.period_value) {
      setError('Укажите значение периода')
      return
    }
    if (form.period_mode === 'custom' && (!form.date_from || !form.date_to)) {
      setError('Укажите даты начала и окончания периода')
      return
    }

    // Build the full payload — same shape for create and update. On edit
    // we send every field so the backend can rebuild the logical key and
    // re-run validations (dup check, numeric column, period mode).
    const payload: PlanCreateRequest =
      form.period_mode === 'fixed'
        ? {
            table_name: form.table_name,
            field_name: form.field_name,
            assigned_by_id: form.assigned_by_id || null,
            period_type: form.period_type,
            period_value: form.period_value,
            date_from: null,
            date_to: null,
            plan_value: planValueNum,
            description: form.description || null,
          }
        : {
            table_name: form.table_name,
            field_name: form.field_name,
            assigned_by_id: form.assigned_by_id || null,
            period_type: 'custom' as PlanPeriodType,
            period_value: null,
            date_from: form.date_from,
            date_to: form.date_to,
            plan_value: planValueNum,
            description: form.description || null,
          }

    setSubmitting(true)
    try {
      if (isEdit && plan) {
        await plansApi.update(plan.id, payload)
      } else {
        await plansApi.create(payload)
      }
      onSaved()
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  // For fixed-period input, the HTML input type depends on period_type
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

          {/* Manager */}
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
                {usersLoading ? 'Загрузка пользователей…' : 'Общий план (все менеджеры)'}
              </option>
              {users.map((u) => {
                const label = `${u.name ?? ''} ${u.last_name ?? ''}`.trim() || u.bitrix_id
                return (
                  <option key={u.bitrix_id} value={u.bitrix_id}>
                    {label} (id: {u.bitrix_id})
                  </option>
                )
              })}
            </select>
          </div>

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
                    // Reset period_value to a sensible default
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
              {submitting ? 'Сохранение…' : isEdit ? 'Сохранить' : 'Создать'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// PlansPage
// ---------------------------------------------------------------------------

export default function PlansPage() {
  const [plans, setPlans] = useState<Plan[]>([])
  const [vsActualMap, setVsActualMap] = useState<Record<number, PlanVsActual>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [tables, setTables] = useState<PlanTableInfo[]>([])
  const [users, setUsers] = useState<BitrixUser[]>([])
  const [usersLoading, setUsersLoading] = useState(false)

  const [modalOpen, setModalOpen] = useState(false)
  const [editingPlan, setEditingPlan] = useState<Plan | null>(null)

  // --- Load plans + facts
  const loadPlans = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const list = await plansApi.list()
      setPlans(list)
      // Batch-load facts
      const results = await Promise.allSettled(
        list.map((p) => plansApi.getVsActual(p.id)),
      )
      const map: Record<number, PlanVsActual> = {}
      results.forEach((res, idx) => {
        if (res.status === 'fulfilled') {
          map[list[idx].id] = res.value
        }
      })
      setVsActualMap(map)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadPlans()
  }, [loadPlans])

  // --- Load tables (once)
  useEffect(() => {
    plansApi
      .getTables()
      .then(setTables)
      .catch((err) => console.error('Failed to load plan tables', err))
  }, [])

  // --- Load bitrix_users via chartsApi.executeSql (no dedicated endpoint)
  useEffect(() => {
    setUsersLoading(true)
    chartsApi
      .executeSql({
        sql_query:
          "SELECT bitrix_id, name, last_name FROM bitrix_users ORDER BY last_name NULLS LAST, name NULLS LAST LIMIT 500",
      })
      .then((res) => {
        const rows = (res.data ?? []) as Array<Record<string, unknown>>
        const list: BitrixUser[] = rows.map((r) => ({
          bitrix_id: String(r.bitrix_id ?? ''),
          name: String(r.name ?? ''),
          last_name: String(r.last_name ?? ''),
        }))
        setUsers(list.filter((u) => u.bitrix_id))
      })
      .catch((err) => {
        // Fallback: try without NULLS LAST (MySQL doesn't support it)
        chartsApi
          .executeSql({
            sql_query:
              'SELECT bitrix_id, name, last_name FROM bitrix_users ORDER BY last_name, name LIMIT 500',
          })
          .then((res) => {
            const rows = (res.data ?? []) as Array<Record<string, unknown>>
            const list: BitrixUser[] = rows.map((r) => ({
              bitrix_id: String(r.bitrix_id ?? ''),
              name: String(r.name ?? ''),
              last_name: String(r.last_name ?? ''),
            }))
            setUsers(list.filter((u) => u.bitrix_id))
          })
          .catch((err2) => {
            console.error('Failed to load bitrix_users', err, err2)
          })
      })
      .finally(() => setUsersLoading(false))
  }, [])

  // --- User label lookup
  const userLabelById = useMemo(() => {
    const map = new Map<string, string>()
    users.forEach((u) => {
      const label = `${u.name ?? ''} ${u.last_name ?? ''}`.trim() || u.bitrix_id
      map.set(u.bitrix_id, label)
    })
    return map
  }, [users])

  const handleCreate = () => {
    setEditingPlan(null)
    setModalOpen(true)
  }

  const handleEdit = (plan: Plan) => {
    setEditingPlan(plan)
    setModalOpen(true)
  }

  const handleDelete = async (plan: Plan) => {
    if (
      !window.confirm(
        `Удалить план по ${plan.table_name}.${plan.field_name}? Это действие нельзя отменить.`,
      )
    ) {
      return
    }
    try {
      await plansApi.remove(plan.id)
      await loadPlans()
    } catch (err) {
      alert(`Ошибка удаления: ${getErrorMessage(err)}`)
    }
  }

  const handleSaved = async () => {
    setModalOpen(false)
    setEditingPlan(null)
    await loadPlans()
  }

  return (
    <div className="space-y-6">
      <AISubTabs />
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold">Планы</h2>
            <p className="text-sm text-gray-500">
              Плановые значения числовых полей — используются для отчётов «план/факт».
            </p>
          </div>
          <button onClick={handleCreate} className="btn btn-primary">
            + Добавить план
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
            {error}
          </div>
        )}

        {loading ? (
          <div className="py-10 text-center text-gray-500">Загрузка планов…</div>
        ) : plans.length === 0 ? (
          <div className="py-10 text-center text-gray-500">
            Планы ещё не заведены. Нажмите «Добавить план», чтобы создать первый.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Таблица
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Поле
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Менеджер
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Период
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">
                    План
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">
                    Факт
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">
                    Отклонение
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">
                    Действия
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {plans.map((plan) => {
                  const vs = vsActualMap[plan.id]
                  const manager = plan.assigned_by_id
                    ? userLabelById.get(plan.assigned_by_id) ??
                      `id: ${plan.assigned_by_id}`
                    : 'Все'
                  const variancePositive =
                    vs && Number(vs.variance) >= 0
                  return (
                    <tr key={plan.id} className="hover:bg-gray-50">
                      <td className="px-3 py-2 text-sm text-gray-900">
                        {plan.table_name}
                      </td>
                      <td className="px-3 py-2 text-sm text-gray-900">
                        {plan.field_name}
                      </td>
                      <td className="px-3 py-2 text-sm text-gray-700">{manager}</td>
                      <td className="px-3 py-2 text-sm text-gray-700">
                        {formatPeriod(plan)}
                      </td>
                      <td className="px-3 py-2 text-sm text-right font-medium">
                        {formatNumber(plan.plan_value)}
                      </td>
                      <td className="px-3 py-2 text-sm text-right text-gray-700">
                        {vs ? formatNumber(vs.actual_value) : '…'}
                      </td>
                      <td
                        className={`px-3 py-2 text-sm text-right ${
                          vs
                            ? variancePositive
                              ? 'text-green-600'
                              : 'text-red-600'
                            : 'text-gray-400'
                        }`}
                      >
                        {formatVariance(vs)}
                      </td>
                      <td className="px-3 py-2 text-sm text-right whitespace-nowrap">
                        <button
                          onClick={() => handleEdit(plan)}
                          className="text-primary-600 hover:text-primary-800 mr-3"
                        >
                          Редактировать
                        </button>
                        <button
                          onClick={() => handleDelete(plan)}
                          className="text-red-600 hover:text-red-800"
                        >
                          Удалить
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {modalOpen && (
        <PlanFormModal
          mode={editingPlan ? 'edit' : 'create'}
          plan={editingPlan}
          tables={tables}
          users={users}
          usersLoading={usersLoading}
          onClose={() => {
            setModalOpen(false)
            setEditingPlan(null)
          }}
          onSaved={handleSaved}
        />
      )}
    </div>
  )
}
