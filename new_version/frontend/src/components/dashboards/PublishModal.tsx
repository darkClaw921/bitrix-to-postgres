import { useState } from 'react'
import type { SavedChart, DashboardPublishResponse } from '../../services/api'
import { usePublishDashboard } from '../../hooks/useDashboards'
import { useTranslation } from '../../i18n'

interface PublishModalProps {
  charts: SavedChart[]
  onClose: () => void
}

export default function PublishModal({ charts, onClose }: PublishModalProps) {
  const { t } = useTranslation()
  const [title, setTitle] = useState('My Dashboard')
  const [description, setDescription] = useState('')
  const [refreshInterval, setRefreshInterval] = useState(10)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set(charts.map((c) => c.id)))
  const [result, setResult] = useState<DashboardPublishResponse | null>(null)
  const [copiedField, setCopiedField] = useState<string | null>(null)

  const publishDashboard = usePublishDashboard()

  const toggleChart = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    if (selectedIds.size === charts.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(charts.map((c) => c.id)))
    }
  }

  const handlePublish = () => {
    if (selectedIds.size === 0 || !title.trim()) return

    publishDashboard.mutate(
      {
        title: title.trim(),
        description: description.trim() || undefined,
        chart_ids: Array.from(selectedIds),
        refresh_interval_minutes: refreshInterval,
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
    const dashboardUrl = `${window.location.origin}/embed/dashboard/${result.dashboard.slug}`

    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
          <h3 className="text-lg font-semibold text-green-700 mb-4">{t('publishModal.published')}</h3>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">{t('publishModal.dashboardUrl')}</label>
              <div className="flex items-center space-x-2">
                <input
                  type="text"
                  readOnly
                  value={dashboardUrl}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded text-sm bg-gray-50"
                />
                <button
                  onClick={() => copyToClipboard(dashboardUrl, 'url')}
                  className="px-3 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
                >
                  {copiedField === 'url' ? t('common.copied') : t('common.copy')}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">{t('publishModal.passwordLabel')}</label>
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
                {t('publishModal.passwordHelp')}
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
        <h3 className="text-lg font-semibold mb-4">{t('publishModal.title')}</h3>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('publishModal.formTitle')}</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder={t('publishModal.dashboardTitle')}
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

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('publishModal.autoRefreshInterval')}</label>
            <select
              value={refreshInterval}
              onChange={(e) => setRefreshInterval(Number(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value={1}>{t('publishModal.minute1')}</option>
              <option value={5}>{t('publishModal.minutes5')}</option>
              <option value={10}>{t('publishModal.minutes10')}</option>
              <option value={15}>{t('publishModal.minutes15')}</option>
              <option value={30}>{t('publishModal.minutes30')}</option>
              <option value={60}>{t('publishModal.minutes60')}</option>
            </select>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-gray-700">
                {t('publishModal.selectCharts')} ({selectedIds.size}/{charts.length})
              </label>
              <button
                onClick={toggleAll}
                className="text-xs text-blue-600 hover:text-blue-800"
              >
                {selectedIds.size === charts.length ? t('publishModal.deselectAll') : t('publishModal.selectAll')}
              </button>
            </div>

            <div className="max-h-48 overflow-y-auto border border-gray-200 rounded-lg divide-y">
              {charts.map((chart) => (
                <label
                  key={chart.id}
                  className="flex items-center px-3 py-2 hover:bg-gray-50 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.has(chart.id)}
                    onChange={() => toggleChart(chart.id)}
                    className="mr-3 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <div className="min-w-0">
                    <div className="text-sm text-gray-800 truncate">{chart.title}</div>
                    <div className="text-xs text-gray-400">{chart.chart_type}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>
        </div>

        {publishDashboard.isError && (
          <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-600">
            {(publishDashboard.error as Error).message || t('publishModal.failedToPublish')}
          </div>
        )}

        <div className="mt-6 flex justify-end space-x-3">
          <button onClick={onClose} className="px-4 py-2 bg-gray-100 text-gray-700 rounded hover:bg-gray-200">
            {t('common.cancel')}
          </button>
          <button
            onClick={handlePublish}
            disabled={publishDashboard.isPending || selectedIds.size === 0 || !title.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {publishDashboard.isPending ? t('publishModal.publishing') : t('publishModal.publish')}
          </button>
        </div>
      </div>
    </div>
  )
}
