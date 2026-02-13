import { useState } from 'react'
import type { Report, PublishReportResponse } from '../../services/api'
import { usePublishReport } from '../../hooks/useReports'
import { useTranslation } from '../../i18n'

interface PublishReportModalProps {
  reports: Report[]
  onClose: () => void
}

export default function PublishReportModal({ reports, onClose }: PublishReportModalProps) {
  const { t } = useTranslation()
  const [selectedReportId, setSelectedReportId] = useState<number | ''>(reports.length > 0 ? reports[0].id : '')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [result, setResult] = useState<PublishReportResponse | null>(null)
  const [copiedField, setCopiedField] = useState<string | null>(null)

  const publishReport = usePublishReport()

  const handlePublish = () => {
    if (!selectedReportId) return

    publishReport.mutate(
      {
        report_id: selectedReportId as number,
        title: title.trim() || undefined,
        description: description.trim() || undefined,
      },
      {
        onSuccess: (data) => setResult(data),
      },
    )
  }

  const copyToClipboard = (text: string, field: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedField(field)
      setTimeout(() => setCopiedField(null), 2000)
    })
  }

  if (result) {
    const reportUrl = `${window.location.origin}/embed/report/${result.published_report.slug}`

    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
          <h3 className="text-lg font-semibold text-green-700 mb-4">{t('reports.reportPublished')}</h3>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">{t('reports.reportUrl')}</label>
              <div className="flex items-center space-x-2">
                <input
                  type="text"
                  readOnly
                  value={reportUrl}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded text-sm bg-gray-50"
                />
                <button
                  onClick={() => copyToClipboard(reportUrl, 'url')}
                  className="px-3 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
                >
                  {copiedField === 'url' ? t('common.copied') : t('common.copy')}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">{t('reports.reportPassword')}</label>
              <div className="flex items-center space-x-2">
                <input
                  type="text"
                  readOnly
                  value={result.password}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded text-sm bg-gray-50 font-mono"
                />
                <button
                  onClick={() => copyToClipboard(result.password, 'password')}
                  className="px-3 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
                >
                  {copiedField === 'password' ? t('common.copied') : t('common.copy')}
                </button>
              </div>
              <p className="text-xs text-gray-400 mt-1">
                {t('reports.reportPasswordHelp')}
              </p>
            </div>
          </div>

          <div className="mt-6 flex justify-end">
            <button onClick={onClose} className="px-4 py-2 bg-gray-100 text-gray-700 rounded hover:bg-gray-200">
              {t('common.close')}
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg p-6">
        <h3 className="text-lg font-semibold mb-4">{t('reports.publishReportTitle')}</h3>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('reports.selectReport')}</label>
            <select
              value={selectedReportId}
              onChange={(e) => setSelectedReportId(Number(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              {reports.map((r) => (
                <option key={r.id} value={r.id}>{r.title}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('publishModal.formTitle')}</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder={t('reports.publishReportTitle')}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('publishModal.descriptionOptional')}</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              rows={2}
              placeholder={t('publishModal.briefDescription')}
            />
          </div>
        </div>

        {publishReport.isError && (
          <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-600">
            {(publishReport.error as Error).message || t('publishModal.failedToPublish')}
          </div>
        )}

        <div className="mt-6 flex justify-end space-x-3">
          <button onClick={onClose} className="px-4 py-2 bg-gray-100 text-gray-700 rounded hover:bg-gray-200">
            {t('common.cancel')}
          </button>
          <button
            onClick={handlePublish}
            disabled={publishReport.isPending || !selectedReportId}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {publishReport.isPending ? t('reports.publishing') : t('reports.publishReport')}
          </button>
        </div>
      </div>
    </div>
  )
}
