import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { DashboardListItem } from '../../services/api'
import { useDeleteDashboard } from '../../hooks/useDashboards'

interface DashboardCardProps {
  dashboard: DashboardListItem
}

export default function DashboardCard({ dashboard }: DashboardCardProps) {
  const [copied, setCopied] = useState(false)
  const deleteDashboard = useDeleteDashboard()
  const navigate = useNavigate()

  const dashboardUrl = `${window.location.origin}/embed/dashboard/${dashboard.slug}`

  const copyLink = () => {
    navigator.clipboard.writeText(dashboardUrl).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="card">
      <div className="flex justify-between items-start">
        <div className="min-w-0 flex-1">
          <h3 className="text-base font-semibold text-gray-800 truncate">{dashboard.title}</h3>
          {dashboard.description && (
            <p className="text-sm text-gray-500 mt-1 line-clamp-2">{dashboard.description}</p>
          )}
          <div className="flex items-center space-x-3 mt-2 text-xs text-gray-400">
            <span>{dashboard.chart_count} chart{dashboard.chart_count !== 1 ? 's' : ''}</span>
            <span>{new Date(dashboard.created_at).toLocaleDateString()}</span>
            {!dashboard.is_active && (
              <span className="text-red-400">Inactive</span>
            )}
          </div>
        </div>

        <div className="flex space-x-1 ml-3">
          <button
            onClick={() => window.open(dashboardUrl, '_blank')}
            className="p-1.5 rounded text-sm bg-green-50 text-green-600 hover:bg-green-100"
            title="Open public page"
          >
            Open
          </button>
          <button
            onClick={() => navigate(`/dashboards/${dashboard.id}/edit`)}
            className="p-1.5 rounded text-sm bg-blue-50 text-blue-600 hover:bg-blue-100"
            title="Edit dashboard"
          >
            Edit
          </button>
          <button
            onClick={copyLink}
            className="p-1.5 rounded text-sm bg-gray-100 text-gray-500 hover:bg-gray-200"
            title="Copy link"
          >
            {copied ? 'Copied!' : 'Link'}
          </button>
          <button
            onClick={() => {
              if (confirm('Delete this dashboard?')) deleteDashboard.mutate(dashboard.id)
            }}
            className="p-1.5 rounded text-sm bg-red-50 text-red-500 hover:bg-red-100"
            title="Delete"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  )
}
