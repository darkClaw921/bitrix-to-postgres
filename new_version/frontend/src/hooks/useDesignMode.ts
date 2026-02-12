import { useState, useCallback, useRef } from 'react'
import type { DesignLayout } from '../services/api'

export type DesignElement = 'legend' | 'title' | 'xAxisLabel' | 'yAxisLabel' | 'dataLabels' | 'margins'

interface DragState {
  element: DesignElement
  startX: number
  startY: number
  startValue: { x: number; y: number }
}

export interface UseDesignModeReturn {
  isActive: boolean
  activate: () => void
  deactivate: () => void
  selectedElement: DesignElement | null
  selectElement: (el: DesignElement | null) => void
  draftLayout: DesignLayout
  updateDraft: (patch: Partial<DesignLayout>) => void
  resetElement: (el: DesignElement) => void
  resetAll: () => void
  applyLayout: () => DesignLayout
  onDragStart: (element: DesignElement, clientX: number, clientY: number, containerRect: DOMRect) => void
  onDragMove: (clientX: number, clientY: number, containerRect: DOMRect) => void
  onDragEnd: () => void
  isDragging: boolean
}

export function useDesignMode(initialLayout?: DesignLayout): UseDesignModeReturn {
  const [isActive, setIsActive] = useState(false)
  const [selectedElement, setSelectedElement] = useState<DesignElement | null>(null)
  const [draftLayout, setDraftLayout] = useState<DesignLayout>(initialLayout || {})
  const dragRef = useRef<DragState | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  const activate = useCallback(() => {
    setIsActive(true)
  }, [])

  const deactivate = useCallback(() => {
    setIsActive(false)
    setSelectedElement(null)
    dragRef.current = null
    setIsDragging(false)
  }, [])

  const selectElement = useCallback((el: DesignElement | null) => {
    setSelectedElement(el)
  }, [])

  const updateDraft = useCallback((patch: Partial<DesignLayout>) => {
    setDraftLayout((prev) => ({ ...prev, ...patch }))
  }, [])

  const resetElement = useCallback((el: DesignElement) => {
    setDraftLayout((prev) => {
      const next = { ...prev }
      delete next[el]
      return next
    })
  }, [])

  const resetAll = useCallback(() => {
    setDraftLayout({})
  }, [])

  const applyLayout = useCallback((): DesignLayout => {
    return { ...draftLayout }
  }, [draftLayout])

  const onDragStart = useCallback(
    (element: DesignElement, clientX: number, clientY: number, _containerRect: DOMRect) => {
      let startValue = { x: 0, y: 0 }

      if (element === 'legend') {
        startValue = {
          x: draftLayout.legend?.x ?? 0,
          y: draftLayout.legend?.y ?? 0,
        }
      } else if (element === 'title') {
        startValue = {
          x: draftLayout.title?.dx ?? 0,
          y: draftLayout.title?.dy ?? 0,
        }
      } else if (element === 'xAxisLabel') {
        startValue = {
          x: draftLayout.xAxisLabel?.dx ?? 0,
          y: draftLayout.xAxisLabel?.dy ?? 0,
        }
      } else if (element === 'yAxisLabel') {
        startValue = {
          x: draftLayout.yAxisLabel?.dx ?? 0,
          y: draftLayout.yAxisLabel?.dy ?? 0,
        }
      } else if (element === 'dataLabels') {
        startValue = {
          x: draftLayout.dataLabels?.dx ?? 0,
          y: draftLayout.dataLabels?.dy ?? 0,
        }
      }

      dragRef.current = { element, startX: clientX, startY: clientY, startValue }
      setIsDragging(true)
      setSelectedElement(element)
    },
    [draftLayout],
  )

  const onDragMove = useCallback(
    (clientX: number, clientY: number, containerRect: DOMRect) => {
      const drag = dragRef.current
      if (!drag) return

      const deltaX = clientX - drag.startX
      const deltaY = clientY - drag.startY

      if (drag.element === 'legend') {
        // Convert delta to % of container
        const pctX = (deltaX / containerRect.width) * 100
        const pctY = (deltaY / containerRect.height) * 100
        setDraftLayout((prev) => ({
          ...prev,
          legend: {
            ...prev.legend,
            x: Math.round((drag.startValue.x + pctX) * 10) / 10,
            y: Math.round((drag.startValue.y + pctY) * 10) / 10,
          },
        }))
      } else if (drag.element === 'title') {
        setDraftLayout((prev) => ({
          ...prev,
          title: {
            dx: Math.round(drag.startValue.x + deltaX),
            dy: Math.round(drag.startValue.y + deltaY),
          },
        }))
      } else if (drag.element === 'xAxisLabel') {
        setDraftLayout((prev) => ({
          ...prev,
          xAxisLabel: {
            ...prev.xAxisLabel,
            dx: Math.round(drag.startValue.x + deltaX),
            dy: Math.round(drag.startValue.y + deltaY),
          },
        }))
      } else if (drag.element === 'yAxisLabel') {
        setDraftLayout((prev) => ({
          ...prev,
          yAxisLabel: {
            ...prev.yAxisLabel,
            dx: Math.round(drag.startValue.x + deltaX),
            dy: Math.round(drag.startValue.y + deltaY),
          },
        }))
      } else if (drag.element === 'dataLabels') {
        setDraftLayout((prev) => ({
          ...prev,
          dataLabels: {
            ...prev.dataLabels,
            dx: Math.round(drag.startValue.x + deltaX),
            dy: Math.round(drag.startValue.y + deltaY),
          },
        }))
      }
    },
    [],
  )

  const onDragEnd = useCallback(() => {
    dragRef.current = null
    setIsDragging(false)
  }, [])

  return {
    isActive,
    activate,
    deactivate,
    selectedElement,
    selectElement,
    draftLayout,
    updateDraft,
    resetElement,
    resetAll,
    applyLayout,
    onDragStart,
    onDragMove,
    onDragEnd,
    isDragging,
  }
}
