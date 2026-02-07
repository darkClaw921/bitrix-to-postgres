import { useTranslation } from '../../i18n'

interface TextSelectorProps {
  value: string | null
  onChange: (value: string | null) => void
  placeholder?: string
}

export default function TextSelector({ value, onChange, placeholder }: TextSelectorProps) {
  const { t } = useTranslation()

  return (
    <input
      type="text"
      value={value || ''}
      onChange={(e) => onChange(e.target.value || null)}
      className="px-2 py-1.5 border border-gray-300 rounded text-sm bg-white min-w-[140px]"
      placeholder={placeholder || t('selectors.enterValue')}
    />
  )
}
