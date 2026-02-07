import { useTranslation } from '../i18n'
import type { Locale } from '../i18n'

const LOCALES: { value: Locale; label: string }[] = [
  { value: 'ru', label: 'RU' },
  { value: 'en', label: 'EN' },
]

export default function LanguageSwitcher() {
  const { locale, setLocale } = useTranslation()

  return (
    <div className="inline-flex rounded-md overflow-hidden border border-gray-300">
      {LOCALES.map((l) => (
        <button
          key={l.value}
          onClick={() => setLocale(l.value)}
          className={`px-2.5 py-1 text-xs font-medium transition-colors ${
            locale === l.value
              ? 'bg-primary-600 text-white'
              : 'bg-white text-gray-600 hover:bg-gray-50'
          }`}
        >
          {l.label}
        </button>
      ))}
    </div>
  )
}
