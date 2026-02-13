import { useEffect, useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { markdownTableComponents } from '../components/reports/markdownComponents'
import PasswordGate from '../components/dashboards/PasswordGate'
import { useTranslation } from '../i18n'
import { publicApi } from '../services/api'
import type { PublicReport, PublicReportRun } from '../services/api'

const SESSION_KEY_PREFIX = 'report_token_'

export default function EmbedReportPage() {
  const { slug } = useParams<{ slug: string }>()
  const { t } = useTranslation()
  const [token, setToken] = useState<string | null>(() => {
    if (!slug) return null
    return sessionStorage.getItem(SESSION_KEY_PREFIX + slug)
  })
  const [report, setReport] = useState<PublicReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  // Tab state
  const [activeTab, setActiveTab] = useState<string>('main')
  const [linkedCache, setLinkedCache] = useState<Record<string, PublicReport>>({})
  const [linkedLoading, setLinkedLoading] = useState(false)

  // Accordion state
  const [expandedRuns, setExpandedRuns] = useState<Set<number>>(new Set())

  const handleAuth = useCallback(
    async (password: string): Promise<string> => {
      if (!slug) throw new Error('No slug')
      const res = await publicApi.authenticateReport(slug, password)
      sessionStorage.setItem(SESSION_KEY_PREFIX + slug, res.token)
      return res.token
    },
    [slug],
  )

  const handleAuthenticated = useCallback((t: string) => {
    setToken(t)
  }, [])

  // Load report once authenticated
  useEffect(() => {
    if (!slug || !token) return

    setLoading(true)
    publicApi
      .getPublicReport(slug, token)
      .then((data) => {
        setReport(data)
        // Auto-expand first run
        if (data.runs.length > 0) {
          setExpandedRuns(new Set([data.runs[0].id]))
        }
      })
      .catch((err) => {
        const axiosErr = err as { response?: { status?: number } }
        if (axiosErr?.response?.status === 401) {
          sessionStorage.removeItem(SESSION_KEY_PREFIX + slug)
          setToken(null)
        } else {
          setError(t('embedReport.reportNotFound'))
        }
      })
      .finally(() => setLoading(false))
  }, [slug, token, t])

  const handleTabClick = useCallback(
    async (tabSlug: string) => {
      if (tabSlug === activeTab) return
      setActiveTab(tabSlug)

      if (tabSlug === 'main') return
      if (linkedCache[tabSlug]) return

      if (!slug || !token) return
      setLinkedLoading(true)
      try {
        const linkedReport = await publicApi.getLinkedReport(slug, tabSlug, token)
        setLinkedCache((prev) => ({ ...prev, [tabSlug]: linkedReport }))
      } catch (err) {
        const axiosErr = err as { response?: { status?: number } }
        if (axiosErr?.response?.status === 401) {
          sessionStorage.removeItem(SESSION_KEY_PREFIX + slug)
          setToken(null)
        }
      } finally {
        setLinkedLoading(false)
      }
    },
    [activeTab, linkedCache, slug, token],
  )

  const toggleRun = (runId: number) => {
    setExpandedRuns((prev) => {
      const next = new Set(prev)
      if (next.has(runId)) next.delete(runId)
      else next.add(runId)
      return next
    })
  }

  if (!token) {
    return (
      <PasswordGate
        onAuthenticated={handleAuthenticated}
        onSubmit={handleAuth}
        title={t('embedReport.reportAccess')}
      />
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-gray-400">{t('embedReport.loadingReport')}</div>
      </div>
    )
  }

  if (error || !report) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-red-500">{error || t('embedReport.reportNotFound')}</div>
      </div>
    )
  }

  const linkedReports = report.linked_reports || []
  const hasTabs = linkedReports.length > 0

  // Determine active data
  let activeReport: PublicReport = report
  if (activeTab !== 'main' && linkedCache[activeTab]) {
    activeReport = linkedCache[activeTab]
  }

  return (
    <div className="min-h-screen bg-gray-50 p-3 md:p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-4">
          <h1 className="text-xl md:text-2xl font-bold text-gray-800">{report.title}</h1>
          {report.report_title && report.report_title !== report.title && (
            <p className="text-sm text-gray-400 mt-0.5">{report.report_title}</p>
          )}
          {report.description && (
            <p className="text-gray-500 mt-1">{report.description}</p>
          )}
        </div>

        {/* Tab bar */}
        {hasTabs && (
          <div className="flex space-x-1 border-b border-gray-200 mb-4">
            <TabButton
              label={report.title}
              isActive={activeTab === 'main'}
              onClick={() => handleTabClick('main')}
            />
            {linkedReports.map((link) => (
              <TabButton
                key={link.id}
                label={link.label || link.linked_title || 'Tab'}
                isActive={activeTab === link.linked_slug}
                onClick={() => link.linked_slug && handleTabClick(link.linked_slug)}
              />
            ))}
          </div>
        )}

        {!hasTabs && <div className="mb-4" />}

        {/* Runs accordion */}
        {linkedLoading ? (
          <div className="flex items-center justify-center h-64 text-gray-400">
            {t('embedReport.loadingReport')}
          </div>
        ) : activeReport.runs.length === 0 ? (
          <div className="card text-center text-gray-400 py-12">
            {t('embedReport.noRuns')}
          </div>
        ) : (
          <div className="space-y-3">
            {activeReport.runs.map((run) => (
              <RunAccordionItem
                key={run.id}
                run={run}
                isExpanded={expandedRuns.has(run.id)}
                onToggle={() => toggleRun(run.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function TabButton({
  label,
  isActive,
  onClick,
}: {
  label: string
  isActive: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
        isActive
          ? 'border-blue-500 text-blue-600'
          : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
      }`}
    >
      {label}
    </button>
  )
}

function RunAccordionItem({
  run,
  isExpanded,
  onToggle,
}: {
  run: PublicReportRun
  isExpanded: boolean
  onToggle: () => void
}) {
  const { t } = useTranslation()

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr)
    return d.toLocaleString()
  }

  const formatDuration = (ms?: number) => {
    if (!ms) return null
    if (ms < 1000) return `${ms}ms`
    return `${(ms / 1000).toFixed(1)}s`
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700">
            {run.status}
          </span>
          <span className="text-sm text-gray-600">
            {t('embedReport.runOn')} {formatDate(run.created_at)}
          </span>
          {run.execution_time_ms && (
            <span className="text-xs text-gray-400">
              {t('embedReport.executionTime')}: {formatDuration(run.execution_time_ms)}
            </span>
          )}
        </div>
        <svg
          className={`w-5 h-5 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isExpanded && (
        <div className="px-4 pb-4 border-t border-gray-100">
          <div className="pt-3 prose prose-sm max-w-none">
            {run.result_markdown ? (
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownTableComponents}>
                {run.result_markdown}
              </ReactMarkdown>
            ) : (
              <p className="text-gray-400 italic">{t('embedReport.noRuns')}</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
