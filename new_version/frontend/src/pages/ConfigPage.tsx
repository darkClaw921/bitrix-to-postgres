import { useState } from 'react'
import { useSyncConfig, useUpdateSyncConfig } from '../hooks/useSync'
import { webhooksApi } from '../services/api'

export default function ConfigPage() {
  const { data: config, isLoading } = useSyncConfig()
  const updateConfig = useUpdateSyncConfig()
  const [webhookBaseUrl, setWebhookBaseUrl] = useState('')
  const [webhookStatus, setWebhookStatus] = useState<string | null>(null)
  const [isRegisteringWebhooks, setIsRegisteringWebhooks] = useState(false)

  const handleIntervalChange = (entityType: string, interval: number) => {
    updateConfig.mutate({
      entity_type: entityType,
      sync_interval_minutes: interval,
    })
  }

  const handleWebhookToggle = (entityType: string, enabled: boolean) => {
    updateConfig.mutate({
      entity_type: entityType,
      webhook_enabled: enabled,
    })
  }

  const handleRegisterWebhooks = async () => {
    setIsRegisteringWebhooks(true)
    setWebhookStatus(null)
    try {
      const result = await webhooksApi.register(webhookBaseUrl || undefined)
      setWebhookStatus(
        `Registered: ${result.registered.length} events. Failed: ${result.failed.length}`
      )
    } catch (err) {
      setWebhookStatus('Failed to register webhooks')
    } finally {
      setIsRegisteringWebhooks(false)
    }
  }

  const handleUnregisterWebhooks = async () => {
    setIsRegisteringWebhooks(true)
    setWebhookStatus(null)
    try {
      const result = await webhooksApi.unregister(webhookBaseUrl || undefined)
      setWebhookStatus(`Unregistered: ${result.unregistered.length} events`)
    } catch (err) {
      setWebhookStatus('Failed to unregister webhooks')
    } finally {
      setIsRegisteringWebhooks(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Configuration</h1>

      {/* Entity Configuration */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Sync Configuration</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Entity
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Enabled
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Sync Interval
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Webhooks
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {config?.entities.map((entity) => (
                <tr key={entity.entity_type}>
                  <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900 capitalize">
                    {entity.entity_type}s
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <label className="flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={entity.enabled}
                        onChange={(e) =>
                          updateConfig.mutate({
                            entity_type: entity.entity_type,
                            enabled: e.target.checked,
                          })
                        }
                        className="sr-only peer"
                      />
                      <div className="relative w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
                    </label>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <select
                      value={entity.sync_interval_minutes}
                      onChange={(e) =>
                        handleIntervalChange(entity.entity_type, Number(e.target.value))
                      }
                      className="input w-32"
                    >
                      <option value={5}>5 min</option>
                      <option value={10}>10 min</option>
                      <option value={15}>15 min</option>
                      <option value={30}>30 min</option>
                      <option value={60}>1 hour</option>
                      <option value={120}>2 hours</option>
                      <option value={360}>6 hours</option>
                      <option value={720}>12 hours</option>
                      <option value={1440}>24 hours</option>
                    </select>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <label className="flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={entity.webhook_enabled}
                        onChange={(e) =>
                          handleWebhookToggle(entity.entity_type, e.target.checked)
                        }
                        className="sr-only peer"
                      />
                      <div className="relative w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
                    </label>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Webhook Registration */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Webhook Registration</h2>
        <p className="text-sm text-gray-600 mb-4">
          Register webhook handlers with Bitrix24 to receive real-time updates.
        </p>

        <div className="space-y-4">
          <div>
            <label className="label">Webhook Handler URL (optional)</label>
            <input
              type="url"
              value={webhookBaseUrl}
              onChange={(e) => setWebhookBaseUrl(e.target.value)}
              placeholder="https://your-domain.com"
              className="input"
            />
            <p className="text-xs text-gray-500 mt-1">
              Leave empty to use default server URL
            </p>
          </div>

          {webhookStatus && (
            <div className="p-3 bg-gray-50 border border-gray-200 rounded text-sm">
              {webhookStatus}
            </div>
          )}

          <div className="flex space-x-2">
            <button
              onClick={handleRegisterWebhooks}
              disabled={isRegisteringWebhooks}
              className="btn btn-primary disabled:opacity-50"
            >
              {isRegisteringWebhooks ? 'Registering...' : 'Register Webhooks'}
            </button>
            <button
              onClick={handleUnregisterWebhooks}
              disabled={isRegisteringWebhooks}
              className="btn btn-danger disabled:opacity-50"
            >
              {isRegisteringWebhooks ? 'Processing...' : 'Unregister All'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
