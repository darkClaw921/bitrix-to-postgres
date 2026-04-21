import { useState, useEffect, useMemo } from 'react'
import {
  BarChart, Bar,
  LineChart, Line,
  AreaChart, Area,
  PieChart, Pie, Cell,
  ResponsiveContainer,
} from 'recharts'
import { useTranslation } from '../../i18n'
import type { ChartSpec } from '../../services/api'

const STORAGE_KEY = 'chart_generation_history'
const MAX_ITEMS = 20
const PREVIEW_ROWS = 8

const MINI_COLORS = [
  '#8884d8', '#82ca9d', '#ffc658', '#ff7300',
  '#0088fe', '#00c49f', '#ffbb28', '#ff8042',
]

export interface GenerationHistoryItem {
  id: string
  prompt: string
  chart: ChartSpec
  previewData: Record<string, unknown>[]
  timestamp: number
}

export function loadHistory(): GenerationHistoryItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    return JSON.parse(raw) as GenerationHistoryItem[]
  } catch {
    return []
  }
}

export function saveHistoryItem(
  prompt: string,
  chart: ChartSpec,
  data: Record<string, unknown>[],
) {
  const history = loadHistory()
  const item: GenerationHistoryItem = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    prompt,
    chart,
    previewData: data.slice(0, PREVIEW_ROWS),
    timestamp: Date.now(),
  }
  history.unshift(item)
  if (history.length > MAX_ITEMS) history.length = MAX_ITEMS
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(history))
  } catch {
    // localStorage full — drop oldest half
    history.length = Math.floor(history.length / 2)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(history))
  }
}

function clearHistory() {
  localStorage.removeItem(STORAGE_KEY)
}

/** Minimal sparkline-style chart preview without axes, grid, legend, tooltips */
function MiniChartPreview({ spec, data }: { spec: ChartSpec; data: Record<string, unknown>[] }) {
  const { chart_type, data_keys, colors } = spec
  const palette = colors?.length ? colors : MINI_COLORS
  const xKey = data_keys.x
  const yKeys = Array.isArray(data_keys.y) ? data_keys.y : [data_keys.y]
  const margin = { top: 4, right: 4, bottom: 4, left: 4 }

  if (chart_type === 'indicator') {
    const row = data[0] || {}
    const val = row[yKeys[0]]
    const num = Number(val)
    const display = isNaN(num) ? String(val ?? '') : num.toLocaleString()
    return (
      <div className="flex items-center justify-center h-full text-sm font-bold text-gray-700 px-1 text-center leading-tight">
        {display}
      </div>
    )
  }

  if (chart_type === 'table') {
    return (
      <div className="flex items-center justify-center h-full">
        <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 10h18M3 14h18M3 6h18M3 18h18M8 6v12M16 6v12" />
        </svg>
      </div>
    )
  }

  if (chart_type === 'pie') {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey={yKeys[0]}
            nameKey={xKey}
            cx="50%"
            cy="50%"
            outerRadius="80%"
            innerRadius={0}
            isAnimationActive={false}
            stroke="none"
          >
            {data.map((_, i) => (
              <Cell key={i} fill={palette[i % palette.length]} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
    )
  }

  if (chart_type === 'line') {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={margin}>
          {yKeys.map((key, i) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={palette[i % palette.length]}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    )
  }

  if (chart_type === 'area') {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={margin}>
          {yKeys.map((key, i) => (
            <Area
              key={key}
              type="monotone"
              dataKey={key}
              fill={palette[i % palette.length]}
              stroke={palette[i % palette.length]}
              fillOpacity={0.4}
              isAnimationActive={false}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    )
  }

  // bar, horizontal_bar, funnel, scatter, default — all render as simple bar
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={margin}>
        {yKeys.map((key, i) => (
          <Bar
            key={key}
            dataKey={key}
            fill={palette[i % palette.length]}
            isAnimationActive={false}
            radius={[2, 2, 0, 0]}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}

interface Props {
  isOpen: boolean
  onClose: () => void
  onSelectPrompt: (prompt: string) => void
}

export default function GenerationHistoryModal({ isOpen, onClose, onSelectPrompt }: Props) {
  const { t } = useTranslation()
  const [items, setItems] = useState<GenerationHistoryItem[]>([])

  useEffect(() => {
    if (isOpen) {
      setItems(loadHistory())
    }
  }, [isOpen])

  const handleUse = (prompt: string) => {
    onSelectPrompt(prompt)
    onClose()
  }

  const handleClear = () => {
    clearHistory()
    setItems([])
  }

  const formatDate = useMemo(() => {
    const fmt = new Intl.DateTimeFormat(undefined, {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
    return (ts: number) => fmt.format(new Date(ts))
  }, [])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b">
          <h3 className="text-lg font-semibold">{t('charts.generationHistory')}</h3>
          <div className="flex items-center gap-3">
            {items.length > 0 && (
              <button
                onClick={handleClear}
                className="text-xs text-red-500 hover:text-red-700"
              >
                {t('charts.historyClearAll')}
              </button>
            )}
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-3">
          {items.length === 0 ? (
            <div className="text-center text-gray-400 py-12">
              {t('charts.historyEmpty')}
            </div>
          ) : (
            <div className="space-y-3">
              {items.map((item) => (
                <div
                  key={item.id}
                  className="border rounded-lg p-3 hover:border-primary-300 hover:bg-primary-50/30 transition-colors cursor-pointer group"
                  onClick={() => handleUse(item.prompt)}
                  title={t('charts.historyUsePrompt')}
                >
                  <div className="flex gap-3">
                    {/* Mini chart */}
                    <div className="w-28 h-20 flex-shrink-0 bg-gray-50 rounded overflow-hidden">
                      {item.previewData.length > 0 ? (
                        <MiniChartPreview spec={item.chart} data={item.previewData} />
                      ) : (
                        <div className="flex items-center justify-center h-full text-gray-300 text-xs">
                          {t('charts.noData')}
                        </div>
                      )}
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-800 line-clamp-2 font-medium">
                        {item.prompt}
                      </p>
                      <div className="flex items-center gap-3 mt-1.5 text-xs text-gray-400">
                        <span>{formatDate(item.timestamp)}</span>
                        <span className="px-1.5 py-0.5 bg-gray-100 rounded text-gray-500">
                          {item.chart.chart_type}
                        </span>
                        <span className="text-gray-300">{item.chart.title}</span>
                      </div>
                    </div>

                    {/* Arrow */}
                    <div className="flex items-center opacity-0 group-hover:opacity-100 transition-opacity">
                      <svg className="w-5 h-5 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
