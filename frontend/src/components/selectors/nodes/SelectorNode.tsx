import { Handle, Position } from '@xyflow/react'
import type { NodeProps } from '@xyflow/react'

export interface SelectorNodeData {
  label: string
  selectorType: string
  operator: string
  [key: string]: unknown
}

export default function SelectorNode({ data }: NodeProps) {
  const d = data as SelectorNodeData
  return (
    <div className="bg-blue-50 border-2 border-blue-400 rounded-lg px-4 py-3 min-w-[180px] shadow-sm">
      <div className="text-xs text-blue-500 font-medium mb-1">Selector</div>
      <div className="font-semibold text-sm text-gray-800 truncate">{d.label || '—'}</div>
      <div className="flex gap-2 mt-1.5 text-[11px] text-gray-500">
        <span className="bg-blue-100 px-1.5 py-0.5 rounded">{d.selectorType}</span>
        <span className="bg-gray-100 px-1.5 py-0.5 rounded">{d.operator}</span>
      </div>
      <Handle
        type="source"
        position={Position.Right}
        className="!w-3 !h-3 !bg-blue-500 !border-2 !border-white"
      />
    </div>
  )
}
