import { BaseEdge, EdgeLabelRenderer, getBezierPath } from '@xyflow/react'
import type { EdgeProps } from '@xyflow/react'

export interface MappingEdgeData {
  targetColumn: string
  operatorOverride?: string
  onDelete?: (edgeId: string) => void
  onConfigure?: (edgeId: string) => void
  [key: string]: unknown
}

export default function MappingEdge(props: EdgeProps) {
  const { id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data, selected } = props
  const d = data as MappingEdgeData | undefined
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  })

  const labelText = d?.targetColumn || ''
  const opText = d?.operatorOverride ? ` (${d.operatorOverride})` : ''

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: selected ? '#3b82f6' : '#94a3b8',
          strokeWidth: selected ? 2.5 : 1.5,
        }}
      />
      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: 'all',
          }}
          className="nodrag nopan"
        >
          <div
            className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] shadow-sm cursor-pointer transition-colors ${
              selected ? 'bg-blue-100 border border-blue-300 text-blue-700' : 'bg-white border border-gray-200 text-gray-600'
            }`}
            onClick={() => d?.onConfigure?.(id)}
          >
            <span className="font-mono">{labelText}{opText}</span>
            {selected && (
              <button
                onClick={(e) => { e.stopPropagation(); d?.onDelete?.(id) }}
                className="text-red-400 hover:text-red-600 ml-1 text-xs leading-none"
                title="Delete"
              >
                &times;
              </button>
            )}
          </div>
        </div>
      </EdgeLabelRenderer>
    </>
  )
}
