import { useTranslation } from '../../i18n'

interface Props {
  value: string | null
  onChange: (value: string | null) => void
}

export default function SingleDateSelector({ value, onChange }: Props) {
  const { t } = useTranslation()

  return (
    <div className="relative">
      <input
        type="date"
        className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
        value={value || ''}
        onChange={(e) => onChange(e.target.value || null)}
      />
      {value && (
        <button
          onClick={() => onChange(null)}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-xs"
          title={t('common.reset')}
        >
          &times;
        </button>
      )}
    </div>
  )
}
