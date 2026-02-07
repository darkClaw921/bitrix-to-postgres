interface SingleDateSelectorProps {
  value: string | null
  onChange: (value: string | null) => void
  placeholder?: string
}

export default function SingleDateSelector({ value, onChange, placeholder }: SingleDateSelectorProps) {
  return (
    <input
      type="date"
      value={value || ''}
      onChange={(e) => onChange(e.target.value || null)}
      className="px-2 py-1.5 border border-gray-300 rounded text-sm bg-white"
      placeholder={placeholder || 'Select date'}
    />
  )
}
