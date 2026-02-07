import { useState } from 'react'
import { useSyncHistory, useHealth } from '../hooks/useSync'
import { statusApi } from '../services/api'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from '../i18n'

export default function MonitoringPage() {
  const { t } = useTranslation()
  const [page, setPage] = useState(1)
  const [entityFilter, setEntityFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [syncTypeFilter, setSyncTypeFilter] = useState('')

  const { data: history, isLoading } = useSyncHistory({
    page,
    per_page: 20,
    entity_type: entityFilter || undefined,
    status: statusFilter || undefined,
    sync_type: syncTypeFilter || undefined,
  })

  const { data: health } = useHealth()

  const { data: scheduler } = useQuery({
    queryKey: ['scheduler'],
    queryFn: statusApi.getScheduler,
    refetchInterval: 10000,
  })

  const formatDate = (date: string | null) => {
    if (!date) return '-'
    return new Date(date).toLocaleString()
  }

  const formatDuration = (start: string | null, end: string | null) => {
    if (!start || !end) return '-'
    const duration = new Date(end).getTime() - new Date(start).getTime()
    if (duration < 1000) return `${duration}ms`
    if (duration < 60000) return `${(duration / 1000).toFixed(1)}s`
    return `${(duration / 60000).toFixed(1)}m`
  }

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      completed: 'bg-green-100 text-green-800',
      running: 'bg-blue-100 text-blue-800',
      failed: 'bg-red-100 text-red-800',
      pending: 'bg-yellow-100 text-yellow-800',
    }
    return colors[status] || 'bg-gray-100 text-gray-800'
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{t('monitoring.monitoring')}</h1>

      {/* Health Status */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <h3 className="text-sm font-medium text-gray-500 mb-2">{t('monitoring.database')}</h3>
          <div className="flex items-center space-x-2">
            <span
              className={`w-3 h-3 rounded-full ${
                health?.database === 'connected' ? 'bg-green-500' : 'bg-red-500'
              }`}
            />
            <span className="font-medium">
              {health?.database === 'connected' ? t('health.connected') : health?.database || 'Unknown'}
            </span>
          </div>
        </div>

        <div className="card">
          <h3 className="text-sm font-medium text-gray-500 mb-2">{t('monitoring.scheduler')}</h3>
          <div className="flex items-center space-x-2">
            <span
              className={`w-3 h-3 rounded-full ${
                scheduler?.running ? 'bg-green-500' : 'bg-red-500'
              }`}
            />
            <span className="font-medium">
              {scheduler?.running ? `${t('monitoring.running')} (${scheduler?.job_count} ${t('monitoring.jobs')})` : t('monitoring.stopped')}
            </span>
          </div>
        </div>

        <div className="card">
          <h3 className="text-sm font-medium text-gray-500 mb-2">{t('monitoring.crmTables')}</h3>
          <span className="font-medium">{health?.crm_tables?.length ?? 0} {t('monitoring.tables')}</span>
          {health?.crm_tables && health.crm_tables.length > 0 && (
            <p className="text-xs text-gray-500 mt-1">
              {health.crm_tables.join(', ')}
            </p>
          )}
        </div>
      </div>

      {/* Scheduled Jobs */}
      {scheduler?.jobs && scheduler.jobs.length > 0 && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">{t('monitoring.scheduledJobs')}</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    {t('monitoring.job')}
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    {t('monitoring.trigger')}
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    {t('monitoring.nextRun')}
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {scheduler.jobs.map((job: { id: string; name: string; trigger: string; next_run: string | null }) => (
                  <tr key={job.id}>
                    <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                      {job.name}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                      {job.trigger}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                      {job.next_run ? new Date(job.next_run).toLocaleString() : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Sync History */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">{t('monitoring.syncHistory')}</h2>

        {/* Filters */}
        <div className="flex flex-wrap gap-4 mb-4">
          <select
            value={entityFilter}
            onChange={(e) => { setEntityFilter(e.target.value); setPage(1) }}
            className="input w-40"
          >
            <option value="">{t('monitoring.allEntities')}</option>
            <option value="deal">{t('monitoring.deals')}</option>
            <option value="contact">{t('monitoring.contacts')}</option>
            <option value="lead">{t('monitoring.leads')}</option>
            <option value="company">{t('monitoring.companies')}</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
            className="input w-40"
          >
            <option value="">{t('monitoring.allStatus')}</option>
            <option value="completed">{t('monitoring.completed')}</option>
            <option value="running">{t('monitoring.running')}</option>
            <option value="failed">{t('monitoring.failed')}</option>
          </select>

          <select
            value={syncTypeFilter}
            onChange={(e) => { setSyncTypeFilter(e.target.value); setPage(1) }}
            className="input w-40"
          >
            <option value="">{t('monitoring.allTypes')}</option>
            <option value="full">{t('monitoring.full')}</option>
            <option value="incremental">{t('monitoring.incremental')}</option>
            <option value="webhook">{t('monitoring.webhook')}</option>
          </select>
        </div>

        {isLoading ? (
          <div className="text-center py-8 text-gray-500">{t('common.loading')}</div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      {t('dashboard.entity')}
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      {t('monitoring.type')}
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      {t('dashboard.status')}
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      {t('dashboard.records')}
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      {t('monitoring.started')}
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      {t('monitoring.duration')}
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {history?.history.map((log) => (
                    <tr key={log.id}>
                      <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900 capitalize">
                        {log.entity_type}s
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500 capitalize">
                        {log.sync_type}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span
                          className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusBadge(
                            log.status
                          )}`}
                        >
                          {log.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                        {log.records_processed ?? '-'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                        {formatDate(log.started_at)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                        {formatDuration(log.started_at, log.completed_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {history && history.total > history.per_page && (
              <div className="flex justify-between items-center mt-4">
                <div className="text-sm text-gray-500">
                  {t('monitoring.showing')} {(page - 1) * history.per_page + 1} -{' '}
                  {Math.min(page * history.per_page, history.total)} {t('monitoring.of')} {history.total}
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={() => setPage(page - 1)}
                    disabled={page === 1}
                    className="btn btn-secondary disabled:opacity-50"
                  >
                    {t('monitoring.previous')}
                  </button>
                  <button
                    onClick={() => setPage(page + 1)}
                    disabled={page * history.per_page >= history.total}
                    className="btn btn-secondary disabled:opacity-50"
                  >
                    {t('monitoring.next')}
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
