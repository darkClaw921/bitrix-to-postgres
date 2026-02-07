import { useState } from 'react'
import type { SavedChart, DashboardPublishResponse } from '../../services/api'
import { usePublishDashboard } from '../../hooks/useDashboards'

interface PublishModalProps {
  charts: SavedChart[]
  onClose: () => void
}

export default function PublishModal({ charts, onClose }: PublishModalProps) {
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
          <h3 className="text-lg font-semibold text-green-700 mb-4">Dashboard Published!</h3>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">Dashboard URL</label>
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
                  {copiedField === 'url' ? 'Copied!' : 'Copy'}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">Password</label>
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
                  {copiedField === 'password' ? 'Copied!' : 'Copy'}
                </button>
              </div>
              <p className="text-xs text-gray-400 mt-1">
                Save this password — it won't be shown again
              </p>
            </div>
          </div>

          <div className="mt-6 flex justify-end">
            <button onClick={onClose} className="px-4 py-2 bg-gray-100 text-gray-700 rounded hover:bg-gray-200">
              Close
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg p-6">
        <h3 className="text-lg font-semibold mb-4">Publish Dashboard</h3>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="Dashboard title"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description (optional)</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              rows={2}
              placeholder="Brief description"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Auto-refresh interval</label>
            <select
              value={refreshInterval}
              onChange={(e) => setRefreshInterval(Number(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value={1}>1 minute</option>
              <option value={5}>5 minutes</option>
              <option value={10}>10 minutes</option>
              <option value={15}>15 minutes</option>
              <option value={30}>30 minutes</option>
              <option value={60}>60 minutes</option>
            </select>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-gray-700">
                Select Charts ({selectedIds.size}/{charts.length})
              </label>
              <button
                onClick={toggleAll}
                className="text-xs text-blue-600 hover:text-blue-800"
              >
                {selectedIds.size === charts.length ? 'Deselect All' : 'Select All'}
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
            {(publishDashboard.error as Error).message || 'Failed to publish'}
          </div>
        )}

        <div className="mt-6 flex justify-end space-x-3">
          <button onClick={onClose} className="px-4 py-2 bg-gray-100 text-gray-700 rounded hover:bg-gray-200">
            Cancel
          </button>
          <button
            onClick={handlePublish}
            disabled={publishDashboard.isPending || selectedIds.size === 0 || !title.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {publishDashboard.isPending ? 'Publishing...' : 'Publish'}
          </button>
        </div>
      </div>
    </div>
  )
}
