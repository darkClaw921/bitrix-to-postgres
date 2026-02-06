import { ReferenceStatusItem } from '../services/api'

const REF_DISPLAY_NAMES: Record<string, string> = {
  crm_status: 'Statuses & Stages',
  crm_deal_category: 'Deal Pipelines',
  crm_currency: 'Currencies',
}

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
  const isRunning = reference.status === 'running'
  const isFailed = reference.status === 'failed'

  const formatDate = (date: string | null) => {
    if (!date) return 'Never'
    return new Date(date).toLocaleString()
  }

  const getStatusColor = () => {
    if (isRunning) return 'text-blue-600'
    if (isFailed) return 'text-red-600'
    if (reference.status === 'completed') return 'text-green-600'
    return 'text-gray-500'
  }

  const getStatusText = () => {
    if (isRunning) return 'Syncing...'
    if (isFailed) return 'Failed'
    if (reference.status === 'completed') return 'Completed'
    return 'Idle'
  }

  const displayName = REF_DISPLAY_NAMES[reference.name] || reference.name

  return (
    <div className="card">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-lg font-semibold">{displayName}</h3>
          <span className={`text-sm ${getStatusColor()}`}>{getStatusText()}</span>
        </div>
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
          Reference
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm mb-4">
        <div>
          <span className="text-gray-500">Last Sync:</span>
          <p className="font-medium">{formatDate(reference.last_sync_at)}</p>
        </div>
        <div>
          <span className="text-gray-500">Table:</span>
          <p className="font-medium">{reference.table_exists ? reference.table_name : 'Not created'}</p>
        </div>
        <div>
          <span className="text-gray-500">Records:</span>
          <p className="font-medium">{reference.record_count}</p>
        </div>
        <div>
          <span className="text-gray-500">Last Synced:</span>
          <p className="font-medium">{reference.records_synced ?? 0} records</p>
        </div>
      </div>

      {isFailed && reference.error_message && (
        <div className="mb-4 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
          {reference.error_message}
        </div>
      )}

      <div className="flex space-x-2">
        <button
          onClick={onSync}
          disabled={isRunning || isSyncing}
          className="btn btn-primary flex-1 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isRunning ? 'Syncing...' : 'Sync'}
        </button>
      </div>
    </div>
  )
}
