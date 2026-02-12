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
