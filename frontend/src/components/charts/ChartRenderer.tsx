import { useState, useMemo, useEffect } from 'react'
import {
  BarChart, Bar,
  LineChart, Line,
  PieChart, Pie, Cell,
  AreaChart, Area,
  ScatterChart, Scatter,
  FunnelChart, Funnel, LabelList,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer,
} from 'recharts'
import type { ChartSpec, DesignLayout } from '../../services/api'
import { useElementSize } from '../../hooks/useElementSize'
import { useTranslation } from '../../i18n'

/**
 * Formats a numeric indicator value according to user-chosen options:
 *  - decimals: 0..6 (rounds to that many fractional digits)
 *  - format:
 *      'number'   → locale grouping ("3 337 172,29")
 *      'currency' → prefixed with `currencySymbol` ("$3 337 172,29")
 *      'percent'  → suffixed with "%" ("12,5 %")
 *      'compact'  → K/M/B/T abbreviation ("3,3 M")
 *
 * Falls through to plain `toLocaleString()` when no format is set, preserving
 * the historical behavior for indicators that have not opted into formatting.
 */
function formatIndicatorNumber(
  value: number,
  format: 'number' | 'currency' | 'percent' | 'compact' | undefined,
  decimals: number | undefined,
  currencySymbol: string | undefined,
): string {
  if (!Number.isFinite(value)) return String(value)

  // No format chosen → preserve legacy `toLocaleString()` output but still
  // honor `decimals` if the user picked one.
  if (!format) {
    return decimals != null
      ? value.toLocaleString(undefined, {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        })
      : value.toLocaleString()
  }

  if (format === 'compact') {
    // Custom compact: divide by the appropriate magnitude and append the
    // suffix manually so the result respects the user's `decimals` setting.
    // `Intl.NumberFormat({ notation: 'compact' })` ignores `maximumFractionDigits`
    // in some locales, hence the hand-rolled fallback.
    const abs = Math.abs(value)
    const tiers: Array<[number, string]> = [
      [1e12, 'T'],
      [1e9, 'B'],
      [1e6, 'M'],
      [1e3, 'K'],
    ]
    for (const [tierValue, suffix] of tiers) {
      if (abs >= tierValue) {
        const scaled = value / tierValue
        const d = decimals ?? 1
        return `${scaled.toLocaleString(undefined, {
          minimumFractionDigits: d,
          maximumFractionDigits: d,
        })} ${suffix}`
      }
    }
    return value.toLocaleString(undefined, {
      minimumFractionDigits: decimals ?? 0,
      maximumFractionDigits: decimals ?? 0,
    })
  }

  const opts: Intl.NumberFormatOptions =
    decimals != null
      ? { minimumFractionDigits: decimals, maximumFractionDigits: decimals }
      : {}
  const formatted = value.toLocaleString(undefined, opts)
  if (format === 'currency') return `${currencySymbol || '₽'}${formatted}`
  if (format === 'percent') return `${formatted}%`
  return formatted
}

const DEFAULT_COLORS = [
  '#8884d8', '#82ca9d', '#ffc658', '#ff7300',
  '#0088fe', '#00c49f', '#ffbb28', '#ff8042',
]

interface ChartRendererProps {
  spec: ChartSpec
  data: Record<string, unknown>[]
  height?: number | string
  designLayout?: DesignLayout
  fontScale?: number
  fillHeight?: boolean
}

function formatValue(value: number, format?: 'number' | 'currency' | 'percent'): string {
  if (format === 'currency') return `$${value.toLocaleString()}`
  if (format === 'percent') return `${value}%`
  return value.toLocaleString()
}

function formatTableCell(value: unknown, format?: 'number' | 'currency' | 'percent' | 'text'): string {
  if (value == null) return ''
  if (format === 'text' || typeof value === 'string') return String(value)
  const num = Number(value)
  if (isNaN(num)) return String(value)
  if (format === 'currency') return `$${num.toLocaleString()}`
  if (format === 'percent') return `${num}%`
  return num.toLocaleString()
}

function IndicatorRenderer({
  spec,
  data,
  fontScale,
  fillHeight,
}: {
  spec: ChartSpec
  data: Record<string, unknown>[]
  fontScale?: number
  fillHeight?: boolean
}) {
  const indicatorCfg = spec.indicator ?? {}
  const yKeys = Array.isArray(spec.data_keys.y) ? spec.data_keys.y : [spec.data_keys.y]
  const valueKey = yKeys[0]
  const row = data[0] || {}
  const rawValue = row[valueKey]
  const numValue = Number(rawValue)
  const isNumeric = !isNaN(numValue) && rawValue != null && rawValue !== ''
  const displayValue = isNumeric
    ? formatIndicatorNumber(
        numValue,
        indicatorCfg.format,
        indicatorCfg.decimals,
        indicatorCfg.currencySymbol,
      )
    : String(rawValue ?? '')

  // Base font size in rem comes from the user's preset (sm/md/lg/xl).
  // In TV mode `fontScale` further scales it to match cell size.
  const baseRemMap: Record<'sm' | 'md' | 'lg' | 'xl', number> = { sm: 1.5, md: 2.5, lg: 3.5, xl: 5 }
  const baseRem = baseRemMap[indicatorCfg.fontSize || 'lg'] ?? 3.5
  const requestedSizePx = baseRem * 16 * (fontScale ?? 1)

  // The renderer runs in three families of contexts that need different sizing
  // strategies:
  //   1. "Fill" mode (fillHeight=true) — TV mode and the dashboard editor body:
  //      the parent has an INTENTIONALLY set definite height (RGL cell or
  //      flex-1 min-h-0 column). Here we want the value to fill almost the
  //      whole cell vertically — derive the font size from the measured
  //      container height. Width is intentionally not a constraint.
  //   2. "Compact" mode (fillHeight=false) — All Charts page (ChartCard) and
  //      embed pages: the parent is either a CSS grid that stretches all
  //      siblings to the tallest item or a fixed pixel height from layout. In
  //      both cases, blindly filling height makes the indicator value
  //      ridiculously large because the cell height is determined by other
  //      content. Here we use the user-chosen preset size and only shrink it
  //      if the cell happens to be smaller than the preset.
  const { ref: fitRef, height: containerHeight } = useElementSize<HTMLDivElement>()
  const autoFit = indicatorCfg.autoFit !== false

  let finalSizePx: number
  if (fillHeight) {
    finalSizePx = autoFit && containerHeight > 0
      ? Math.max(10, containerHeight * 0.9)
      : Math.max(10, requestedSizePx)
  } else {
    // Compact mode: never grow above the preset; only shrink if the cell is
    // smaller than the preset (the original pre-fill behavior).
    const cap = autoFit && containerHeight > 0 ? containerHeight * 0.9 : Infinity
    finalSizePx = Math.max(10, Math.min(requestedSizePx, cap))
  }

  // Wrapper height behavior also differs between modes:
  //   - Fill: take 100% of the parent (h-full). No minHeight — the parent
  //     container provides a definite height (RGL cell in editor/TV/embed).
  //     Adding minHeight here would cause a jump at small card sizes because
  //     the floor conflicts with containerHeight * 0.9 scaling.
  //   - Compact: do NOT use h-full — otherwise CSS grid stretch on the All
  //     Charts page would inflate the wrapper to the row height (and the
  //     value with it). Use auto height with a minHeight floor so the card
  //     stays the size of its content + small padding.
  const wrapperStyle: React.CSSProperties = fillHeight ? {} : { minHeight: 80 }

  // Horizontal alignment: defaults to center for backward compatibility, but
  // users can opt into left/right via the settings panel.
  const textAlign = indicatorCfg.textAlign || 'center'
  const justifyClass =
    textAlign === 'left' ? 'justify-start' : textAlign === 'right' ? 'justify-end' : 'justify-center'
  const textAlignClass =
    textAlign === 'left' ? 'text-left' : textAlign === 'right' ? 'text-right' : 'text-center'

  const heightClass = fillHeight ? 'h-full' : ''

  return (
    <div
      ref={fitRef}
      className={`flex items-center w-full ${heightClass} overflow-hidden px-1 ${justifyClass}`}
      style={wrapperStyle}
    >
      <div
        className={`font-bold leading-none break-words max-w-full ${textAlignClass}`}
        style={{ fontSize: `${finalSizePx}px`, color: indicatorCfg.color || '#1f2937' }}
      >
        {indicatorCfg.prefix && <span>{indicatorCfg.prefix} </span>}
        {displayValue}
        {indicatorCfg.suffix && <span> {indicatorCfg.suffix}</span>}
      </div>
    </div>
  )
}

function TableRenderer({ spec, data, maxHeight, fontScale }: { spec: ChartSpec; data: Record<string, unknown>[]; maxHeight?: number | string; fontScale?: number }) {
  const { t } = useTranslation()
  const tableCfg = spec.table ?? {}
  const columns = useMemo(() => {
    if (!data.length) return []
    return Object.keys(data[0])
  }, [data])

  const [sortColumn, setSortColumn] = useState<string | null>(tableCfg.defaultSortColumn || null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>(tableCfg.defaultSortDirection || 'asc')
  const [page, setPage] = useState(0)
  const pageSize = tableCfg.pageSize || 0

  useEffect(() => {
    setSortDir(tableCfg.defaultSortDirection || 'asc')
  }, [tableCfg.defaultSortDirection])

  useEffect(() => {
    setSortColumn(tableCfg.defaultSortColumn || null)
  }, [tableCfg.defaultSortColumn])

  const numericColumns = useMemo(() => {
    const set = new Set<string>()
    for (const col of columns) {
      const format = tableCfg.columnFormats?.[col]
      if (format === 'text') continue
      const allNumeric = data.every((row) => {
        const v = row[col]
        return v == null || !isNaN(Number(v))
      })
      if (allNumeric) set.add(col)
    }
    return set
  }, [columns, data, tableCfg.columnFormats])

  const sortedData = useMemo(() => {
    if (!sortColumn) return data
    return [...data].sort((a, b) => {
      const av = a[sortColumn]
      const bv = b[sortColumn]
      if (av == null && bv == null) return 0
      if (av == null) return 1
      if (bv == null) return -1
      if (numericColumns.has(sortColumn)) {
        const diff = Number(av) - Number(bv)
        return sortDir === 'asc' ? diff : -diff
      }
      const cmp = String(av).localeCompare(String(bv))
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [data, sortColumn, sortDir, numericColumns])

  const pagedData = useMemo(() => {
    if (!pageSize) return sortedData
    const start = page * pageSize
    return sortedData.slice(start, start + pageSize)
  }, [sortedData, page, pageSize])

  const totalPages = pageSize ? Math.ceil(sortedData.length / pageSize) : 1

  const columnTotals = useMemo(() => {
    if (!tableCfg.showColumnTotals) return null
    const totals: Record<string, number> = {}
    for (const col of columns) {
      if (numericColumns.has(col)) {
        totals[col] = data.reduce((sum, row) => sum + (Number(row[col]) || 0), 0)
      }
    }
    return totals
  }, [tableCfg.showColumnTotals, columns, data, numericColumns])

  const handleSort = (col: string) => {
    if (!tableCfg.sortable) return
    if (sortColumn === col) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortColumn(col)
      setSortDir('asc')
    }
  }

  const displayColumns = tableCfg.showRowTotals ? [...columns, '__row_total__'] : columns

  // Non-regression: when fontScale is undefined (editor & non-TV embed),
  // preserve the original Tailwind `text-sm` class on the <table> (keeps both
  // font-size: 0.875rem AND line-height: 1.25rem). In TV mode (fontScale
  // defined), fall back to an inline fontSize on the wrapper so the cells
  // scale with the cell size.
  const wrapperStyle: React.CSSProperties = {
    height: maxHeight || '100%',
    maxHeight: maxHeight || undefined,
    overflow: 'hidden',
    ...(fontScale != null ? { fontSize: `${Math.round(14 * fontScale)}px` } : {}),
  }
  const tableClass = fontScale == null ? 'w-full text-sm border-collapse' : 'w-full border-collapse'

  return (
    <div className="flex flex-col" style={wrapperStyle}>
      <div className="overflow-auto flex-1 min-h-0">
        <table className={tableClass}>
          <thead className="sticky top-0 z-10">
            <tr className="bg-gray-100">
              {displayColumns.map((col) => (
                <th
                  key={col}
                  className={`border border-gray-200 px-3 py-2 text-left font-semibold text-gray-700 ${
                    tableCfg.sortable ? 'cursor-pointer hover:bg-gray-200 select-none' : ''
                  }`}
                  onClick={() => col !== '__row_total__' && handleSort(col)}
                >
                  {col === '__row_total__' ? t('common.total') : col}
                  {sortColumn === col && (
                    <span className="ml-1">{sortDir === 'asc' ? '\u25B2' : '\u25BC'}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pagedData.map((row, ri) => {
              const rowTotal = tableCfg.showRowTotals
                ? columns.reduce((sum, col) => sum + (numericColumns.has(col) ? (Number(row[col]) || 0) : 0), 0)
                : 0
              return (
                <tr key={ri} className={ri % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                  {columns.map((col) => (
                    <td key={col} className="border border-gray-200 px-3 py-1.5">
                      {formatTableCell(row[col], tableCfg.columnFormats?.[col])}
                    </td>
                  ))}
                  {tableCfg.showRowTotals && (
                    <td className="border border-gray-200 px-3 py-1.5 font-semibold bg-blue-50">
                      {rowTotal.toLocaleString()}
                    </td>
                  )}
                </tr>
              )
            })}
          </tbody>
          {columnTotals && (
            <tfoot>
              <tr className="bg-gray-100 font-semibold">
                {columns.map((col, i) => (
                  <td key={col} className="border border-gray-200 px-3 py-2">
                    {i === 0 && !numericColumns.has(col)
                      ? t('common.total')
                      : columnTotals[col] != null
                        ? formatTableCell(columnTotals[col], tableCfg.columnFormats?.[col])
                        : ''}
                  </td>
                ))}
                {tableCfg.showRowTotals && (
                  <td className="border border-gray-200 px-3 py-2 bg-blue-50">
                    {Object.values(columnTotals).reduce((a, b) => a + b, 0).toLocaleString()}
                  </td>
                )}
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      {pageSize > 0 && totalPages > 1 && (
        <div className="flex items-center justify-between mt-2 text-xs text-gray-500 flex-shrink-0">
          <span>
            {t('chartRenderer.page')} {page + 1} {t('chartRenderer.ofPages')} {totalPages} ({sortedData.length} {t('chartRenderer.rowsCount')})
          </span>
          <div className="flex gap-1">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-2 py-1 border rounded disabled:opacity-30 hover:bg-gray-100"
            >
              {t('chartRenderer.prev')}
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="px-2 py-1 border rounded disabled:opacity-30 hover:bg-gray-100"
            >
              {t('chartRenderer.next')}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default function ChartRenderer({ spec, data, height = 350, designLayout: designLayoutProp, fontScale, fillHeight }: ChartRendererProps) {
  const { t } = useTranslation()
  // When the user enables `general.fixedFontSize`, we fully ignore the
  // TV/stretch-driven `fontScale` so that axis ticks, legend, labels, indicator
  // value and table cells all keep their preset font size regardless of the
  // surrounding cell size. This is treated as a hard override of the prop.
  const _fixedFontSize = spec.general?.fixedFontSize === true
  const effectiveFontScale = _fixedFontSize ? undefined : fontScale
  const fs = (base: number) => Math.max(8, Math.round(base * (effectiveFontScale ?? 1)))
  const { chart_type, data_keys, colors } = spec
  const palette = colors?.length ? colors : DEFAULT_COLORS
  const xKey = data_keys.x
  const yKeys = Array.isArray(data_keys.y) ? data_keys.y : [data_keys.y]

  // Merge designLayout from prop or spec
  const dl = designLayoutProp ?? spec.designLayout

  // Display config with defaults
  const legendCfg = spec.legend ?? { visible: true, position: 'bottom' }
  const gridCfg = spec.grid ?? { visible: true, strokeDasharray: '3 3' }
  const xAxisCfg = spec.xAxis ?? { label: '', angle: 0 }
  const yAxisCfg = spec.yAxis ?? { label: '', format: 'number' }
  const lineCfg = spec.line ?? { strokeWidth: 2, type: 'monotone' as const }
  const areaCfg = spec.area ?? { fillOpacity: 0.3 }
  const pieCfg = spec.pie ?? { innerRadius: 0, showLabels: true }
  const generalCfg = spec.general ?? {}

  const yTickFormatter = (v: number) => formatValue(v, yAxisCfg.format)
  const tooltipFormatter = (v: number | undefined) => formatValue(v ?? 0, yAxisCfg.format)

  // General settings
  const showTooltip = generalCfg.showTooltip !== false
  const isAnimated = generalCfg.animate !== false
  const showDataLabels = generalCfg.showDataLabels || false
  // Defaults tuned so the first/last X-tick labels and Y-tick labels do not get
  // clipped at the plot edges. Recharts places tick text centered on the tick,
  // so a zero left/right margin cuts ~half the leftmost/rightmost label.
  // Bottom defaults to 20 to leave room for the X-axis label row; when the
  // user rotates X-ticks we bump it further below.
  const defaultMargin = { top: 10, right: 30, bottom: 20, left: 10 }
  const baseMargin = generalCfg.margins
    ? { ...defaultMargin, ...generalCfg.margins }
    : { ...defaultMargin }
  // Rotated X-axis ticks need extra vertical room — `tick.height: 60` only
  // allocates the tick area inside the plot, not outside margin. Without this
  // the rotated labels get clipped against the card border. Rotation also
  // makes the leftmost label extend to the LEFT of its tick (textAnchor=end),
  // so we also widen left/right margins proportional to rotation magnitude.
  const userMargins = generalCfg.margins ?? {}
  // All margin reservations below are computed in 12px-base units, then
  // scaled by `fontScale` so TV/preview mode (which blows up tick font via
  // `fs()`) gets proportionally larger reservations. Without this scaling
  // rotated dates and bottom legends get clipped again at large fontScale.
  const fScale = effectiveFontScale ?? 1
  const scaled = (px: number) => Math.round(px * fScale)

  // Whether the legend takes room along the bottom of the chart (default
  // placement). We need to reserve extra bottom margin for it, because
  // Recharts places the bottom legend INSIDE the chart's bottom margin —
  // if rotated X-axis ticks already consumed that space, the legend gets
  // clipped by the card border.
  const _legendHasDesignPos = dl?.legend && (dl.legend.x != null || dl.legend.y != null)
  const legendAtBottom =
    legendCfg.visible &&
    !_legendHasDesignPos &&
    (legendCfg.position == null || legendCfg.position === 'bottom')
  const legendReserve = legendAtBottom ? scaled(24) : 0

  // Dynamically compute how much room rotated X-axis tick labels need. At
  // angle θ, a label of width W projects horizontally as |W·cos θ| + |H·sin θ|
  // and vertically as |W·sin θ| + |H·cos θ|. W is approximated from the
  // longest label's character count (~0.58em per char) at the current tick
  // font size. This is far more robust than a fixed 50px — it adapts to both
  // long labels (e.g. "2026-01-12") and to TV mode's larger fontScale.
  const maxLabelChars = data.reduce((m, row) => {
    const s = String(row[xKey] ?? '')
    return s.length > m ? s.length : m
  }, 0)
  const tickFontPx = fs(12)
  const approxLabelWidthPx = Math.max(1, maxLabelChars) * tickFontPx * 0.58
  const approxLabelHeightPx = tickFontPx * 1.1
  const angleRad = ((Math.abs(xAxisCfg.angle ?? 0)) * Math.PI) / 180
  const horizOverhang = Math.ceil(
    approxLabelWidthPx * Math.cos(angleRad) + approxLabelHeightPx * Math.sin(angleRad)
  )
  const vertOverhang = Math.ceil(
    approxLabelWidthPx * Math.sin(angleRad) + approxLabelHeightPx * Math.cos(angleRad)
  )
  // +16px safety margin beyond the geometric overhang: the approximation
  // underestimates real rendered text width (font metrics, kerning, SVG
  // subpixel rounding) and the cost of a slightly looser reservation is
  // much smaller than the cost of a clipped character.
  const sidePad = horizOverhang + 16
  const bottomPad = vertOverhang + 16

  if (xAxisCfg.angle) {
    if (userMargins.bottom == null) {
      baseMargin.bottom = Math.max(baseMargin.bottom ?? 0, bottomPad + legendReserve)
    }
    if (userMargins.left == null) {
      baseMargin.left = Math.max(baseMargin.left ?? 0, sidePad)
    }
    if (userMargins.right == null) {
      baseMargin.right = Math.max(baseMargin.right ?? 0, sidePad)
    }
  } else if (legendAtBottom && userMargins.bottom == null) {
    // Even without rotation, make sure the bottom legend has breathing room.
    baseMargin.bottom = Math.max(baseMargin.bottom ?? 0, scaled(20) + legendReserve)
  }
  // Reserve room for the X-axis label (value text) when present.
  if (xAxisCfg.label && userMargins.bottom == null) {
    baseMargin.bottom = Math.max(baseMargin.bottom ?? 0, scaled(40) + legendReserve)
  }
  // Reserve room on the left when Y-axis label is present (YAxis width is
  // limited; the rotated label text needs extra outer breathing room so the
  // tick numbers don't get clipped either).
  if (yAxisCfg.label && userMargins.left == null) {
    baseMargin.left = Math.max(baseMargin.left ?? 0, scaled(20))
  }
  // Apply design layout margins on top
  const chartMargin = dl?.margins
    ? { ...baseMargin, ...dl.margins }
    : baseMargin

  // Legend position mapping — with design layout override
  const legendProps = legendCfg.visible
    ? _legendHasDesignPos
      ? {
          wrapperStyle: {
            position: 'absolute' as const,
            left: `${dl!.legend!.x ?? 0}%`,
            top: `${dl!.legend!.y ?? 0}%`,
            fontSize: fs(12),
          },
          layout: (dl!.legend!.layout || 'horizontal') as 'horizontal' | 'vertical',
        }
      : {
          verticalAlign: (legendCfg.position === 'top' || legendCfg.position === 'bottom'
            ? legendCfg.position
            : 'middle') as 'top' | 'bottom' | 'middle',
          align: (legendCfg.position === 'left' || legendCfg.position === 'right'
            ? legendCfg.position
            : 'center') as 'left' | 'right' | 'center',
          wrapperStyle: { fontSize: fs(12) },
        }
    : null

  // XAxis tick props. NOTE: `height` belongs on the <XAxis> element, not on
  // tick props. Also, Recharts' <Text> inside tick uses `width` from its slot
  // to wrap/truncate text — for rotated labels that's wrong (text has already
  // been rotated to fit diagonally, no need to word-wrap). Passing an explicit
  // large `width` on tick disables that truncation and lets the full label
  // render regardless of slot width.
  const rotated = !!xAxisCfg.angle
  // Disable Recharts' per-slot word-wrap on rotated labels by passing a large
  // explicit `width` — uses the dynamic label width so it always exceeds the
  // longest label regardless of fontScale.
  const xTickWidth = Math.max(200, Math.ceil(approxLabelWidthPx + 20))
  const xTickProps = rotated
    ? { angle: xAxisCfg.angle, textAnchor: 'end' as const, fontSize: fs(12), width: xTickWidth }
    : { fontSize: fs(12) }

  // Design layout: axis label offsets
  const xLabelDx = dl?.xAxisLabel?.dx ?? 0
  const xLabelDy = dl?.xAxisLabel?.dy ?? 0
  const yLabelDx = dl?.yAxisLabel?.dx ?? 0
  const yLabelDy = dl?.yAxisLabel?.dy ?? 0
  const dataLabelDx = dl?.dataLabels?.dx ?? 0
  const dataLabelDy = dl?.dataLabels?.dy ?? 0

  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400">
        {t('charts.noData')}
      </div>
    )
  }

  // Funnel display config
  const funnelCfg = spec.funnel ?? { showLabels: true, labelPosition: 'right' as const }

  // Indicator — rendered as plain HTML, no ResponsiveContainer.
  // `fillHeight` tells the renderer it's mounted in a context with a real
  // intentional height it should fill (TV mode or dashboard editor body).
  // ChartCard / embed pages pass numeric heights and live inside CSS grids
  // that stretch siblings — there we want compact preset-sized values.
  if (chart_type === 'indicator') {
    // fillHeight=true: indicator grows to fill the parent container height.
    // Used in TV mode (fontScale set) and dashboard editor (fillHeight prop set explicitly).
    // Compact mode (false): indicator uses its preset size, can only shrink, never grow.
    // With fixedFontSize: force compact sizing so the indicator uses its
    // preset and never autoFits to the (stretched) container.
    const resolvedFillHeight = _fixedFontSize ? false : (fillHeight ?? (fontScale != null))
    return <IndicatorRenderer spec={spec} data={data} fontScale={effectiveFontScale} fillHeight={resolvedFillHeight} />
  }

  // Table — rendered as plain HTML, no ResponsiveContainer
  if (chart_type === 'table') {
    return <TableRenderer spec={spec} data={data} maxHeight={height} fontScale={effectiveFontScale} />
  }

  const renderGrid = () =>
    gridCfg.visible ? <CartesianGrid strokeDasharray={gridCfg.strokeDasharray || '3 3'} /> : null

  const renderXAxis = () => (
    <XAxis
      dataKey={xKey}
      height={rotated ? Math.max(scaled(40), bottomPad) : undefined}
      interval={rotated ? 0 : 'preserveStartEnd'}
      tickMargin={rotated ? scaled(8) : scaled(4)}
      label={xAxisCfg.label ? { value: xAxisCfg.label, position: 'insideBottom', offset: -5, dx: xLabelDx, dy: xLabelDy, style: { fontSize: fs(12) } } : undefined}
      tick={xTickProps}
    />
  )

  // When a Y-axis label is present, widen the axis so the rotated label text
  // (angle -90, positioned at `insideLeft`) is not clipped to the default
  // ~60px Recharts axis width. We also offset the label (`dx: -5`) to keep
  // a gap from the tick numbers, unless the user set their own offset.
  const renderYAxis = () => (
    <YAxis
      tickFormatter={yTickFormatter}
      tick={{ fontSize: fs(12) }}
      width={yAxisCfg.label ? scaled(80) : undefined}
      label={yAxisCfg.label ? {
        value: yAxisCfg.label,
        angle: -90,
        position: 'insideLeft',
        dx: yLabelDx || -5,
        dy: yLabelDy,
        style: { fontSize: fs(12), textAnchor: 'middle' },
      } : undefined}
    />
  )

  const renderTooltip = () =>
    showTooltip ? <Tooltip formatter={tooltipFormatter} /> : null

  const renderLegend = () =>
    legendProps ? <Legend {...legendProps} /> : null

  return (
    <ResponsiveContainer width="100%" height={height as number | `${number}%`}>
      {chart_type === 'bar' ? (
        <BarChart data={data} margin={chartMargin}>
          {renderGrid()}
          {renderXAxis()}
          {renderYAxis()}
          {renderTooltip()}
          {renderLegend()}
          {yKeys.map((key, i) => (
            <Bar key={key} dataKey={key} fill={palette[i % palette.length]} isAnimationActive={isAnimated}>
              {showDataLabels && <LabelList dataKey={key} position="top" fontSize={fs(11)} dx={dataLabelDx} dy={dataLabelDy} />}
            </Bar>
          ))}
        </BarChart>
      ) : chart_type === 'line' ? (
        <LineChart data={data} margin={chartMargin}>
          {renderGrid()}
          {renderXAxis()}
          {renderYAxis()}
          {renderTooltip()}
          {renderLegend()}
          {yKeys.map((key, i) => (
            <Line
              key={key}
              type={lineCfg.type || 'monotone'}
              dataKey={key}
              stroke={palette[i % palette.length]}
              strokeWidth={lineCfg.strokeWidth ?? 2}
              isAnimationActive={isAnimated}
            >
              {showDataLabels && <LabelList dataKey={key} position="top" fontSize={fs(11)} dx={dataLabelDx} dy={dataLabelDy} />}
            </Line>
          ))}
        </LineChart>
      ) : chart_type === 'area' ? (
        <AreaChart data={data} margin={chartMargin}>
          {renderGrid()}
          {renderXAxis()}
          {renderYAxis()}
          {renderTooltip()}
          {renderLegend()}
          {yKeys.map((key, i) => (
            <Area
              key={key}
              type={lineCfg.type || 'monotone'}
              dataKey={key}
              fill={palette[i % palette.length]}
              stroke={palette[i % palette.length]}
              fillOpacity={areaCfg.fillOpacity ?? 0.3}
              isAnimationActive={isAnimated}
            />
          ))}
        </AreaChart>
      ) : chart_type === 'pie' ? (
        <PieChart margin={{ top: 5, right: 50, bottom: 5, left: 50 }}>
          <Pie
            data={data}
            dataKey={yKeys[0]}
            nameKey={xKey}
            cx="50%"
            cy="50%"
            outerRadius={typeof height === 'number' ? height * 0.28 : '28%'}
            innerRadius={pieCfg.innerRadius || 0}
            label={pieCfg.showLabels !== false ? { fontSize: fs(12) } : false}
            isAnimationActive={isAnimated}
          >
            {data.map((_, i) => (
              <Cell key={`cell-${i}`} fill={palette[i % palette.length]} />
            ))}
          </Pie>
          {renderTooltip()}
          {renderLegend()}
        </PieChart>
      ) : chart_type === 'scatter' ? (
        <ScatterChart margin={chartMargin}>
          {renderGrid()}
          <XAxis type="number" dataKey={xKey} name={xKey} />
          <YAxis type="number" dataKey={yKeys[0]} name={yKeys[0]} tickFormatter={yTickFormatter} />
          {showTooltip ? <Tooltip cursor={{ strokeDasharray: '3 3' }} formatter={tooltipFormatter} /> : null}
          {renderLegend()}
          <Scatter name={spec.title} data={data} fill={palette[0]} isAnimationActive={isAnimated} />
        </ScatterChart>
      ) : chart_type === 'funnel' ? (
        <FunnelChart margin={{ top: 5, right: 120, bottom: 5, left: 5 }}>
          {showTooltip ? <Tooltip formatter={tooltipFormatter} /> : null}
          <Funnel dataKey={yKeys[0]} data={data.map((d, i) => ({ ...d, fill: palette[i % palette.length] }))} isAnimationActive={isAnimated}>
            <LabelList
              position="right"
              fill="#374151"
              stroke="none"
              dataKey={xKey}
              fontSize={fs(12)}
            />
            {funnelCfg.showLabels !== false && (
              <LabelList
                position="inside"
                fill="#fff"
                stroke="none"
                dataKey={yKeys[0]}
                fontSize={fs(11)}
                formatter={(v: unknown) => Number(v).toLocaleString()}
              />
            )}
          </Funnel>
        </FunnelChart>
      ) : chart_type === 'horizontal_bar' ? (
        (() => {
          // Compute Y-axis width from the longest category label so long names
          // like "Звонок поступил на номер: +7..." don't get clipped. We use a
          // conservative ~7px per character for the default font, add padding,
          // and clamp between 80 and 200. `fontScale` (TV mode) widens further.
          const longest = data.reduce((m, row) => {
            const s = String(row[xKey] ?? '')
            return s.length > m ? s.length : m
          }, 0)
          const charPx = 7 * (effectiveFontScale ?? 1)
          const yAxisWidth = Math.min(200, Math.max(80, Math.round(longest * charPx) + 12))
          return (
            <BarChart data={data} layout="vertical" margin={{ ...chartMargin, left: Math.max(chartMargin.left ?? 0, 10) }}>
              {renderGrid()}
              <XAxis type="number" tickFormatter={yTickFormatter} tick={{ fontSize: fs(12) }} />
              <YAxis type="category" dataKey={xKey} width={yAxisWidth} tick={{ fontSize: fs(12) }} />
              {renderTooltip()}
              {renderLegend()}
              {yKeys.map((key, i) => (
                <Bar key={key} dataKey={key} fill={palette[i % palette.length]} isAnimationActive={isAnimated}>
                  {showDataLabels && <LabelList dataKey={key} position="right" fontSize={fs(11)} dx={dataLabelDx} dy={dataLabelDy} />}
                </Bar>
              ))}
            </BarChart>
          )
        })()
      ) : (
        <BarChart data={data}>
          {renderGrid()}
          <XAxis dataKey={xKey} />
          <YAxis tickFormatter={yTickFormatter} />
          {renderTooltip()}
          <Bar dataKey={yKeys[0]} fill={palette[0]} isAnimationActive={isAnimated} />
        </BarChart>
      )}
    </ResponsiveContainer>
  )
}
