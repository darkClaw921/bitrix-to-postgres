import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || '/api/v1'

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Types
export interface SyncConfigItem {
  entity_type: string
  enabled: boolean
  sync_interval_minutes: number
  webhook_enabled: boolean
  last_sync_at: string | null
}

export interface SyncConfigResponse {
  entities: SyncConfigItem[]
  default_interval_minutes: number
}

export interface SyncStatusItem {
  entity_type: string
  status: string
  last_sync_type: string | null
  last_sync_at: string | null
  records_synced: number | null
  error_message: string | null
}

export interface SyncStatusResponse {
  overall_status: string
  entities: SyncStatusItem[]
}

export interface SyncStartResponse {
  status: string
  entity: string
  sync_type: string
  message: string | null
}

export interface SyncLogEntry {
  id: number
  entity_type: string
  sync_type: string
  status: string
  records_processed: number | null
  error_message: string | null
  started_at: string | null
  completed_at: string | null
}

export interface SyncHistoryResponse {
  history: SyncLogEntry[]
  total: number
  page: number
  per_page: number
}

export interface EntityStats {
  count: number
  last_sync: string | null
  last_modified: string | null
}

export interface SyncStatsResponse {
  entities: Record<string, EntityStats>
  total_records: number
}

export interface HealthResponse {
  status: string
  database: string
  scheduler: {
    running: boolean
    jobs_count: number
  }
  crm_tables: string[]
}

// API functions
export const syncApi = {
  getConfig: () =>
    api.get<SyncConfigResponse>('/sync/config').then((r) => r.data),

  updateConfig: (data: Partial<SyncConfigItem>) =>
    api.put<SyncConfigItem>('/sync/config', data).then((r) => r.data),

  startSync: (entity: string, syncType: 'full' | 'incremental' = 'full') =>
    api.post<SyncStartResponse>(`/sync/start/${entity}`, { sync_type: syncType }).then((r) => r.data),

  getStatus: () =>
    api.get<SyncStatusResponse>('/sync/status').then((r) => r.data),

  getRunningSyncs: () =>
    api.get<{ running_syncs: string[]; count: number }>('/sync/running').then((r) => r.data),
}

export const statusApi = {
  getHistory: (params?: {
    page?: number
    per_page?: number
    entity_type?: string
    status?: string
    sync_type?: string
  }) =>
    api.get<SyncHistoryResponse>('/status/history', { params }).then((r) => r.data),

  getStats: () =>
    api.get<SyncStatsResponse>('/status/stats').then((r) => r.data),

  getHealth: () =>
    api.get<HealthResponse>('/status/health').then((r) => r.data),

  getScheduler: () =>
    api.get('/status/scheduler').then((r) => r.data),
}

export const webhooksApi = {
  register: (handlerBaseUrl?: string) =>
    api.post('/webhooks/register', null, { params: { handler_base_url: handlerBaseUrl } }).then((r) => r.data),

  unregister: (handlerBaseUrl?: string) =>
    api.delete('/webhooks/unregister', { params: { handler_base_url: handlerBaseUrl } }).then((r) => r.data),

  getRegistered: () =>
    api.get('/webhooks/registered').then((r) => r.data),
}

export default api
