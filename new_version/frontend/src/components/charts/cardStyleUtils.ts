import type React from 'react'
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
 * md=text-lg/18px, lg=text-xl/20px, xl=text-2xl/24px).
 */
const TITLE_BASE_PX: Record<string, number> = {
  sm: 14,
  md: 18,
  lg: 20,
  xl: 24,
}

/**
 * Parse title font size string:
 *  - legacy presets ('sm'→14, 'md'→18, 'lg'→20, 'xl'→24)
 *  - numeric string ('16' → 16)
 *  - undefined/null → undefined
 */
export function parseTitleFontSizePx(fontSize?: string): number | undefined {
  if (!fontSize) return undefined
  if (TITLE_BASE_PX[fontSize] != null) return TITLE_BASE_PX[fontSize]
  const n = parseInt(fontSize, 10)
  return !isNaN(n) ? n : undefined
}

/**
 * Returns inline style object for title font size. Use instead of getTitleSizeClass
 * when you need numeric/slider values to work alongside legacy sm/md/lg/xl presets.
 */
export function getTitleSizeStyle(fontSize?: string): React.CSSProperties {
  const px = parseTitleFontSizePx(fontSize)
  return px != null ? { fontSize: `${px}px` } : {}
}
