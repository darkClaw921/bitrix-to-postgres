import type { DesignElement } from '../../../hooks/useDesignMode'
import type { DesignLayout } from '../../../services/api'
import { useTranslation } from '../../../i18n'

interface DesignModeToolbarProps {
  selectedElement: DesignElement | null
  draftLayout: DesignLayout
  onResetElement: (el: DesignElement) => void
  onResetAll: () => void
  onApply: () => void
  onCancel: () => void
  isSaving: boolean
  chartType: string
}

const ELEMENT_LABELS: Record<DesignElement, string> = {
  legend: 'designMode.legend',
  title: 'designMode.title',
  xAxisLabel: 'designMode.xAxisLabel',
  yAxisLabel: 'designMode.yAxisLabel',
  dataLabels: 'designMode.dataLabels',
  margins: 'designMode.margins',
}

export default function DesignModeToolbar({
  selectedElement,
  draftLayout,
  onResetElement,
  onResetAll,
  onApply,
  onCancel,
  isSaving,
  chartType,
}: DesignModeToolbarProps) {
  const { t } = useTranslation()

  const getElementValues = (): string => {
    if (!selectedElement) return ''

    if (selectedElement === 'legend') {
      const l = draftLayout.legend
      if (!l) return t('designMode.defaultPosition')
      return `x: ${l.x?.toFixed(1) ?? 0}%, y: ${l.y?.toFixed(1) ?? 0}%`
    }
    if (selectedElement === 'title') {
      const ti = draftLayout.title
      if (!ti) return t('designMode.defaultPosition')
      return `dx: ${ti.dx ?? 0}px, dy: ${ti.dy ?? 0}px`
    }
    if (selectedElement === 'xAxisLabel') {
      const x = draftLayout.xAxisLabel
      if (!x) return t('designMode.defaultPosition')
      return `dx: ${x.dx ?? 0}px, dy: ${x.dy ?? 0}px`
    }
    if (selectedElement === 'yAxisLabel') {
      const y = draftLayout.yAxisLabel
      if (!y) return t('designMode.defaultPosition')
      return `dx: ${y.dx ?? 0}px, dy: ${y.dy ?? 0}px`
    }
    if (selectedElement === 'dataLabels') {
      const d = draftLayout.dataLabels
      if (!d) return t('designMode.defaultPosition')
      return `dx: ${d.dx ?? 0}px, dy: ${d.dy ?? 0}px`
    }
    if (selectedElement === 'margins') {
      const m = draftLayout.margins
      if (!m) return t('designMode.defaultPosition')
      return `T:${m.top ?? 0} R:${m.right ?? 0} B:${m.bottom ?? 0} L:${m.left ?? 0}`
    }
    return ''
  }

  const isPieOrFunnel = chartType === 'pie' || chartType === 'funnel'

  return (
    <div
      className="flex items-center gap-2 px-2 py-1.5 bg-purple-50 border border-purple-200 rounded-lg text-xs"
      onMouseDown={(e) => e.stopPropagation()}
    >
      <span className="font-semibold text-purple-700">{t('designMode.designMode')}</span>

      <div className="h-4 w-px bg-purple-200" />

      {selectedElement ? (
        <>
          <span className="text-purple-600">
            {t(ELEMENT_LABELS[selectedElement])}:
          </span>
          <span className="font-mono text-purple-800">{getElementValues()}</span>
          <button
            onClick={() => onResetElement(selectedElement)}
            className="px-1.5 py-0.5 bg-purple-100 hover:bg-purple-200 text-purple-600 rounded"
          >
            {t('designMode.resetPosition')}
          </button>
        </>
      ) : (
        <span className="text-purple-400">{t('designMode.noElementSelected')}</span>
      )}

      <div className="flex-1" />

      {!isPieOrFunnel && (
        <span className="text-[10px] text-purple-400">
          {t('designMode.dragHint')}
        </span>
      )}

      <button
        onClick={onResetAll}
        className="px-2 py-0.5 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded"
      >
        {t('designMode.resetAll')}
      </button>
      <button
        onClick={onCancel}
        className="px-2 py-0.5 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded"
      >
        {t('common.cancel')}
      </button>
      <button
        onClick={onApply}
        disabled={isSaving}
        className="px-2 py-0.5 bg-purple-600 hover:bg-purple-700 text-white rounded disabled:opacity-50"
      >
        {isSaving ? t('common.saving') : t('designMode.applyLayout')}
      </button>
    </div>
  )
}
