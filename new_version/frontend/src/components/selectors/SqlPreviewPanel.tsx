import { useState } from 'react'
import { useTranslation } from '../../i18n'
import type { FilterPreviewResponse } from '../../services/api'

interface Props {
  preview: FilterPreviewResponse | null
  loading?: boolean
}

export default function SqlPreviewPanel({ preview, loading }: Props) {
  const { t } = useTranslation()
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="border-t border-gray-200 bg-gray-50">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between px-4 py-2 text-xs font-semibold text-gray-600 hover:bg-gray-100 transition-colors"
      >
        <span>{t('selectors.sqlPreview')}</span>
        <span className="text-gray-400">{collapsed ? '▲' : '▼'}</span>
      </button>
      {!collapsed && (
        <div className="px-4 pb-3 max-h-[180px] overflow-y-auto">
          {loading ? (
            <div className="text-xs text-gray-400 py-2">Loading...</div>
          ) : !preview ? (
            <div className="text-xs text-gray-400 py-2">{t('selectors.clickEdgeToConfig')}</div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-xs font-medium text-gray-500 mb-1">{t('selectors.sqlOriginal')}</div>
                <pre className="text-[11px] bg-white border border-gray-200 rounded p-2 whitespace-pre-wrap break-all text-gray-700 max-h-[120px] overflow-auto">
                  {preview.original_sql || '—'}
                </pre>
              </div>
              <div>
                <div className="text-xs font-medium text-gray-500 mb-1">{t('selectors.sqlFiltered')}</div>
                <pre className="text-[11px] bg-white border border-green-200 rounded p-2 whitespace-pre-wrap break-all text-gray-700 max-h-[120px] overflow-auto">
                  {preview.filtered_sql ? highlightWhere(preview.filtered_sql, preview.where_clause) : '—'}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function highlightWhere(sql: string, whereClause: string): React.ReactNode {
  if (!whereClause) return sql
  // Simple approach: find the WHERE clause addition and wrap it
  const idx = sql.toLowerCase().lastIndexOf('where')
  if (idx === -1) return sql
  const before = sql.slice(0, idx)
  const after = sql.slice(idx)
  return (
    <>
      {before}
      <span className="bg-green-100 text-green-800">{after}</span>
    </>
  )
}
