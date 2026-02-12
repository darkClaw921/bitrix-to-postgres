import { useCallback } from 'react'
import type { DesignElement } from '../../../hooks/useDesignMode'

interface DraggableHandleProps {
  element: DesignElement
  label: string
  isSelected: boolean
  rect: { left: number; top: number; width: number; height: number } | null
  onSelect: (el: DesignElement) => void
  onDragStart: (element: DesignElement, clientX: number, clientY: number) => void
}

export default function DraggableHandle({
  element,
  label,
  isSelected,
  rect,
  onSelect,
  onDragStart,
}: DraggableHandleProps) {
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      e.stopPropagation()
      onSelect(element)
      onDragStart(element, e.clientX, e.clientY)
    },
    [element, onSelect, onDragStart],
  )

  if (!rect) return null

  return (
    <div
      style={{
        position: 'absolute',
        left: rect.left,
        top: rect.top,
        width: rect.width,
        height: rect.height,
        pointerEvents: 'auto',
        cursor: 'move',
      }}
      className={`border-2 border-dashed rounded transition-colors ${
        isSelected
          ? 'border-purple-500 bg-purple-100/30'
          : 'border-purple-300/50 hover:border-purple-400 hover:bg-purple-50/20'
      }`}
      onMouseDown={handleMouseDown}
      title={label}
    >
      <span
        className="absolute -top-5 left-0 text-[10px] font-medium px-1 rounded whitespace-nowrap"
        style={{
          backgroundColor: isSelected ? '#8b5cf6' : '#a78bfa',
          color: '#fff',
        }}
      >
        {label}
      </span>
    </div>
  )
}
