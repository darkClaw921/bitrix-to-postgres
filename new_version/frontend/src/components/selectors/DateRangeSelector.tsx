interface DateRangeSelectorProps {
  value: { from: string; to: string } | null
  onChange: (value: { from: string; to: string } | null) => void
  placeholder?: string
}

export default function DateRangeSelector({ value, onChange, placeholder }: DateRangeSelectorProps) {
  return (
    <div className="flex items-center space-x-1">
      <input
        type="date"
        value={value?.from || ''}
        onChange={(e) =>
          onChange(e.target.value ? { from: e.target.value, to: value?.to || '' } : null)
        }
        className="px-2 py-1.5 border border-gray-300 rounded text-sm bg-white"
        placeholder={placeholder || 'From'}
      />
      <span className="text-gray-400 text-xs">—</span>
      <input
        type="date"
        value={value?.to || ''}
        onChange={(e) =>
          onChange(e.target.value ? { from: value?.from || '', to: e.target.value } : null)
        }
        className="px-2 py-1.5 border border-gray-300 rounded text-sm bg-white"
        placeholder="To"
      />
    </div>
  )
}
