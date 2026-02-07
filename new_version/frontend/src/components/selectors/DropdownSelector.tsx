import { useTranslation } from '../../i18n'

const getOptValue = (opt: unknown): string =>
  typeof opt === 'object' && opt !== null && 'value' in opt ? String((opt as { value: unknown }).value) : String(opt)

const getOptLabel = (opt: unknown): string =>
  typeof opt === 'object' && opt !== null && 'label' in opt ? String((opt as { label: unknown }).label) : String(opt)

interface DropdownSelectorProps {
  value: string | null
  onChange: (value: string | null) => void
  options: unknown[]
  placeholder?: string
}

export default function DropdownSelector({ value, onChange, options, placeholder }: DropdownSelectorProps) {
  const { t } = useTranslation()

  return (
    <select
      value={value || ''}
      onChange={(e) => onChange(e.target.value || null)}
      className="px-2 py-1.5 border border-gray-300 rounded text-sm bg-white min-w-[140px]"
    >
      <option value="">{placeholder || t('selectors.select')}</option>
      {options.map((opt) => (
        <option key={getOptValue(opt)} value={getOptValue(opt)}>
          {getOptLabel(opt)}
        </option>
      ))}
    </select>
  )
}
