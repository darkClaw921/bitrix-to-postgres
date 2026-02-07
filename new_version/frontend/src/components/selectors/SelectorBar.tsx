import { useState, useEffect, useCallback } from 'react'
import type { DashboardSelector } from '../../services/api'
import { publicApi } from '../../services/api'
import { useTranslation } from '../../i18n'
import DateRangeSelector from './DateRangeSelector'
import SingleDateSelector from './SingleDateSelector'
import DropdownSelector from './DropdownSelector'
import MultiSelectSelector from './MultiSelectSelector'
import TextSelector from './TextSelector'

interface SelectorBarProps {
  selectors: DashboardSelector[]
  filterValues: Record<string, unknown>
  onFilterChange: (values: Record<string, unknown>) => void
  onApply: () => void
  slug: string
  token: string
}

export default function SelectorBar({
  selectors,
  filterValues,
  onFilterChange,
  onApply,
  slug,
  token,
}: SelectorBarProps) {
  const [optionsCache, setOptionsCache] = useState<Record<number, unknown[]>>({})
  const { t } = useTranslation()

  // Load dropdown options for selectors that need them
  useEffect(() => {
    for (const sel of selectors) {
      if (
        (sel.selector_type === 'dropdown' || sel.selector_type === 'multi_select') &&
        !sel.config?.static_options &&
        !optionsCache[sel.id]
      ) {
        publicApi
          .getSelectorOptions(slug, sel.id, token)
          .then((res) => {
            setOptionsCache((prev) => ({ ...prev, [sel.id]: res.options }))
          })
          .catch(() => {})
      }
    }
  }, [selectors, slug, token, optionsCache])

  const handleValueChange = useCallback(
    (name: string, value: unknown) => {
      onFilterChange({ ...filterValues, [name]: value })
    },
    [filterValues, onFilterChange],
  )

  const handleReset = useCallback(() => {
    const cleared: Record<string, unknown> = {}
    for (const sel of selectors) {
      cleared[sel.name] = null
    }
    onFilterChange(cleared)
    // Auto-apply on reset
    setTimeout(onApply, 0)
  }, [selectors, onFilterChange, onApply])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') onApply()
    },
    [onApply],
  )

  if (selectors.length === 0) return null

  const hasActiveFilters = Object.values(filterValues).some(
    (v) => v !== null && v !== '' && v !== undefined && !(Array.isArray(v) && v.length === 0),
  )

  return (
    <div
      className="flex flex-wrap items-end gap-3 p-3 bg-white rounded-lg border border-gray-200 shadow-sm mb-4"
      onKeyDown={handleKeyDown}
    >
      {selectors.map((sel) => {
        const value = filterValues[sel.name] ?? null
        const options = sel.config?.static_options || optionsCache[sel.id] || []

        return (
          <div key={sel.id} className="flex flex-col">
            <label className="text-xs text-gray-500 mb-1">
              {sel.label}
              {sel.is_required && <span className="text-red-400 ml-0.5">*</span>}
            </label>
            {sel.selector_type === 'date_range' && (
              <DateRangeSelector
                value={value as { from: string; to: string } | null}
                onChange={(v) => handleValueChange(sel.name, v)}
                placeholder={sel.config?.placeholder}
              />
            )}
            {sel.selector_type === 'single_date' && (
              <SingleDateSelector
                value={value as string | null}
                onChange={(v) => handleValueChange(sel.name, v)}
                placeholder={sel.config?.placeholder}
              />
            )}
            {sel.selector_type === 'dropdown' && (
              <DropdownSelector
                value={value as string | null}
                onChange={(v) => handleValueChange(sel.name, v)}
                options={options}
                placeholder={sel.config?.placeholder}
              />
            )}
            {sel.selector_type === 'multi_select' && (
              <MultiSelectSelector
                value={value as string[] | null}
                onChange={(v) => handleValueChange(sel.name, v)}
                options={options}
                placeholder={sel.config?.placeholder}
              />
            )}
            {sel.selector_type === 'text' && (
              <TextSelector
                value={value as string | null}
                onChange={(v) => handleValueChange(sel.name, v)}
                placeholder={sel.config?.placeholder}
              />
            )}
          </div>
        )
      })}

      <div className="flex items-end space-x-2 ml-auto">
        <button
          onClick={onApply}
          className="px-3 py-1.5 bg-blue-500 text-white text-sm rounded hover:bg-blue-600 transition-colors"
        >
          {t('common.apply')}
        </button>
        {hasActiveFilters && (
          <button
            onClick={handleReset}
            className="px-3 py-1.5 bg-gray-100 text-gray-600 text-sm rounded hover:bg-gray-200 transition-colors"
          >
            {t('common.reset')}
          </button>
        )}
      </div>
    </div>
  )
}
