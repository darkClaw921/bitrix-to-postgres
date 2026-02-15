import { useTranslation } from '../../i18n'
import type { SelectorOption } from '../../services/api'

interface Props {
  options: SelectorOption[]
  value: unknown
  onChange: (value: unknown) => void
  loading?: boolean
}

export default function DropdownSelector({ options, value, onChange, loading }: Props) {
  const { t } = useTranslation()

  return (
    <div className="relative">
      <select
        className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm bg-white focus:ring-1 focus:ring-blue-500 focus:border-blue-500 appearance-none pr-8"
        value={value != null ? String(value) : ''}
        onChange={(e) => {
          const val = e.target.value
          if (val === '') {
            onChange(null)
          } else {
            const opt = options.find((o) => String(o.value) === val)
            onChange(opt ? opt.value : val)
          }
        }}
        disabled={loading}
      >
        <option value="">{t('selectors.allValues')}</option>
        {options.map((opt, i) => (
          <option key={i} value={String(opt.value)}>
            {opt.label}
          </option>
        ))}
      </select>
      {value != null && (
        <button
          onClick={() => onChange(null)}
          className="absolute right-6 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-xs"
          title={t('common.reset')}
        >
          &times;
        </button>
      )}
    </div>
  )
}
