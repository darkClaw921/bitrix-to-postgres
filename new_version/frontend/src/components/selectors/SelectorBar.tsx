import { useState, useEffect, useCallback, useRef } from 'react'
import { useTranslation } from '../../i18n'
import { publicApi } from '../../services/api'
import type { DashboardSelector, SelectorOption } from '../../services/api'
import { resolveFilterValue } from '../../utils/dateTokens'
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
  /**
   * When true (default), changes are dispatched automatically with a debounce.
   * When false, an explicit Apply button is shown.
   */
  autoApply?: boolean
  /**
   * If set, options are fetched via the linked dashboard endpoint
   * (`/public/dashboard/{slug}/linked/{linkedSlug}/selector-options`) so the
   * caller's main-slug JWT remains valid for linked tabs.
   */
  linkedSlug?: string
}

const TEXT_DEBOUNCE_MS = 500
const DEFAULT_DEBOUNCE_MS = 250

function isEmpty(v: unknown): boolean {
  if (v == null || v === '') return true
  if (Array.isArray(v) && v.length === 0) return true
  if (typeof v === 'object' && !Array.isArray(v)) {
    const obj = v as Record<string, unknown>
    return Object.keys(obj).length === 0 || Object.values(obj).every((x) => x == null || x === '')
  }
  return false
}

function cleanValues(draft: Record<string, unknown>): Record<string, unknown> {
  const cleaned: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(draft)) {
    if (!isEmpty(v)) cleaned[k] = v
  }
  return cleaned
}

/**
 * Compute the initial draft value for a single selector, honouring its
 * ``config.default_value`` (which can be a date token like ``LAST_30_DAYS``).
 * Tokens are intentionally NOT pre-resolved here — the backend resolves them
 * on every request, and the inputs render them via their own helpers.
 */
function defaultValueFor(sel: DashboardSelector): unknown {
  const cfg = sel.config || {}
  const dv = (cfg as { default_value?: unknown }).default_value
  if (dv === undefined || dv === null) return null
  return dv
}

export default function SelectorBar({
  selectors,
  slug,
  token,
  filterValues,
  onApply,
  autoApply = true,
  linkedSlug,
}: Props) {
  const { t } = useTranslation()
  const [draft, setDraft] = useState<Record<string, unknown>>(filterValues)
  const [options, setOptions] = useState<Record<number, SelectorOption[]>>({})
  const [loadingOpts, setLoadingOpts] = useState(false)
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastDispatchedJson = useRef<string>('')
  const initializedFor = useRef<string>('')

  // Sync draft from external filterValues (e.g. tab switch). Skip if values
  // are equivalent so we don't fight the user's local edits.
  useEffect(() => {
    setDraft(filterValues)
    lastDispatchedJson.current = JSON.stringify(cleanValues(filterValues))
  }, [filterValues])

  // Initialize defaults from selector config when this dashboard's selectors
  // first arrive (and the user hasn't already applied filters of their own).
  useEffect(() => {
    const key = selectors.map((s) => s.id).join(',')
    if (!key || initializedFor.current === key) return
    initializedFor.current = key

    if (Object.keys(filterValues).length > 0) return

    const initial: Record<string, unknown> = {}
    for (const sel of selectors) {
      const dv = defaultValueFor(sel)
      if (dv !== null && dv !== undefined) {
        initial[sel.name] = dv
      }
    }

    if (Object.keys(initial).length > 0) {
      setDraft(initial)
      // Resolve tokens before sending up — backend handles them too, but the
      // round trip is faster if we don't have to make it.
      const resolved: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(initial)) {
        resolved[k] = resolveFilterValue(v)
      }
      const cleaned = cleanValues(resolved)
      lastDispatchedJson.current = JSON.stringify(cleaned)
      onApply(cleaned)
    }
  }, [selectors, filterValues, onApply])

  // Load options for all dropdown/multi-select selectors in one batch request.
  useEffect(() => {
    const needsOptions = selectors.some(
      (sel) => sel.selector_type === 'dropdown' || sel.selector_type === 'multi_select',
    )
    if (!needsOptions) return

    setLoadingOpts(true)
    const fetcher = linkedSlug
      ? publicApi.getLinkedPublicSelectorOptionsBatch(slug, linkedSlug, token)
      : publicApi.getPublicSelectorOptionsBatch(slug, token)
    fetcher
      .then((allOpts) => setOptions(allOpts))
      .catch(() => setOptions({}))
      .finally(() => setLoadingOpts(false))
  }, [selectors, slug, token, linkedSlug])

  // Cleanup debounce on unmount
  useEffect(() => {
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current)
    }
  }, [])

  const dispatch = useCallback(
    (next: Record<string, unknown>) => {
      const resolved: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(next)) {
        resolved[k] = resolveFilterValue(v)
      }
      const cleaned = cleanValues(resolved)
      const json = JSON.stringify(cleaned)
      if (json === lastDispatchedJson.current) return
      lastDispatchedJson.current = json
      onApply(cleaned)
    },
    [onApply],
  )

  const updateDraft = useCallback(
    (sel: DashboardSelector, value: unknown) => {
      setDraft((prev) => {
        const next = { ...prev, [sel.name]: value }

        if (autoApply) {
          if (debounceTimer.current) clearTimeout(debounceTimer.current)
          const delay = sel.selector_type === 'text' ? TEXT_DEBOUNCE_MS : DEFAULT_DEBOUNCE_MS
          debounceTimer.current = setTimeout(() => dispatch(next), delay)
        }

        return next
      })
    },
    [autoApply, dispatch],
  )

  const handleApply = () => {
    if (debounceTimer.current) clearTimeout(debounceTimer.current)
    dispatch(draft)
  }

  const handleReset = () => {
    if (debounceTimer.current) clearTimeout(debounceTimer.current)
    setDraft({})
    lastDispatchedJson.current = '{}'
    onApply({})
  }

  const hasActiveFilters = !isEmpty(draft) && Object.values(draft).some((v) => !isEmpty(v))

  if (selectors.length === 0) return null

  // Selectors are laid out in a single horizontal row (wrapping only when
  // the viewport can't fit them). Per-type widths are chosen so every
  // selector sits on one line — date_range is wider because it has to host
  // from/to inputs + four preset chips, while dropdown/text are narrow.
  const typeClass = (sel: DashboardSelector): string => {
    switch (sel.selector_type) {
      case 'date_range':
        return 'flex-shrink-0'
      case 'single_date':
        return 'w-[150px] flex-shrink-0'
      case 'dropdown':
      case 'multi_select':
        return 'w-[200px] flex-shrink-0'
      case 'text':
      default:
        return 'w-[180px] flex-shrink-0'
    }
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg px-3 py-2 mb-4">
      <div className="flex flex-wrap gap-x-4 gap-y-2 items-center">
        {selectors.map((sel) => (
          <div key={sel.id} className={`flex items-center gap-2 ${typeClass(sel)}`}>
            <label className="text-xs text-gray-500 whitespace-nowrap">
              {sel.label}
              {sel.is_required && <span className="text-red-500 ml-0.5">*</span>}
            </label>
            <div className="flex-1 min-w-0">
              {sel.selector_type === 'dropdown' && (
                <DropdownSelector
                  options={options[sel.id] || []}
                  value={draft[sel.name] ?? null}
                  onChange={(v) => updateDraft(sel, v)}
                  loading={loadingOpts}
                />
              )}
              {sel.selector_type === 'multi_select' && (
                <MultiSelectSelector
                  options={options[sel.id] || []}
                  value={(draft[sel.name] as unknown[]) || []}
                  onChange={(v) => updateDraft(sel, v)}
                  loading={loadingOpts}
                />
              )}
              {sel.selector_type === 'date_range' && (
                <DateRangeSelector
                  value={(draft[sel.name] as { from?: string; to?: string }) || null}
                  onChange={(v) => updateDraft(sel, v)}
                />
              )}
              {sel.selector_type === 'single_date' && (
                <SingleDateSelector
                  value={(draft[sel.name] as string) || null}
                  onChange={(v) => updateDraft(sel, v)}
                />
              )}
              {sel.selector_type === 'text' && (
                <TextSelector
                  value={(draft[sel.name] as string) || null}
                  onChange={(v) => updateDraft(sel, v)}
                />
              )}
            </div>
          </div>
        ))}

        <div className="flex gap-2 items-center ml-auto">
          {!autoApply && (
            <button
              onClick={handleApply}
              className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
            >
              {t('selectors.applyFilters')}
            </button>
          )}
          {hasActiveFilters && (
            <button
              onClick={handleReset}
              className="px-3 py-1 text-gray-500 text-sm rounded border border-gray-300 hover:bg-gray-50 transition-colors"
            >
              {t('selectors.resetFilters')}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
