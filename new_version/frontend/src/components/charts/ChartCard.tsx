import { useState } from 'react'
import ChartRenderer from './ChartRenderer'
import type { SavedChart } from '../../services/api'
import { useChartData, useDeleteChart, useToggleChartPin } from '../../hooks/useCharts'

interface ChartCardProps {
  chart: SavedChart
}

export default function ChartCard({ chart }: ChartCardProps) {
  const [showSql, setShowSql] = useState(false)
  const { data: freshData, refetch, isFetching } = useChartData(chart.id)
  const deleteChart = useDeleteChart()
  const togglePin = useToggleChartPin()

  const config = chart.chart_config as {
    x: string
    y: string | string[]
    colors?: string[]
    description?: string
  }

  const spec = {
    title: chart.title,
    chart_type: chart.chart_type as 'bar' | 'line' | 'pie' | 'area' | 'scatter',
    sql_query: chart.sql_query,
    data_keys: { x: config.x || 'x', y: config.y || 'y' },
    colors: config.colors,
    description: chart.description || config.description,
  }

  const chartData = freshData?.data

  return (
    <div className="card">
      <div className="flex justify-between items-start mb-3">
        <div>
          <h3 className="text-lg font-semibold">{chart.title}</h3>
          {chart.description && (
            <p className="text-sm text-gray-500 mt-1">{chart.description}</p>
          )}
          <p className="text-xs text-gray-400 mt-1 italic">"{chart.user_prompt}"</p>
        </div>
        <div className="flex space-x-1">
          <button
            onClick={() => togglePin.mutate(chart.id)}
            className={`p-1.5 rounded text-sm ${
              chart.is_pinned
                ? 'bg-yellow-100 text-yellow-700'
                : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
            }`}
            title={chart.is_pinned ? 'Unpin' : 'Pin'}
          >
            {chart.is_pinned ? 'Pinned' : 'Pin'}
          </button>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="p-1.5 rounded text-sm bg-gray-100 text-gray-500 hover:bg-gray-200 disabled:opacity-50"
            title="Refresh data"
          >
            {isFetching ? '...' : 'Refresh'}
          </button>
          <button
            onClick={() => setShowSql(!showSql)}
            className="p-1.5 rounded text-sm bg-gray-100 text-gray-500 hover:bg-gray-200"
            title="Show SQL"
          >
            SQL
          </button>
          <button
            onClick={() => {
              if (confirm('Delete this chart?')) deleteChart.mutate(chart.id)
            }}
            className="p-1.5 rounded text-sm bg-red-50 text-red-500 hover:bg-red-100"
            title="Delete"
          >
            Delete
          </button>
        </div>
      </div>

      {showSql && (
        <pre className="mb-3 p-3 bg-gray-50 rounded text-xs overflow-x-auto">
          {chart.sql_query}
        </pre>
      )}

      {chartData ? (
        <ChartRenderer spec={spec} data={chartData} />
      ) : (
        <div className="flex items-center justify-center h-48 text-gray-400">
          Click "Refresh" to load chart data
        </div>
      )}

      <div className="mt-2 flex justify-between text-xs text-gray-400">
        <span>Type: {chart.chart_type}</span>
        {freshData && (
          <span>
            {freshData.row_count} rows | {freshData.execution_time_ms.toFixed(0)}ms
          </span>
        )}
        <span>{new Date(chart.created_at).toLocaleDateString()}</span>
      </div>
    </div>
  )
}
