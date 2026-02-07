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
import type { ChartSpec } from '../../services/api'

const DEFAULT_COLORS = [
  '#8884d8', '#82ca9d', '#ffc658', '#ff7300',
  '#0088fe', '#00c49f', '#ffbb28', '#ff8042',
]

interface ChartRendererProps {
  spec: ChartSpec
  data: Record<string, unknown>[]
  height?: number
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

function IndicatorRenderer({ spec, data }: { spec: ChartSpec; data: Record<string, unknown>[] }) {
  const indicatorCfg = spec.indicator ?? {}
  const yKeys = Array.isArray(spec.data_keys.y) ? spec.data_keys.y : [spec.data_keys.y]
  const valueKey = yKeys[0]
  const row = data[0] || {}
  const rawValue = row[valueKey]
  const numValue = Number(rawValue)
  const displayValue = isNaN(numValue) ? String(rawValue ?? '') : numValue.toLocaleString()

  const fontSizeMap = { sm: '1.5rem', md: '2.5rem', lg: '3.5rem', xl: '5rem' }
  const fontSize = fontSizeMap[indicatorCfg.fontSize || 'lg'] || '3.5rem'

  return (
    <div className="flex flex-col items-center justify-center h-full py-8">
      <div
        className="font-bold leading-tight"
        style={{ fontSize, color: indicatorCfg.color || '#1f2937' }}
      >
        {indicatorCfg.prefix && <span>{indicatorCfg.prefix} </span>}
        {displayValue}
        {indicatorCfg.suffix && <span> {indicatorCfg.suffix}</span>}
      </div>
    </div>
  )
}

function TableRenderer({ spec, data }: { spec: ChartSpec; data: Record<string, unknown>[] }) {
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

  return (
    <div className="overflow-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-gray-100">
            {displayColumns.map((col) => (
              <th
                key={col}
                className={`border border-gray-200 px-3 py-2 text-left font-semibold text-gray-700 ${
                  tableCfg.sortable ? 'cursor-pointer hover:bg-gray-200 select-none' : ''
                }`}
                onClick={() => col !== '__row_total__' && handleSort(col)}
              >
                {col === '__row_total__' ? 'Total' : col}
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
                    ? 'Total'
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

      {pageSize > 0 && totalPages > 1 && (
        <div className="flex items-center justify-between mt-2 text-xs text-gray-500">
          <span>
            Page {page + 1} of {totalPages} ({sortedData.length} rows)
          </span>
          <div className="flex gap-1">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-2 py-1 border rounded disabled:opacity-30 hover:bg-gray-100"
            >
              Prev
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="px-2 py-1 border rounded disabled:opacity-30 hover:bg-gray-100"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default function ChartRenderer({ spec, data, height = 350 }: ChartRendererProps) {
  const { chart_type, data_keys, colors } = spec
  const palette = colors?.length ? colors : DEFAULT_COLORS
  const xKey = data_keys.x
  const yKeys = Array.isArray(data_keys.y) ? data_keys.y : [data_keys.y]

  // Display config with defaults
  const legendCfg = spec.legend ?? { visible: true, position: 'bottom' }
  const gridCfg = spec.grid ?? { visible: true, strokeDasharray: '3 3' }
  const xAxisCfg = spec.xAxis ?? { label: '', angle: 0 }
  const yAxisCfg = spec.yAxis ?? { label: '', format: 'number' }
  const lineCfg = spec.line ?? { strokeWidth: 2, type: 'monotone' as const }
  const areaCfg = spec.area ?? { fillOpacity: 0.3 }
  const pieCfg = spec.pie ?? { innerRadius: 0, showLabels: true }

  const yTickFormatter = (v: number) => formatValue(v, yAxisCfg.format)
  const tooltipFormatter = (v: number | undefined) => formatValue(v ?? 0, yAxisCfg.format)

  // Legend position mapping
  const legendProps = legendCfg.visible
    ? {
        verticalAlign: (legendCfg.position === 'top' || legendCfg.position === 'bottom'
          ? legendCfg.position
          : 'middle') as 'top' | 'bottom' | 'middle',
        align: (legendCfg.position === 'left' || legendCfg.position === 'right'
          ? legendCfg.position
          : 'center') as 'left' | 'right' | 'center',
      }
    : null

  // XAxis tick angle props
  const xTickProps = xAxisCfg.angle
    ? { angle: xAxisCfg.angle, textAnchor: 'end' as const, height: 60 }
    : {}

  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400">
        No data to display
      </div>
    )
  }

  // Funnel display config
  const funnelCfg = spec.funnel ?? { showLabels: true, labelPosition: 'right' as const }

  // Indicator — rendered as plain HTML, no ResponsiveContainer
  if (chart_type === 'indicator') {
    return <IndicatorRenderer spec={spec} data={data} />
  }

  // Table — rendered as plain HTML, no ResponsiveContainer
  if (chart_type === 'table') {
    return <TableRenderer spec={spec} data={data} />
  }

  const renderGrid = () =>
    gridCfg.visible ? <CartesianGrid strokeDasharray={gridCfg.strokeDasharray || '3 3'} /> : null

  const renderXAxis = () => (
    <XAxis
      dataKey={xKey}
      label={xAxisCfg.label ? { value: xAxisCfg.label, position: 'insideBottom', offset: -5 } : undefined}
      tick={xTickProps}
    />
  )

  const renderYAxis = () => (
    <YAxis
      tickFormatter={yTickFormatter}
      label={yAxisCfg.label ? { value: yAxisCfg.label, angle: -90, position: 'insideLeft' } : undefined}
    />
  )

  const renderTooltip = () => (
    <Tooltip formatter={tooltipFormatter} />
  )

  const renderLegend = () =>
    legendProps ? <Legend {...legendProps} /> : null

  return (
    <ResponsiveContainer width="100%" height={height}>
      {chart_type === 'bar' ? (
        <BarChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          {renderGrid()}
          {renderXAxis()}
          {renderYAxis()}
          {renderTooltip()}
          {renderLegend()}
          {yKeys.map((key, i) => (
            <Bar key={key} dataKey={key} fill={palette[i % palette.length]} />
          ))}
        </BarChart>
      ) : chart_type === 'line' ? (
        <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
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
            />
          ))}
        </LineChart>
      ) : chart_type === 'area' ? (
        <AreaChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
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
            />
          ))}
        </AreaChart>
      ) : chart_type === 'pie' ? (
        <PieChart>
          <Pie
            data={data}
            dataKey={yKeys[0]}
            nameKey={xKey}
            cx="50%"
            cy="50%"
            outerRadius={height * 0.35}
            innerRadius={pieCfg.innerRadius || 0}
            label={pieCfg.showLabels !== false}
          >
            {data.map((_, i) => (
              <Cell key={`cell-${i}`} fill={palette[i % palette.length]} />
            ))}
          </Pie>
          {renderTooltip()}
          {renderLegend()}
        </PieChart>
      ) : chart_type === 'scatter' ? (
        <ScatterChart margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          {renderGrid()}
          <XAxis type="number" dataKey={xKey} name={xKey} />
          <YAxis type="number" dataKey={yKeys[0]} name={yKeys[0]} tickFormatter={yTickFormatter} />
          <Tooltip cursor={{ strokeDasharray: '3 3' }} formatter={tooltipFormatter} />
          {renderLegend()}
          <Scatter name={spec.title} data={data} fill={palette[0]} />
        </ScatterChart>
      ) : chart_type === 'funnel' ? (
        <FunnelChart margin={{ top: 5, right: 120, bottom: 5, left: 5 }}>
          <Tooltip formatter={tooltipFormatter} />
          <Funnel dataKey={yKeys[0]} data={data.map((d, i) => ({ ...d, fill: palette[i % palette.length] }))} isAnimationActive>
            <LabelList
              position="right"
              fill="#374151"
              stroke="none"
              dataKey={xKey}
              fontSize={12}
            />
            {funnelCfg.showLabels !== false && (
              <LabelList
                position="inside"
                fill="#fff"
                stroke="none"
                dataKey={yKeys[0]}
                fontSize={11}
                formatter={(v: unknown) => Number(v).toLocaleString()}
              />
            )}
          </Funnel>
        </FunnelChart>
      ) : chart_type === 'horizontal_bar' ? (
        <BarChart data={data} layout="vertical" margin={{ top: 5, right: 20, bottom: 5, left: 80 }}>
          {renderGrid()}
          <XAxis type="number" tickFormatter={yTickFormatter} />
          <YAxis type="category" dataKey={xKey} width={80} />
          {renderTooltip()}
          {renderLegend()}
          {yKeys.map((key, i) => (
            <Bar key={key} dataKey={key} fill={palette[i % palette.length]} />
          ))}
        </BarChart>
      ) : (
        <BarChart data={data}>
          {renderGrid()}
          <XAxis dataKey={xKey} />
          <YAxis tickFormatter={yTickFormatter} />
          {renderTooltip()}
          <Bar dataKey={yKeys[0]} fill={palette[0]} />
        </BarChart>
      )}
    </ResponsiveContainer>
  )
}
