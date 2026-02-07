import { useState, useRef, useEffect } from 'react'
import { useTranslation } from '../../i18n'

const getOptValue = (opt: unknown): string =>
  typeof opt === 'object' && opt !== null && 'value' in opt ? String((opt as { value: unknown }).value) : String(opt)

const getOptLabel = (opt: unknown): string =>
  typeof opt === 'object' && opt !== null && 'label' in opt ? String((opt as { label: unknown }).label) : String(opt)

interface MultiSelectSelectorProps {
  value: string[] | null
  onChange: (value: string[] | null) => void
  options: unknown[]
  placeholder?: string
}

export default function MultiSelectSelector({ value, onChange, options, placeholder }: MultiSelectSelectorProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const selected = value || []
  const { t } = useTranslation()

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const toggle = (val: string) => {
    const next = selected.includes(val)
      ? selected.filter((v) => v !== val)
      : [...selected, val]
    onChange(next.length > 0 ? next : null)
  }

  const displayText = selected.length > 0 ? `${selected.length} ${t('selectors.selected')}` : (placeholder || t('selectors.select'))

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="px-2 py-1.5 border border-gray-300 rounded text-sm bg-white min-w-[140px] text-left flex items-center justify-between"
      >
        <span className={selected.length > 0 ? 'text-gray-900' : 'text-gray-400'}>
          {displayText}
        </span>
        <svg className="w-3 h-3 ml-2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute z-50 mt-1 bg-white border border-gray-200 rounded shadow-lg max-h-48 overflow-auto min-w-[180px]">
          {options.map((opt) => {
            const val = getOptValue(opt)
            const lbl = getOptLabel(opt)
            const checked = selected.includes(val)
            return (
              <label
                key={val}
                className="flex items-center px-3 py-1.5 hover:bg-gray-50 cursor-pointer text-sm"
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggle(val)}
                  className="mr-2"
                />
                {lbl}
              </label>
            )
          })}
          {options.length === 0 && (
            <div className="px-3 py-2 text-sm text-gray-400">{t('selectors.noOptions')}</div>
          )}
        </div>
      )}
    </div>
  )
}
