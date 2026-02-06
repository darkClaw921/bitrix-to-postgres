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

// === References Types ===

export interface ReferenceTypeInfo {
  name: string
  table_name: string
  api_method: string
  unique_key: string[]
  fields_count: number
}

export interface ReferenceTypesResponse {
  reference_types: ReferenceTypeInfo[]
}

export interface ReferenceStatusItem {
  name: string
  table_name: string
  table_exists: boolean
  record_count: number
  status: string
  last_sync_type: string | null
  records_synced: number | null
  error_message: string | null
  last_sync_at: string | null
  completed_at: string | null
  auto_only?: boolean
}

export interface ReferenceStatusResponse {
  references: ReferenceStatusItem[]
}

export interface RefSyncStartResponse {
  status: string
  ref_name?: string
  message: string
  reference_types?: string[]
}

// === References API ===

export const referencesApi = {
  getTypes: () =>
    api.get<ReferenceTypesResponse>('/references/types').then((r) => r.data),

  getStatus: () =>
    api.get<ReferenceStatusResponse>('/references/status').then((r) => r.data),

  syncOne: (refName: string) =>
    api.post<RefSyncStartResponse>(`/references/sync/${refName}`).then((r) => r.data),

  syncAll: () =>
    api.post<RefSyncStartResponse>('/references/sync-all').then((r) => r.data),
}

// === Charts Types ===

export interface ChartSpec {
  title: string
  chart_type: 'bar' | 'line' | 'pie' | 'area' | 'scatter'
  sql_query: string
  data_keys: {
    x: string
    y: string | string[]
  }
  colors?: string[]
  description?: string
}

export interface ChartGenerateRequest {
  prompt: string
  table_filter?: string[]
}

export interface ChartGenerateResponse {
  chart: ChartSpec
  data: Record<string, unknown>[]
  row_count: number
  execution_time_ms: number
}

export interface ChartSaveRequest {
  title: string
  description?: string
  user_prompt: string
  chart_type: string
  chart_config: Record<string, unknown>
  sql_query: string
}

export interface SavedChart {
  id: number
  title: string
  description?: string
  user_prompt: string
  chart_type: string
  chart_config: Record<string, unknown>
  sql_query: string
  is_pinned: boolean
  created_at: string
  updated_at: string
}

export interface ChartListResponse {
  charts: SavedChart[]
  total: number
  page: number
  per_page: number
}

export interface ChartDataResponse {
  data: Record<string, unknown>[]
  row_count: number
  execution_time_ms: number
}

// === Schema Types ===

export interface ColumnInfo {
  name: string
  data_type: string
  is_nullable: boolean
  column_default?: string
  description?: string
}

export interface TableInfo {
  table_name: string
  columns: ColumnInfo[]
  row_count?: number
}

export interface SchemaTablesResponse {
  tables: TableInfo[]
}

export interface SchemaDescriptionResponse {
  id: number
  tables: TableInfo[]
  markdown: string
  entity_filter?: string
  include_related: boolean
  created_at: string
  updated_at: string
}

export interface SchemaDescriptionUpdateRequest {
  markdown: string
}

export interface SchemaDescriptionListItem {
  id: number
  entity_filter?: string
  include_related: boolean
  created_at: string
  updated_at: string
}

export interface SchemaDescriptionListResponse {
  items: SchemaDescriptionListItem[]
  total: number
}

// === Charts API ===

export const chartsApi = {
  generate: (data: ChartGenerateRequest) =>
    api.post<ChartGenerateResponse>('/charts/generate', data).then((r) => r.data),

  save: (data: ChartSaveRequest) =>
    api.post<SavedChart>('/charts/save', data).then((r) => r.data),

  list: (page = 1, perPage = 20) =>
    api.get<ChartListResponse>('/charts/list', { params: { page, per_page: perPage } }).then((r) => r.data),

  getData: (chartId: number) =>
    api.get<ChartDataResponse>(`/charts/${chartId}/data`).then((r) => r.data),

  delete: (chartId: number) =>
    api.delete(`/charts/${chartId}`).then((r) => r.data),

  togglePin: (chartId: number) =>
    api.post<SavedChart>(`/charts/${chartId}/pin`).then((r) => r.data),
}

// === Schema API ===

export const schemaApi = {
  describe: () =>
    api.get<SchemaDescriptionResponse>('/schema/describe').then((r) => r.data),

  tables: () =>
    api.get<SchemaTablesResponse>('/schema/tables').then((r) => r.data),

  getHistory: () =>
    api.get<SchemaDescriptionResponse>('/schema/history').then((r) => r.data),

  update: (descId: number, data: SchemaDescriptionUpdateRequest) =>
    api.patch<SchemaDescriptionResponse>(`/schema/${descId}`, data).then((r) => r.data),

  list: () =>
    api.get<SchemaDescriptionListResponse>('/schema/list').then((r) => r.data),
}

export default api
