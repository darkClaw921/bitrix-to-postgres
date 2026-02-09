import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || '/api/v1'

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Restore token from localStorage on module init
const savedToken = localStorage.getItem('auth_token')
if (savedToken) {
  api.defaults.headers.common['Authorization'] = `Bearer ${savedToken}`
}

// 401 response interceptor — clear token and redirect to login
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token')
      delete api.defaults.headers.common['Authorization']
      // Only redirect if not already on login page
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

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

export interface ChartDisplayConfig {
  // data keys (existing)
  x: string
  y: string | string[]
  colors?: string[]
  description?: string
  // legend
  legend?: { visible?: boolean; position?: 'top' | 'bottom' | 'left' | 'right' }
  // grid
  grid?: { visible?: boolean; strokeDasharray?: string }
  // axes
  xAxis?: { label?: string; angle?: number }
  yAxis?: { label?: string; format?: 'number' | 'currency' | 'percent' }
  // line/area
  line?: { strokeWidth?: number; type?: 'monotone' | 'linear' | 'natural' | 'step' }
  area?: { fillOpacity?: number }
  // pie
  pie?: { innerRadius?: number; showLabels?: boolean }
  // indicator
  indicator?: {
    prefix?: string
    suffix?: string
    fontSize?: 'sm' | 'md' | 'lg' | 'xl'
    color?: string
  }
  // table
  table?: {
    showColumnTotals?: boolean
    showRowTotals?: boolean
    sortable?: boolean
    defaultSortColumn?: string
    defaultSortDirection?: 'asc' | 'desc'
    pageSize?: number
    columnFormats?: Record<string, 'number' | 'currency' | 'percent' | 'text'>
  }
  // funnel
  funnel?: { showLabels?: boolean; labelPosition?: 'right' | 'inside' }
  // horizontal_bar (uses same settings as bar — grid, xAxis, yAxis)
  horizontal_bar?: {}
}

export interface ChartSpec {
  title: string
  chart_type: 'bar' | 'line' | 'pie' | 'area' | 'scatter' | 'indicator' | 'table' | 'funnel' | 'horizontal_bar'
  sql_query: string
  data_keys: {
    x: string
    y: string | string[]
  }
  colors?: string[]
  description?: string
  // display config (optional, from chart_config)
  legend?: ChartDisplayConfig['legend']
  grid?: ChartDisplayConfig['grid']
  xAxis?: ChartDisplayConfig['xAxis']
  yAxis?: ChartDisplayConfig['yAxis']
  line?: ChartDisplayConfig['line']
  area?: ChartDisplayConfig['area']
  pie?: ChartDisplayConfig['pie']
  indicator?: ChartDisplayConfig['indicator']
  table?: ChartDisplayConfig['table']
  funnel?: ChartDisplayConfig['funnel']
  horizontal_bar?: ChartDisplayConfig['horizontal_bar']
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

export interface ChartPromptTemplate {
  id: number
  name: string
  content: string
  is_active: boolean
  created_at: string
  updated_at: string
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

  updateConfig: (chartId: number, config: Partial<ChartDisplayConfig>) =>
    api.patch<SavedChart>(`/charts/${chartId}/config`, { config }).then((r) => r.data),

  getPromptTemplate: () =>
    api.get<ChartPromptTemplate>('/charts/prompt-template/bitrix-context').then((r) => r.data),

  updatePromptTemplate: (content: string) =>
    api.put<ChartPromptTemplate>('/charts/prompt-template/bitrix-context', { content }).then((r) => r.data),
}

// === Schema API ===

export const schemaApi = {
  describe: () =>
    api.get<SchemaDescriptionResponse>('/schema/describe').then((r) => r.data),

  describeRaw: () =>
    api.get<SchemaDescriptionResponse>('/schema/describe-raw').then((r) => r.data),

  tables: () =>
    api.get<SchemaTablesResponse>('/schema/tables').then((r) => r.data),

  getHistory: () =>
    api.get<SchemaDescriptionResponse>('/schema/history').then((r) => r.data),

  update: (descId: number, data: SchemaDescriptionUpdateRequest) =>
    api.patch<SchemaDescriptionResponse>(`/schema/${descId}`, data).then((r) => r.data),

  list: () =>
    api.get<SchemaDescriptionListResponse>('/schema/list').then((r) => r.data),
}

// === Dashboard Types ===

export interface DashboardChart {
  id: number
  dashboard_id: number
  chart_id: number
  title_override?: string
  description_override?: string
  layout_x: number
  layout_y: number
  layout_w: number
  layout_h: number
  sort_order: number
  chart_title?: string
  chart_description?: string
  chart_type?: string
  chart_config?: Record<string, unknown>
  sql_query?: string
  user_prompt?: string
  created_at?: string
}

export interface DashboardLink {
  id: number
  dashboard_id: number
  linked_dashboard_id: number
  sort_order: number
  label?: string
  linked_title?: string
  linked_slug?: string
}

export interface Dashboard {
  id: number
  slug: string
  title: string
  description?: string
  is_active: boolean
  refresh_interval_minutes: number
  charts: DashboardChart[]
  linked_dashboards?: DashboardLink[]
  selectors?: DashboardSelector[]
  created_at: string
  updated_at: string
}

export interface DashboardListItem {
  id: number
  slug: string
  title: string
  description?: string
  is_active: boolean
  refresh_interval_minutes: number
  chart_count: number
  created_at: string
  updated_at: string
}

export interface DashboardListResponse {
  dashboards: DashboardListItem[]
  total: number
  page: number
  per_page: number
}

export interface DashboardPublishRequest {
  title: string
  description?: string
  chart_ids: number[]
  refresh_interval_minutes?: number
}

export interface DashboardPublishResponse {
  dashboard: Dashboard
  password: string
}

export interface DashboardUpdateRequest {
  title?: string
  description?: string
  refresh_interval_minutes?: number
}

export interface LayoutItem {
  id: number
  x: number
  y: number
  w: number
  h: number
  sort_order: number
}

export interface DashboardLayoutUpdateRequest {
  layouts: LayoutItem[]
}

export interface ChartOverrideUpdateRequest {
  title_override?: string
  description_override?: string
}

export interface IframeCodeRequest {
  chart_ids: number[]
  width?: string
  height?: string
}

export interface IframeCodeItem {
  chart_id: number
  html: string
}

export interface IframeCodeResponse {
  iframes: IframeCodeItem[]
}

export interface DashboardAuthResponse {
  token: string
  expires_in_minutes: number
}

export interface PasswordChangeResponse {
  password: string
}

// === Selector Types ===

export interface SelectorMapping {
  id: number
  selector_id: number
  dashboard_chart_id: number
  target_column: string
  target_table?: string
  operator_override?: string
  created_at?: string
}

export interface DashboardSelector {
  id: number
  dashboard_id: number
  name: string
  label: string
  selector_type: 'date_range' | 'single_date' | 'dropdown' | 'multi_select' | 'text'
  operator: string
  config?: {
    source_table?: string
    source_column?: string
    static_options?: string[]
    default_value?: unknown
    placeholder?: string
    label_table?: string
    label_column?: string
    label_value_column?: string
  }
  sort_order: number
  is_required: boolean
  mappings: SelectorMapping[]
  created_at?: string
}

export interface SelectorCreateRequest {
  name: string
  label: string
  selector_type: string
  operator?: string
  config?: Record<string, unknown>
  sort_order?: number
  is_required?: boolean
  mappings?: {
    dashboard_chart_id: number
    target_column: string
    target_table?: string
    operator_override?: string
  }[]
}

export interface SelectorUpdateRequest {
  name?: string
  label?: string
  selector_type?: string
  operator?: string
  config?: Record<string, unknown>
  sort_order?: number
  is_required?: boolean
}

export interface FilterValue {
  name: string
  value: unknown
}

// === Dashboards API (internal) ===

export const dashboardsApi = {
  publish: (data: DashboardPublishRequest) =>
    api.post<DashboardPublishResponse>('/dashboards/publish', data).then((r) => r.data),

  list: (page = 1, perPage = 20) =>
    api.get<DashboardListResponse>('/dashboards/list', { params: { page, per_page: perPage } }).then((r) => r.data),

  get: (id: number) =>
    api.get<Dashboard>(`/dashboards/${id}`).then((r) => r.data),

  update: (id: number, data: DashboardUpdateRequest) =>
    api.put<Dashboard>(`/dashboards/${id}`, data).then((r) => r.data),

  delete: (id: number) =>
    api.delete(`/dashboards/${id}`).then((r) => r.data),

  updateLayout: (id: number, data: DashboardLayoutUpdateRequest) =>
    api.put<Dashboard>(`/dashboards/${id}/layout`, data).then((r) => r.data),

  updateChartOverride: (dashboardId: number, dcId: number, data: ChartOverrideUpdateRequest) =>
    api.put(`/dashboards/${dashboardId}/charts/${dcId}`, data).then((r) => r.data),

  removeChart: (dashboardId: number, dcId: number) =>
    api.delete(`/dashboards/${dashboardId}/charts/${dcId}`).then((r) => r.data),

  changePassword: (id: number) =>
    api.post<PasswordChangeResponse>(`/dashboards/${id}/change-password`).then((r) => r.data),

  getIframeCode: (data: IframeCodeRequest) =>
    api.post<IframeCodeResponse>('/dashboards/iframe-code', data).then((r) => r.data),

  addLink: (dashboardId: number, data: { linked_dashboard_id: number; label?: string; sort_order?: number }) =>
    api.post<DashboardLink>(`/dashboards/${dashboardId}/links`, data).then((r) => r.data),

  removeLink: (dashboardId: number, linkId: number) =>
    api.delete(`/dashboards/${dashboardId}/links/${linkId}`).then((r) => r.data),

  updateLinks: (dashboardId: number, links: { id: number; sort_order: number }[]) =>
    api.put<DashboardLink[]>(`/dashboards/${dashboardId}/links`, { links }).then((r) => r.data),

  // Selectors
  createSelector: (dashboardId: number, data: SelectorCreateRequest) =>
    api.post<DashboardSelector>(`/dashboards/${dashboardId}/selectors`, data).then((r) => r.data),

  listSelectors: (dashboardId: number) =>
    api.get<{ selectors: DashboardSelector[] }>(`/dashboards/${dashboardId}/selectors`).then((r) => r.data),

  updateSelector: (dashboardId: number, selectorId: number, data: SelectorUpdateRequest) =>
    api.put<DashboardSelector>(`/dashboards/${dashboardId}/selectors/${selectorId}`, data).then((r) => r.data),

  deleteSelector: (dashboardId: number, selectorId: number) =>
    api.delete(`/dashboards/${dashboardId}/selectors/${selectorId}`).then((r) => r.data),

  addSelectorMapping: (dashboardId: number, selectorId: number, data: {
    dashboard_chart_id: number
    target_column: string
    target_table?: string
    operator_override?: string
  }) =>
    api.post<SelectorMapping>(`/dashboards/${dashboardId}/selectors/${selectorId}/mappings`, data).then((r) => r.data),

  removeSelectorMapping: (dashboardId: number, selectorId: number, mappingId: number) =>
    api.delete(`/dashboards/${dashboardId}/selectors/${selectorId}/mappings/${mappingId}`).then((r) => r.data),

  getSelectorOptions: (dashboardId: number, selectorId: number) =>
    api.get<{ options: unknown[] }>(`/dashboards/${dashboardId}/selectors/${selectorId}/options`).then((r) => r.data),

  getChartColumns: (dashboardId: number, dcId: number) =>
    api.get<{ columns: string[] }>(`/dashboards/${dashboardId}/charts/${dcId}/columns`).then((r) => r.data),

  generateSelectors: (dashboardId: number) =>
    api.post<{ selectors: DashboardSelector[] }>(`/dashboards/${dashboardId}/selectors/generate`).then((r) => r.data),
}

// === Public API (no auth interceptor) ===

const publicAxios = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
})

export const publicApi = {
  getChartMeta: (chartId: number) =>
    publicAxios.get(`/public/chart/${chartId}/meta`).then((r) => r.data),

  getChartData: (chartId: number) =>
    publicAxios.get<ChartDataResponse>(`/public/chart/${chartId}/data`).then((r) => r.data),

  authenticateDashboard: (slug: string, password: string) =>
    publicAxios.post<DashboardAuthResponse>(`/public/dashboard/${slug}/auth`, { password }).then((r) => r.data),

  getDashboard: (slug: string, token: string) =>
    publicAxios.get<Dashboard>(`/public/dashboard/${slug}`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => r.data),

  getDashboardChartData: (slug: string, dcId: number, token: string) =>
    publicAxios.get<ChartDataResponse>(`/public/dashboard/${slug}/chart/${dcId}/data`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => r.data),

  getLinkedDashboard: (slug: string, linkedSlug: string, token: string) =>
    publicAxios.get<Dashboard>(`/public/dashboard/${slug}/linked/${linkedSlug}`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => r.data),

  getLinkedDashboardChartData: (slug: string, linkedSlug: string, dcId: number, token: string) =>
    publicAxios.get<ChartDataResponse>(`/public/dashboard/${slug}/linked/${linkedSlug}/chart/${dcId}/data`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => r.data),

  // Filtered chart data (POST with filters)
  getDashboardChartDataFiltered: (slug: string, dcId: number, token: string, filters: FilterValue[]) =>
    publicAxios.post<ChartDataResponse>(`/public/dashboard/${slug}/chart/${dcId}/data`, { filters }, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => r.data),

  getLinkedDashboardChartDataFiltered: (slug: string, linkedSlug: string, dcId: number, token: string, filters: FilterValue[]) =>
    publicAxios.post<ChartDataResponse>(`/public/dashboard/${slug}/linked/${linkedSlug}/chart/${dcId}/data`, { filters }, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => r.data),

  // Public selector endpoints
  getDashboardSelectors: (slug: string, token: string) =>
    publicAxios.get<{ selectors: DashboardSelector[] }>(`/public/dashboard/${slug}/selectors`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => r.data),

  getSelectorOptions: (slug: string, selectorId: number, token: string) =>
    publicAxios.get<{ options: unknown[] }>(`/public/dashboard/${slug}/selector/${selectorId}/options`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => r.data),
}

export default api
