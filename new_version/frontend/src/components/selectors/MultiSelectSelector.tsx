import { useState, useRef, useEffect } from 'react'
import { useTranslation } from '../../i18n'
import type { SelectorOption } from '../../services/api'

interface Props {
  options: SelectorOption[]
  value: unknown[]
  onChange: (value: unknown[]) => void
  loading?: boolean
}

export default function MultiSelectSelector({ options, value, onChange, loading }: Props) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const selectedSet = new Set((value || []).map(String))
  const filtered = options.filter(
    (o) => o.label.toLowerCase().includes(search.toLowerCase()),
  )

  const toggle = (optValue: unknown) => {
    const key = String(optValue)
    if (selectedSet.has(key)) {
      onChange(value.filter((v) => String(v) !== key))
    } else {
      onChange([...value, optValue])
    }
  }

  const label = value.length > 0
    ? `${value.length} ${t('selectors.selected')}`
    : t('selectors.allValues')

  return (
    <div className="relative" ref={ref}>
      <button
        className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm bg-white text-left focus:ring-1 focus:ring-blue-500 focus:border-blue-500 flex items-center justify-between"
        onClick={() => setOpen(!open)}
        disabled={loading}
      >
        <span className={value.length > 0 ? 'text-gray-800' : 'text-gray-400'}>{label}</span>
        <svg className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute z-50 mt-1 w-full bg-white border border-gray-200 rounded shadow-lg max-h-60 overflow-auto">
          <div className="p-1.5 border-b">
            <input
              type="text"
              className="w-full border border-gray-200 rounded px-2 py-1 text-sm"
              placeholder={t('selectors.search')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              autoFocus
            />
          </div>
          <div className="flex gap-1 px-2 py-1 border-b text-xs">
            <button
              className="text-blue-600 hover:underline"
              onClick={() => onChange(options.map((o) => o.value))}
            >
              {t('selectors.selectAll')}
            </button>
            <span className="text-gray-300">|</span>
            <button
              className="text-blue-600 hover:underline"
              onClick={() => onChange([])}
            >
              {t('selectors.deselectAll')}
            </button>
          </div>
          {filtered.map((opt, i) => (
            <label
              key={i}
              className="flex items-center px-2 py-1.5 hover:bg-gray-50 cursor-pointer text-sm"
            >
              <input
                type="checkbox"
                checked={selectedSet.has(String(opt.value))}
                onChange={() => toggle(opt.value)}
                className="mr-2 rounded"
              />
              {opt.label}
            </label>
          ))}
          {filtered.length === 0 && (
            <div className="px-2 py-3 text-center text-sm text-gray-400">
              {t('charts.noData')}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
