// Date token resolution shared between selectors and the public dashboard.
// The backend resolves the same tokens in `app/domain/services/date_tokens.py`,
// so the two sides MUST stay in sync.

export const DATE_TOKENS = [
  'TODAY',
  'YESTERDAY',
  'TOMORROW',
  'LAST_7_DAYS',
  'LAST_14_DAYS',
  'LAST_30_DAYS',
  'LAST_90_DAYS',
  'THIS_MONTH_START',
  'LAST_MONTH_START',
  'THIS_QUARTER_START',
  'LAST_QUARTER_START',
  'THIS_YEAR_START',
  'LAST_YEAR_START',
  'YEAR_START',
] as const

export type DateToken = (typeof DATE_TOKENS)[number]

const DATE_ONLY_RE = /^\d{4}-\d{2}-\d{2}$/

const pad = (n: number): string => String(n).padStart(2, '0')
const fmt = (d: Date): string =>
  `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`

function quarterStart(d: Date): Date {
  const month = Math.floor(d.getMonth() / 3) * 3
  return new Date(d.getFullYear(), month, 1)
}

export function isDateToken(value: unknown): value is DateToken {
  return typeof value === 'string' && (DATE_TOKENS as readonly string[]).includes(value)
}

export function isDateOnly(value: unknown): boolean {
  return typeof value === 'string' && DATE_ONLY_RE.test(value)
}

/**
 * Resolve a date token to a `YYYY-MM-DD` string. Pass-through for anything that
 * is not a recognized token.
 */
export function resolveDateToken(value: unknown): unknown {
  if (!isDateToken(value)) return value

  const now = new Date()

  switch (value) {
    case 'TODAY':
      return fmt(now)
    case 'YESTERDAY': {
      const d = new Date(now)
      d.setDate(d.getDate() - 1)
      return fmt(d)
    }
    case 'TOMORROW': {
      const d = new Date(now)
      d.setDate(d.getDate() + 1)
      return fmt(d)
    }
    case 'LAST_7_DAYS': {
      const d = new Date(now)
      d.setDate(d.getDate() - 7)
      return fmt(d)
    }
    case 'LAST_14_DAYS': {
      const d = new Date(now)
      d.setDate(d.getDate() - 14)
      return fmt(d)
    }
    case 'LAST_30_DAYS': {
      const d = new Date(now)
      d.setDate(d.getDate() - 30)
      return fmt(d)
    }
    case 'LAST_90_DAYS': {
      const d = new Date(now)
      d.setDate(d.getDate() - 90)
      return fmt(d)
    }
    case 'THIS_MONTH_START':
      return fmt(new Date(now.getFullYear(), now.getMonth(), 1))
    case 'LAST_MONTH_START':
      return fmt(new Date(now.getFullYear(), now.getMonth() - 1, 1))
    case 'THIS_QUARTER_START':
      return fmt(quarterStart(now))
    case 'LAST_QUARTER_START': {
      const thisQ = quarterStart(now)
      const prevQ = new Date(thisQ)
      prevQ.setMonth(prevQ.getMonth() - 3)
      return fmt(prevQ)
    }
    case 'THIS_YEAR_START':
    case 'YEAR_START':
      return fmt(new Date(now.getFullYear(), 0, 1))
    case 'LAST_YEAR_START':
      return fmt(new Date(now.getFullYear() - 1, 0, 1))
    default:
      return value
  }
}

/**
 * Resolve any date tokens hiding inside a filter value, mirroring the backend
 * `resolve_filter_value` shape: handles dicts (`{from, to}`), arrays, scalars.
 */
export function resolveFilterValue(value: unknown): unknown {
  if (value === null || value === undefined) return value
  if (Array.isArray(value)) return value.map(resolveDateToken)
  if (typeof value === 'object') {
    const out: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      out[k] = resolveDateToken(v)
    }
    return out
  }
  return resolveDateToken(value)
}

/**
 * Human-readable label for a token (used in dropdowns and tooltips).
 */
export function tokenLabel(token: DateToken): string {
  switch (token) {
    case 'TODAY':
      return 'Сегодня'
    case 'YESTERDAY':
      return 'Вчера'
    case 'TOMORROW':
      return 'Завтра'
    case 'LAST_7_DAYS':
      return '7 дней назад'
    case 'LAST_14_DAYS':
      return '14 дней назад'
    case 'LAST_30_DAYS':
      return '30 дней назад'
    case 'LAST_90_DAYS':
      return '90 дней назад'
    case 'THIS_MONTH_START':
      return 'Начало месяца'
    case 'LAST_MONTH_START':
      return 'Начало прошлого месяца'
    case 'THIS_QUARTER_START':
      return 'Начало квартала'
    case 'LAST_QUARTER_START':
      return 'Начало прошлого квартала'
    case 'THIS_YEAR_START':
    case 'YEAR_START':
      return 'Начало года'
    case 'LAST_YEAR_START':
      return 'Начало прошлого года'
    default:
      return token
  }
}
