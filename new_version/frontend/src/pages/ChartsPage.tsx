import { useState } from 'react'
import Editor from 'react-simple-code-editor'
import Prism from 'prismjs'
import 'prismjs/components/prism-sql'
import 'prismjs/themes/prism.css'
import ChartRenderer from '../components/charts/ChartRenderer'
import ChartCard from '../components/charts/ChartCard'
import PromptEditorModal from '../components/charts/PromptEditorModal'
import GenerationHistoryModal, { saveHistoryItem } from '../components/charts/GenerationHistoryModal'
import AISubTabs from '../components/ai/AISubTabs'
import DashboardCard from '../components/dashboards/DashboardCard'
import PublishModal from '../components/dashboards/PublishModal'
import { useGenerateChart, useSaveChart, useSavedCharts, useExecuteSql } from '../hooks/useCharts'
import { useDashboardList } from '../hooks/useDashboards'
import { useTranslation } from '../i18n'
import type { ChartGenerateResponse } from '../services/api'

// Helper to extract error message from axios error
function getErrorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'response' in error) {
    const axiosError = error as { response?: { data?: { detail?: string } } }
    if (axiosError.response?.data?.detail) {
      return axiosError.response.data.detail
    }
  }
  if (error instanceof Error) {
    return error.message
  }
  return 'Произошла неизвестная ошибка'
}

export default function ChartsPage() {
  const { t } = useTranslation()
  const [prompt, setPrompt] = useState('')
  const [preview, setPreview] = useState<ChartGenerateResponse | null>(null)
  const [showPublishModal, setShowPublishModal] = useState(false)
  const [showPromptEditor, setShowPromptEditor] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [editedSql, setEditedSql] = useState('')
  const [sqlOpen, setSqlOpen] = useState(false)

  const generateChart = useGenerateChart()
  const saveChart = useSaveChart()
  const executeSql = useExecuteSql()
  const { data: savedData, isLoading: savedLoading } = useSavedCharts()
  const { data: dashboardsData } = useDashboardList()

  const handleGenerate = () => {
    if (!prompt.trim()) return
    generateChart.mutate(
      { prompt: prompt.trim() },
      {
        onSuccess: (data) => {
          setPreview(data)
          setEditedSql(data.chart.sql_query)
          setSqlOpen(false)
          executeSql.reset()
          saveHistoryItem(prompt.trim(), data.chart, data.data)
        },
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
        sql_query: editedSql || chart.sql_query,
      },
      {
        onSuccess: () => {
          setPreview(null)
          setPrompt('')
        },
      },
    )
  }

  const handleRunSql = () => {
    if (!editedSql.trim() || !preview) return
    executeSql.mutate(
      { sql_query: editedSql.trim() },
      {
        onSuccess: (result) => {
          setPreview({
            ...preview,
            chart: { ...preview.chart, sql_query: editedSql.trim() },
            data: result.data,
            row_count: result.row_count,
            execution_time_ms: result.execution_time_ms,
          })
        },
      },
    )
  }

  const handleDiscard = () => {
    setPreview(null)
    setSqlOpen(false)
    executeSql.reset()
  }

  return (
    <div className="space-y-6">
      <AISubTabs />

      {/* Generation Section */}
      <div className="card">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold">{t('charts.aiGenerator')}</h2>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowHistory(true)}
              className="text-sm text-gray-600 hover:text-primary-600 flex items-center gap-2"
              title={t('charts.generationHistory')}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {t('charts.generationHistory')}
            </button>
            <button
              onClick={() => setShowPromptEditor(true)}
              className="text-sm text-gray-600 hover:text-primary-600 flex items-center gap-2"
              title="Настроить промпт для AI"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              Настроить промпт
            </button>
          </div>
        </div>
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
            <strong>Ошибка генерации:</strong> {getErrorMessage(generateChart.error)}
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

          <div className="mt-3">
            <button
              onClick={() => setSqlOpen(!sqlOpen)}
              className="text-sm text-gray-500 cursor-pointer hover:text-gray-700 flex items-center gap-1"
            >
              <svg
                className={`w-3.5 h-3.5 transition-transform ${sqlOpen ? 'rotate-90' : ''}`}
                fill="none" stroke="currentColor" viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              {t('charts.editSql')}
            </button>

            {sqlOpen && (
              <div className="mt-2">
                <div className="border border-gray-200 rounded-lg overflow-hidden bg-gray-50">
                  <Editor
                    value={editedSql}
                    onValueChange={setEditedSql}
                    highlight={(code) =>
                      Prism.highlight(code, Prism.languages.sql, 'sql')
                    }
                    padding={12}
                    style={{
                      fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
                      fontSize: 13,
                      lineHeight: 1.5,
                      minHeight: 80,
                      maxHeight: 300,
                      overflow: 'auto',
                    }}
                    className="sql-editor"
                  />
                </div>
                <div className="flex items-center gap-3 mt-2">
                  <button
                    onClick={handleRunSql}
                    disabled={executeSql.isPending || !editedSql.trim()}
                    className="btn btn-primary text-sm px-4 py-1.5 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
                  >
                    <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M8 5v14l11-7z" />
                    </svg>
                    {executeSql.isPending ? t('charts.runningSql') : t('charts.runSql')}
                  </button>
                  {editedSql !== preview.chart.sql_query && (
                    <button
                      onClick={() => setEditedSql(preview.chart.sql_query)}
                      className="text-xs text-gray-400 hover:text-gray-600"
                    >
                      {t('common.reset')}
                    </button>
                  )}
                </div>
                {executeSql.isError && (
                  <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
                    <strong>{t('charts.sqlError')}</strong> {getErrorMessage(executeSql.error)}
                  </div>
                )}
              </div>
            )}
          </div>
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

      {/* Prompt Editor Modal */}
      <PromptEditorModal
        isOpen={showPromptEditor}
        onClose={() => setShowPromptEditor(false)}
      />

      {/* Generation History Modal */}
      <GenerationHistoryModal
        isOpen={showHistory}
        onClose={() => setShowHistory(false)}
        onSelectPrompt={(p) => setPrompt(p)}
      />
    </div>
  )
}
