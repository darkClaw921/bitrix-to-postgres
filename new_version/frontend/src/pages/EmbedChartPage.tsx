import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import ChartRenderer from '../components/charts/ChartRenderer'
import { publicApi } from '../services/api'
import { useTranslation } from '../i18n'
import type { ChartSpec, ChartDataResponse, ChartDisplayConfig } from '../services/api'

export default function EmbedChartPage() {
  const { chartId } = useParams<{ chartId: string }>()
  const [meta, setMeta] = useState<Record<string, unknown> | null>(null)
  const [data, setData] = useState<ChartDataResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const { t } = useTranslation()

  useEffect(() => {
    if (!chartId) return

    const id = Number(chartId)
    Promise.all([publicApi.getChartMeta(id), publicApi.getChartData(id)])
      .then(([metaRes, dataRes]) => {
        setMeta(metaRes)
        setData(dataRes)
      })
      .catch((err) => {
        setError(err?.response?.data?.detail || 'Failed to load chart')
      })
      .finally(() => setLoading(false))
  }, [chartId])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-white">
        <div className="text-gray-400">{t('embed.loadingChart')}</div>
      </div>
    )
  }

  if (error || !meta || !data) {
    return (
      <div className="flex items-center justify-center h-screen bg-white">
        <div className="text-red-500">{error || t('embed.chartNotFound')}</div>
      </div>
    )
  }

  const config = meta.chart_config as unknown as ChartDisplayConfig
  const spec: ChartSpec = {
    title: meta.title as string,
    chart_type: meta.chart_type as ChartSpec['chart_type'],
    sql_query: '',
    data_keys: { x: config?.x || 'x', y: config?.y || 'y' },
    colors: config?.colors,
    description: meta.description as string | undefined,
    legend: config?.legend,
    grid: config?.grid,
    xAxis: config?.xAxis,
    yAxis: config?.yAxis,
    line: config?.line,
    area: config?.area,
    pie: config?.pie,
    indicator: config?.indicator,
    table: config?.table,
    funnel: config?.funnel,
    horizontal_bar: config?.horizontal_bar,
  }

  return (
    <div className="w-full h-screen bg-white p-4 flex flex-col">
      <h3 className="text-sm font-semibold text-gray-700 mb-2">{spec.title}</h3>
      <div className="flex-1 min-h-0">
        <ChartRenderer spec={spec} data={data.data} height={window.innerHeight - 60} />
      </div>
    </div>
  )
}
