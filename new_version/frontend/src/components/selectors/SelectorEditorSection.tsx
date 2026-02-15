import { useState } from 'react'
import { useTranslation } from '../../i18n'
import {
  useDashboardSelectors,
  useCreateSelector,
  useUpdateSelector,
  useDeleteSelector,
} from '../../hooks/useSelectors'
import type { DashboardSelector, DashboardChart, SelectorCreateRequest, SelectorUpdateRequest } from '../../services/api'
import SelectorBoardDialog from './SelectorBoardDialog'

const TYPE_ICONS: Record<string, string> = {
  dropdown: '\u25BC',
  multi_select: '\u2611',
  date_range: '\u2194',
  single_date: '\u{1F4C5}',
  text: 'Aa',
}

interface Props {
  dashboardId: number
  charts: DashboardChart[]
}

export default function SelectorEditorSection({ dashboardId, charts }: Props) {
  const { t } = useTranslation()
  const { data: selectors, refetch } = useDashboardSelectors(dashboardId)
  const createSelector = useCreateSelector()
  const updateSelector = useUpdateSelector()
  const deleteSelector = useDeleteSelector()

  const [modalOpen, setModalOpen] = useState(false)
  const [editingSelector, setEditingSelector] = useState<DashboardSelector | null>(null)

  const handleCreate = () => {
    setEditingSelector(null)
    setModalOpen(true)
  }

  const handleEdit = (sel: DashboardSelector) => {
    setEditingSelector(sel)
    setModalOpen(true)
  }

  const handleDelete = (sel: DashboardSelector) => {
    if (!confirm(t('selectors.confirmDelete'))) return
    deleteSelector.mutate(
      { dashboardId, selectorId: sel.id },
      { onSuccess: () => refetch() },
    )
  }

  const handleSave = (data: SelectorCreateRequest | SelectorUpdateRequest) => {
    if (editingSelector) {
      updateSelector.mutate(
        { dashboardId, selectorId: editingSelector.id, data: data as SelectorUpdateRequest },
        {
          onSuccess: () => {
            setModalOpen(false)
            refetch()
          },
        },
      )
    } else {
      createSelector.mutate(
        { dashboardId, data: data as SelectorCreateRequest },
        {
          onSuccess: () => {
            setModalOpen(false)
            refetch()
          },
        },
      )
    }
  }

  const handleMoveUp = (sel: DashboardSelector, index: number) => {
    if (index === 0 || !selectors) return
    const prev = selectors[index - 1]
    updateSelector.mutate(
      { dashboardId, selectorId: sel.id, data: { sort_order: prev.sort_order } },
      { onSuccess: () => {
        updateSelector.mutate(
          { dashboardId, selectorId: prev.id, data: { sort_order: sel.sort_order } },
          { onSuccess: () => refetch() },
        )
      }},
    )
  }

  const handleMoveDown = (sel: DashboardSelector, index: number) => {
    if (!selectors || index >= selectors.length - 1) return
    const next = selectors[index + 1]
    updateSelector.mutate(
      { dashboardId, selectorId: sel.id, data: { sort_order: next.sort_order } },
      { onSuccess: () => {
        updateSelector.mutate(
          { dashboardId, selectorId: next.id, data: { sort_order: sel.sort_order } },
          { onSuccess: () => refetch() },
        )
      }},
    )
  }

  return (
    <div className="mt-8">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold">{t('selectors.title')}</h3>
        <button
          onClick={handleCreate}
          className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
        >
          + {t('selectors.addSelector')}
        </button>
      </div>

      {(!selectors || selectors.length === 0) ? (
        <div className="text-gray-400 text-sm py-4 text-center border border-dashed border-gray-200 rounded">
          {t('selectors.noSelectors')}
        </div>
      ) : (
        <div className="space-y-2">
          {selectors.map((sel, index) => (
            <div
              key={sel.id}
              className="flex items-center gap-3 bg-white border border-gray-200 rounded-lg px-4 py-2"
            >
              <span className="text-lg w-6 text-center" title={sel.selector_type}>
                {TYPE_ICONS[sel.selector_type] || '?'}
              </span>
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm truncate">{sel.label}</div>
                <div className="text-xs text-gray-400">
                  {sel.selector_type} &middot; {sel.mappings.length} {t('selectors.mappedCharts')}
                  {sel.is_required && <span className="text-red-500 ml-1">*</span>}
                </div>
              </div>

              <div className="flex items-center gap-1">
                <button
                  onClick={() => handleMoveUp(sel, index)}
                  disabled={index === 0}
                  className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-30"
                  title={t('selectors.moveUp')}
                >
                  &uarr;
                </button>
                <button
                  onClick={() => handleMoveDown(sel, index)}
                  disabled={index >= selectors.length - 1}
                  className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-30"
                  title={t('selectors.moveDown')}
                >
                  &darr;
                </button>
                <button
                  onClick={() => handleEdit(sel)}
                  className="p-1 text-blue-500 hover:text-blue-700 text-sm"
                  title={t('common.edit')}
                >
                  {t('common.edit')}
                </button>
                <button
                  onClick={() => handleDelete(sel)}
                  className="p-1 text-red-400 hover:text-red-600 text-sm"
                  title={t('common.delete')}
                >
                  {t('common.delete')}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {modalOpen && (
        <SelectorBoardDialog
          dashboardId={dashboardId}
          charts={charts}
          selector={editingSelector}
          onClose={() => setModalOpen(false)}
          onSave={handleSave}
          saving={createSelector.isPending || updateSelector.isPending}
        />
      )}
    </div>
  )
}
