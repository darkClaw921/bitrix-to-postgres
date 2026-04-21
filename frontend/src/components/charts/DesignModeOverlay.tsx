import { useEffect, useRef, useCallback, useState } from 'react'
import DraggableHandle from './design/DraggableHandle'
import MarginHandle from './design/MarginHandle'
import type { DesignElement } from '../../hooks/useDesignMode'
import type { DesignLayout } from '../../services/api'
import { useTranslation } from '../../i18n'

interface ElementRect {
  left: number
  top: number
  width: number
  height: number
}

interface DesignModeOverlayProps {
  containerRef: React.RefObject<HTMLDivElement | null>
  selectedElement: DesignElement | null
  draftLayout: DesignLayout
  chartType: string
  onSelectElement: (el: DesignElement | null) => void
  onDragStart: (element: DesignElement, clientX: number, clientY: number, containerRect: DOMRect) => void
  onDragMove: (clientX: number, clientY: number, containerRect: DOMRect) => void
  onDragEnd: () => void
  onMarginChange: (side: 'top' | 'right' | 'bottom' | 'left', value: number) => void
  isDragging: boolean
}

export default function DesignModeOverlay({
  containerRef,
  selectedElement,
  draftLayout,
  chartType,
  onSelectElement,
  onDragStart,
  onDragMove,
  onDragEnd,
  onMarginChange,
  isDragging,
}: DesignModeOverlayProps) {
  const { t } = useTranslation()
  const overlayRef = useRef<HTMLDivElement>(null)
  const [elementRects, setElementRects] = useState<Partial<Record<DesignElement, ElementRect>>>({})

  const isPieOrFunnel = chartType === 'pie' || chartType === 'funnel'
  const hasAxes = !isPieOrFunnel && chartType !== 'scatter'

  // Detect element positions from DOM, fallback to estimated positions
  const detectElements = useCallback(() => {
    const container = containerRef.current
    if (!container) return

    const containerRect = container.getBoundingClientRect()
    const cw = containerRect.width
    const ch = containerRect.height
    const rects: Partial<Record<DesignElement, ElementRect>> = {}

    // Legend — detect from DOM
    const legendEl = container.querySelector('.recharts-legend-wrapper')
    if (legendEl) {
      const r = legendEl.getBoundingClientRect()
      rects.legend = {
        left: r.left - containerRect.left,
        top: r.top - containerRect.top,
        width: r.width,
        height: Math.max(r.height, 20),
      }
    } else {
      // Fallback: bottom center
      rects.legend = { left: cw * 0.2, top: ch - 30, width: cw * 0.6, height: 24 }
    }

    // Title — detect or fallback to top area
    const titleEl = container.querySelector('h3') ||
      container.closest('[data-design-card]')?.querySelector('h3')
    if (titleEl) {
      const r = titleEl.getBoundingClientRect()
      const top = r.top - containerRect.top
      // Clamp to visible area
      rects.title = {
        left: Math.max(0, r.left - containerRect.left),
        top: Math.max(-10, top),
        width: Math.min(r.width, cw),
        height: r.height,
      }
    } else {
      rects.title = { left: 0, top: -10, width: cw * 0.5, height: 20 }
    }

    if (hasAxes) {
      // X-axis label — detect or place at bottom center
      const xLabel = container.querySelector('.recharts-xAxis .recharts-label') ||
        container.querySelector('.recharts-xAxis text.recharts-text')
      if (xLabel) {
        const r = xLabel.getBoundingClientRect()
        rects.xAxisLabel = {
          left: r.left - containerRect.left,
          top: r.top - containerRect.top,
          width: Math.max(r.width, 60),
          height: Math.max(r.height, 18),
        }
      } else {
        // Fallback: bottom center of chart area
        rects.xAxisLabel = { left: cw * 0.3, top: ch - 50, width: cw * 0.4, height: 20 }
      }

      // Y-axis label — detect or place at left center
      const yLabel = container.querySelector('.recharts-yAxis .recharts-label') ||
        container.querySelector('.recharts-yAxis text.recharts-text')
      if (yLabel) {
        const r = yLabel.getBoundingClientRect()
        rects.yAxisLabel = {
          left: r.left - containerRect.left,
          top: r.top - containerRect.top,
          width: Math.max(r.width, 18),
          height: Math.max(r.height, 60),
        }
      } else {
        // Fallback: left center of chart area
        rects.yAxisLabel = { left: 2, top: ch * 0.2, width: 20, height: ch * 0.4 }
      }
    }

    // Data labels — detect from DOM
    const labelList = container.querySelector('.recharts-label-list')
    if (labelList) {
      const r = labelList.getBoundingClientRect()
      rects.dataLabels = {
        left: r.left - containerRect.left,
        top: r.top - containerRect.top,
        width: Math.max(r.width, 60),
        height: Math.max(r.height, 20),
      }
    } else {
      // Fallback: center of chart
      rects.dataLabels = { left: cw * 0.3, top: ch * 0.15, width: cw * 0.4, height: 20 }
    }

    setElementRects(rects)
  }, [containerRef, hasAxes])

  // Re-detect on draft layout changes and initial render
  useEffect(() => {
    const timer = setTimeout(detectElements, 150)
    return () => clearTimeout(timer)
  }, [detectElements, draftLayout])

  // Global mouse move/up handlers for drag
  useEffect(() => {
    if (!isDragging) return

    const handleMouseMove = (e: MouseEvent) => {
      const container = containerRef.current
      if (!container) return
      onDragMove(e.clientX, e.clientY, container.getBoundingClientRect())
    }

    const handleMouseUp = () => {
      onDragEnd()
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging, containerRef, onDragMove, onDragEnd])

  const handleDragStart = useCallback(
    (element: DesignElement, clientX: number, clientY: number) => {
      const container = containerRef.current
      if (!container) return
      onDragStart(element, clientX, clientY, container.getBoundingClientRect())
    },
    [containerRef, onDragStart],
  )

  const handleOverlayClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === overlayRef.current) {
        onSelectElement(null)
      }
    },
    [onSelectElement],
  )

  const margins = draftLayout.margins ?? {}

  return (
    <div
      ref={overlayRef}
      style={{
        position: 'absolute',
        inset: 0,
        pointerEvents: 'none',
        zIndex: 10,
        overflow: 'visible',
      }}
      onClick={handleOverlayClick}
    >
      {/* Margin handles */}
      <MarginHandle
        side="top"
        value={margins.top ?? 5}
        onChange={onMarginChange}
      />
      <MarginHandle
        side="right"
        value={margins.right ?? 20}
        onChange={onMarginChange}
      />
      <MarginHandle
        side="bottom"
        value={margins.bottom ?? 5}
        onChange={onMarginChange}
      />
      <MarginHandle
        side="left"
        value={margins.left ?? 0}
        onChange={onMarginChange}
      />

      {/* Element handles — always show for applicable elements */}
      {elementRects.legend && (
        <DraggableHandle
          element="legend"
          label={t('designMode.legend')}
          isSelected={selectedElement === 'legend'}
          rect={elementRects.legend}
          onSelect={onSelectElement}
          onDragStart={handleDragStart}
        />
      )}

      {elementRects.title && (
        <DraggableHandle
          element="title"
          label={t('designMode.title')}
          isSelected={selectedElement === 'title'}
          rect={elementRects.title}
          onSelect={onSelectElement}
          onDragStart={handleDragStart}
        />
      )}

      {hasAxes && elementRects.xAxisLabel && (
        <DraggableHandle
          element="xAxisLabel"
          label={t('designMode.xAxisLabel')}
          isSelected={selectedElement === 'xAxisLabel'}
          rect={elementRects.xAxisLabel}
          onSelect={onSelectElement}
          onDragStart={handleDragStart}
        />
      )}

      {hasAxes && elementRects.yAxisLabel && (
        <DraggableHandle
          element="yAxisLabel"
          label={t('designMode.yAxisLabel')}
          isSelected={selectedElement === 'yAxisLabel'}
          rect={elementRects.yAxisLabel}
          onSelect={onSelectElement}
          onDragStart={handleDragStart}
        />
      )}

      {elementRects.dataLabels && (
        <DraggableHandle
          element="dataLabels"
          label={t('designMode.dataLabels')}
          isSelected={selectedElement === 'dataLabels'}
          rect={elementRects.dataLabels}
          onSelect={onSelectElement}
          onDragStart={handleDragStart}
        />
      )}
    </div>
  )
}
