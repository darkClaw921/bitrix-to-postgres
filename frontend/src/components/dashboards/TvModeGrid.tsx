import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ReactGridLayout, { useContainerWidth } from 'react-grid-layout'
import type { Layout, LayoutItem } from 'react-grid-layout'
import 'react-grid-layout/css/styles.css'
import 'react-resizable/css/styles.css'
import { useElementSize } from '../../hooks/useElementSize'
import type { DashboardChart, ChartDataResponse } from '../../services/api'

/**
 * TvModeGrid — drag/resize-enabled grid used by the public dashboard "TV mode".
 *
 * High-level responsibilities (split across Phase 3 tasks):
 *  - P3.1 (this commit): props/state shape, layout merge strategy with localStorage
 *    persistence and the legacy 12-col → TV 24-col coordinate migration.
 *  - P3.2: internal `TvCellMeasurer` that derives `fontScale` and `chartHeight`
 *    from the actual cell size via `useElementSize`.
 *  - P3.3: full `<ReactGridLayout>` render with `useContainerWidth` + adaptive
 *    `rowHeight` driven by `window.innerHeight`.
 *
 * The merge strategy lives in `useMemo` (not `useState`) on purpose: when the
 * editor adds a new chart and the parent re-renders with an updated `charts`
 * prop, the new element appears in the grid with its default layout while all
 * other items keep the positions the user picked in TV mode.
 */

export interface TvModeGridProps {
  /**
   * Stable localStorage key. The parent owns it because linked-tab dashboards
   * need different keys, e.g. `"<slug>"` vs `"<slug>:<linkedSlug>"`.
   */
  storageKey: string
  /** Polymorphic dashboard items (charts + headings) in display order. */
  charts: DashboardChart[]
  /** Pre-fetched chart data, indexed by `DashboardChart.id`. */
  chartData: Record<number, ChartDataResponse>
  /** Renders a chart cell once we know its scale and inner height. */
  renderChart: (
    dc: DashboardChart,
    fontScale: number,
    chartHeight: number,
  ) => React.ReactNode
  /** Renders a heading cell once we know its scale. */
  renderHeading: (dc: DashboardChart, fontScale: number) => React.ReactNode
}

/** TV-mode grid uses 24 columns (legacy editor uses 12). */
export const TV_GRID_COLS = 24

/** localStorage key builder — kept here so callers do not need to know the prefix. */
export const TV_LAYOUT_KEY = (k: string): string => `tv_layout_${k}`

/**
 * Persisted shape: a record from `String(dc.id)` → `{x, y, w, h}`.
 * Only the four positional fields are stored — `i`, `minW`, `minH` are
 * recomputed on read because they are derived from the chart, not chosen
 * by the user.
 */
type StoredLayoutMap = Record<
  string,
  { x: number; y: number; w: number; h: number }
>

/**
 * Reads the persisted layout map for `storageKey`.
 * Wrapped in try/catch — `JSON.parse` may throw on corrupted entries and
 * `localStorage` access itself can throw in private mode / disabled storage.
 */
function readStoredLayout(storageKey: string): StoredLayoutMap {
  try {
    const raw = localStorage.getItem(TV_LAYOUT_KEY(storageKey))
    if (!raw) return {}
    const parsed = JSON.parse(raw) as unknown
    if (parsed && typeof parsed === 'object') {
      return parsed as StoredLayoutMap
    }
    return {}
  } catch {
    return {}
  }
}

/**
 * Persists `next` to `localStorage[TV_LAYOUT_KEY(storageKey)]`.
 * Swallows quota / private-mode errors — TV mode is best-effort, never throw
 * from a layout-change handler.
 */
function persistLayoutTo(storageKey: string, next: Layout): void {
  try {
    const indexed: StoredLayoutMap = Object.fromEntries(
      next.map((l) => [l.i, { x: l.x, y: l.y, w: l.w, h: l.h }]),
    )
    localStorage.setItem(TV_LAYOUT_KEY(storageKey), JSON.stringify(indexed))
  } catch {
    /* quota exceeded / private mode / storage disabled — silently skip */
  }
}

/**
 * Builds the merged layout: for every chart, prefer the persisted entry,
 * otherwise seed from `dc.layout_*` (multiplying x and w by 2 to migrate the
 * editor's 12-column space into TV mode's 24-column space). Persisted entries
 * for charts that no longer exist are ignored.
 */
function buildMergedLayout(
  charts: DashboardChart[],
  stored: StoredLayoutMap,
): Layout {
  const items: LayoutItem[] = charts.map((dc) => {
    const id = String(dc.id)
    const fromStorage = stored[id]
    if (fromStorage) {
      return {
        i: id,
        x: fromStorage.x,
        y: fromStorage.y,
        w: fromStorage.w,
        h: fromStorage.h,
        minW: 1,
        minH: 1,
      }
    }
    // Default seed from editor layout, migrated 12-col → 24-col.
    return {
      i: id,
      x: dc.layout_x * 2,
      y: dc.layout_y,
      w: dc.layout_w * 2,
      h: dc.layout_h,
      minW: 1,
      minH: 1,
    }
  })
  return items
}

/** Numeric clamp helper used by the font-scale formula. */
const clamp = (min: number, max: number, v: number): number =>
  Math.max(min, Math.min(max, v))

interface TvCellMeasurerProps {
  dc: DashboardChart
  chartData: ChartDataResponse | undefined
  renderChart: (
    dc: DashboardChart,
    fontScale: number,
    chartHeight: number,
  ) => React.ReactNode
  renderHeading: (dc: DashboardChart, fontScale: number) => React.ReactNode
}

/**
 * Internal cell wrapper. Measures the rendered cell with `useElementSize`,
 * derives a font scale from `sqrt(w*h)/350` clamped to [0.4, 2.5], and forwards
 * the measurements to the parent's render callbacks.
 *
 * Heading vs chart is decided by `dc.item_type === 'heading'`, the same
 * discriminator already used in `EmbedDashboardPage` and `DashboardEditorPage`.
 *
 * Tables get a width-only font scale (`sqrt(width / 350)`) instead of the
 * default width*height formula. Otherwise stretching a table vertically would
 * make its text balloon — but tables already manage their own row layout and
 * the user expectation is that a taller table just shows more rows at the
 * same font size, not bigger text.
 *
 * For chart cells, the inner chart height is the measured height minus the
 * fixed title row (36px header + 8px margin = 44px), with a 60px floor so the
 * chart never collapses entirely. Headings get the full measured height —
 * they have no separate title row.
 *
 * `Math.max(1, ...)` inside the `sqrt` keeps the formula numerically safe
 * before the first `ResizeObserver` callback fires (when both dimensions are
 * 0), so the initial render lands at the lower clamp (`0.4`) instead of `NaN`.
 */
function TvCellMeasurer({
  dc,
  chartData: _chartData,
  renderChart,
  renderHeading,
}: TvCellMeasurerProps): React.ReactElement {
  const { ref, width, height } = useElementSize<HTMLDivElement>()

  const isHeading = dc.item_type === 'heading'
  const isTable = !isHeading && dc.chart_type === 'table'

  const fontScale = isTable
    ? clamp(0.4, 2.5, Math.sqrt(Math.max(1, width) / 350))
    : clamp(0.4, 2.5, Math.sqrt(Math.max(1, width * height)) / 350)

  const chartHeight = Math.max(60, height - 44)

  const content = isHeading
    ? renderHeading(dc, fontScale)
    : renderChart(dc, fontScale, chartHeight)

  return (
    <div ref={ref} className="h-full w-full">
      {content}
    </div>
  )
}

/**
 * Computes a TV-mode `rowHeight` from the current viewport height.
 *
 * Dividing `window.innerHeight` by 24 means the default seed layout (h≈6 rows)
 * occupies roughly a quarter of the screen vertically — visually balanced when
 * the user opens TV mode for the first time. The 20px floor protects very
 * small viewports (e.g. picture-in-picture) from collapsing rows to nothing.
 */
function computeRowHeight(): number {
  if (typeof window === 'undefined') return 20
  return Math.max(20, Math.floor(window.innerHeight / 24))
}

export function TvModeGrid({
  storageKey,
  charts,
  chartData,
  renderChart,
  renderHeading,
}: TvModeGridProps): React.ReactElement {
  /**
   * Seed layout from `charts` + localStorage. Recomputed when `charts` (e.g.
   * new chart added) or `storageKey` (linked tab switched) changes.
   */
  const seedLayout = useMemo<Layout>(() => {
    const stored = readStoredLayout(storageKey)
    return buildMergedLayout(charts, stored)
  }, [charts, storageKey])

  /**
   * Controlled layout state — required so drag/resize events update the prop
   * react-grid-layout receives. Without this, the grid fights the parent on
   * every interaction and can loop into React error #185 during rapid resize.
   */
  const [layout, setLayout] = useState<Layout>(seedLayout)

  /**
   * Re-seed when charts/storageKey change (not on every seedLayout identity
   * change — that would thrash during re-renders caused by other state).
   */
  const prevSeedKeyRef = useRef<string>('')
  useEffect(() => {
    const seedKey = `${storageKey}|${charts.map((c) => c.id).join(',')}`
    if (prevSeedKeyRef.current !== seedKey) {
      prevSeedKeyRef.current = seedKey
      setLayout(seedLayout)
    }
  }, [seedLayout, storageKey, charts])

  /**
   * react-grid-layout v2 ResizeObserver hook. Mirrors the pattern used in
   * `DashboardEditorPage` (line ~99): always render the wrapper div with
   * `containerRef`, but only render `<ReactGridLayout>` once `mounted` is true
   * AND `containerWidth > 0`. Otherwise the grid mounts with width=0 and items
   * compute their pixel positions against a non-measured container.
   */
  const { containerRef, width: containerWidth, mounted, measureWidth } = useContainerWidth()

  /**
   * Force a re-measure on mount and again on the next animation frame.
   * `useContainerWidth` initializes with a hardcoded 1280px and measures via
   * `useEffect` after the first paint. On a page refresh with `?tv=1` the
   * grid can lock to that 1280px width before the browser finishes laying
   * out the fixed parent, leaving a permanent right margin. Two delayed
   * measurements ensure the grid sees the real viewport-relative width.
   */
  const measureWidthRef = useRef(measureWidth)
  useEffect(() => {
    measureWidthRef.current = measureWidth
  }, [measureWidth])
  useEffect(() => {
    measureWidthRef.current?.()
    const raf = requestAnimationFrame(() => {
      measureWidthRef.current?.()
    })
    const timer = setTimeout(() => {
      measureWidthRef.current?.()
    }, 100)
    return () => {
      cancelAnimationFrame(raf)
      clearTimeout(timer)
    }
  }, [])

  /**
   * Adaptive row height. Recomputed on every `window.resize` so the grid stays
   * proportional when the user enters/exits browser fullscreen or rotates
   * a tablet. We do not depend on `containerHeight` here because the grid is
   * vertically free-scrolling — `window.innerHeight` is the right reference.
   */
  const [rowHeight, setRowHeight] = useState<number>(() => computeRowHeight())
  useEffect(() => {
    if (typeof window === 'undefined') return
    const handler = (): void => setRowHeight(computeRowHeight())
    window.addEventListener('resize', handler)
    return () => window.removeEventListener('resize', handler)
  }, [])

  /**
   * Controlled layout change handler. Compares with previous layout to skip
   * no-op updates (react-grid-layout can call this with byte-identical layouts
   * during hover/drag handshakes — avoiding setState on those prevents a
   * Maximum Update Depth loop during rapid drag/resize interactions).
   */
  const handleLayoutChange = useCallback(
    (next: Layout) => {
      setLayout((prev) => {
        if (prev.length === next.length) {
          let same = true
          for (let i = 0; i < prev.length; i++) {
            const a = prev[i]
            const b = next[i]
            if (
              a.i !== b.i ||
              a.x !== b.x ||
              a.y !== b.y ||
              a.w !== b.w ||
              a.h !== b.h
            ) {
              same = false
              break
            }
          }
          if (same) return prev
        }
        persistLayoutTo(storageKey, next)
        return next
      })
    },
    [storageKey],
  )

  return (
    <div
      ref={containerRef as React.RefObject<HTMLDivElement>}
      className="w-full"
    >
      {mounted && containerWidth > 0 && charts.length > 0 && (
        <ReactGridLayout
          layout={layout}
          width={containerWidth}
          onLayoutChange={handleLayoutChange}
          gridConfig={{
            cols: TV_GRID_COLS,
            rowHeight,
            margin: [8, 8] as const,
            containerPadding: [0, 0] as const,
            maxRows: Infinity,
          }}
          dragConfig={{ enabled: true, bounded: false, threshold: 3 }}
          resizeConfig={{ enabled: true, handles: ['se'] }}
        >
          {charts.map((dc) => (
            <div key={String(dc.id)} className="overflow-hidden">
              <TvCellMeasurer
                dc={dc}
                chartData={chartData[dc.id]}
                renderChart={renderChart}
                renderHeading={renderHeading}
              />
            </div>
          ))}
        </ReactGridLayout>
      )}
    </div>
  )
}

export default TvModeGrid
