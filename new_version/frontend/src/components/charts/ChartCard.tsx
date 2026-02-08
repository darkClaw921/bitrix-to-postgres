import { useState, useCallback } from 'react'
import ChartRenderer from './ChartRenderer'
import ChartSettingsPanel from './ChartSettingsPanel'
import IframeCopyButton from './IframeCopyButton'
import type { SavedChart, ChartDisplayConfig } from '../../services/api'
import { useChartData, useDeleteChart, useToggleChartPin, useUpdateChartConfig } from '../../hooks/useCharts'
import { useTranslation } from '../../i18n'

interface ChartCardProps {
  chart: SavedChart
}

export default function ChartCard({ chart }: ChartCardProps) {
  const { t } = useTranslation()
  const [showSql, setShowSql] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const { data: freshData, refetch, isFetching } = useChartData(chart.id)
  const deleteChart = useDeleteChart()
  const togglePin = useToggleChartPin()
  const updateConfig = useUpdateChartConfig()

  const config = chart.chart_config as unknown as ChartDisplayConfig

  const spec = {
    title: chart.title,
    chart_type: chart.chart_type as 'bar' | 'line' | 'pie' | 'area' | 'scatter' | 'indicator' | 'table' | 'funnel' | 'horizontal_bar',
    sql_query: chart.sql_query,
    data_keys: { x: config.x || 'x', y: config.y || 'y' },
    colors: config.colors,
    description: chart.description || config.description,
    legend: config.legend,
    grid: config.grid,
    xAxis: config.xAxis,
    yAxis: config.yAxis,
    line: config.line,
    area: config.area,
    pie: config.pie,
    indicator: config.indicator,
    table: config.table,
    funnel: config.funnel,
    horizontal_bar: config.horizontal_bar,
  }

  const chartData = freshData?.data

  const handleConfigUpdate = useCallback((patch: Partial<ChartDisplayConfig>) => {
    updateConfig.mutate({ chartId: chart.id, config: patch })
  }, [chart.id, updateConfig])

  return (
    <div className="card">
      <div className="flex justify-end mb-2">
        <div className="flex space-x-1">
          <button
            onClick={() => togglePin.mutate(chart.id)}
            className={`p-1.5 rounded text-sm ${
              chart.is_pinned
                ? 'bg-yellow-100 text-yellow-700'
                : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
            }`}
            title={chart.is_pinned ? t('charts.unpin') : t('charts.pin')}
          >
            {chart.is_pinned ? t('charts.pinned') : t('charts.pin')}
          </button>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="p-1.5 rounded text-sm bg-gray-100 text-gray-500 hover:bg-gray-200 disabled:opacity-50"
            title={t('charts.refreshData')}
          >
            {isFetching ? '...' : t('charts.refresh')}
          </button>
          <IframeCopyButton chartId={chart.id} />
          <button
            onClick={() => setShowSettings(!showSettings)}
            className={`p-1.5 rounded text-sm ${
              showSettings
                ? 'bg-blue-100 text-blue-700'
                : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
            }`}
            title={t('charts.chartSettings')}
          >
            {t('charts.settings')}
          </button>
          <button
            onClick={() => setShowSql(!showSql)}
            className="p-1.5 rounded text-sm bg-gray-100 text-gray-500 hover:bg-gray-200"
            title={t('charts.showSql')}
          >
            {t('charts.sql')}
          </button>
          <button
            onClick={() => {
              if (confirm(t('editor.confirmDeleteChart'))) deleteChart.mutate(chart.id)
            }}
            className="p-1.5 rounded text-sm bg-red-50 text-red-500 hover:bg-red-100"
            title={t('common.delete')}
          >
            {t('common.delete')}
          </button>
        </div>
      </div>
      <div className="mb-3">
        <h3 className="text-lg font-semibold">{chart.title}</h3>
        {chart.description && (
          <p className="text-sm text-gray-500 mt-1">{chart.description}</p>
        )}
        {chart.user_prompt && (
          <p className="text-xs text-gray-400 mt-1 italic">"{chart.user_prompt}"</p>
        )}
      </div>

      {showSettings && (
        <ChartSettingsPanel
          chartType={chart.chart_type}
          config={config}
          onApply={handleConfigUpdate}
          isSaving={updateConfig.isPending}
        />
      )}

      {showSql && (
        <pre className="mb-3 p-3 bg-gray-50 rounded text-xs overflow-x-auto">
          {chart.sql_query}
        </pre>
      )}

      {chartData ? (
        <ChartRenderer spec={spec} data={chartData} />
      ) : (
        <div className="flex items-center justify-center h-48 text-gray-400">
          {t('charts.emptyChart')}
        </div>
      )}

      <div className="mt-2 flex justify-between text-xs text-gray-400">
        <span>Type: {chart.chart_type}</span>
        {freshData && (
          <span>
            {freshData.row_count} {t('charts.rows')} | {freshData.execution_time_ms.toFixed(0)}ms
          </span>
        )}
        <span>{new Date(chart.created_at).toLocaleDateString()}</span>
      </div>
    </div>
  )
}
