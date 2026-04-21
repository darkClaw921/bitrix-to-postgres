import { useCallback, useRef, useState } from 'react'

type Side = 'top' | 'right' | 'bottom' | 'left'

interface MarginHandleProps {
  side: Side
  value: number
  onChange: (side: Side, value: number) => void
}

export default function MarginHandle({
  side,
  value,
  onChange,
}: MarginHandleProps) {
  const [dragging, setDragging] = useState(false)
  const startRef = useRef({ clientPos: 0, startValue: 0 })

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      e.stopPropagation()

      const clientPos = side === 'left' || side === 'right' ? e.clientX : e.clientY
      startRef.current = { clientPos, startValue: value }
      setDragging(true)

      const handleMove = (ev: MouseEvent) => {
        const currentPos = side === 'left' || side === 'right' ? ev.clientX : ev.clientY
        const delta = currentPos - startRef.current.clientPos
        const sign = side === 'right' || side === 'bottom' ? -1 : 1
        const newValue = Math.max(0, Math.round(startRef.current.startValue + delta * sign))
        onChange(side, newValue)
      }

      const handleUp = () => {
        setDragging(false)
        window.removeEventListener('mousemove', handleMove)
        window.removeEventListener('mouseup', handleUp)
      }

      window.addEventListener('mousemove', handleMove)
      window.addEventListener('mouseup', handleUp)
    },
    [side, value, onChange],
  )

  const minSize = 10
  const style: React.CSSProperties = {
    position: 'absolute',
    pointerEvents: 'auto',
    zIndex: 5,
  }

  if (side === 'top') {
    Object.assign(style, {
      top: 0,
      left: 0,
      right: 0,
      height: Math.max(minSize, value),
      cursor: 'ns-resize',
    })
  } else if (side === 'bottom') {
    Object.assign(style, {
      bottom: 0,
      left: 0,
      right: 0,
      height: Math.max(minSize, value),
      cursor: 'ns-resize',
    })
  } else if (side === 'left') {
    Object.assign(style, {
      top: 0,
      left: 0,
      bottom: 0,
      width: Math.max(minSize, value),
      cursor: 'ew-resize',
    })
  } else {
    Object.assign(style, {
      top: 0,
      right: 0,
      bottom: 0,
      width: Math.max(minSize, value),
      cursor: 'ew-resize',
    })
  }

  return (
    <div
      style={style}
      className={`transition-colors border-dashed ${
        dragging
          ? 'bg-orange-300/50 border-orange-500'
          : 'bg-orange-100/30 hover:bg-orange-200/50 border-orange-300/60 hover:border-orange-400'
      } ${
        side === 'top' ? 'border-b-2' : side === 'bottom' ? 'border-t-2' : side === 'left' ? 'border-r-2' : 'border-l-2'
      }`}
      onMouseDown={handleMouseDown}
    >
      <span
        className="absolute text-[10px] text-orange-700 font-mono font-semibold whitespace-nowrap bg-orange-100/80 px-0.5 rounded"
        style={{
          ...(side === 'top' || side === 'bottom'
            ? { left: '50%', transform: 'translateX(-50%)', top: side === 'top' ? 0 : undefined, bottom: side === 'bottom' ? 0 : undefined }
            : { top: '50%', transform: 'translateY(-50%)', left: side === 'left' ? 0 : undefined, right: side === 'right' ? 0 : undefined }),
        }}
      >
        {value}px
      </span>
    </div>
  )
}
