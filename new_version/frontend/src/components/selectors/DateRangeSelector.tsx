import { useTranslation } from '../../i18n'
import { isDateToken, resolveDateToken } from '../../utils/dateTokens'

interface DateRangeValue {
  from?: string
  to?: string
}

interface Props {
  value: DateRangeValue | null
  onChange: (value: DateRangeValue | null) => void
}

// Resolve token-or-date to a date string suitable for <input type="date">.
function toInputDate(v: string | undefined): string {
  if (!v) return ''
  return isDateToken(v) ? (resolveDateToken(v) as string) : v
}

export default function DateRangeSelector({ value, onChange }: Props) {
  const { t } = useTranslation()
  const current = value || {}

  // Token-based presets — these snap from/to to backend-recognized tokens so
  // that defaults stay "live" if the user saves the selector configuration.
  const setTokenRange = (fromToken: string, toToken: string) => {
    onChange({ from: fromToken, to: toToken })
  }

  return (
    <div className="space-y-1.5">
      <div className="flex gap-1.5">
        <div className="flex-1">
          <label className="text-[10px] text-gray-400 uppercase">{t('selectors.from')}</label>
          <input
            type="date"
            className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
            value={toInputDate(current.from)}
            onChange={(e) => onChange({ ...current, from: e.target.value || undefined })}
          />
        </div>
        <div className="flex-1">
          <label className="text-[10px] text-gray-400 uppercase">{t('selectors.to')}</label>
          <input
            type="date"
            className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
            value={toInputDate(current.to)}
            onChange={(e) => onChange({ ...current, to: e.target.value || undefined })}
          />
        </div>
      </div>
      <div className="flex gap-1 flex-wrap">
        {[
          { label: t('selectors.today'), from: 'TODAY', to: 'TODAY' },
          { label: t('selectors.last7Days'), from: 'LAST_7_DAYS', to: 'TODAY' },
          { label: t('selectors.lastMonth'), from: 'LAST_30_DAYS', to: 'TODAY' },
          { label: t('selectors.lastQuarter'), from: 'THIS_QUARTER_START', to: 'TODAY' },
        ].map((preset) => (
          <button
            key={preset.label}
            className="px-2 py-0.5 text-[11px] bg-gray-100 hover:bg-gray-200 rounded text-gray-600"
            onClick={() => setTokenRange(preset.from, preset.to)}
          >
            {preset.label}
          </button>
        ))}
      </div>
    </div>
  )
}
