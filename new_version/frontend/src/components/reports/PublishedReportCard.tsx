import { useState } from 'react'
import type { PublishedReportListItem } from '../../services/api'
import { useDeletePublishedReport } from '../../hooks/useReports'
import { useTranslation } from '../../i18n'

interface PublishedReportCardProps {
  report: PublishedReportListItem
}

export default function PublishedReportCard({ report }: PublishedReportCardProps) {
  const { t } = useTranslation()
  const [copiedLink, setCopiedLink] = useState(false)
  const deletePublished = useDeletePublishedReport()

  const reportUrl = `${window.location.origin}/embed/report/${report.slug}`

  const handleCopyLink = () => {
    navigator.clipboard.writeText(reportUrl).then(() => {
      setCopiedLink(true)
      setTimeout(() => setCopiedLink(false), 2000)
    })
  }

  const handleDelete = () => {
    if (confirm(t('reports.confirmDelete'))) {
      deletePublished.mutate(report.id)
    }
  }

  const handleOpen = () => {
    window.open(reportUrl, '_blank')
  }

  return (
    <div className="card flex items-center justify-between">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-gray-800 truncate">{report.title}</h3>
          {!report.is_active && (
            <span className="text-xs px-2 py-0.5 bg-gray-200 text-gray-600 rounded">
              {t('dashboardCard.inactive')}
            </span>
          )}
        </div>
        {report.report_title && (
          <p className="text-xs text-gray-400 mt-0.5">{report.report_title}</p>
        )}
        {report.description && (
          <p className="text-sm text-gray-500 mt-1 truncate">{report.description}</p>
        )}
      </div>

      <div className="flex items-center space-x-2 ml-4">
        <button
          onClick={handleOpen}
          className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          {t('reports.openReport')}
        </button>
        <button
          onClick={handleCopyLink}
          className="px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
        >
          {copiedLink ? t('common.copied') : t('dashboardCard.copyLink')}
        </button>
        <button
          onClick={handleDelete}
          disabled={deletePublished.isPending}
          className="px-3 py-1.5 text-sm bg-red-50 text-red-600 rounded hover:bg-red-100 disabled:opacity-50"
        >
          {t('common.delete')}
        </button>
      </div>
    </div>
  )
}
