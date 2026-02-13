import { useState } from 'react'
import type { PublishedReportListItem } from '../../services/api'
import { useDeletePublishedReport, usePublishedReport, useAddPublishedReportLink, useRemovePublishedReportLink, useChangePublishedReportPassword } from '../../hooks/useReports'
import { useTranslation } from '../../i18n'

interface PublishedReportCardProps {
  report: PublishedReportListItem
  allPublishedReports: PublishedReportListItem[]
}

export default function PublishedReportCard({ report, allPublishedReports }: PublishedReportCardProps) {
  const { t } = useTranslation()
  const [copiedLink, setCopiedLink] = useState(false)
  const [showLinks, setShowLinks] = useState(false)
  const [selectedLinkId, setSelectedLinkId] = useState<number | ''>('')
  const [linkLabel, setLinkLabel] = useState('')
  const [newPassword, setNewPassword] = useState<string | null>(null)
  const deletePublished = useDeletePublishedReport()
  const addLink = useAddPublishedReportLink()
  const removeLink = useRemovePublishedReportLink()
  const changePassword = useChangePublishedReportPassword()
  const { data: publishedDetail, isLoading: detailLoading } = usePublishedReport(
    showLinks ? report.id : 0,
  )

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

  const handleChangePassword = () => {
    changePassword.mutate(report.id, {
      onSuccess: (data) => {
        setNewPassword(data.password)
      },
    })
  }

  const handleAddLink = () => {
    if (!selectedLinkId) return
    addLink.mutate(
      {
        pubId: report.id,
        data: {
          linked_published_report_id: Number(selectedLinkId),
          label: linkLabel.trim() || undefined,
        },
      },
      {
        onSuccess: () => {
          setSelectedLinkId('')
          setLinkLabel('')
        },
      },
    )
  }

  const handleRemoveLink = (linkId: number) => {
    removeLink.mutate({ pubId: report.id, linkId })
  }

  const linkedReports = publishedDetail?.linked_reports || []
  const linkedIds = new Set(linkedReports.map((lr) => lr.id))
  const availableReports = allPublishedReports.filter(
    (r) => r.id !== report.id && !linkedIds.has(r.id),
  )

  return (
    <div className="card">
      <div className="flex items-center justify-between">
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
            onClick={() => setShowLinks(!showLinks)}
            className={`px-3 py-1.5 text-sm rounded ${
              showLinks ? 'bg-indigo-100 text-indigo-700' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {t('reports.linkedReports')}
          </button>
          <button
            onClick={handleChangePassword}
            disabled={changePassword.isPending}
            className="px-3 py-1.5 text-sm bg-yellow-50 text-yellow-700 rounded hover:bg-yellow-100 disabled:opacity-50"
            title={t('editor.changePassword')}
          >
            {changePassword.isPending ? '...' : t('editor.changePassword')}
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

      {/* New password display */}
      {newPassword && (
        <div className="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium text-yellow-800">{t('reports.reportPassword')}</div>
              <code className="text-sm font-mono text-yellow-900">{newPassword}</code>
              <div className="text-xs text-yellow-600 mt-1">{t('reports.reportPasswordHelp')}</div>
            </div>
            <button
              onClick={() => {
                navigator.clipboard.writeText(newPassword)
                setNewPassword(null)
              }}
              className="px-3 py-1 text-xs bg-yellow-200 text-yellow-800 rounded hover:bg-yellow-300"
            >
              {t('common.copy')}
            </button>
          </div>
        </div>
      )}

      {/* Linked Reports Management */}
      {showLinks && (
        <div className="mt-4 pt-4 border-t border-gray-100">
          <h4 className="text-sm font-medium mb-3">{t('reports.linkedReports')}</h4>

          {detailLoading ? (
            <div className="text-sm text-gray-400">{t('common.loading')}</div>
          ) : linkedReports.length === 0 ? (
            <div className="text-sm text-gray-400 mb-3">{t('reports.noLinkedReports')}</div>
          ) : (
            <div className="space-y-2 mb-3">
              {linkedReports.map((link) => (
                <div
                  key={link.id}
                  className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{link.label || link.linked_title || '-'}</span>
                    {link.linked_slug && (
                      <span className="text-xs text-gray-400">/{link.linked_slug}</span>
                    )}
                  </div>
                  <button
                    onClick={() => handleRemoveLink(link.id)}
                    disabled={removeLink.isPending}
                    className="text-xs text-red-500 hover:text-red-700 disabled:opacity-50"
                  >
                    {t('common.remove')}
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Add new link */}
          {availableReports.length > 0 && (
            <div className="flex items-center gap-2">
              <select
                value={selectedLinkId}
                onChange={(e) => setSelectedLinkId(e.target.value ? Number(e.target.value) : '')}
                className="flex-1 text-sm border border-gray-200 rounded px-2 py-1.5"
              >
                <option value="">{t('reports.selectPublishedReport')}</option>
                {availableReports.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.title}
                  </option>
                ))}
              </select>
              <input
                type="text"
                value={linkLabel}
                onChange={(e) => setLinkLabel(e.target.value)}
                placeholder={t('reports.tabLabel')}
                className="w-32 text-sm border border-gray-200 rounded px-2 py-1.5"
              />
              <button
                onClick={handleAddLink}
                disabled={!selectedLinkId || addLink.isPending}
                className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
              >
                {t('common.add')}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
