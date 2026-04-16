import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  chartsApi,
  plansApi,
  type Plan,
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
