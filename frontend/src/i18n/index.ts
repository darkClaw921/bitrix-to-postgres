import { createContext, useContext, useState, useCallback, createElement } from 'react'
import type { ReactNode } from 'react'
import type { Locale, Translations } from './types'
import { ru } from './locales/ru'
import { en } from './locales/en'

const STORAGE_KEY = 'locale'
const DEFAULT_LOCALE: Locale = 'ru'

const translations: Record<Locale, Translations> = { ru, en }

function getStoredLocale(): Locale {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'ru' || stored === 'en') return stored
  } catch {}
  return DEFAULT_LOCALE
}

interface I18nContextValue {
  locale: Locale
  setLocale: (l: Locale) => void
  t: (key: string) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(getStoredLocale)

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l)
    try {
      localStorage.setItem(STORAGE_KEY, l)
    } catch {}
  }, [])

  const t = useCallback(
    (key: string): string => {
      const parts = key.split('.')
      let current: unknown = translations[locale]
      for (const part of parts) {
        if (current && typeof current === 'object' && part in current) {
          current = (current as Record<string, unknown>)[part]
        } else {
          return key
        }
      }
      return typeof current === 'string' ? current : key
    },
    [locale],
  )

  return createElement(
    I18nContext.Provider,
    { value: { locale, setLocale, t } },
    children,
  )
}

export function useTranslation() {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useTranslation must be used within I18nProvider')
  return ctx
}

export type { Locale, Translations }
