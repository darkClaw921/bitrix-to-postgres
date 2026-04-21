import { useState } from 'react'
import { useTranslation } from '../../i18n'
import {
  useExecuteSql,
  useUpdateChartSql,
  useRefineChartSqlWithAi,
} from '../../hooks/useCharts'
import type { SavedChart } from '../../services/api'

interface Props {
  chart: SavedChart
  onClose: () => void
  onSaved?: () => void
}

/**
 * Modal editor for a saved chart's SQL query.
 *
 * Two editing paths:
 * - Manual: user edits the SQL directly in the textarea.
 * - AI: user describes the change in free text ("Что изменить?"), the backend
 *   calls the AI refine endpoint which returns a new SQL string; the new SQL
 *   replaces the editor content and can be further edited manually.
 *
 * In both paths the user can click "Предпросмотр" to run the draft SQL via
 * ``POST /charts/execute-sql`` and inspect the first rows before committing
 * the change via ``PATCH /charts/{id}/sql``.
 */
export default function SqlEditorModal({ chart, onClose, onSaved }: Props) {
  const { t } = useTranslation()
  const [draftSql, setDraftSql] = useState(chart.sql_query)
  const [aiInstruction, setAiInstruction] = useState('')
  const [previewRows, setPreviewRows] = useState<Record<string, unknown>[] | null>(null)
  const [previewMeta, setPreviewMeta] = useState<{ row_count: number; execution_time_ms: number } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const executeSql = useExecuteSql()
  const updateChartSql = useUpdateChartSql()
  const refineAi = useRefineChartSqlWithAi()

  const handlePreview = () => {
    setError(null)
    setPreviewRows(null)
    setPreviewMeta(null)
    executeSql.mutate(
      { sql_query: draftSql },
      {
        onSuccess: (res) => {
          setPreviewRows(res.data)
          setPreviewMeta({ row_count: res.row_count, execution_time_ms: res.execution_time_ms })
        },
        onError: (e) => {
          const err = e as { response?: { data?: { detail?: string } }; message?: string }
          setError(err?.response?.data?.detail || err?.message || 'Ошибка выполнения SQL')
        },
      },
    )
  }

  const handleAiRefine = () => {
    const instruction = aiInstruction.trim()
    if (!instruction) {
      setError('Опишите, что нужно изменить в запросе')
      return
    }
    setError(null)
    refineAi.mutate(
      { chartId: chart.id, instruction },
      {
        onSuccess: (res) => {
          setDraftSql(res.sql_query)
          // Preview not auto-run — user may want to edit the result first.
          setPreviewRows(null)
          setPreviewMeta(null)
        },
        onError: (e) => {
          const err = e as { response?: { data?: { detail?: string } }; message?: string }
          setError(err?.response?.data?.detail || err?.message || 'Ошибка AI-рефайна')
        },
      },
    )
  }

  const handleSave = () => {
    if (draftSql.trim() === chart.sql_query.trim()) {
      onClose()
      return
    }
    setError(null)
    updateChartSql.mutate(
      { chartId: chart.id, sqlQuery: draftSql },
      {
        onSuccess: () => {
          onSaved?.()
          onClose()
        },
        onError: (e) => {
          const err = e as { response?: { data?: { detail?: string } }; message?: string }
          setError(err?.response?.data?.detail || err?.message || 'Ошибка сохранения')
        },
      },
    )
  }

  const previewColumns =
    previewRows && previewRows.length > 0 ? Object.keys(previewRows[0]) : []

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-5xl h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <div>
            <h2 className="text-lg font-semibold">{t('charts.editSql')}</h2>
            <p className="text-xs text-gray-500 mt-0.5 truncate max-w-[600px]">{chart.title}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl"
            aria-label="close"
          >
            &times;
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* AI refine panel */}
          <div className="border border-purple-200 bg-purple-50 rounded-lg p-3">
            <label className="block text-xs font-semibold text-purple-700 mb-1">
              {t('charts.aiRefineSql')}
            </label>
            <textarea
              value={aiInstruction}
              onChange={(e) => setAiInstruction(e.target.value)}
              placeholder="Например: добавь фильтр по последним 30 дням, сгруппируй по менеджерам"
              rows={2}
              maxLength={2000}
              className="w-full px-2 py-1.5 text-sm border border-purple-300 rounded focus:outline-none focus:ring-1 focus:ring-purple-500 bg-white"
            />
            <div className="flex items-center justify-between mt-2">
              <div className="text-[11px] text-gray-500">
                {aiInstruction.length}/2000
              </div>
              <button
                onClick={handleAiRefine}
                disabled={refineAi.isPending}
                className="px-3 py-1.5 text-sm bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50"
              >
                {refineAi.isPending ? t('charts.aiGenerating') : t('charts.aiRefineSqlButton')}
              </button>
            </div>
          </div>

          {/* Manual SQL editor */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-semibold text-gray-700">
                SQL
              </label>
              <button
                onClick={() => setDraftSql(chart.sql_query)}
                disabled={draftSql === chart.sql_query}
                className="text-[11px] text-gray-500 hover:text-gray-700 disabled:opacity-30"
              >
                {t('charts.resetSql')}
              </button>
            </div>
            <textarea
              value={draftSql}
              onChange={(e) => setDraftSql(e.target.value)}
              rows={12}
              spellCheck={false}
              className="w-full px-3 py-2 text-xs font-mono border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 bg-gray-50"
            />
            <div className="flex items-center gap-2 mt-2">
              <button
                onClick={handlePreview}
                disabled={executeSql.isPending || !draftSql.trim()}
                className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              >
                {executeSql.isPending ? t('charts.running') : t('charts.preview')}
              </button>
              {previewMeta && (
                <span className="text-[11px] text-gray-500">
                  {previewMeta.row_count} {t('charts.rows')} · {previewMeta.execution_time_ms.toFixed(0)}ms
                </span>
              )}
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="px-3 py-2 bg-red-50 border border-red-200 text-red-600 text-xs rounded whitespace-pre-wrap">
              {error}
            </div>
          )}

          {/* Preview result */}
          {previewRows && previewRows.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-gray-700 mb-1">{t('charts.previewResult')}</div>
              <div className="border border-gray-200 rounded overflow-auto max-h-[260px]">
                <table className="min-w-full text-xs">
                  <thead className="bg-gray-50 sticky top-0">
                    <tr>
                      {previewColumns.map((col) => (
                        <th
                          key={col}
                          className="px-2 py-1 text-left font-semibold text-gray-700 border-b border-gray-200 whitespace-nowrap"
                        >
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {previewRows.slice(0, 50).map((row, i) => (
                      <tr key={i} className="border-b border-gray-100">
                        {previewColumns.map((col) => (
                          <td
                            key={col}
                            className="px-2 py-1 text-gray-700 whitespace-nowrap"
                          >
                            {formatCell(row[col])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {previewRows.length > 50 && (
                <div className="text-[11px] text-gray-400 mt-1">
                  {t('charts.previewTruncated')} 50 / {previewRows.length}
                </div>
              )}
            </div>
          )}
          {previewRows && previewRows.length === 0 && (
            <div className="text-xs text-gray-500">{t('charts.previewEmpty')}</div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t bg-gray-50">
          <div className="text-[11px] text-gray-500">
            {draftSql === chart.sql_query ? t('charts.noChanges') : t('charts.hasChanges')}
          </div>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded hover:bg-gray-50"
            >
              {t('common.cancel')}
            </button>
            <button
              onClick={handleSave}
              disabled={updateChartSql.isPending || draftSql.trim() === chart.sql_query.trim()}
              className="px-4 py-2 text-sm text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {updateChartSql.isPending ? t('common.saving') : t('common.save')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function formatCell(v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}
