import { useState } from 'react'
import AISubTabs from '../components/ai/AISubTabs'
import ReportChat from '../components/reports/ReportChat'
import ReportCard from '../components/reports/ReportCard'
import ReportPromptEditorModal from '../components/reports/ReportPromptEditorModal'
import PublishReportModal from '../components/reports/PublishReportModal'
import PublishedReportCard from '../components/reports/PublishedReportCard'
import { useReports, useReportSave, usePublishedReports } from '../hooks/useReports'
import { useTranslation } from '../i18n'
import type { ReportPreview } from '../services/api'

export default function ReportsPage() {
  const { t } = useTranslation()
  const [showPromptEditor, setShowPromptEditor] = useState(false)
  const [showPublishModal, setShowPublishModal] = useState(false)
  const [reportReady, setReportReady] = useState<{
    sessionId: string
    preview: ReportPreview
  } | null>(null)
  const [saveTitle, setSaveTitle] = useState('')
  const [saveDescription, setSaveDescription] = useState('')

  const { data: reportsData, isLoading: reportsLoading } = useReports()
  const { data: publishedData, isLoading: publishedLoading } = usePublishedReports()
  const saveReport = useReportSave()

  const handleReportReady = (sessionId: string, preview: ReportPreview) => {
    setReportReady({ sessionId, preview })
    setSaveTitle(preview.title)
    setSaveDescription(preview.description || '')
  }

  const handleSave = () => {
    if (!reportReady || !saveTitle.trim()) return
    saveReport.mutate(
      {
        session_id: reportReady.sessionId,
        title: saveTitle.trim(),
        description: saveDescription.trim() || undefined,
      },
      {
        onSuccess: () => {
          setReportReady(null)
          setSaveTitle('')
          setSaveDescription('')
        },
      },
    )
  }

  return (
    <div className="space-y-6">
      <AISubTabs />

      {/* Chat Section */}
      <div className="relative">
        <div className="absolute top-0 right-0 z-10">
          <button
            onClick={() => setShowPromptEditor(true)}
            className="text-sm text-gray-600 hover:text-primary-600 flex items-center gap-2 mt-2 mr-2"
            title={t('reports.promptEditor')}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </button>
        </div>
        <ReportChat onReportReady={handleReportReady} />
      </div>

      {/* Save Section */}
      {reportReady && (
        <div className="card border-2 border-primary-200">
          <h3 className="text-lg font-semibold mb-3">{t('reports.saveReport')}</h3>

          {/* Preview */}
          <div className="bg-gray-50 rounded-lg p-3 mb-4">
            <div className="text-sm font-medium">{reportReady.preview.title}</div>
            {reportReady.preview.description && (
              <div className="text-xs text-gray-500 mt-1">{reportReady.preview.description}</div>
            )}
            <div className="text-xs text-gray-400 mt-2">
              SQL-запросов: {reportReady.preview.sql_queries.length}
            </div>
            {reportReady.preview.data_results.length > 0 && (
              <div className="mt-2 space-y-1">
                {reportReady.preview.data_results.map((dr, i) => (
                  <div key={i} className="text-xs text-gray-500">
                    {dr.purpose}: {dr.row_count} rows
                    {dr.error && <span className="text-red-500 ml-1">({dr.error})</span>}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-3">
            <input
              type="text"
              value={saveTitle}
              onChange={(e) => setSaveTitle(e.target.value)}
              placeholder="Название отчёта"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
            />
            <input
              type="text"
              value={saveDescription}
              onChange={(e) => setSaveDescription(e.target.value)}
              placeholder="Описание (необязательно)"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
            />
            <div className="flex gap-2">
              <button
                onClick={handleSave}
                disabled={saveReport.isPending || !saveTitle.trim()}
                className="btn btn-primary disabled:opacity-50"
              >
                {saveReport.isPending ? t('common.saving') : t('reports.saveReport')}
              </button>
              <button
                onClick={() => setReportReady(null)}
                className="btn btn-secondary"
              >
                {t('common.cancel')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Saved Reports */}
      <div>
        <h2 className="text-lg font-semibold mb-4">
          {t('reports.savedReports')} {reportsData ? `(${reportsData.total})` : ''}
        </h2>

        {reportsLoading ? (
          <div className="flex items-center justify-center h-32 text-gray-500">
            {t('common.loading')}
          </div>
        ) : !reportsData?.reports.length ? (
          <div className="card text-center text-gray-400 py-12">
            {t('reports.noSavedReports')}
          </div>
        ) : (
          <div className="space-y-4">
            {reportsData.reports.map((report) => (
              <ReportCard key={report.id} report={report} />
            ))}
          </div>
        )}
      </div>

      {/* Published Reports */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">
            {t('reports.publishedReports')} {publishedData ? `(${publishedData.total})` : ''}
          </h2>
          {reportsData?.reports && reportsData.reports.length > 0 && (
            <button
              onClick={() => setShowPublishModal(true)}
              className="btn btn-primary text-sm"
            >
              {t('reports.publishReport')}
            </button>
          )}
        </div>

        {publishedLoading ? (
          <div className="flex items-center justify-center h-32 text-gray-500">
            {t('common.loading')}
          </div>
        ) : !publishedData?.reports.length ? (
          <div className="card text-center text-gray-400 py-12">
            {t('reports.noPublishedReports')}
          </div>
        ) : (
          <div className="space-y-4">
            {publishedData.reports.map((pub) => (
              <PublishedReportCard key={pub.id} report={pub} />
            ))}
          </div>
        )}
      </div>

      {/* Publish Report Modal */}
      {showPublishModal && reportsData?.reports && (
        <PublishReportModal
          reports={reportsData.reports}
          onClose={() => setShowPublishModal(false)}
        />
      )}

      {/* Prompt Editor Modal */}
      <ReportPromptEditorModal
        isOpen={showPromptEditor}
        onClose={() => setShowPromptEditor(false)}
      />
    </div>
  )
}
