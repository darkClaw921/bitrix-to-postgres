import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from '../../i18n'
import { publicApi } from '../../services/api'
import type { DashboardSelector, SelectorOption } from '../../services/api'
import DropdownSelector from './DropdownSelector'
import MultiSelectSelector from './MultiSelectSelector'
import DateRangeSelector from './DateRangeSelector'
import SingleDateSelector from './SingleDateSelector'
import TextSelector from './TextSelector'

interface Props {
  selectors: DashboardSelector[]
  slug: string
  token: string
  filterValues: Record<string, unknown>
  onApply: (values: Record<string, unknown>) => void
}

export default function SelectorBar({ selectors, slug, token, filterValues, onApply }: Props) {
  const { t } = useTranslation()
  const [draft, setDraft] = useState<Record<string, unknown>>(filterValues)
  const [options, setOptions] = useState<Record<number, SelectorOption[]>>({})
  const [loadingOpts, setLoadingOpts] = useState(false)

  // Sync draft with external filterValues
  useEffect(() => {
    setDraft(filterValues)
  }, [filterValues])

  // Load options for all dropdown/multi-select selectors in one batch request
  useEffect(() => {
    const needsOptions = selectors.some(
      (sel) => (sel.selector_type === 'dropdown' || sel.selector_type === 'multi_select'),
    )
    if (!needsOptions) return

    setLoadingOpts(true)
    publicApi
      .getPublicSelectorOptionsBatch(slug, token)
      .then((allOpts) => setOptions(allOpts))
      .catch(() => setOptions({}))
      .finally(() => setLoadingOpts(false))
  }, [selectors, slug, token])

  const updateDraft = useCallback((name: string, value: unknown) => {
    setDraft((prev) => ({ ...prev, [name]: value }))
  }, [])

  const handleApply = () => {
    // Remove null/undefined/empty values
    const cleaned: Record<string, unknown> = {}
    for (const [key, val] of Object.entries(draft)) {
      if (val != null && val !== '' && !(Array.isArray(val) && val.length === 0)) {
        cleaned[key] = val
      }
    }
    onApply(cleaned)
  }

  const handleReset = () => {
    setDraft({})
    onApply({})
  }

  const hasActiveFilters = Object.values(draft).some(
    (v) => v != null && v !== '' && !(Array.isArray(v) && v.length === 0),
  )

  if (selectors.length === 0) return null

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3 mb-4">
      <div className="flex flex-wrap gap-3 items-end">
        {selectors.map((sel) => (
          <div key={sel.id} className="min-w-[160px] max-w-[240px] flex-shrink-0">
            <label className="block text-xs text-gray-500 mb-1">
              {sel.label}
              {sel.is_required && <span className="text-red-500 ml-0.5">*</span>}
            </label>
            {sel.selector_type === 'dropdown' && (
              <DropdownSelector
                options={options[sel.id] || []}
                value={draft[sel.name] ?? null}
                onChange={(v) => updateDraft(sel.name, v)}
                loading={loadingOpts}
              />
            )}
            {sel.selector_type === 'multi_select' && (
              <MultiSelectSelector
                options={options[sel.id] || []}
                value={(draft[sel.name] as unknown[]) || []}
                onChange={(v) => updateDraft(sel.name, v)}
                loading={loadingOpts}
              />
            )}
            {sel.selector_type === 'date_range' && (
              <DateRangeSelector
                value={(draft[sel.name] as { from?: string; to?: string }) || null}
                onChange={(v) => updateDraft(sel.name, v)}
              />
            )}
            {sel.selector_type === 'single_date' && (
              <SingleDateSelector
                value={(draft[sel.name] as string) || null}
                onChange={(v) => updateDraft(sel.name, v)}
              />
            )}
            {sel.selector_type === 'text' && (
              <TextSelector
                value={(draft[sel.name] as string) || null}
                onChange={(v) => updateDraft(sel.name, v)}
              />
            )}
          </div>
        ))}

        <div className="flex gap-2 items-center ml-auto">
          <button
            onClick={handleApply}
            className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
          >
            {t('selectors.applyFilters')}
          </button>
          {hasActiveFilters && (
            <button
              onClick={handleReset}
              className="px-3 py-1.5 text-gray-500 text-sm rounded border border-gray-300 hover:bg-gray-50 transition-colors"
            >
              {t('selectors.resetFilters')}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
