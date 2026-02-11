import { useState } from 'react'
import { SyncConfigItem, SyncStatusItem, type BitrixFilter } from '../services/api'
import { useTranslation } from '../i18n'
import FilterDialog from './FilterDialog'

interface SyncCardProps {
  config: SyncConfigItem
  status?: SyncStatusItem
  onStartSync: (syncType: 'full' | 'incremental', filter?: BitrixFilter) => void
  onToggleEnabled: (enabled: boolean) => void
  isStarting?: boolean
}

export default function SyncCard({
  config,
  status,
  onStartSync,
  onToggleEnabled,
  isStarting,
}: SyncCardProps) {
  const { t } = useTranslation()
  const [showFilterDialog, setShowFilterDialog] = useState(false)

  const isRunning = status?.status === 'running'
  const isQueued = status?.status === 'queued'
  const isFailed = status?.status === 'failed'
  const isTimeLimitError = isFailed && status?.error_message?.includes('OPERATION_TIME_LIMIT')

  const formatDate = (date: string | null) => {
    if (!date) return t('common.never')
    return new Date(date).toLocaleString()
  }

  const getStatusColor = () => {
    if (isRunning) return 'text-blue-600'
    if (isQueued) return 'text-amber-600'
    if (isTimeLimitError) return 'text-yellow-600'
    if (isFailed) return 'text-red-600'
    if (status?.status === 'completed') return 'text-green-600'
    return 'text-gray-500'
  }

  const getStatusText = () => {
    if (isRunning) return t('syncCard.syncing')
    if (isQueued) return t('syncCard.queued')
    if (isFailed) return t('syncCard.failed')
    if (status?.status === 'completed') return t('syncCard.completed')
    return t('common.idle')
  }

  const handleFullSyncClick = () => {
    if (isTimeLimitError) {
      setShowFilterDialog(true)
    } else {
      onStartSync('full')
    }
  }

  const handleFilterApply = (filter: BitrixFilter) => {
    setShowFilterDialog(false)
    onStartSync('full', filter)
  }

  return (
    <div className="card">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-lg font-semibold capitalize">{config.entity_type}s</h3>
          <span className={`text-sm ${getStatusColor()}`}>{getStatusText()}</span>
        </div>
        <label className="flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={config.enabled}
            onChange={(e) => onToggleEnabled(e.target.checked)}
            className="sr-only peer"
          />
          <div className="relative w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
          <span className="ml-2 text-sm text-gray-600">{t('common.enabled')}</span>
        </label>
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm mb-4">
        <div>
          <span className="text-gray-500">{t('syncCard.lastSync')}</span>
          <p className="font-medium">{formatDate(config.last_sync_at)}</p>
        </div>
        <div>
          <span className="text-gray-500">{t('syncCard.interval')}</span>
          <p className="font-medium">{config.sync_interval_minutes} {t('syncCard.minutes')}</p>
        </div>
        <div>
          <span className="text-gray-500">{t('dashboard.records')}:</span>
          <p className="font-medium">{status?.records_synced ?? 0}</p>
        </div>
        <div>
          <span className="text-gray-500">{t('syncCard.webhooks')}</span>
          <p className="font-medium">{config.webhook_enabled ? t('common.enabled') : t('common.disabled')}</p>
        </div>
      </div>

      {/* OPERATION_TIME_LIMIT warning (yellow) */}
      {isTimeLimitError && status?.error_message && (
        <div className="mb-4 p-3 bg-yellow-50 border border-yellow-300 rounded text-sm text-yellow-800">
          <div className="font-medium mb-1">{t('syncCard.timeLimitError')}</div>
          <div className="text-xs text-yellow-700">{t('syncCard.useFilter')}</div>
        </div>
      )}

      {/* Regular error (red), but not for OPERATION_TIME_LIMIT */}
      {isFailed && !isTimeLimitError && status?.error_message && (
        <div className="mb-4 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
          {status.error_message}
        </div>
      )}

      <div className="flex space-x-2">
        <button
          onClick={handleFullSyncClick}
          disabled={isRunning || isQueued || isStarting || !config.enabled}
          className="btn btn-primary flex-1 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isRunning ? t('syncCard.syncing') : isQueued ? t('syncCard.queued') : isTimeLimitError ? t('syncCard.useFilter') : t('syncCard.fullSync')}
        </button>
        {isTimeLimitError && (
          <button
            onClick={() => setShowFilterDialog(true)}
            disabled={isRunning || isQueued || isStarting || !config.enabled}
            className="btn btn-secondary px-3 disabled:opacity-50 disabled:cursor-not-allowed"
            title={t('syncCard.filterByDate')}
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M3 3a1 1 0 011-1h12a1 1 0 011 1v3a1 1 0 01-.293.707L12 11.414V15a1 1 0 01-.293.707l-2 2A1 1 0 018 17v-5.586L3.293 6.707A1 1 0 013 6V3z" clipRule="evenodd" />
            </svg>
          </button>
        )}
        <button
          onClick={() => onStartSync('incremental')}
          disabled={isRunning || isQueued || isStarting || !config.enabled}
          className="btn btn-secondary flex-1 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {t('monitoring.incremental')}
        </button>
      </div>

      {showFilterDialog && (
        <FilterDialog
          entityType={config.entity_type}
          onApply={handleFilterApply}
          onCancel={() => setShowFilterDialog(false)}
        />
      )}
    </div>
  )
}
