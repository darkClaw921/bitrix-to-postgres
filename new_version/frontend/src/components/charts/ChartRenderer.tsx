import {
  BarChart, Bar,
  LineChart, Line,
  PieChart, Pie, Cell,
  AreaChart, Area,
  ScatterChart, Scatter,
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
