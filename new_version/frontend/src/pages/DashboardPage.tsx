import SyncCard from '../components/SyncCard'
import ReferenceCard from '../components/ReferenceCard'
import {
  useSyncConfig,
  useSyncStatus,
  useSyncStats,
  useStartSync,
  useUpdateSyncConfig,
  useReferenceStatus,
  useStartRefSync,
  useStartAllRefSync,
} from '../hooks/useSync'

export default function DashboardPage() {
  const { data: config, isLoading: configLoading } = useSyncConfig()
  const { data: status } = useSyncStatus()
  const { data: stats } = useSyncStats()
  const startSync = useStartSync()
  const updateConfig = useUpdateSyncConfig()
  const { data: refStatus } = useReferenceStatus()
  const startRefSync = useStartRefSync()
  const startAllRefSync = useStartAllRefSync()

  if (configLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading...</div>
      </div>
    )
  }

  const getStatusForEntity = (entityType: string) => {
    return status?.entities.find((e) => e.entity_type === entityType)
  }

  return (
    <div className="space-y-6">
      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card bg-primary-50 border border-primary-200">
          <div className="text-sm text-primary-600">Total Records</div>
          <div className="text-2xl font-bold text-primary-800">
            {stats?.total_records.toLocaleString() ?? 0}
          </div>
        </div>
        <div className="card bg-green-50 border border-green-200">
          <div className="text-sm text-green-600">Entities Enabled</div>
          <div className="text-2xl font-bold text-green-800">
            {config?.entities.filter((e) => e.enabled).length ?? 0} / {config?.entities.length ?? 0}
          </div>
        </div>
        <div className="card bg-blue-50 border border-blue-200">
          <div className="text-sm text-blue-600">Status</div>
          <div className="text-2xl font-bold text-blue-800 capitalize">
            {status?.overall_status ?? 'Idle'}
          </div>
        </div>
        <div className="card bg-yellow-50 border border-yellow-200">
          <div className="text-sm text-yellow-600">Tables Synced</div>
          <div className="text-2xl font-bold text-yellow-800">
            {Object.values(stats?.entities ?? {}).filter((e) => e.count > 0).length}
          </div>
        </div>
      </div>

      {/* Entity Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {config?.entities.map((entityConfig) => (
          <SyncCard
            key={entityConfig.entity_type}
            config={entityConfig}
            status={getStatusForEntity(entityConfig.entity_type)}
            isStarting={startSync.isPending}
            onStartSync={(syncType) =>
              startSync.mutate({ entity: entityConfig.entity_type, syncType })
            }
            onToggleEnabled={(enabled) =>
              updateConfig.mutate({
                entity_type: entityConfig.entity_type,
                enabled,
              })
            }
          />
        ))}
      </div>

      {/* Reference Data Cards */}
      {refStatus && refStatus.references.length > 0 && (
        <div>
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold">Reference Data</h2>
            <button
              onClick={() => startAllRefSync.mutate()}
              disabled={startAllRefSync.isPending}
              className="btn btn-secondary text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {startAllRefSync.isPending ? 'Syncing...' : 'Sync All References'}
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {refStatus.references.map((ref) => (
              <ReferenceCard
                key={ref.name}
                reference={ref}
                onSync={() => startRefSync.mutate(ref.name)}
                isSyncing={startRefSync.isPending}
              />
            ))}
          </div>
        </div>
      )}

      {/* Stats Table */}
      {stats && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Detailed Statistics</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Entity
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Records
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Last Sync
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Last Modified
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {Object.entries(stats.entities).map(([entityType, entityStats]) => (
                  <tr key={entityType}>
                    <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900 capitalize">
                      {entityType}s
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                      {entityStats.count.toLocaleString()}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                      {entityStats.last_sync
                        ? new Date(entityStats.last_sync).toLocaleString()
                        : 'Never'}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                      {entityStats.last_modified
                        ? new Date(entityStats.last_modified).toLocaleString()
                        : 'N/A'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
