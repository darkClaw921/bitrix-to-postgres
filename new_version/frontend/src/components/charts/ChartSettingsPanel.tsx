import { useState } from 'react'
import type { ChartDisplayConfig } from '../../services/api'

interface ChartSettingsPanelProps {
  chartType: string
  config: ChartDisplayConfig
  onApply: (patch: Partial<ChartDisplayConfig>) => void
  isSaving: boolean
}

export default function ChartSettingsPanel({ chartType, config, onApply, isSaving }: ChartSettingsPanelProps) {
  const yKeys = Array.isArray(config.y) ? config.y : [config.y]

  // All local draft state — initialized from saved config
  const [colors, setColors] = useState(config.colors || ['#8884d8', '#82ca9d', '#ffc658', '#ff7300'])
  const [legend, setLegend] = useState(config.legend ?? { visible: true, position: 'bottom' as const })
  const [grid, setGrid] = useState(config.grid ?? { visible: true })
  const [xAxis, setXAxis] = useState(config.xAxis ?? { label: '', angle: 0 })
  const [yAxis, setYAxis] = useState(config.yAxis ?? { label: '', format: 'number' as const })
  const [line, setLine] = useState(config.line ?? { strokeWidth: 2, type: 'monotone' as const })
  const [area, setArea] = useState(config.area ?? { fillOpacity: 0.3 })
  const [pie, setPie] = useState(config.pie ?? { innerRadius: 0, showLabels: true })
  const [indicator, setIndicator] = useState(config.indicator ?? { prefix: '', suffix: '', fontSize: 'lg' as const, color: '#1f2937' })
  const [table, setTable] = useState(config.table ?? { showColumnTotals: false, showRowTotals: false, sortable: true, defaultSortDirection: 'asc' as const, pageSize: 0 })

  const isCartesian = ['bar', 'line', 'area', 'scatter'].includes(chartType)
  const isLineOrArea = ['line', 'area'].includes(chartType)
  const isPie = chartType === 'pie'
  const isIndicator = chartType === 'indicator'
  const isTable = chartType === 'table'

  const handleApply = () => {
    const patch: Partial<ChartDisplayConfig> = { colors, legend, grid, xAxis, yAxis, line, area, pie, indicator, table }
    onApply(patch)
  }

  return (
    <div className="mb-4 p-4 bg-gray-50 rounded-lg border border-gray-200 space-y-4 text-sm">
      {/* Visual settings */}
      <div>
        <h4 className="font-semibold text-gray-700 mb-2">Visual</h4>
        <div className="grid grid-cols-2 gap-3">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={legend.visible !== false}
              onChange={(e) => setLegend({ ...legend, visible: e.target.checked })}
            />
            <span>Show legend</span>
          </label>
          <label className="flex items-center gap-2">
            <span className="text-gray-500">Position:</span>
            <select
              className="border rounded px-1 py-0.5 text-xs"
              value={legend.position || 'bottom'}
              onChange={(e) => setLegend({ ...legend, position: e.target.value as 'top' | 'bottom' | 'left' | 'right' })}
            >
              <option value="top">Top</option>
              <option value="bottom">Bottom</option>
              <option value="left">Left</option>
              <option value="right">Right</option>
            </select>
          </label>

          {isCartesian && (
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={grid.visible !== false}
                onChange={(e) => setGrid({ ...grid, visible: e.target.checked })}
              />
              <span>Show grid</span>
            </label>
          )}
        </div>

        {/* Colors */}
        <div className="mt-3">
          <span className="text-gray-500">Colors:</span>
          <div className="flex gap-2 mt-1 flex-wrap">
            {(isPie ? Array.from({ length: Math.max(4, yKeys.length) }) : yKeys).map((_, i) => (
              <label key={i} className="flex items-center gap-1">
                <input
                  type="color"
                  value={colors[i] || '#8884d8'}
                  onChange={(e) => {
                    const next = [...colors]
                    next[i] = e.target.value
                    setColors(next)
                  }}
                  className="w-7 h-7 border rounded cursor-pointer"
                />
                {!isPie && <span className="text-xs text-gray-400">{yKeys[i]}</span>}
              </label>
            ))}
          </div>
        </div>
      </div>

      {/* Data format settings (cartesian only) */}
      {isCartesian && (
        <div>
          <h4 className="font-semibold text-gray-700 mb-2">Data Format</h4>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex items-center gap-2">
              <span className="text-gray-500">Y-axis format:</span>
              <select
                className="border rounded px-1 py-0.5 text-xs"
                value={yAxis.format || 'number'}
                onChange={(e) => setYAxis({ ...yAxis, format: e.target.value as 'number' | 'currency' | 'percent' })}
              >
                <option value="number">Number</option>
                <option value="currency">Currency ($)</option>
                <option value="percent">Percent (%)</option>
              </select>
            </label>

            <label className="flex items-center gap-2">
              <span className="text-gray-500">X-axis angle:</span>
              <select
                className="border rounded px-1 py-0.5 text-xs"
                value={xAxis.angle || 0}
                onChange={(e) => setXAxis({ ...xAxis, angle: Number(e.target.value) })}
              >
                <option value={0}>0°</option>
                <option value={-30}>-30°</option>
                <option value={-45}>-45°</option>
                <option value={-90}>-90°</option>
              </select>
            </label>

            <label className="flex flex-col gap-1">
              <span className="text-gray-500">X-axis label:</span>
              <input
                type="text"
                className="border rounded px-2 py-0.5 text-xs"
                placeholder="e.g. Month"
                value={xAxis.label || ''}
                onChange={(e) => setXAxis({ ...xAxis, label: e.target.value })}
              />
            </label>

            <label className="flex flex-col gap-1">
              <span className="text-gray-500">Y-axis label:</span>
              <input
                type="text"
                className="border rounded px-2 py-0.5 text-xs"
                placeholder="e.g. Revenue"
                value={yAxis.label || ''}
                onChange={(e) => setYAxis({ ...yAxis, label: e.target.value })}
              />
            </label>
          </div>
        </div>
      )}

      {/* Line / Area specific */}
      {isLineOrArea && (
        <div>
          <h4 className="font-semibold text-gray-700 mb-2">
            {chartType === 'line' ? 'Line' : 'Area'} Settings
          </h4>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex items-center gap-2">
              <span className="text-gray-500">Stroke width:</span>
              <input
                type="number"
                min={1}
                max={5}
                className="border rounded px-2 py-0.5 text-xs w-14"
                value={line.strokeWidth ?? 2}
                onChange={(e) => setLine({ ...line, strokeWidth: Number(e.target.value) })}
              />
            </label>

            <label className="flex items-center gap-2">
              <span className="text-gray-500">Line type:</span>
              <select
                className="border rounded px-1 py-0.5 text-xs"
                value={line.type || 'monotone'}
                onChange={(e) => setLine({ ...line, type: e.target.value as 'monotone' | 'linear' | 'natural' | 'step' })}
              >
                <option value="monotone">Monotone</option>
                <option value="linear">Linear</option>
                <option value="natural">Natural</option>
                <option value="step">Step</option>
              </select>
            </label>

            {chartType === 'area' && (
              <label className="flex items-center gap-2 col-span-2">
                <span className="text-gray-500">Fill opacity:</span>
                <input
                  type="range"
                  min={0.1}
                  max={1}
                  step={0.1}
                  className="flex-1"
                  value={area.fillOpacity ?? 0.3}
                  onChange={(e) => setArea({ fillOpacity: Number(e.target.value) })}
                />
                <span className="text-xs text-gray-400 w-8">{(area.fillOpacity ?? 0.3).toFixed(1)}</span>
              </label>
            )}
          </div>
        </div>
      )}

      {/* Pie specific */}
      {isPie && (
        <div>
          <h4 className="font-semibold text-gray-700 mb-2">Pie Settings</h4>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex items-center gap-2 col-span-2">
              <span className="text-gray-500">Inner radius (donut):</span>
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                className="flex-1"
                value={pie.innerRadius ?? 0}
                onChange={(e) => setPie({ ...pie, innerRadius: Number(e.target.value) })}
              />
              <span className="text-xs text-gray-400 w-8">{pie.innerRadius ?? 0}</span>
            </label>

            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={pie.showLabels !== false}
                onChange={(e) => setPie({ ...pie, showLabels: e.target.checked })}
              />
              <span>Show labels</span>
            </label>
          </div>
        </div>
      )}

      {/* Indicator specific */}
      {isIndicator && (
        <div>
          <h4 className="font-semibold text-gray-700 mb-2">Indicator Settings</h4>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-gray-500">Prefix:</span>
              <input
                type="text"
                className="border rounded px-2 py-0.5 text-xs"
                placeholder="e.g. $, ₽"
                value={indicator.prefix || ''}
                onChange={(e) => setIndicator({ ...indicator, prefix: e.target.value })}
              />
            </label>

            <label className="flex flex-col gap-1">
              <span className="text-gray-500">Suffix:</span>
              <input
                type="text"
                className="border rounded px-2 py-0.5 text-xs"
                placeholder="e.g. %, шт."
                value={indicator.suffix || ''}
                onChange={(e) => setIndicator({ ...indicator, suffix: e.target.value })}
              />
            </label>

            <label className="flex items-center gap-2">
              <span className="text-gray-500">Font size:</span>
              <select
                className="border rounded px-1 py-0.5 text-xs"
                value={indicator.fontSize || 'lg'}
                onChange={(e) => setIndicator({ ...indicator, fontSize: e.target.value as 'sm' | 'md' | 'lg' | 'xl' })}
              >
                <option value="sm">Small</option>
                <option value="md">Medium</option>
                <option value="lg">Large</option>
                <option value="xl">Extra Large</option>
              </select>
            </label>

            <label className="flex items-center gap-2">
              <span className="text-gray-500">Color:</span>
              <input
                type="color"
                value={indicator.color || '#1f2937'}
                onChange={(e) => setIndicator({ ...indicator, color: e.target.value })}
                className="w-7 h-7 border rounded cursor-pointer"
              />
            </label>
          </div>
        </div>
      )}

      {/* Table specific */}
      {isTable && (
        <div>
          <h4 className="font-semibold text-gray-700 mb-2">Table Settings</h4>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={table.showColumnTotals || false}
                onChange={(e) => setTable({ ...table, showColumnTotals: e.target.checked })}
              />
              <span>Column totals</span>
            </label>

            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={table.showRowTotals || false}
                onChange={(e) => setTable({ ...table, showRowTotals: e.target.checked })}
              />
              <span>Row totals</span>
            </label>

            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={table.sortable !== false}
                onChange={(e) => setTable({ ...table, sortable: e.target.checked })}
              />
              <span>Sortable columns</span>
            </label>

            <label className="flex items-center gap-2">
              <span className="text-gray-500">Sort direction:</span>
              <select
                className="border rounded px-1 py-0.5 text-xs"
                value={table.defaultSortDirection || 'asc'}
                onChange={(e) => setTable({ ...table, defaultSortDirection: e.target.value as 'asc' | 'desc' })}
              >
                <option value="asc">Ascending</option>
                <option value="desc">Descending</option>
              </select>
            </label>

            <label className="flex flex-col gap-1 col-span-2">
              <span className="text-gray-500">Page size (0 = no pagination):</span>
              <input
                type="number"
                min={0}
                max={1000}
                className="border rounded px-2 py-0.5 text-xs w-24"
                value={table.pageSize || 0}
                onChange={(e) => setTable({ ...table, pageSize: Number(e.target.value) })}
              />
            </label>
          </div>
        </div>
      )}

      {/* Apply button */}
      <div className="flex items-center gap-2 pt-2 border-t border-gray-200">
        <button
          onClick={handleApply}
          disabled={isSaving}
          className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {isSaving ? 'Saving...' : 'Apply'}
        </button>
      </div>
    </div>
  )
}
