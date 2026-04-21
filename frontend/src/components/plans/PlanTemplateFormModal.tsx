import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  departmentsApi,
  plansApi,
  type DepartmentTreeNode,
  type NumericFieldInfo,
  type PlanAssigneesMode,
  type PlanManagerInfo,
  type PlanPeriodMode,
  type PlanPeriodType,
  type PlanTableInfo,
  type PlanTemplate,
  type PlanTemplateCreateRequest,
  type PlanTemplateUpdateRequest,
} from '../../services/api'

interface PlanTemplateFormModalProps {
  open: boolean
  mode: 'create' | 'edit'
  template: PlanTemplate | null
  onClose: () => void
  onSaved: () => void
}

interface FormState {
  name: string
  description: string
  table_name: string
  field_name: string
  period_mode: PlanPeriodMode
  period_type: PlanPeriodType
  period_value: string
  date_from: string
  date_to: string
  assignees_mode: PlanAssigneesMode
  department_name: string
  specific_manager_ids: string[]
  default_plan_value: string
}

function emptyForm(): FormState {
  return {
    name: '',
    description: '',
    table_name: '',
    field_name: '',
    period_mode: 'current_month',
    period_type: 'month',
    period_value: '',
    date_from: '',
    date_to: '',
    assignees_mode: 'all_managers',
    department_name: '',
    specific_manager_ids: [],
    default_plan_value: '',
  }
}

function templateToForm(t: PlanTemplate): FormState {
  return {
    name: t.name,
    description: t.description ?? '',
    table_name: t.table_name ?? '',
    field_name: t.field_name ?? '',
    period_mode: t.period_mode,
    period_type: (t.period_type ?? 'month') as PlanPeriodType,
    period_value: t.period_value ?? '',
    date_from: t.date_from ?? '',
    date_to: t.date_to ?? '',
    assignees_mode: t.assignees_mode,
    department_name: t.department_name ?? '',
    specific_manager_ids: t.specific_manager_ids ?? [],
    default_plan_value:
      t.default_plan_value === null || t.default_plan_value === undefined
        ? ''
        : String(t.default_plan_value),
  }
}

function getErrorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'response' in error) {
    const axiosError = error as { response?: { data?: { detail?: string } } }
    if (axiosError.response?.data?.detail) return axiosError.response.data.detail
  }
  if (error instanceof Error) return error.message
  return 'Произошла неизвестная ошибка'
}

/**
 * Flatten a DepartmentTreeNode[] into [{id, label}] with indent prefixes
 * so a regular <select> can render the hierarchy.
 */
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

export default function PlanTemplateFormModal({
  open,
  mode,
  template,
  onClose,
  onSaved,
}: PlanTemplateFormModalProps) {
  const [form, setForm] = useState<FormState>(() =>
    template ? templateToForm(template) : emptyForm(),
  )
  const [tables, setTables] = useState<PlanTableInfo[]>([])
  const [fields, setFields] = useState<NumericFieldInfo[]>([])
  const [fieldsLoading, setFieldsLoading] = useState(false)
  const [tree, setTree] = useState<DepartmentTreeNode[]>([])
  const [managers, setManagers] = useState<PlanManagerInfo[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const deptOptions = useMemo(() => flattenDepartments(tree), [tree])

  // Reset form when modal opens with a different template.
  useEffect(() => {
    if (!open) return
    setForm(template ? templateToForm(template) : emptyForm())
    setError(null)
  }, [open, template])

  // Load meta on open.
  useEffect(() => {
    if (!open) return
    plansApi
      .getTables()
      .then(setTables)
      .catch(() => setTables([]))
    departmentsApi
      .getTree()
      .then((resp) => setTree(resp.tree))
      .catch(() => setTree([]))
    plansApi
      .listManagers()
      .then((resp) => setManagers(resp.managers))
      .catch(() => setManagers([]))
  }, [open])

  // Load numeric fields when table changes.
  useEffect(() => {
    if (!form.table_name) {
      setFields([])
      return
    }
    let cancelled = false
    setFieldsLoading(true)
    plansApi
      .getNumericFields(form.table_name)
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
  }, [form.table_name])

  const update = useCallback(
    <K extends keyof FormState>(key: K, value: FormState[K]) => {
      setForm((prev) => ({ ...prev, [key]: value }))
    },
    [],
  )

  const isEdit = mode === 'edit'
  const isBuiltin = isEdit && !!template?.is_builtin

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!form.name.trim()) {
      setError('Укажите название шаблона')
      return
    }
    if (form.period_mode === 'custom_period') {
      if (form.period_type !== 'custom' && !form.period_value) {
        setError('Укажите значение периода')
        return
      }
      if (form.period_type === 'custom' && (!form.date_from || !form.date_to)) {
        setError('Укажите даты начала и окончания периода')
        return
      }
    }
    if (form.assignees_mode === 'department' && !form.department_name) {
      setError('Выберите отдел')
      return
    }
    if (
      form.assignees_mode === 'specific' &&
      form.specific_manager_ids.length === 0
    ) {
      setError('Выберите хотя бы одного менеджера')
      return
    }

    const payload: PlanTemplateCreateRequest | PlanTemplateUpdateRequest = {
      name: form.name.trim(),
      description: form.description.trim() || null,
      table_name: form.table_name || null,
      field_name: form.field_name || null,
      period_mode: form.period_mode,
      period_type:
        form.period_mode === 'custom_period' ? form.period_type : null,
      period_value:
        form.period_mode === 'custom_period' && form.period_type !== 'custom'
          ? form.period_value
          : null,
      date_from:
        form.period_mode === 'custom_period' && form.period_type === 'custom'
          ? form.date_from
          : null,
      date_to:
        form.period_mode === 'custom_period' && form.period_type === 'custom'
          ? form.date_to
          : null,
      assignees_mode: form.assignees_mode,
      department_name:
        form.assignees_mode === 'department' ? form.department_name : null,
      specific_manager_ids:
        form.assignees_mode === 'specific' ? form.specific_manager_ids : null,
      default_plan_value: form.default_plan_value
        ? Number(form.default_plan_value)
        : null,
    }

    setSubmitting(true)
    try {
      if (isEdit && template) {
        await plansApi.updateTemplate(template.id, payload)
      } else {
        await plansApi.createTemplate(payload as PlanTemplateCreateRequest)
      }
      onSaved()
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h3 className="text-lg font-semibold">
            {isEdit ? 'Редактировать шаблон' : 'Новый шаблон плана'}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
            aria-label="Закрыть"
            disabled={submitting}
          >
            ×
          </button>
        </div>

        <form
          onSubmit={handleSubmit}
          className="flex-1 overflow-y-auto px-6 py-4 space-y-4"
        >
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
              {error}
            </div>
          )}
          {isBuiltin && (
            <div className="p-3 bg-blue-50 border border-blue-200 rounded text-sm text-blue-700">
              Это системный шаблон. Нельзя менять имя, режим периода и режим назначения.
            </div>
          )}

          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Название
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => update('name', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 disabled:bg-gray-100"
              required
              disabled={isBuiltin}
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Описание
            </label>
            <textarea
              value={form.description}
              onChange={(e) => update('description', e.target.value)}
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            />
          </div>

          {/* Table / Field (optional) */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Таблица (необязательно)
              </label>
              <select
                value={form.table_name}
                onChange={(e) => {
                  update('table_name', e.target.value)
                  update('field_name', '')
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              >
                <option value="">— не задано —</option>
                {tables.map((t) => (
                  <option key={t.name} value={t.name}>
                    {t.label ? `${t.label} (${t.name})` : t.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Поле (необязательно)
              </label>
              <select
                value={form.field_name}
                onChange={(e) => update('field_name', e.target.value)}
                disabled={!form.table_name || fieldsLoading}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg disabled:bg-gray-100"
              >
                <option value="">
                  {fieldsLoading
                    ? 'Загрузка…'
                    : form.table_name
                    ? '— не задано —'
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

          {/* Period mode */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Режим периода
            </label>
            <div className="flex flex-wrap items-center gap-4 mb-2">
              {(
                [
                  ['current_month', 'Текущий месяц'],
                  ['current_quarter', 'Текущий квартал'],
                  ['current_year', 'Текущий год'],
                  ['custom_period', 'Кастомный'],
                ] as Array<[PlanPeriodMode, string]>
              ).map(([value, label]) => (
                <label
                  key={value}
                  className="inline-flex items-center gap-2 text-sm"
                >
                  <input
                    type="radio"
                    name="period_mode"
                    checked={form.period_mode === value}
                    onChange={() => update('period_mode', value)}
                    disabled={isBuiltin}
                  />
                  {label}
                </label>
              ))}
            </div>

            {form.period_mode === 'custom_period' && (
              <div className="grid grid-cols-2 gap-3 mt-2">
                <select
                  value={form.period_type}
                  onChange={(e) =>
                    update('period_type', e.target.value as PlanPeriodType)
                  }
                  className="px-3 py-2 border border-gray-300 rounded-lg"
                >
                  <option value="month">Месяц (2026-04)</option>
                  <option value="quarter">Квартал (2026-Q2)</option>
                  <option value="year">Год (2026)</option>
                  <option value="custom">Диапазон дат</option>
                </select>

                {form.period_type === 'custom' ? (
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="date"
                      value={form.date_from}
                      onChange={(e) => update('date_from', e.target.value)}
                      className="px-3 py-2 border border-gray-300 rounded-lg"
                    />
                    <input
                      type="date"
                      value={form.date_to}
                      onChange={(e) => update('date_to', e.target.value)}
                      className="px-3 py-2 border border-gray-300 rounded-lg"
                    />
                  </div>
                ) : (
                  <input
                    type="text"
                    value={form.period_value}
                    onChange={(e) => update('period_value', e.target.value)}
                    placeholder={
                      form.period_type === 'month'
                        ? '2026-04'
                        : form.period_type === 'quarter'
                        ? '2026-Q2'
                        : '2026'
                    }
                    className="px-3 py-2 border border-gray-300 rounded-lg"
                  />
                )}
              </div>
            )}
          </div>

          {/* Assignees mode */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Назначение
            </label>
            <div className="flex flex-wrap items-center gap-4 mb-2">
              {(
                [
                  ['all_managers', 'Все менеджеры'],
                  ['department', 'Отдел'],
                  ['specific', 'Конкретные'],
                  ['global', 'Общий (без менеджера)'],
                ] as Array<[PlanAssigneesMode, string]>
              ).map(([value, label]) => (
                <label
                  key={value}
                  className="inline-flex items-center gap-2 text-sm"
                >
                  <input
                    type="radio"
                    name="assignees_mode"
                    checked={form.assignees_mode === value}
                    onChange={() => update('assignees_mode', value)}
                    disabled={isBuiltin}
                  />
                  {label}
                </label>
              ))}
            </div>

            {form.assignees_mode === 'department' && (
              <div className="mt-2">
                <select
                  value={form.department_name}
                  onChange={(e) => update('department_name', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                >
                  <option value="">— выберите отдел —</option>
                  {deptOptions.map((d) => (
                    <option key={d.id} value={d.label.trim().replace(/^└\s/, '')}>
                      {d.label}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  Значение сохраняется как имя отдела — backend сам резолвит его в id с подотделами.
                </p>
              </div>
            )}

            {form.assignees_mode === 'specific' && (
              <div className="mt-2">
                <select
                  multiple
                  value={form.specific_manager_ids}
                  onChange={(e) => {
                    const ids = Array.from(e.target.selectedOptions).map(
                      (o) => o.value,
                    )
                    update('specific_manager_ids', ids)
                  }}
                  size={Math.min(10, Math.max(4, managers.length))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                >
                  {managers.map((m) => {
                    const label =
                      `${m.name ?? ''} ${m.last_name ?? ''}`.trim() ||
                      m.bitrix_id
                    return (
                      <option key={m.bitrix_id} value={m.bitrix_id}>
                        {label} (id: {m.bitrix_id})
                      </option>
                    )
                  })}
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  Удерживайте Ctrl/Cmd для выбора нескольких.
                </p>
              </div>
            )}
          </div>

          {/* Default plan value */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Значение плана по умолчанию (необязательно)
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={form.default_plan_value}
              onChange={(e) => update('default_plan_value', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              placeholder="Например, 500000"
            />
            <p className="text-xs text-gray-500 mt-1">
              При применении шаблона это значение будет проставлено всем menagers автоматически.
            </p>
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
