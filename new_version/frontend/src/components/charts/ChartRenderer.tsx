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

export default function ChartRenderer({ spec, data, height = 350 }: ChartRendererProps) {
  const { chart_type, data_keys, colors } = spec
  const palette = colors?.length ? colors : DEFAULT_COLORS
  const xKey = data_keys.x
  const yKeys = Array.isArray(data_keys.y) ? data_keys.y : [data_keys.y]

  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400">
        No data to display
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      {chart_type === 'bar' ? (
        <BarChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={xKey} />
          <YAxis />
          <Tooltip />
          <Legend />
          {yKeys.map((key, i) => (
            <Bar key={key} dataKey={key} fill={palette[i % palette.length]} />
          ))}
        </BarChart>
      ) : chart_type === 'line' ? (
        <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={xKey} />
          <YAxis />
          <Tooltip />
          <Legend />
          {yKeys.map((key, i) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={palette[i % palette.length]}
              strokeWidth={2}
            />
          ))}
        </LineChart>
      ) : chart_type === 'area' ? (
        <AreaChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={xKey} />
          <YAxis />
          <Tooltip />
          <Legend />
          {yKeys.map((key, i) => (
            <Area
              key={key}
              type="monotone"
              dataKey={key}
              fill={palette[i % palette.length]}
              stroke={palette[i % palette.length]}
              fillOpacity={0.3}
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
            label
          >
            {data.map((_, i) => (
              <Cell key={`cell-${i}`} fill={palette[i % palette.length]} />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      ) : chart_type === 'scatter' ? (
        <ScatterChart margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" dataKey={xKey} name={xKey} />
          <YAxis type="number" dataKey={yKeys[0]} name={yKeys[0]} />
          <Tooltip cursor={{ strokeDasharray: '3 3' }} />
          <Legend />
          <Scatter name={spec.title} data={data} fill={palette[0]} />
        </ScatterChart>
      ) : (
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={xKey} />
          <YAxis />
          <Tooltip />
          <Bar dataKey={yKeys[0]} fill={palette[0]} />
        </BarChart>
      )}
    </ResponsiveContainer>
  )
}
