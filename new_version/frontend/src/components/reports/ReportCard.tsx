import { useState } from 'react'
import { useTranslation } from '../../i18n'
import { useDeleteReport, useRunReport, useToggleReportPin } from '../../hooks/useReports'
import type { Report } from '../../services/api'
import ReportRunViewer from './ReportRunViewer'
import ScheduleSelector from './ScheduleSelector'

interface ReportCardProps {
  report: Report
}

const statusColors: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700',
  active: 'bg-green-100 text-green-700',
  paused: 'bg-yellow-100 text-yellow-700',
  error: 'bg-red-100 text-red-700',
}

const scheduleLabels: Record<string, string> = {
  once: 'scheduleOnce',
  daily: 'scheduleDaily',
  weekly: 'scheduleWeekly',
  monthly: 'scheduleMonthly',
}

export default function ReportCard({ report }: ReportCardProps) {
  const { t } = useTranslation()
  const [showRuns, setShowRuns] = useState(false)
  const [showSchedule, setShowSchedule] = useState(false)
  const deleteReport = useDeleteReport()
  const runReport = useRunReport()
  const togglePin = useToggleReportPin()

  const statusKey = `status${report.status.charAt(0).toUpperCase()}${report.status.slice(1)}` as keyof typeof t
  const scheduleKey = scheduleLabels[report.schedule_type] || 'scheduleOnce'

  const handleDelete = () => {
    if (window.confirm(t('reports.confirmDelete'))) {
      deleteReport.mutate(report.id)
    }
  }

  return (
    <div className="card">
      <div className="flex justify-between items-start">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            {report.is_pinned && (
              <span className="text-yellow-500 text-sm" title={t('charts.pinned')}>
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M5 5a2 2 0 012-2h6a2 2 0 012 2v2h2a1 1 0 010 2h-1l-1 8a2 2 0 01-2 2H7a2 2 0 01-2-2L4 9H3a1 1 0 010-2h2V5z" />
                </svg>
              </span>
            )}
            <h3 className="text-base font-semibold truncate">{report.title}</h3>
          </div>
          {report.description && (
            <p className="text-sm text-gray-500 mt-1 line-clamp-2">{report.description}</p>
          )}
          <div className="flex items-center gap-2 mt-2">
            <span className={`px-2 py-0.5 text-xs rounded-full ${statusColors[report.status] || statusColors.draft}`}>
              {(t as Function)(`reports.${statusKey}`)}
            </span>
            <span className="text-xs text-gray-400">
              {(t as Function)(`reports.${scheduleKey}`)}
            </span>
            {report.last_run_at && (
              <span className="text-xs text-gray-400">
                {new Date(report.last_run_at).toLocaleString()}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1 ml-3 flex-shrink-0">
          <button
            onClick={() => runReport.mutate(report.id)}
            disabled={runReport.isPending}
            className="btn btn-primary text-xs px-3 py-1 disabled:opacity-50"
            title={t('reports.runNow')}
          >
            {runReport.isPending ? t('reports.running') : t('reports.runNow')}
          </button>
          <button
            onClick={() => setShowRuns(!showRuns)}
            className="btn btn-secondary text-xs px-3 py-1"
            title={t('reports.viewResults')}
          >
            {t('reports.viewResults')}
          </button>
          <button
            onClick={() => setShowSchedule(!showSchedule)}
            className="text-gray-400 hover:text-gray-600 p-1"
            title={t('reports.schedule')}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </button>
          <button
            onClick={() => togglePin.mutate(report.id)}
            className="text-gray-400 hover:text-yellow-500 p-1"
            title={report.is_pinned ? t('reports.unpin') : t('reports.pin')}
          >
            <svg className="w-4 h-4" fill={report.is_pinned ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h6a2 2 0 012 2v2h2a1 1 0 010 2h-1l-1 8a2 2 0 01-2 2H7a2 2 0 01-2-2L4 9H3a1 1 0 010-2h2V5z" />
            </svg>
          </button>
          <button
            onClick={handleDelete}
            className="text-gray-400 hover:text-red-500 p-1"
            title={t('common.delete')}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>

      {/* Schedule Editor */}
      {showSchedule && (
        <div className="mt-4 pt-4 border-t border-gray-100">
          <ScheduleSelector report={report} onClose={() => setShowSchedule(false)} />
        </div>
      )}

      {/* Runs Viewer */}
      {showRuns && (
        <div className="mt-4 pt-4 border-t border-gray-100">
          <ReportRunViewer reportId={report.id} />
        </div>
      )}
    </div>
  )
}
