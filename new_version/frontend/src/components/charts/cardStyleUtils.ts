import type { ChartDisplayConfig } from '../../services/api'

type CardStyle = ChartDisplayConfig['cardStyle']

const BORDER_RADIUS_MAP: Record<string, string> = {
  none: 'rounded-none',
  sm: 'rounded',
  md: 'rounded-lg',
  lg: 'rounded-xl',
  xl: 'rounded-2xl',
}

const SHADOW_MAP: Record<string, string> = {
  none: 'shadow-none',
  sm: 'shadow-sm',
  md: 'shadow-md',
  lg: 'shadow-lg',
}

const PADDING_MAP: Record<string, string> = {
  sm: 'p-2',
  md: 'p-4',
  lg: 'p-6',
}

export function getCardStyleClasses(cardStyle?: CardStyle): string {
  if (!cardStyle) return 'card'

  const radius = BORDER_RADIUS_MAP[cardStyle.borderRadius || 'md'] || 'rounded-lg'
  const shadow = SHADOW_MAP[cardStyle.shadow || 'sm'] || 'shadow-sm'
  const padding = PADDING_MAP[cardStyle.padding || 'md'] || 'p-4'

  return `border border-gray-200 ${radius} ${shadow} ${padding}`
}

export function getCardInlineStyle(cardStyle?: CardStyle): React.CSSProperties | undefined {
  if (!cardStyle?.backgroundColor || cardStyle.backgroundColor === '#ffffff') return undefined
  return { backgroundColor: cardStyle.backgroundColor }
}

const TITLE_SIZE_MAP: Record<string, string> = {
  sm: 'text-sm',
  md: 'text-lg',
  lg: 'text-xl',
  xl: 'text-2xl',
}

export function getTitleSizeClass(fontSize?: string): string {
  return TITLE_SIZE_MAP[fontSize || 'md'] || 'text-lg'
}

/**
 * Numeric pixel sizes that mirror `TITLE_SIZE_MAP` (sm=text-sm/14px,
 * md=text-lg/18px, lg=text-xl/20px, xl=text-2xl/24px). Used by TV-mode title
 * rendering, which needs an integer base it can multiply by `fontScale`.
 */
const TITLE_BASE_PX: Record<string, number> = {
  sm: 14,
  md: 18,
  lg: 20,
  xl: 24,
}

/**
 * Base title size in px for TV-mode chart cards. The user can override via
 * `general.titleFontSize` (sm/md/lg/xl) — when set, that value wins so the
 * settings panel works in TV mode the same way it does in the public list view.
 *
 * When the user has not set a size, indicator charts get a larger default
 * (24px) than other chart types (18px) because an indicator has no axes,
 * legend or other text — the title needs to read at a glance beside the
 * single big value.
 */
export function getTvTitleBasePx(chartType: string, fontSize?: string): number {
  if (fontSize && TITLE_BASE_PX[fontSize] != null) {
    return TITLE_BASE_PX[fontSize]
  }
  return chartType === 'indicator' ? 36 : 18
}
