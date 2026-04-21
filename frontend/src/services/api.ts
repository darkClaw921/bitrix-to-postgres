import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || '/api/v1'

/** Таймаут для долгих AI-запросов (генерация графиков, отчётов) в мс */
const AI_REQUEST_TIMEOUT = 300_000 // 5 минут

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

export interface BitrixFilter {
  field: string
  operator: string
  value: string
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
  records_fetched: number | null
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

  startSync: (entity: string, syncType: 'full' | 'incremental' = 'full', filter?: BitrixFilter) =>
    api.post<SyncStartResponse>(`/sync/start/${entity}`, {
      sync_type: syncType,
      ...(filter ? { filter } : {}),
    }).then((r) => r.data),

  getStatus: () =>
    api.get<SyncStatusResponse>('/sync/status').then((r) => r.data),

  getEntityFields: (entity: string) =>
    api.get<{ entity_type: string; fields: string[] }>(`/sync/fields/${entity}`).then((r) => r.data),

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
    // Number formatting
    decimals?: number  // 0..6, default = original locale formatting
    format?: 'number' | 'currency' | 'percent' | 'compact'  // compact = K/M/B abbreviation
    currencySymbol?: string  // used when format='currency', default '₽'
    autoFit?: boolean  // when true, scale font down so the value always fits the cell
    textAlign?: 'left' | 'center' | 'right'  // horizontal alignment of value text, default 'center'
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
  // card style
  cardStyle?: {
    backgroundColor?: string
    borderRadius?: 'none' | 'sm' | 'md' | 'lg' | 'xl'
    shadow?: 'none' | 'sm' | 'md' | 'lg'
    padding?: 'sm' | 'md' | 'lg'
  }
  // general chart settings
  general?: {
    titleFontSize?: 'sm' | 'md' | 'lg' | 'xl'
    showTooltip?: boolean
    animate?: boolean
    showDataLabels?: boolean
    margins?: { top?: number; right?: number; bottom?: number; left?: number }
    // When true, the chart ignores TV/stretch-driven fontScale so axis ticks,
    // legend, data labels, indicator value and table cells keep their preset
    // font size regardless of cell size. Indicator additionally switches to
    // compact (preset) sizing so autoFit-to-container is disabled.
    fixedFontSize?: boolean
  }
  // design layout (interactive positioning)
  designLayout?: DesignLayout
  // post-processing rules to replace raw IDs in result rows with display labels
  label_resolvers?: LabelResolver[]
}

export interface DesignLayout {
  legend?: { x?: number; y?: number; layout?: 'horizontal' | 'vertical' }
  title?: { dx?: number; dy?: number }
  xAxisLabel?: { dx?: number; dy?: number }
  yAxisLabel?: { dx?: number; dy?: number }
  dataLabels?: { dx?: number; dy?: number }
  margins?: { top?: number; right?: number; bottom?: number; left?: number }
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
  cardStyle?: ChartDisplayConfig['cardStyle']
  general?: ChartDisplayConfig['general']
  designLayout?: DesignLayout
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

export interface ChartExecuteSqlRequest {
  sql_query: string
}

export const chartsApi = {
  generate: (data: ChartGenerateRequest) =>
    api.post<ChartGenerateResponse>('/charts/generate', data, { timeout: AI_REQUEST_TIMEOUT }).then((r) => r.data),

  executeSql: (data: ChartExecuteSqlRequest) =>
    api.post<ChartDataResponse>('/charts/execute-sql', data, { timeout: AI_REQUEST_TIMEOUT }).then((r) => r.data),

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

  updateSql: (chartId: number, sqlQuery: string, title?: string, description?: string) =>
    api
      .patch<SavedChart>(`/charts/${chartId}/sql`, {
        sql_query: sqlQuery,
        ...(title !== undefined ? { title } : {}),
        ...(description !== undefined ? { description } : {}),
      })
      .then((r) => r.data),

  refineSqlWithAi: (chartId: number, instruction: string) =>
    api
      .post<{ sql_query: string }>(
        `/charts/${chartId}/refine-sql-ai`,
        { instruction },
        { timeout: AI_REQUEST_TIMEOUT },
      )
      .then((r) => r.data),

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

export interface HeadingConfig {
  text: string
  level: 1 | 2 | 3 | 4 | 5 | 6
  align: 'left' | 'center' | 'right'
  color?: string | null
  bg_color?: string | null
  divider: boolean
}

export interface HeadingCreateRequest {
  heading: HeadingConfig
  layout_x?: number
  layout_y?: number
  layout_w?: number
  layout_h?: number
  sort_order?: number
}

export interface HeadingUpdateRequest {
  heading: HeadingConfig
}

export interface DashboardChart {
  id: number
  dashboard_id: number
  chart_id?: number
  item_type: 'chart' | 'heading'
  heading_config?: HeadingConfig | null
  title_override?: string
  description_override?: string
  hide_title?: boolean
  title_font_size_override?: string
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

export interface SelectorMapping {
  id: number
  selector_id: number
  dashboard_chart_id: number
  target_column: string
  target_table?: string
  operator_override?: string
  // Two-step (post_filter) filtering: when target_column lives in the chart's
  // table but the selector value semantically belongs to a different table,
  // the backend rewrites the WHERE into
  //   target_column IN (SELECT post_filter_resolve_id_column
  //                     FROM post_filter_resolve_table
  //                     WHERE post_filter_resolve_column <op> :value)
  post_filter_resolve_table?: string
  post_filter_resolve_column?: string
  post_filter_resolve_id_column?: string
  created_at?: string
}

export interface LabelResolver {
  column: string
  resolve_table: string
  resolve_value_column?: string
  resolve_label_column: string
}

export interface DashboardSelector {
  id: number
  dashboard_id: number
  name: string
  label: string
  selector_type: string
  operator: string
  config?: Record<string, unknown>
  sort_order: number
  is_required: boolean
  mappings: SelectorMapping[]
  created_at?: string
}

export interface SelectorMappingRequest {
  dashboard_chart_id: number
  target_column: string
  target_table?: string
  operator_override?: string
  post_filter_resolve_table?: string
  post_filter_resolve_column?: string
  post_filter_resolve_id_column?: string
}

export interface SelectorCreateRequest {
  name: string
  label: string
  selector_type: string
  operator?: string
  config?: Record<string, unknown>
  sort_order?: number
  is_required?: boolean
  mappings?: SelectorMappingRequest[]
}

export interface SelectorUpdateRequest {
  name?: string
  label?: string
  selector_type?: string
  operator?: string
  config?: Record<string, unknown>
  sort_order?: number
  is_required?: boolean
  mappings?: SelectorMappingRequest[]
}

export interface SelectorOption {
  value: unknown
  label: string
}

export interface FilterValue {
  name: string
  value: unknown
}

export interface FilterPreviewRequest {
  selector_name: string
  selector_type: string
  operator: string
  target_column: string
  target_table?: string
  sample_value?: string
}

export interface FilterPreviewResponse {
  original_sql: string
  filtered_sql: string
  where_clause: string
}

export interface Dashboard {
  id: number
  slug: string
  title: string
  tab_label?: string
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
  tab_label?: string
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
  hide_title?: boolean
  title_font_size_override?: string
}

export interface ChartAddRequest {
  chart_id: number
  /** Optional layout overrides; omit to let the server compute defaults
   *  (layout_x=0, layout_w=6, layout_h=4, layout_y=MAX(y+h) so the new
   *  chart lands at the bottom of the existing layout). */
  layout_x?: number
  layout_y?: number
  layout_w?: number
  layout_h?: number
  sort_order?: number
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

  addChart: (dashboardId: number, data: ChartAddRequest) =>
    api.post<DashboardChart>(`/dashboards/${dashboardId}/charts`, data).then((r) => r.data),

  addHeading: (dashboardId: number, data: HeadingCreateRequest) =>
    api.post<DashboardChart>(`/dashboards/${dashboardId}/headings`, data).then((r) => r.data),

  updateHeading: (dashboardId: number, dcId: number, data: HeadingUpdateRequest) =>
    api.put<DashboardChart>(`/dashboards/${dashboardId}/headings/${dcId}`, data).then((r) => r.data),

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
  listSelectors: (dashboardId: number) =>
    api.get<{ selectors: DashboardSelector[] }>(`/dashboards/${dashboardId}/selectors`).then((r) => r.data.selectors),

  createSelector: (dashboardId: number, data: SelectorCreateRequest) =>
    api.post<DashboardSelector>(`/dashboards/${dashboardId}/selectors`, data).then((r) => r.data),

  updateSelector: (dashboardId: number, selectorId: number, data: SelectorUpdateRequest) =>
    api.put<DashboardSelector>(`/dashboards/${dashboardId}/selectors/${selectorId}`, data).then((r) => r.data),

  deleteSelector: (dashboardId: number, selectorId: number) =>
    api.delete(`/dashboards/${dashboardId}/selectors/${selectorId}`).then((r) => r.data),

  getSelectorOptions: (dashboardId: number, selectorId: number) =>
    api.get<{ options: SelectorOption[] }>(`/dashboards/${dashboardId}/selectors/${selectorId}/options`).then((r) => r.data.options),

  getChartColumns: (dashboardId: number, dcId: number) =>
    api.get<{ columns: string[] }>(`/dashboards/${dashboardId}/charts/${dcId}/columns`).then((r) => r.data.columns),

  getChartTables: (dashboardId: number, dcId: number) =>
    api.get<{ tables: string[] }>(`/dashboards/${dashboardId}/charts/${dcId}/tables`).then((r) => r.data.tables),

  previewFilter: (dashboardId: number, dcId: number, data: FilterPreviewRequest) =>
    api.post<FilterPreviewResponse>(`/dashboards/${dashboardId}/charts/${dcId}/preview-filter`, data).then((r) => r.data),

  generateSelectors: (
    dashboardId: number,
    userRequest?: string,
    chartIds?: number[],
  ) => {
    const body: { user_request?: string; chart_ids?: number[] } = {}
    if (userRequest) body.user_request = userRequest
    if (chartIds && chartIds.length > 0) body.chart_ids = chartIds
    return api
      .post<{ selectors: SelectorCreateRequest[] }>(
        `/dashboards/${dashboardId}/selectors/generate`,
        body,
        { timeout: AI_REQUEST_TIMEOUT },
      )
      .then((r) => r.data)
  },

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

  // Filtered chart data (POST)
  getDashboardChartDataFiltered: (slug: string, dcId: number, token: string, filters: FilterValue[]) =>
    publicAxios.post<ChartDataResponse>(`/public/dashboard/${slug}/chart/${dcId}/data`, { filters }, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => r.data),

  getLinkedDashboardChartDataFiltered: (slug: string, linkedSlug: string, dcId: number, token: string, filters: FilterValue[]) =>
    publicAxios.post<ChartDataResponse>(`/public/dashboard/${slug}/linked/${linkedSlug}/chart/${dcId}/data`, { filters }, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => r.data),

  // Public selectors
  getPublicSelectors: (slug: string, token: string) =>
    publicAxios.get<{ selectors: DashboardSelector[] }>(`/public/dashboard/${slug}/selectors`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => r.data.selectors),

  getPublicSelectorOptions: (slug: string, selectorId: number, token: string) =>
    publicAxios.get<{ options: SelectorOption[] }>(`/public/dashboard/${slug}/selector/${selectorId}/options`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => r.data.options),

  getPublicSelectorOptionsBatch: (slug: string, token: string) =>
    publicAxios.get<{ options: Record<number, SelectorOption[]> }>(`/public/dashboard/${slug}/selector-options`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => r.data.options),

  getLinkedPublicSelectorOptionsBatch: (slug: string, linkedSlug: string, token: string) =>
    publicAxios.get<{ options: Record<number, SelectorOption[]> }>(
      `/public/dashboard/${slug}/linked/${linkedSlug}/selector-options`,
      { headers: { Authorization: `Bearer ${token}` } },
    ).then((r) => r.data.options),

  // Published Reports
  authenticateReport: (slug: string, password: string) =>
    publicAxios.post<PublishedReportAuthResponse>(`/public/report/${slug}/auth`, { password }).then((r) => r.data),

  getPublicReport: (slug: string, token: string) =>
    publicAxios.get<PublicReport>(`/public/report/${slug}`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => r.data),

  getLinkedReport: (slug: string, linkedSlug: string, token: string) =>
    publicAxios.get<PublicReport>(`/public/report/${slug}/linked/${linkedSlug}`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => r.data),
}

// === Reports Types ===

export interface ReportConversationRequest {
  session_id?: string
  message: string
}

export interface SqlQueryItem {
  sql: string
  purpose: string
}

export interface DataResultItem {
  sql: string
  purpose: string
  rows: Record<string, unknown>[]
  row_count: number
  time_ms: number
  error?: string
}

export interface ReportPreview {
  title: string
  description?: string
  sql_queries: SqlQueryItem[]
  report_template: string
  data_results: DataResultItem[]
}

export interface ReportConversationResponse {
  session_id: string
  content: string
  is_complete: boolean
  report_preview?: ReportPreview
}

export interface ReportSaveRequest {
  session_id: string
  title: string
  description?: string
  schedule_type?: string
  schedule_config?: Record<string, unknown>
}

export interface ReportScheduleUpdateRequest {
  schedule_type?: string
  schedule_config?: Record<string, unknown>
  status?: string
}

export interface ReportUpdateRequest {
  title?: string
  description?: string
  user_prompt?: string
  sql_queries?: Record<string, unknown>[]
  report_template?: string
}

export interface Report {
  id: number
  title: string
  description?: string
  user_prompt: string
  status: string
  schedule_type: string
  schedule_config?: Record<string, unknown>
  next_run_at?: string
  last_run_at?: string
  sql_queries?: Record<string, unknown>[]
  report_template?: string
  is_pinned: boolean
  created_at: string
  updated_at: string
}

export interface ReportListResponse {
  reports: Report[]
  total: number
  page: number
  per_page: number
}

export interface ReportRun {
  id: number
  report_id: number
  status: string
  trigger_type: string
  result_markdown?: string
  result_data?: Record<string, unknown>[]
  sql_queries_executed?: Record<string, unknown>[]
  error_message?: string
  execution_time_ms?: number
  llm_prompt?: string
  started_at?: string
  completed_at?: string
  created_at: string
}

export interface ReportRunListResponse {
  runs: ReportRun[]
  total: number
  page: number
  per_page: number
}

export interface ReportPromptTemplate {
  id: number
  name: string
  content: string
  is_active: boolean
  created_at: string
  updated_at: string
}

// === Published Reports Types ===

export interface PublishedReportLink {
  id: number
  sort_order: number
  label?: string
  linked_title?: string
  linked_slug?: string
}

export interface PublishedReport {
  id: number
  slug: string
  title: string
  description?: string
  report_id: number
  is_active: boolean
  created_at: string
  updated_at: string
  linked_reports: PublishedReportLink[]
}

export interface PublishedReportListItem {
  id: number
  slug: string
  title: string
  description?: string
  report_id: number
  report_title?: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface PublishedReportListResponse {
  reports: PublishedReportListItem[]
  total: number
  page: number
  per_page: number
}

export interface PublishReportRequest {
  report_id: number
  title?: string
  description?: string
}

export interface PublishReportResponse {
  published_report: PublishedReport
  password: string
}

export interface PublicReportRun {
  id: number
  status: string
  trigger_type: string
  result_markdown?: string
  execution_time_ms?: number
  created_at: string
  completed_at?: string
}

export interface PublicReport {
  id: number
  slug: string
  title: string
  description?: string
  report_title?: string
  runs: PublicReportRun[]
  linked_reports: PublishedReportLink[]
}

export interface PublishedReportAuthResponse {
  token: string
  expires_in_minutes: number
}

// === Reports API ===

export const reportsApi = {
  converse: (data: ReportConversationRequest) =>
    api.post<ReportConversationResponse>('/reports/converse', data, { timeout: AI_REQUEST_TIMEOUT }).then((r) => r.data),

  save: (data: ReportSaveRequest) =>
    api.post<Report>('/reports/save', data).then((r) => r.data),

  list: (page = 1, perPage = 20) =>
    api.get<ReportListResponse>('/reports/list', { params: { page, per_page: perPage } }).then((r) => r.data),

  get: (reportId: number) =>
    api.get<Report>(`/reports/${reportId}`).then((r) => r.data),

  delete: (reportId: number) =>
    api.delete(`/reports/${reportId}`).then((r) => r.data),

  update: (reportId: number, data: ReportUpdateRequest) =>
    api.patch<Report>(`/reports/${reportId}`, data).then((r) => r.data),

  updateSchedule: (reportId: number, data: ReportScheduleUpdateRequest) =>
    api.patch<Report>(`/reports/${reportId}/schedule`, data).then((r) => r.data),

  run: (reportId: number) =>
    api.post<ReportRun>(`/reports/${reportId}/run`, null, { timeout: AI_REQUEST_TIMEOUT }).then((r) => r.data),

  togglePin: (reportId: number) =>
    api.post<Report>(`/reports/${reportId}/pin`).then((r) => r.data),

  listRuns: (reportId: number, page = 1, perPage = 20) =>
    api.get<ReportRunListResponse>(`/reports/${reportId}/runs`, { params: { page, per_page: perPage } }).then((r) => r.data),

  getRun: (reportId: number, runId: number) =>
    api.get<ReportRun>(`/reports/${reportId}/runs/${runId}`).then((r) => r.data),

  getPromptTemplate: () =>
    api.get<ReportPromptTemplate>('/reports/prompt-template/report-context').then((r) => r.data),

  updatePromptTemplate: (content: string) =>
    api.put<ReportPromptTemplate>('/reports/prompt-template/report-context', { content }).then((r) => r.data),
}

// === Published Reports API (internal) ===

export const publishedReportsApi = {
  publish: (data: PublishReportRequest) =>
    api.post<PublishReportResponse>('/reports/publish', data).then((r) => r.data),

  list: (page = 1, perPage = 20) =>
    api.get<PublishedReportListResponse>('/reports/published', { params: { page, per_page: perPage } }).then((r) => r.data),

  get: (pubId: number) =>
    api.get<PublishedReport>(`/reports/published/${pubId}`).then((r) => r.data),

  delete: (pubId: number) =>
    api.delete(`/reports/published/${pubId}`).then((r) => r.data),

  changePassword: (pubId: number) =>
    api.post<PasswordChangeResponse>(`/reports/published/${pubId}/change-password`).then((r) => r.data),

  addLink: (pubId: number, data: { linked_published_report_id: number; label?: string; sort_order?: number }) =>
    api.post<PublishedReportLink>(`/reports/published/${pubId}/links`, data).then((r) => r.data),

  removeLink: (pubId: number, linkId: number) =>
    api.delete(`/reports/published/${pubId}/links/${linkId}`).then((r) => r.data),

  updateLinks: (pubId: number, links: { id: number; sort_order: number }[]) =>
    api.put<PublishedReportLink[]>(`/reports/published/${pubId}/links`, { links }).then((r) => r.data),
}

// === Plans Types ===

export type PlanPeriodType = 'month' | 'quarter' | 'year' | 'custom'

export interface Plan {
  id: number
  table_name: string
  field_name: string
  assigned_by_id: string | null
  period_type: PlanPeriodType | null
  period_value: string | null
  date_from: string | null
  date_to: string | null
  plan_value: number | string
  description: string | null
  created_by_id: string | null
  created_at: string | null
  updated_at: string | null
}

export interface PlanCreateRequest {
  table_name: string
  field_name: string
  assigned_by_id?: string | null
  period_type: PlanPeriodType
  period_value?: string | null
  date_from?: string | null
  date_to?: string | null
  plan_value: number | string
  description?: string | null
  created_by_id?: string | null
}

export interface PlanUpdateRequest {
  table_name?: string
  field_name?: string
  assigned_by_id?: string | null
  period_type?: PlanPeriodType
  period_value?: string | null
  date_from?: string | null
  date_to?: string | null
  plan_value?: number | string
  description?: string | null
}

export interface PlanVsActual {
  plan_id: number
  plan_value: number | string
  actual_value: number | string
  variance: number | string
  variance_pct: number | null
  period_effective_from: string
  period_effective_to: string
}

export interface NumericFieldInfo {
  name: string
  data_type: string
}

export interface NumericFieldsResponse {
  table_name: string
  fields: NumericFieldInfo[]
}

export interface PlanTableInfo {
  name: string
  label?: string | null
}

export interface PlanTablesResponse {
  tables: PlanTableInfo[]
}

export interface PlanListFilters {
  table_name?: string
  field_name?: string
  assigned_by_id?: string
  period_type?: PlanPeriodType
}

// === Plan Templates Types ===

/**
 * Template-level period modes (backend `ALL_PERIOD_MODES`).
 *
 * - `current_month` / `current_quarter` / `current_year` — сервис сам
 *   вычисляет `period_value` на момент expand/apply.
 * - `custom_period` — требует `period_type` (month/quarter/year/custom)
 *   + `period_value` или `date_from`/`date_to`.
 */
export type PlanPeriodMode =
  | 'current_month'
  | 'current_quarter'
  | 'current_year'
  | 'custom_period'

/**
 * Template-level assignee modes (backend `ALL_ASSIGNEES_MODES`).
 *
 * - `all_managers` — expand разворачивает на всех активных менеджеров.
 * - `department` — разворачивает на менеджеров отдела (с подотделами).
 * - `specific` — использует `specific_manager_ids`.
 * - `global` — один план без `assigned_by_id` (для всей компании).
 */
export type PlanAssigneesMode =
  | 'all_managers'
  | 'department'
  | 'specific'
  | 'global'

/**
 * Plan template — зеркалит backend `PlanTemplateResponse`.
 *
 * Builtin (`is_builtin=true`) создаются только миграцией 024; через API
 * создаются только пользовательские (`is_builtin=false`).
 */
export interface PlanTemplate {
  id: number
  name: string
  description: string | null

  table_name: string | null
  field_name: string | null

  period_mode: PlanPeriodMode
  period_type: PlanPeriodType | null
  period_value: string | null
  date_from: string | null
  date_to: string | null

  assignees_mode: PlanAssigneesMode
  department_name: string | null
  specific_manager_ids: string[] | null

  default_plan_value: number | string | null

  is_builtin: boolean
  created_by_id: string | null
  created_at: string | null
  updated_at: string | null
}

/**
 * Payload для `POST /plans/templates` — создание пользовательского шаблона.
 *
 * `is_builtin` и `created_by_id` не передаются (сервис проставляет
 * автоматически). Связи полей: при `assignees_mode='department'` обязателен
 * `department_name`; при `'specific'` — `specific_manager_ids` (непустой);
 * при `period_mode='custom_period'` — `period_type` + соответствующие
 * поля.
 */
export interface PlanTemplateCreateRequest {
  name: string
  description?: string | null

  table_name?: string | null
  field_name?: string | null

  period_mode: PlanPeriodMode
  period_type?: PlanPeriodType | null
  period_value?: string | null
  date_from?: string | null
  date_to?: string | null

  assignees_mode: PlanAssigneesMode
  department_name?: string | null
  specific_manager_ids?: string[] | null

  default_plan_value?: number | string | null
}

/**
 * Payload для `PUT /plans/templates/{id}` — частичное обновление.
 *
 * Все поля опциональны; backend патчит только переданные. Изменение
 * `is_builtin` не поддерживается (поле отсутствует в схеме).
 */
export interface PlanTemplateUpdateRequest {
  name?: string
  description?: string | null

  table_name?: string | null
  field_name?: string | null

  period_mode?: PlanPeriodMode
  period_type?: PlanPeriodType | null
  period_value?: string | null
  date_from?: string | null
  date_to?: string | null

  assignees_mode?: PlanAssigneesMode
  department_name?: string | null
  specific_manager_ids?: string[] | null

  default_plan_value?: number | string | null
}

/**
 * Preview entry — возвращается из `POST /plans/templates/{id}/expand` и
 * `POST /plans/ai-generate`, затем идёт обратно в
 * `PlanTemplateApplyRequest.entries`.
 *
 * `warnings` — мягкие сообщения (менеджер неактивен, дубль и т.п.),
 * которые UI показывает рядом со строкой.
 */
export interface PlanDraft {
  assigned_by_id: string | null
  assigned_by_name: string | null

  table_name: string
  field_name: string

  period_type: PlanPeriodType
  period_value?: string | null
  date_from?: string | null
  date_to?: string | null

  plan_value?: number | string | null
  description?: string | null

  warnings: string[]
}

/**
 * Payload для `POST /plans/batch` — транзакционный batch create.
 *
 * All-or-nothing: любая ошибка откатывает всю транзакцию.
 */
export interface PlanBatchCreateRequest {
  plans: PlanCreateRequest[]
}

/**
 * Payload для `POST /plans/templates/{id}/expand` — overrides для
 * builtin шаблонов с NULL-target или для выбора конкретного периода.
 *
 * Все поля опциональны: без них шаблон разворачивается «как есть».
 */
export interface PlanTemplateExpandRequest {
  table_name?: string | null
  field_name?: string | null
  period_value?: string | null
}

/**
 * Payload для `POST /plans/templates/{id}/apply` — финальное сохранение
 * отредактированных draft'ов.
 *
 * `template_id` дублирует path-параметр (защита от path/body mismatch).
 * `table_name` / `field_name` — override'ы target (обязательны для
 * builtin без привязки). `period_value_override` применяется ко всем
 * `entries`.
 */
export interface PlanTemplateApplyRequest {
  template_id: number
  table_name?: string | null
  field_name?: string | null
  period_value_override?: string | null
  entries: PlanDraft[]
}

/**
 * Payload для `POST /plans/ai-generate` — LLM превью по описанию.
 *
 * `description` 5-4000 символов. `table_name` / `field_name` — опциональные
 * подсказки для модели (если пользователь не указал цель явно).
 */
export interface PlanAIGenerateRequest {
  description: string
  table_name?: string | null
  field_name?: string | null
}

/**
 * Ответ `POST /plans/ai-generate`. Endpoint НЕ пишет в БД — фронт
 * показывает `plans` пользователю, даёт отредактировать и отправляет в
 * `POST /plans/batch`.
 */
export interface PlanAIGenerateResponse {
  plans: PlanDraft[]
  warnings: string[]
}

/**
 * Менеджер, возвращаемый `GET /plans/meta/managers` и
 * `GET /departments/{id}/managers` (идентичные по форме DTO).
 */
export interface PlanManagerInfo {
  bitrix_id: string
  name: string | null
  last_name: string | null
  active: string | null
}

/**
 * Ответ `GET /plans/meta/managers` / `GET /departments/{id}/managers`.
 */
export interface PlanManagersResponse {
  department_id: string | null
  recursive: boolean
  managers: PlanManagerInfo[]
}

// === Departments Types ===

/**
 * Одна запись из `bitrix_departments` — плоский DTO (backend
 * `DepartmentResponse`).
 */
export interface Department {
  bitrix_id: string
  name: string | null
  parent_id: string | null
  sort: number
  uf_head: string | null
}

/**
 * Узел иерархического дерева отделов. Листовые отделы имеют
 * `children=[]` (не null). Self-referencing.
 */
export interface DepartmentTreeNode {
  id: string
  name: string | null
  sort: number
  uf_head: string | null
  children: DepartmentTreeNode[]
}

/** Ответ `GET /departments/tree`. */
export interface DepartmentTreeResponse {
  tree: DepartmentTreeNode[]
}

/**
 * Ответ `POST /departments/sync`. `status`:
 * - `started` — фоновая синхронизация запущена.
 * - `already_running` — обрабатывается на уровне HTTP 409 (клиент увидит
 *   axios-ошибку, а не этот payload).
 */
export interface DepartmentSyncResponse {
  status: string
  message: string | null
}

// === Plans API ===

export const plansApi = {
  list: (filters?: PlanListFilters) =>
    api
      .get<Plan[]>('/plans', { params: filters })
      .then((r) => r.data),

  get: (id: number) =>
    api.get<Plan>(`/plans/${id}`).then((r) => r.data),

  create: (payload: PlanCreateRequest) =>
    api.post<Plan>('/plans', payload).then((r) => r.data),

  update: (id: number, payload: PlanUpdateRequest) =>
    api.put<Plan>(`/plans/${id}`, payload).then((r) => r.data),

  remove: (id: number) =>
    api.delete<void>(`/plans/${id}`).then((r) => r.data),

  getVsActual: (id: number) =>
    api.get<PlanVsActual>(`/plans/${id}/vs-actual`).then((r) => r.data),

  getTables: () =>
    api
      .get<PlanTablesResponse>('/plans/meta/tables')
      .then((r) => r.data.tables),

  getNumericFields: (tableName: string) =>
    api
      .get<NumericFieldsResponse>('/plans/meta/numeric-fields', {
        params: { table_name: tableName },
      })
      .then((r) => r.data.fields),

  /**
   * Транзакционный batch create — `POST /plans/batch`. All-or-nothing:
   * любая валидационная/DB-ошибка откатывает всю транзакцию и axios
   * отдаст HTTP 4xx/5xx (ошибки не перехватываются здесь — React Query
   * обработает выше по стеку).
   */
  batchCreate: (payload: PlanBatchCreateRequest) =>
    api.post<Plan[]>('/plans/batch', payload).then((r) => r.data),

  /**
   * LLM-генерация черновиков планов по описанию — `POST /plans/ai-generate`.
   * Использует увеличенный `AI_REQUEST_TIMEOUT` (5 мин), как `chartsApi.generate`.
   * Endpoint возвращает preview (`PlanDraft[]`) — сохранение идёт отдельно
   * через `batchCreate`.
   */
  aiGenerate: (payload: PlanAIGenerateRequest) =>
    api
      .post<PlanAIGenerateResponse>('/plans/ai-generate', payload, {
        timeout: AI_REQUEST_TIMEOUT,
      })
      .then((r) => r.data),

  // --- Plan templates ---

  /** `GET /plans/templates` — список всех шаблонов (builtin + user), oldest first. */
  listTemplates: () =>
    api.get<PlanTemplate[]>('/plans/templates').then((r) => r.data),

  /** `GET /plans/templates/{id}` — один шаблон. 404 если не найден. */
  getTemplate: (id: number) =>
    api.get<PlanTemplate>(`/plans/templates/${id}`).then((r) => r.data),

  /** `POST /plans/templates` — создать пользовательский шаблон. */
  createTemplate: (payload: PlanTemplateCreateRequest) =>
    api.post<PlanTemplate>('/plans/templates', payload).then((r) => r.data),

  /**
   * `PUT /plans/templates/{id}` — частичное обновление. Для builtin
   * запрещено менять name/period_mode/assignees_mode (400 с backend).
   */
  updateTemplate: (id: number, payload: PlanTemplateUpdateRequest) =>
    api.put<PlanTemplate>(`/plans/templates/${id}`, payload).then((r) => r.data),

  /**
   * `DELETE /plans/templates/{id}` — удалить. 400 для builtin, 404 если нет.
   * Backend возвращает 204 No Content — промис резолвится в void.
   */
  deleteTemplate: (id: number) =>
    api.delete<void>(`/plans/templates/${id}`).then(() => undefined),

  /**
   * `POST /plans/templates/{id}/expand` — развернуть шаблон в черновики
   * планов (по одному на менеджера, согласно `assignees_mode`). Тело
   * опционально: без него шаблон разворачивается как есть; с ним можно
   * переопределить `table_name` / `field_name` / `period_value`.
   */
  expandTemplate: (id: number, overrides?: PlanTemplateExpandRequest) =>
    api
      .post<PlanDraft[]>(`/plans/templates/${id}/expand`, overrides ?? {})
      .then((r) => r.data),

  /**
   * `POST /plans/templates/{id}/apply` — финальное применение шаблона.
   * Принимает отредактированные `entries` и транзакционно создаёт планы
   * через `PlanService.batch_create_plans` (all-or-nothing).
   * `payload.template_id` должен совпадать с `id` в пути (backend guard).
   */
  applyTemplate: (id: number, payload: PlanTemplateApplyRequest) =>
    api
      .post<Plan[]>(`/plans/templates/${id}/apply`, payload)
      .then((r) => r.data),

  /**
   * `GET /plans/meta/managers` — активные менеджеры (для UI выбора
   * `assigned_by_id`). Без параметров — все активные из `bitrix_users`.
   * С `department_id` — только менеджеры этого отдела (и подотделов при
   * `recursive=true`, default на backend).
   */
  listManagers: (params?: { department_id?: string; recursive?: boolean }) =>
    api
      .get<PlanManagersResponse>('/plans/meta/managers', { params })
      .then((r) => r.data),
}

// === Departments API ===

/**
 * Клиент эндпоинтов `/api/v1/departments`.
 *
 * Используется для:
 * - UI выбора отдела в PlanTemplate (`assignees_mode='department'`);
 * - админского экрана иерархии + триггера синхронизации из Bitrix;
 * - резолвинга менеджеров выбранного отдела (тот же DTO, что
 *   `plansApi.listManagers` — `PlanManagersResponse`).
 */
export const departmentsApi = {
  /** `GET /departments` — плоский список, отсортирован по (sort, bitrix_id). */
  list: () => api.get<Department[]>('/departments').then((r) => r.data),

  /** `GET /departments/tree` — корневые узлы с рекурсивными `children`. */
  getTree: () =>
    api.get<DepartmentTreeResponse>('/departments/tree').then((r) => r.data),

  /**
   * `POST /departments/sync` — запустить фоновую синхронизацию
   * `DepartmentSyncService.full_sync`. 409 если уже запущена
   * (дедуп через `DepartmentSyncService.is_running`).
   */
  triggerSync: () =>
    api.post<DepartmentSyncResponse>('/departments/sync').then((r) => r.data),

  /**
   * `GET /departments/{id}/managers` — менеджеры отдела. Default
   * `recursive=true`, `active_only=true` (совпадает с backend).
   * При отсутствии отдела backend отдаёт пустой `managers` (не 404).
   */
  getManagers: (
    id: string,
    params?: { recursive?: boolean; active_only?: boolean },
  ) =>
    api
      .get<PlanManagersResponse>(`/departments/${id}/managers`, { params })
      .then((r) => r.data),
}

export default api
