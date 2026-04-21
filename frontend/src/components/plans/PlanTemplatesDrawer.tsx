import { useCallback, useEffect, useState } from 'react'
import { plansApi, type PlanTemplate } from '../../services/api'
import PlanTemplateFormModal from './PlanTemplateFormModal'

interface PlanTemplatesDrawerProps {
  open: boolean
  onClose: () => void
  /** Called when the user clicks "Применить" on a template. Parent opens ApplyTemplateModal. */
  onApply: (templateId: number) => void
}

function getErrorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'response' in error) {
    const axiosError = error as { response?: { data?: { detail?: string } } }
    if (axiosError.response?.data?.detail) return axiosError.response.data.detail
  }
  if (error instanceof Error) return error.message
  return 'Произошла неизвестная ошибка'
}

const ASSIGNEES_LABEL: Record<string, string> = {
  all_managers: 'Все менеджеры',
  department: 'Отдел',
  specific: 'Конкретные',
  global: 'Общий',
}

const PERIOD_LABEL: Record<string, string> = {
  current_month: 'Текущий месяц',
  current_quarter: 'Текущий квартал',
  current_year: 'Текущий год',
  custom_period: 'Кастомный период',
}

export default function PlanTemplatesDrawer({
  open,
  onClose,
  onApply,
}: PlanTemplatesDrawerProps) {
  const [templates, setTemplates] = useState<PlanTemplate[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [formOpen, setFormOpen] = useState(false)
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create')
  const [editingTemplate, setEditingTemplate] = useState<PlanTemplate | null>(
    null,
  )

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const list = await plansApi.listTemplates()
      setTemplates(list)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (open) load()
  }, [open, load])

  const handleCreate = () => {
    setEditingTemplate(null)
    setFormMode('create')
    setFormOpen(true)
  }

  const handleEdit = (tpl: PlanTemplate) => {
    setEditingTemplate(tpl)
    setFormMode('edit')
    setFormOpen(true)
  }

  const handleDelete = async (tpl: PlanTemplate) => {
    if (tpl.is_builtin) return
    if (
      !window.confirm(
        `Удалить шаблон «${tpl.name}»? Это действие нельзя отменить.`,
      )
    ) {
      return
    }
    try {
      await plansApi.deleteTemplate(tpl.id)
      await load()
    } catch (err) {
      alert(`Ошибка удаления: ${getErrorMessage(err)}`)
    }
  }

  const handleFormSaved = async () => {
    setFormOpen(false)
    setEditingTemplate(null)
    await load()
  }

  if (!open) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/30"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer (right side) */}
      <aside
        className="fixed top-0 right-0 h-full w-full sm:w-[520px] bg-white shadow-xl z-50 flex flex-col"
        role="dialog"
        aria-label="Избранные шаблоны планов"
      >
        <div className="flex items-center justify-between px-5 py-4 border-b">
          <div>
            <h3 className="text-lg font-semibold">Избранные шаблоны планов</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Готовые наборы планов, которые можно применить в один клик.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
            aria-label="Закрыть"
          >
            ×
          </button>
        </div>

        <div className="px-5 py-3 border-b">
          <button
            type="button"
            onClick={handleCreate}
            className="btn btn-primary w-full"
          >
            + Новый шаблон
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {error && (
            <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
              {error}
            </div>
          )}

          {loading ? (
            <div className="py-10 text-center text-sm text-gray-500">
              Загрузка шаблонов…
            </div>
          ) : templates.length === 0 ? (
            <div className="py-10 text-center text-sm text-gray-500">
              Шаблонов нет. Создайте первый кнопкой выше.
            </div>
          ) : (
            <ul className="space-y-3">
              {templates.map((tpl) => (
                <li
                  key={tpl.id}
                  className="border border-gray-200 rounded-lg p-3 hover:border-primary-300 transition-colors"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h4 className="font-medium text-gray-900 truncate">
                          {tpl.name}
                        </h4>
                        {tpl.is_builtin && (
                          <span
                            className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-blue-100 text-blue-800 rounded"
                            title="Системный шаблон"
                          >
                            ⭐ builtin
                          </span>
                        )}
                      </div>
                      {tpl.description && (
                        <p className="text-sm text-gray-600 mt-1">
                          {tpl.description}
                        </p>
                      )}
                      <div className="text-xs text-gray-500 mt-2 space-x-2">
                        <span>
                          Период:{' '}
                          <b>
                            {PERIOD_LABEL[tpl.period_mode] ?? tpl.period_mode}
                          </b>
                        </span>
                        <span>·</span>
                        <span>
                          Назначение:{' '}
                          <b>
                            {ASSIGNEES_LABEL[tpl.assignees_mode] ??
                              tpl.assignees_mode}
                          </b>
                        </span>
                        {tpl.table_name && (
                          <>
                            <span>·</span>
                            <span>
                              {tpl.table_name}
                              {tpl.field_name ? `.${tpl.field_name}` : ''}
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 mt-3">
                    <button
                      type="button"
                      onClick={() => onApply(tpl.id)}
                      className="btn btn-primary text-sm py-1"
                    >
                      Применить
                    </button>
                    <button
                      type="button"
                      onClick={() => handleEdit(tpl)}
                      className="btn btn-secondary text-sm py-1"
                      title={
                        tpl.is_builtin
                          ? 'Системный шаблон: можно менять только необязательные поля'
                          : undefined
                      }
                    >
                      Редактировать
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(tpl)}
                      disabled={tpl.is_builtin}
                      className="text-red-600 hover:text-red-800 text-sm disabled:opacity-40 disabled:cursor-not-allowed ml-auto"
                      title={
                        tpl.is_builtin
                          ? 'Системные шаблоны удалять нельзя'
                          : 'Удалить шаблон'
                      }
                    >
                      Удалить
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>

      {formOpen && (
        <PlanTemplateFormModal
          open={formOpen}
          mode={formMode}
          template={editingTemplate}
          onClose={() => {
            setFormOpen(false)
            setEditingTemplate(null)
          }}
          onSaved={handleFormSaved}
        />
      )}
    </>
  )
}
