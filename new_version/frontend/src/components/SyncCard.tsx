import { SyncConfigItem, SyncStatusItem } from '../services/api'
import { useTranslation } from '../i18n'

interface SyncCardProps {
  config: SyncConfigItem
  status?: SyncStatusItem
  onStartSync: (syncType: 'full' | 'incremental') => void
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
  const isRunning = status?.status === 'running'
  const isFailed = status?.status === 'failed'

  const formatDate = (date: string | null) => {
    if (!date) return t('common.never')
    return new Date(date).toLocaleString()
  }

  const getStatusColor = () => {
    if (isRunning) return 'text-blue-600'
    if (isFailed) return 'text-red-600'
    if (status?.status === 'completed') return 'text-green-600'
    return 'text-gray-500'
  }

  const getStatusText = () => {
    if (isRunning) return t('syncCard.syncing')
    if (isFailed) return t('syncCard.failed')
    if (status?.status === 'completed') return t('syncCard.completed')
    return t('common.idle')
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

      {isFailed && status?.error_message && (
        <div className="mb-4 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
          {status.error_message}
        </div>
      )}

      <div className="flex space-x-2">
        <button
          onClick={() => onStartSync('full')}
          disabled={isRunning || isStarting || !config.enabled}
          className="btn btn-primary flex-1 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isRunning ? t('syncCard.syncing') : t('syncCard.fullSync')}
        </button>
        <button
          onClick={() => onStartSync('incremental')}
          disabled={isRunning || isStarting || !config.enabled}
          className="btn btn-secondary flex-1 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {t('monitoring.incremental')}
        </button>
      </div>
    </div>
  )
}
