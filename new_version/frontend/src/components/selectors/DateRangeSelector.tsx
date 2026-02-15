import { useTranslation } from '../../i18n'

interface DateRangeValue {
  from?: string
  to?: string
}

interface Props {
  value: DateRangeValue | null
  onChange: (value: DateRangeValue | null) => void
}

export default function DateRangeSelector({ value, onChange }: Props) {
  const { t } = useTranslation()
  const current = value || {}

  const setPreset = (days: number) => {
    const to = new Date()
    const from = new Date()
    from.setDate(from.getDate() - days)
    onChange({
      from: from.toISOString().split('T')[0],
      to: to.toISOString().split('T')[0],
    })
  }

  const setQuarter = () => {
    const now = new Date()
    const quarter = Math.floor(now.getMonth() / 3)
    const from = new Date(now.getFullYear(), quarter * 3, 1)
    onChange({
      from: from.toISOString().split('T')[0],
      to: now.toISOString().split('T')[0],
    })
  }

  return (
    <div className="space-y-1.5">
      <div className="flex gap-1.5">
        <div className="flex-1">
          <label className="text-[10px] text-gray-400 uppercase">{t('selectors.from')}</label>
          <input
            type="date"
            className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
            value={current.from || ''}
            onChange={(e) => onChange({ ...current, from: e.target.value || undefined })}
          />
        </div>
        <div className="flex-1">
          <label className="text-[10px] text-gray-400 uppercase">{t('selectors.to')}</label>
          <input
            type="date"
            className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
            value={current.to || ''}
            onChange={(e) => onChange({ ...current, to: e.target.value || undefined })}
          />
        </div>
      </div>
      <div className="flex gap-1 flex-wrap">
        {[
          { label: t('selectors.today'), action: () => setPreset(0) },
          { label: t('selectors.last7Days'), action: () => setPreset(7) },
          { label: t('selectors.lastMonth'), action: () => setPreset(30) },
          { label: t('selectors.lastQuarter'), action: () => setQuarter() },
        ].map((preset) => (
          <button
            key={preset.label}
            className="px-2 py-0.5 text-[11px] bg-gray-100 hover:bg-gray-200 rounded text-gray-600"
            onClick={preset.action}
          >
            {preset.label}
          </button>
        ))}
      </div>
    </div>
  )
}
