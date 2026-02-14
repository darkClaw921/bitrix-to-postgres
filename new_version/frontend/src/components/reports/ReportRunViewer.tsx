import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useTranslation } from '../../i18n'
import { markdownTableComponents } from './markdownComponents'
import { useReportRuns } from '../../hooks/useReports'
import type { ReportRun } from '../../services/api'

interface ReportRunViewerProps {
  reportId: number
}

const runStatusColors: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-700',
  running: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
}

export default function ReportRunViewer({ reportId }: ReportRunViewerProps) {
  const { t } = useTranslation()
  const [selectedRun, setSelectedRun] = useState<ReportRun | null>(null)
  const [activeTab, setActiveTab] = useState<'markdown' | 'sql' | 'data' | 'prompt'>('markdown')
  const { data, isLoading } = useReportRuns(reportId)

  if (isLoading) {
    return <div className="text-sm text-gray-500">{t('common.loading')}</div>
  }

  if (!data?.runs.length) {
    return <div className="text-sm text-gray-400">{t('reports.noRuns')}</div>
  }

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium">{t('reports.reportRuns')}</h4>

      {/* Runs list */}
      <div className="space-y-2">
        {data.runs.map((run) => (
          <div
            key={run.id}
            onClick={() => setSelectedRun(selectedRun?.id === run.id ? null : run)}
            className={`flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer text-sm
              ${selectedRun?.id === run.id ? 'bg-primary-50 border border-primary-200' : 'bg-gray-50 hover:bg-gray-100'}`}
          >
            <div className="flex items-center gap-2">
              <span className={`px-2 py-0.5 text-xs rounded-full ${runStatusColors[run.status]}`}>
                {(t as Function)(`reports.runStatus${run.status.charAt(0).toUpperCase()}${run.status.slice(1)}`)}
              </span>
              <span className="text-xs text-gray-500">
                {run.trigger_type === 'manual' ? t('reports.triggerManual') : t('reports.triggerScheduled')}
              </span>
            </div>
            <div className="flex items-center gap-3 text-xs text-gray-400">
              {run.execution_time_ms && (
                <span>{(run.execution_time_ms / 1000).toFixed(1)}s</span>
              )}
              <span>{new Date(run.created_at).toLocaleString()}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Selected run details */}
      {selectedRun && (
        <div className="border border-gray-200 rounded-lg p-4">
          {selectedRun.error_message && (
            <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
              {selectedRun.error_message}
            </div>
          )}

          {/* Tabs */}
          <div className="flex gap-4 border-b border-gray-200 mb-3">
            <button
              onClick={() => setActiveTab('markdown')}
              className={`pb-2 text-sm font-medium border-b-2 ${
                activeTab === 'markdown'
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {t('reports.reportPreview')}
            </button>
            <button
              onClick={() => setActiveTab('sql')}
              className={`pb-2 text-sm font-medium border-b-2 ${
                activeTab === 'sql'
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {t('reports.sqlQueries')}
            </button>
            <button
              onClick={() => setActiveTab('data')}
              className={`pb-2 text-sm font-medium border-b-2 ${
                activeTab === 'data'
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {t('reports.rawData')}
            </button>
            <button
              onClick={() => setActiveTab('prompt')}
              className={`pb-2 text-sm font-medium border-b-2 ${
                activeTab === 'prompt'
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {t('reports.fullPrompt')}
            </button>
          </div>

          {/* Tab content */}
          {activeTab === 'markdown' && selectedRun.result_markdown && (
            <div className="prose prose-sm max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownTableComponents}>
                {selectedRun.result_markdown}
              </ReactMarkdown>
            </div>
          )}

          {activeTab === 'sql' && selectedRun.sql_queries_executed && (
            <div className="space-y-3">
              {selectedRun.sql_queries_executed.map((q: Record<string, unknown>, i: number) => (
                <div key={i} className="bg-gray-50 rounded p-3">
                  <div className="text-xs text-gray-500 mb-1">{String(q.purpose || '')}</div>
                  <pre className="text-xs font-mono whitespace-pre-wrap overflow-x-auto">
                    {String(q.sql || '')}
                  </pre>
                  <div className="text-xs text-gray-400 mt-1">
                    {Number(q.row_count || 0)} rows | {Number(q.time_ms || 0).toFixed(0)}ms
                    {q.error ? <span className="text-red-500 ml-2">{String(q.error)}</span> : null}
                  </div>
                </div>
              ))}
            </div>
          )}

          {activeTab === 'data' && selectedRun.result_data && (
            <div className="max-h-96 overflow-auto">
              <pre className="text-xs font-mono whitespace-pre-wrap">
                {JSON.stringify(selectedRun.result_data, null, 2)}
              </pre>
            </div>
          )}

          {activeTab === 'prompt' && (
            <div className="max-h-96 overflow-auto">
              {selectedRun.llm_prompt ? (
                <pre className="text-xs font-mono whitespace-pre-wrap bg-gray-50 rounded p-3">
                  {selectedRun.llm_prompt}
                </pre>
              ) : (
                <div className="text-sm text-gray-400">{t('reports.noPromptData')}</div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
