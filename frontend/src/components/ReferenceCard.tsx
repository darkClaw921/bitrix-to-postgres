import { ReferenceStatusItem } from '../services/api'
import { useTranslation } from '../i18n'

interface ReferenceCardProps {
  reference: ReferenceStatusItem
  onSync: () => void
  isSyncing?: boolean
}

export default function ReferenceCard({
  reference,
  onSync,
  isSyncing,
}: ReferenceCardProps) {
  const { t } = useTranslation()

  const isRunning = reference.status === 'running'
  const isFailed = reference.status === 'failed'
  const isAutoOnly = reference.auto_only === true

  const getDisplayName = (name: string) => {
    const map: Record<string, string> = {
      crm_status: t('referenceCard.statuses'),
      crm_deal_category: t('referenceCard.pipelines'),
      crm_currency: t('referenceCard.currencies'),
      enum_values: t('referenceCard.enumValues'),
    }
    return map[name] || name
  }

  const formatDate = (date: string | null) => {
    if (!date) return t('common.never')
    return new Date(date).toLocaleString()
  }

  const getStatusColor = () => {
    if (isRunning) return 'text-blue-600'
    if (isFailed) return 'text-red-600'
    if (reference.status === 'completed') return 'text-green-600'
    return 'text-gray-500'
  }

  const getStatusText = () => {
    if (isRunning) return t('syncCard.syncing')
    if (isFailed) return t('syncCard.failed')
    if (reference.status === 'completed') return t('syncCard.completed')
    return t('common.idle')
  }

  const displayName = getDisplayName(reference.name)

  return (
    <div className="card">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-lg font-semibold">{displayName}</h3>
          <span className={`text-sm ${getStatusColor()}`}>{getStatusText()}</span>
        </div>
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${isAutoOnly ? 'bg-gray-100 text-gray-600' : 'bg-purple-100 text-purple-800'}`}>
          {isAutoOnly ? t('referenceCard.auto') : t('referenceCard.reference')}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm mb-4">
        <div>
          <span className="text-gray-500">{t('syncCard.lastSync')}</span>
          <p className="font-medium">{formatDate(reference.last_sync_at)}</p>
        </div>
        <div>
          <span className="text-gray-500">{t('referenceCard.table')}</span>
          <p className="font-medium">{reference.table_exists ? reference.table_name : t('referenceCard.notCreated')}</p>
        </div>
        <div>
          <span className="text-gray-500">{t('dashboard.records')}:</span>
          <p className="font-medium">{reference.record_count}</p>
        </div>
        <div>
          <span className="text-gray-500">{t('referenceCard.lastSynced')}</span>
          <p className="font-medium">{reference.records_synced ?? 0} {t('referenceCard.recordsSuffix')}</p>
        </div>
      </div>

      {isFailed && reference.error_message && (
        <div className="mb-4 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
          {reference.error_message}
        </div>
      )}

      <div className="flex space-x-2">
        {isAutoOnly ? (
          <span className="text-xs text-gray-400 flex-1 text-center py-2">
            {t('referenceCard.autoSyncText')}
          </span>
        ) : (
          <button
            onClick={onSync}
            disabled={isRunning || isSyncing}
            className="btn btn-primary flex-1 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isRunning ? t('syncCard.syncing') : t('referenceCard.sync')}
          </button>
        )}
      </div>
    </div>
  )
}
