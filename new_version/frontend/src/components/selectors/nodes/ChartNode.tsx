import { Handle, Position } from '@xyflow/react'
import type { NodeProps } from '@xyflow/react'

export interface ChartNodeData {
  chartTitle: string
  dcId: number
  columns: string[]
  loading?: boolean
  [key: string]: unknown
}

export default function ChartNode({ data }: NodeProps) {
  const d = data as ChartNodeData
  return (
    <div className="bg-white border border-gray-300 rounded-lg min-w-[200px] shadow-sm">
      <div className="px-3 py-2 border-b border-gray-200 bg-gray-50 rounded-t-lg">
        <div className="text-xs text-gray-400 font-medium">Chart</div>
        <div className="font-semibold text-sm text-gray-800 truncate">{d.chartTitle}</div>
      </div>
      <div className="max-h-[200px] overflow-y-auto">
        {d.loading ? (
          <div className="px-3 py-2 text-xs text-gray-400">Loading...</div>
        ) : d.columns.length === 0 ? (
          <div className="px-3 py-2 text-xs text-gray-400">No columns</div>
        ) : (
          d.columns.map((col) => (
            <div key={col} className="relative px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50 border-b border-gray-100 last:border-b-0">
              <Handle
                type="target"
                position={Position.Left}
                id={`${d.dcId}-${col}`}
                className="!w-2.5 !h-2.5 !bg-gray-400 !border-2 !border-white !-left-1"
                style={{ top: '50%' }}
              />
              <span className="font-mono">{col}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
