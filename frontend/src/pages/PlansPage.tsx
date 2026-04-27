import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  chartsApi,
  plansApi,
  type Plan,
  type PlanListFilters,
  type PlanManagerInfo,
  type PlanTableInfo,
  type PlanVsActual,
} from '../services/api'
import AISubTabs from '../components/ai/AISubTabs'
import PlanFormModal, {
  type BitrixUser,
} from '../components/plans/PlanFormModal'
import AIGeneratePlansModal from '../components/plans/AIGeneratePlansModal'
import PlanTemplatesDrawer from '../components/plans/PlanTemplatesDrawer'
import ApplyTemplateModal from '../components/plans/ApplyTemplateModal'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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
  const [managers, setManagers] = useState<PlanManagerInfo[]>([])

  // Edit/create form
  const [modalOpen, setModalOpen] = useState(false)
  const [editingPlan, setEditingPlan] = useState<Plan | null>(null)

  // AI generation modal
  const [aiOpen, setAiOpen] = useState(false)

  // Templates drawer + apply modal
  const [templatesOpen, setTemplatesOpen] = useState(false)
  const [applyTemplateId, setApplyTemplateId] = useState<number | null>(null)

  // Toast for batch flows
  const [toast, setToast] = useState<string | null>(null)

  // --- Filters
  const [filterManagerIds, setFilterManagerIds] = useState<string[]>([])
  const [filterPeriodType, setFilterPeriodType] = useState<string>('')
  const [filterPeriodValue, setFilterPeriodValue] = useState<string>('')
  const [filterMonthYear, setFilterMonthYear] = useState<string>('')
  const [filterMonthMonth, setFilterMonthMonth] = useState<string>('')
  const [managerDropdownOpen, setManagerDropdownOpen] = useState(false)
  const [managerSearch, setManagerSearch] = useState('')
  const managerDropdownRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!managerDropdownOpen) return
    const onDocClick = (ev: MouseEvent) => {
      if (
        managerDropdownRef.current &&
        !managerDropdownRef.current.contains(ev.target as Node)
      ) {
        setManagerDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [managerDropdownOpen])

  // --- Load plans + facts
  const loadPlans = useCallback(async (filters?: PlanListFilters) => {
    setLoading(true)
    setError(null)
    setVsActualMap({})
    try {
      const list = await plansApi.list(filters)
      setPlans(list)
      setLoading(false)
      // Lazy-load facts in parallel; update map as each resolves so the
      // table fills in progressively without blocking the initial render.
      list.forEach((p) => {
        plansApi
          .getVsActual(p.id)
          .then((vs) => {
            setVsActualMap((prev) => ({ ...prev, [p.id]: vs }))
          })
          .catch(() => {})
      })
    } catch (err) {
      setError(getErrorMessage(err))
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadPlans()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleApplyFilters = useCallback(() => {
    const filters: PlanListFilters = {}
    if (filterManagerIds.length > 0) filters.assigned_by_id = filterManagerIds
    if (filterPeriodType) filters.period_type = filterPeriodType as PlanListFilters['period_type']
    if (filterPeriodValue) filters.period_value = filterPeriodValue
    loadPlans(filters)
  }, [filterManagerIds, filterPeriodType, filterPeriodValue, loadPlans])

  const handleResetFilters = useCallback(() => {
    setFilterManagerIds([])
    setFilterPeriodType('')
    setFilterPeriodValue('')
    setFilterMonthYear('')
    setFilterMonthMonth('')
    loadPlans()
  }, [loadPlans])

  // --- Load tables (once)
  useEffect(() => {
    plansApi
      .getTables()
      .then(setTables)
      .catch((err) => console.error('Failed to load plan tables', err))
  }, [])

  // --- Load managers via dedicated endpoint (for drafts table name resolution)
  useEffect(() => {
    plansApi
      .listManagers()
      .then((resp) => setManagers(resp.managers))
      .catch(() => setManagers([]))
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

  // Auto-hide toast after 3s
  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 3000)
    return () => clearTimeout(t)
  }, [toast])

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

  const handleAiSuccess = async () => {
    setToast('Планы созданы через AI')
    await loadPlans()
  }

  const handleApplySuccess = async () => {
    setToast('План применён')
    await loadPlans()
  }

  const handleApplyTemplate = (templateId: number) => {
    setApplyTemplateId(templateId)
    setTemplatesOpen(false)
  }

  return (
    <div className="space-y-6">
      <AISubTabs />
      <div className="card">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <div>
            <h2 className="text-lg font-semibold">Планы</h2>
            <p className="text-sm text-gray-500">
              Плановые значения числовых полей — используются для отчётов «план/факт».
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <button onClick={handleCreate} className="btn btn-primary">
              + Добавить план
            </button>
            <button
              onClick={() => setAiOpen(true)}
              className="btn btn-secondary"
              title="Сгенерировать планы через AI"
            >
              ✨ Сгенерировать через AI
            </button>
            <button
              onClick={() => setTemplatesOpen(true)}
              className="btn btn-secondary"
              title="Применить один из шаблонов"
            >
              ⭐ Избранные
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="mb-4 flex flex-wrap gap-3 items-end">
          <div className="flex flex-col gap-1" ref={managerDropdownRef}>
            <label className="text-xs text-gray-500 font-medium">
              Менеджеры{filterManagerIds.length > 0 && ` (${filterManagerIds.length})`}
            </label>
            <div className="relative">
              <button
                type="button"
                onClick={() => setManagerDropdownOpen((v) => !v)}
                className="border border-gray-300 rounded px-2 py-1.5 text-sm min-w-[220px] text-left bg-white hover:bg-gray-50 flex items-center justify-between gap-2"
              >
                <span className="truncate">
                  {filterManagerIds.length === 0
                    ? 'Все менеджеры'
                    : filterManagerIds.length === 1
                    ? (() => {
                        const m = managers.find(
                          (x) => x.bitrix_id === filterManagerIds[0],
                        )
                        return m
                          ? `${m.name ?? ''} ${m.last_name ?? ''}`.trim() ||
                              m.bitrix_id
                          : filterManagerIds[0]
                      })()
                    : `Выбрано: ${filterManagerIds.length}`}
                </span>
                <span className="text-gray-400">▾</span>
              </button>
              {managerDropdownOpen && (
                <div className="absolute z-20 mt-1 w-72 max-h-72 overflow-auto bg-white border border-gray-300 rounded shadow-lg">
                  <div className="sticky top-0 bg-white border-b p-2 flex gap-2">
                    <input
                      type="text"
                      placeholder="Поиск…"
                      value={managerSearch}
                      onChange={(e) => setManagerSearch(e.target.value)}
                      className="flex-1 border border-gray-300 rounded px-2 py-1 text-sm"
                    />
                    {filterManagerIds.length > 0 && (
                      <button
                        type="button"
                        onClick={() => setFilterManagerIds([])}
                        className="text-xs text-gray-500 hover:text-gray-700"
                      >
                        Очистить
                      </button>
                    )}
                  </div>
                  {managers
                    .filter((m) => {
                      if (!managerSearch.trim()) return true
                      const label = `${m.name ?? ''} ${m.last_name ?? ''} ${
                        m.bitrix_id
                      }`.toLowerCase()
                      return label.includes(managerSearch.trim().toLowerCase())
                    })
                    .map((m) => {
                      const label =
                        `${m.name ?? ''} ${m.last_name ?? ''}`.trim() ||
                        m.bitrix_id
                      const checked = filterManagerIds.includes(m.bitrix_id)
                      return (
                        <label
                          key={m.bitrix_id}
                          className="flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-gray-50 cursor-pointer"
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => {
                              setFilterManagerIds((prev) =>
                                checked
                                  ? prev.filter((id) => id !== m.bitrix_id)
                                  : [...prev, m.bitrix_id],
                              )
                            }}
                          />
                          <span className="truncate">{label}</span>
                        </label>
                      )
                    })}
                  {managers.length === 0 && (
                    <div className="px-3 py-2 text-sm text-gray-500">
                      Нет данных
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">Тип периода</label>
            <select
              className="border border-gray-300 rounded px-2 py-1.5 text-sm"
              value={filterPeriodType}
              onChange={(e) => {
                setFilterPeriodType(e.target.value)
                setFilterPeriodValue('')
                setFilterMonthYear('')
                setFilterMonthMonth('')
              }}
            >
              <option value="">Любой</option>
              <option value="month">Месяц</option>
              <option value="quarter">Квартал</option>
              <option value="year">Год</option>
              <option value="custom">Произвольный</option>
            </select>
          </div>
          {filterPeriodType === 'month' && (
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500 font-medium">Месяц</label>
              <div className="flex gap-2">
                <select
                  className="border border-gray-300 rounded px-2 py-1.5 text-sm"
                  value={filterMonthYear}
                  onChange={(e) => {
                    const y = e.target.value
                    setFilterMonthYear(y)
                    setFilterPeriodValue(y && filterMonthMonth ? `${y}-${filterMonthMonth}` : '')
                  }}
                >
                  <option value="">Год</option>
                  {(() => {
                    const cy = new Date().getFullYear()
                    const years: number[] = []
                    for (let y = cy - 5; y <= cy + 2; y++) years.push(y)
                    return years.map((y) => (
                      <option key={y} value={String(y)}>
                        {y}
                      </option>
                    ))
                  })()}
                </select>
                <select
                  className="border border-gray-300 rounded px-2 py-1.5 text-sm"
                  value={filterMonthMonth}
                  onChange={(e) => {
                    const m = e.target.value
                    setFilterMonthMonth(m)
                    setFilterPeriodValue(filterMonthYear && m ? `${filterMonthYear}-${m}` : '')
                  }}
                >
                  <option value="">Месяц</option>
                  {MONTHS_RU.map((label, idx) => {
                    const mm = String(idx + 1).padStart(2, '0')
                    return (
                      <option key={mm} value={mm}>
                        {label}
                      </option>
                    )
                  })}
                </select>
              </div>
            </div>
          )}
          {filterPeriodType === 'quarter' && (
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500 font-medium">Квартал</label>
              <select
                className="border border-gray-300 rounded px-2 py-1.5 text-sm"
                value={filterPeriodValue}
                onChange={(e) => setFilterPeriodValue(e.target.value)}
              >
                <option value="">— выберите —</option>
                {(() => {
                  const cy = new Date().getFullYear()
                  const years = [cy - 2, cy - 1, cy, cy + 1]
                  return years.flatMap((y) =>
                    ['Q1', 'Q2', 'Q3', 'Q4'].map((q) => (
                      <option key={`${y}-${q}`} value={`${y}-${q}`}>
                        {y} — {q}
                      </option>
                    )),
                  )
                })()}
              </select>
            </div>
          )}
          {filterPeriodType === 'year' && (
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500 font-medium">Год</label>
              <select
                className="border border-gray-300 rounded px-2 py-1.5 text-sm w-28"
                value={filterPeriodValue}
                onChange={(e) => setFilterPeriodValue(e.target.value)}
              >
                <option value="">— выберите —</option>
                {(() => {
                  const cy = new Date().getFullYear()
                  const years: number[] = []
                  for (let y = cy - 5; y <= cy + 2; y++) years.push(y)
                  return years.map((y) => (
                    <option key={y} value={String(y)}>
                      {y}
                    </option>
                  ))
                })()}
              </select>
            </div>
          )}
          <div className="flex gap-2">
            <button onClick={handleApplyFilters} className="btn btn-primary">
              Применить
            </button>
            {(filterManagerIds.length > 0 || filterPeriodType || filterPeriodValue) && (
              <button onClick={handleResetFilters} className="btn btn-secondary">
                Сбросить
              </button>
            )}
          </div>
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

      <AIGeneratePlansModal
        open={aiOpen}
        onClose={() => setAiOpen(false)}
        onSuccess={handleAiSuccess}
        managers={managers}
      />

      <PlanTemplatesDrawer
        open={templatesOpen}
        onClose={() => setTemplatesOpen(false)}
        onApply={handleApplyTemplate}
      />

      <ApplyTemplateModal
        open={applyTemplateId !== null}
        onClose={() => setApplyTemplateId(null)}
        templateId={applyTemplateId}
        onSuccess={handleApplySuccess}
        managers={managers}
      />

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-[80] px-4 py-3 bg-gray-900 text-white rounded-lg shadow-lg text-sm">
          {toast}
        </div>
      )}
    </div>
  )
}
