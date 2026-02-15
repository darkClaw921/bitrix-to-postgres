import { useState, useEffect, useRef } from 'react'
import { useTranslation } from '../../i18n'

interface Props {
  value: string | null
  onChange: (value: string | null) => void
}

export default function TextSelector({ value, onChange }: Props) {
  const { t } = useTranslation()
  const [local, setLocal] = useState(value || '')
  const timerRef = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    setLocal(value || '')
  }, [value])

  const handleChange = (v: string) => {
    setLocal(v)
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      onChange(v || null)
    }, 300)
  }

  return (
    <div className="relative">
      <input
        type="text"
        className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
        placeholder={t('selectors.search')}
        value={local}
        onChange={(e) => handleChange(e.target.value)}
      />
      {local && (
        <button
          onClick={() => { setLocal(''); onChange(null) }}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-xs"
          title={t('common.reset')}
        >
          &times;
        </button>
      )}
    </div>
  )
}
