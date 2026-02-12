import { useState } from 'react'
import type { ChartDisplayConfig } from '../../services/api'
import { useTranslation } from '../../i18n'

interface ChartSettingsPanelProps {
  chartType: string
  config: ChartDisplayConfig
  onApply: (patch: Partial<ChartDisplayConfig>) => void
  isSaving: boolean
}

export default function ChartSettingsPanel({ chartType, config, onApply, isSaving }: ChartSettingsPanelProps) {
  const { t } = useTranslation()
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
  const [funnel, setFunnel] = useState(config.funnel ?? { showLabels: true, labelPosition: 'right' as const })
  const [cardStyle, setCardStyle] = useState(config.cardStyle ?? { backgroundColor: '', borderRadius: 'md' as const, shadow: 'sm' as const, padding: 'md' as const })
  const [general, setGeneral] = useState(config.general ?? { titleFontSize: 'md' as const, showTooltip: true, animate: true, showDataLabels: false, margins: { top: 5, right: 20, bottom: 5, left: 0 } })

  const isCartesian = ['bar', 'line', 'area', 'scatter', 'horizontal_bar'].includes(chartType)
  const isLineOrArea = ['line', 'area'].includes(chartType)
  const isPie = chartType === 'pie'
  const isIndicator = chartType === 'indicator'
  const isTable = chartType === 'table'
  const isFunnel = chartType === 'funnel'
  const isChartWithTooltip = isCartesian || isPie || isFunnel

  const handleApply = () => {
    const patch: Partial<ChartDisplayConfig> = { colors, legend, grid, xAxis, yAxis, line, area, pie, indicator, table, funnel, cardStyle, general }
    onApply(patch)
  }

  return (
    <div className="mb-4 p-4 bg-gray-50 rounded-lg border border-gray-200 space-y-4 text-sm">
      {/* Visual settings */}
      <div>
        <h4 className="font-semibold text-gray-700 mb-2">{t('chartSettings.visual')}</h4>
        <div className="grid grid-cols-2 gap-3">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={legend.visible !== false}
              onChange={(e) => setLegend({ ...legend, visible: e.target.checked })}
            />
            <span>{t('chartSettings.showLegend')}</span>
          </label>
          <label className="flex items-center gap-2">
            <span className="text-gray-500">{t('chartSettings.position')}</span>
            <select
              className="border rounded px-1 py-0.5 text-xs"
              value={legend.position || 'bottom'}
              onChange={(e) => setLegend({ ...legend, position: e.target.value as 'top' | 'bottom' | 'left' | 'right' })}
            >
              <option value="top">{t('chartSettings.top')}</option>
              <option value="bottom">{t('chartSettings.bottom')}</option>
              <option value="left">{t('chartSettings.left')}</option>
              <option value="right">{t('chartSettings.right')}</option>
            </select>
          </label>

          {isCartesian && (
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={grid.visible !== false}
                onChange={(e) => setGrid({ ...grid, visible: e.target.checked })}
              />
              <span>{t('chartSettings.showGrid')}</span>
            </label>
          )}
        </div>

        {/* Colors */}
        <div className="mt-3">
          <span className="text-gray-500">{t('chartSettings.colors')}</span>
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
          <h4 className="font-semibold text-gray-700 mb-2">{t('chartSettings.dataFormat')}</h4>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex items-center gap-2">
              <span className="text-gray-500">{t('chartSettings.yAxisFormat')}</span>
              <select
                className="border rounded px-1 py-0.5 text-xs"
                value={yAxis.format || 'number'}
                onChange={(e) => setYAxis({ ...yAxis, format: e.target.value as 'number' | 'currency' | 'percent' })}
              >
                <option value="number">{t('chartSettings.number')}</option>
                <option value="currency">{t('chartSettings.currency')}</option>
                <option value="percent">{t('chartSettings.percent')}</option>
              </select>
            </label>

            <label className="flex items-center gap-2">
              <span className="text-gray-500">{t('chartSettings.xAxisAngle')}</span>
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
              <span className="text-gray-500">{t('chartSettings.xAxisLabel')}</span>
              <input
                type="text"
                className="border rounded px-2 py-0.5 text-xs"
                placeholder="e.g. Month"
                value={xAxis.label || ''}
                onChange={(e) => setXAxis({ ...xAxis, label: e.target.value })}
              />
            </label>

            <label className="flex flex-col gap-1">
              <span className="text-gray-500">{t('chartSettings.yAxisLabel')}</span>
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
            {chartType === 'line' ? t('chartSettings.lineSettings') : t('chartSettings.areaSettings')}
          </h4>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex items-center gap-2">
              <span className="text-gray-500">{t('chartSettings.strokeWidth')}</span>
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
              <span className="text-gray-500">{t('chartSettings.lineType')}</span>
              <select
                className="border rounded px-1 py-0.5 text-xs"
                value={line.type || 'monotone'}
                onChange={(e) => setLine({ ...line, type: e.target.value as 'monotone' | 'linear' | 'natural' | 'step' })}
              >
                <option value="monotone">{t('chartSettings.monotone')}</option>
                <option value="linear">{t('chartSettings.linear')}</option>
                <option value="natural">{t('chartSettings.natural')}</option>
                <option value="step">{t('chartSettings.step')}</option>
              </select>
            </label>

            {chartType === 'area' && (
              <label className="flex items-center gap-2 col-span-2">
                <span className="text-gray-500">{t('chartSettings.fillOpacity')}</span>
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
          <h4 className="font-semibold text-gray-700 mb-2">{t('chartSettings.pieSettings')}</h4>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex items-center gap-2 col-span-2">
              <span className="text-gray-500">{t('chartSettings.innerRadius')}</span>
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
              <span>{t('chartSettings.showLabels')}</span>
            </label>
          </div>
        </div>
      )}

      {/* Indicator specific */}
      {isIndicator && (
        <div>
          <h4 className="font-semibold text-gray-700 mb-2">{t('chartSettings.indicatorSettings')}</h4>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-gray-500">{t('chartSettings.prefix')}</span>
              <input
                type="text"
                className="border rounded px-2 py-0.5 text-xs"
                placeholder="e.g. $, ₽"
                value={indicator.prefix || ''}
                onChange={(e) => setIndicator({ ...indicator, prefix: e.target.value })}
              />
            </label>

            <label className="flex flex-col gap-1">
              <span className="text-gray-500">{t('chartSettings.suffix')}</span>
              <input
                type="text"
                className="border rounded px-2 py-0.5 text-xs"
                placeholder="e.g. %, шт."
                value={indicator.suffix || ''}
                onChange={(e) => setIndicator({ ...indicator, suffix: e.target.value })}
              />
            </label>

            <label className="flex items-center gap-2">
              <span className="text-gray-500">{t('chartSettings.fontSize')}</span>
              <select
                className="border rounded px-1 py-0.5 text-xs"
                value={indicator.fontSize || 'lg'}
                onChange={(e) => setIndicator({ ...indicator, fontSize: e.target.value as 'sm' | 'md' | 'lg' | 'xl' })}
              >
                <option value="sm">{t('chartSettings.small')}</option>
                <option value="md">{t('chartSettings.medium')}</option>
                <option value="lg">{t('chartSettings.large')}</option>
                <option value="xl">{t('chartSettings.extraLarge')}</option>
              </select>
            </label>

            <label className="flex items-center gap-2">
              <span className="text-gray-500">{t('chartSettings.color')}</span>
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
          <h4 className="font-semibold text-gray-700 mb-2">{t('chartSettings.tableSettings')}</h4>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={table.showColumnTotals || false}
                onChange={(e) => setTable({ ...table, showColumnTotals: e.target.checked })}
              />
              <span>{t('chartSettings.columnTotals')}</span>
            </label>

            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={table.showRowTotals || false}
                onChange={(e) => setTable({ ...table, showRowTotals: e.target.checked })}
              />
              <span>{t('chartSettings.rowTotals')}</span>
            </label>

            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={table.sortable !== false}
                onChange={(e) => setTable({ ...table, sortable: e.target.checked })}
              />
              <span>{t('chartSettings.sortableColumns')}</span>
            </label>

            <label className="flex items-center gap-2">
              <span className="text-gray-500">{t('chartSettings.sortDirection')}</span>
              <select
                className="border rounded px-1 py-0.5 text-xs"
                value={table.defaultSortDirection || 'asc'}
                onChange={(e) => setTable({ ...table, defaultSortDirection: e.target.value as 'asc' | 'desc' })}
              >
                <option value="asc">{t('chartSettings.ascending')}</option>
                <option value="desc">{t('chartSettings.descending')}</option>
              </select>
            </label>

            <label className="flex flex-col gap-1 col-span-2">
              <span className="text-gray-500">{t('chartSettings.pageSize')}</span>
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

      {/* Funnel specific */}
      {isFunnel && (
        <div>
          <h4 className="font-semibold text-gray-700 mb-2">{t('chartSettings.funnelSettings')}</h4>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={funnel.showLabels !== false}
                onChange={(e) => setFunnel({ ...funnel, showLabels: e.target.checked })}
              />
              <span>{t('chartSettings.showValuesInside')}</span>
            </label>
          </div>
        </div>
      )}

      {/* Card Style */}
      <div>
        <h4 className="font-semibold text-gray-700 mb-2">{t('chartSettings.cardStyle')}</h4>
        <div className="grid grid-cols-2 gap-3">
          <label className="flex items-center gap-2">
            <span className="text-gray-500">{t('chartSettings.backgroundColor')}</span>
            <input
              type="color"
              value={cardStyle.backgroundColor || '#ffffff'}
              onChange={(e) => setCardStyle({ ...cardStyle, backgroundColor: e.target.value })}
              className="w-7 h-7 border rounded cursor-pointer"
            />
          </label>

          <label className="flex items-center gap-2">
            <span className="text-gray-500">{t('chartSettings.borderRadius')}</span>
            <select
              className="border rounded px-1 py-0.5 text-xs"
              value={cardStyle.borderRadius || 'md'}
              onChange={(e) => setCardStyle({ ...cardStyle, borderRadius: e.target.value as 'none' | 'sm' | 'md' | 'lg' | 'xl' })}
            >
              <option value="none">{t('chartSettings.radiusNone')}</option>
              <option value="sm">{t('chartSettings.radiusSm')}</option>
              <option value="md">{t('chartSettings.radiusMd')}</option>
              <option value="lg">{t('chartSettings.radiusLg')}</option>
              <option value="xl">{t('chartSettings.radiusXl')}</option>
            </select>
          </label>

          <label className="flex items-center gap-2">
            <span className="text-gray-500">{t('chartSettings.shadow')}</span>
            <select
              className="border rounded px-1 py-0.5 text-xs"
              value={cardStyle.shadow || 'sm'}
              onChange={(e) => setCardStyle({ ...cardStyle, shadow: e.target.value as 'none' | 'sm' | 'md' | 'lg' })}
            >
              <option value="none">{t('chartSettings.shadowNone')}</option>
              <option value="sm">{t('chartSettings.shadowSm')}</option>
              <option value="md">{t('chartSettings.shadowMd')}</option>
              <option value="lg">{t('chartSettings.shadowLg')}</option>
            </select>
          </label>

          <label className="flex items-center gap-2">
            <span className="text-gray-500">{t('chartSettings.padding')}</span>
            <select
              className="border rounded px-1 py-0.5 text-xs"
              value={cardStyle.padding || 'md'}
              onChange={(e) => setCardStyle({ ...cardStyle, padding: e.target.value as 'sm' | 'md' | 'lg' })}
            >
              <option value="sm">{t('chartSettings.paddingSm')}</option>
              <option value="md">{t('chartSettings.paddingMd')}</option>
              <option value="lg">{t('chartSettings.paddingLg')}</option>
            </select>
          </label>
        </div>
      </div>

      {/* General Settings */}
      <div>
        <h4 className="font-semibold text-gray-700 mb-2">{t('chartSettings.generalSettings')}</h4>
        <div className="grid grid-cols-2 gap-3">
          <label className="flex items-center gap-2">
            <span className="text-gray-500">{t('chartSettings.titleFontSize')}</span>
            <select
              className="border rounded px-1 py-0.5 text-xs"
              value={general.titleFontSize || 'md'}
              onChange={(e) => setGeneral({ ...general, titleFontSize: e.target.value as 'sm' | 'md' | 'lg' | 'xl' })}
            >
              <option value="sm">{t('chartSettings.small')}</option>
              <option value="md">{t('chartSettings.medium')}</option>
              <option value="lg">{t('chartSettings.large')}</option>
              <option value="xl">{t('chartSettings.extraLarge')}</option>
            </select>
          </label>

          {isChartWithTooltip && (
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={general.showTooltip !== false}
                onChange={(e) => setGeneral({ ...general, showTooltip: e.target.checked })}
              />
              <span>{t('chartSettings.showTooltip')}</span>
            </label>
          )}

          {!isTable && !isIndicator && (
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={general.animate !== false}
                onChange={(e) => setGeneral({ ...general, animate: e.target.checked })}
              />
              <span>{t('chartSettings.animation')}</span>
            </label>
          )}

          {(isCartesian) && (
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={general.showDataLabels || false}
                onChange={(e) => setGeneral({ ...general, showDataLabels: e.target.checked })}
              />
              <span>{t('chartSettings.showDataLabels')}</span>
            </label>
          )}
        </div>

        {/* Chart margins */}
        {!isTable && !isIndicator && (
          <div className="mt-3">
            <span className="text-gray-500 text-xs">{t('chartSettings.chartMargins')}</span>
            <div className="grid grid-cols-4 gap-2 mt-1">
              <label className="flex flex-col gap-0.5">
                <span className="text-xs text-gray-400">{t('chartSettings.marginTop')}</span>
                <input
                  type="number"
                  className="border rounded px-2 py-0.5 text-xs w-full"
                  value={general.margins?.top ?? 5}
                  onChange={(e) => setGeneral({ ...general, margins: { ...general.margins, top: Number(e.target.value) } })}
                />
              </label>
              <label className="flex flex-col gap-0.5">
                <span className="text-xs text-gray-400">{t('chartSettings.marginRight')}</span>
                <input
                  type="number"
                  className="border rounded px-2 py-0.5 text-xs w-full"
                  value={general.margins?.right ?? 20}
                  onChange={(e) => setGeneral({ ...general, margins: { ...general.margins, right: Number(e.target.value) } })}
                />
              </label>
              <label className="flex flex-col gap-0.5">
                <span className="text-xs text-gray-400">{t('chartSettings.marginBottom')}</span>
                <input
                  type="number"
                  className="border rounded px-2 py-0.5 text-xs w-full"
                  value={general.margins?.bottom ?? 5}
                  onChange={(e) => setGeneral({ ...general, margins: { ...general.margins, bottom: Number(e.target.value) } })}
                />
              </label>
              <label className="flex flex-col gap-0.5">
                <span className="text-xs text-gray-400">{t('chartSettings.marginLeft')}</span>
                <input
                  type="number"
                  className="border rounded px-2 py-0.5 text-xs w-full"
                  value={general.margins?.left ?? 0}
                  onChange={(e) => setGeneral({ ...general, margins: { ...general.margins, left: Number(e.target.value) } })}
                />
              </label>
            </div>
          </div>
        )}
      </div>

      {/* Apply button */}
      <div className="flex items-center gap-2 pt-2 border-t border-gray-200">
        <button
          onClick={handleApply}
          disabled={isSaving}
          className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {isSaving ? t('common.saving') : t('common.apply')}
        </button>
      </div>
    </div>
  )
}
