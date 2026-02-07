import { useState } from 'react'
import ChartRenderer from '../components/charts/ChartRenderer'
import ChartCard from '../components/charts/ChartCard'
import DashboardCard from '../components/dashboards/DashboardCard'
import PublishModal from '../components/dashboards/PublishModal'
import { useGenerateChart, useSaveChart, useSavedCharts } from '../hooks/useCharts'
import { useDashboardList } from '../hooks/useDashboards'
import { useTranslation } from '../i18n'
import type { ChartGenerateResponse } from '../services/api'

export default function ChartsPage() {
  const { t } = useTranslation()
  const [prompt, setPrompt] = useState('')
  const [preview, setPreview] = useState<ChartGenerateResponse | null>(null)
  const [showPublishModal, setShowPublishModal] = useState(false)

  const generateChart = useGenerateChart()
  const saveChart = useSaveChart()
  const { data: savedData, isLoading: savedLoading } = useSavedCharts()
  const { data: dashboardsData } = useDashboardList()

  const handleGenerate = () => {
    if (!prompt.trim()) return
    generateChart.mutate(
      { prompt: prompt.trim() },
      {
        onSuccess: (data) => setPreview(data),
      },
    )
  }

  const handleSave = () => {
    if (!preview) return
    const { chart } = preview
    saveChart.mutate(
      {
        title: chart.title,
        description: chart.description,
        user_prompt: prompt,
        chart_type: chart.chart_type,
        chart_config: chart.data_keys as Record<string, unknown>,
        sql_query: chart.sql_query,
      },
      {
        onSuccess: () => {
          setPreview(null)
          setPrompt('')
        },
      },
    )
  }

  const handleDiscard = () => {
    setPreview(null)
  }

  return (
    <div className="space-y-6">
      {/* Generation Section */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">{t('charts.aiGenerator')}</h2>
        <div className="flex space-x-3">
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
            placeholder={t('charts.generatePlaceholder')}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          />
          <button
            onClick={handleGenerate}
            disabled={generateChart.isPending || !prompt.trim()}
            className="btn btn-primary px-6 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {generateChart.isPending ? t('common.generating') : t('common.generate')}
          </button>
        </div>

        {generateChart.isError && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
            {(generateChart.error as Error).message || t('charts.failedToGenerate')}
          </div>
        )}
      </div>

      {/* Preview Section */}
      {preview && (
        <div className="card border-2 border-primary-200">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h3 className="text-lg font-semibold">{preview.chart.title}</h3>
              {preview.chart.description && (
                <p className="text-sm text-gray-500 mt-1">{preview.chart.description}</p>
              )}
            </div>
            <div className="flex space-x-2">
              <button
                onClick={handleSave}
                disabled={saveChart.isPending}
                className="btn btn-primary disabled:opacity-50"
              >
                {saveChart.isPending ? t('common.saving') : t('common.save')}
              </button>
              <button onClick={handleDiscard} className="btn btn-secondary">
                {t('charts.discard')}
              </button>
            </div>
          </div>

          <ChartRenderer spec={preview.chart} data={preview.data} />

          <div className="mt-3 flex justify-between text-xs text-gray-400">
            <span>
              {preview.row_count} {t('charts.rows')} | {preview.execution_time_ms.toFixed(0)}ms
            </span>
            <span>Type: {preview.chart.chart_type}</span>
          </div>

          <details className="mt-3">
            <summary className="text-sm text-gray-500 cursor-pointer hover:text-gray-700">
              {t('charts.showSqlQuery')}
            </summary>
            <pre className="mt-2 p-3 bg-gray-50 rounded text-xs overflow-x-auto">
              {preview.chart.sql_query}
            </pre>
          </details>
        </div>
      )}

      {/* Saved Charts */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">
            {t('charts.savedCharts')} {savedData ? `(${savedData.total})` : ''}
          </h2>
          {savedData && savedData.charts.length > 0 && (
            <button
              onClick={() => setShowPublishModal(true)}
              className="btn btn-primary text-sm"
            >
              {t('charts.publishDashboard')}
            </button>
          )}
        </div>

        {savedLoading ? (
          <div className="flex items-center justify-center h-32 text-gray-500">{t('common.loading')}</div>
        ) : !savedData?.charts.length ? (
          <div className="card text-center text-gray-400 py-12">
            {t('charts.noSavedCharts')}
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {savedData.charts.map((chart) => (
              <ChartCard key={chart.id} chart={chart} />
            ))}
          </div>
        )}
      </div>

      {/* Published Dashboards */}
      {dashboardsData && dashboardsData.dashboards.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-4">
            {t('charts.publishedDashboards')} ({dashboardsData.total})
          </h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {dashboardsData.dashboards.map((d) => (
              <DashboardCard key={d.id} dashboard={d} />
            ))}
          </div>
        </div>
      )}

      {/* Publish Modal */}
      {showPublishModal && savedData && (
        <PublishModal
          charts={savedData.charts}
          onClose={() => setShowPublishModal(false)}
        />
      )}
    </div>
  )
}
