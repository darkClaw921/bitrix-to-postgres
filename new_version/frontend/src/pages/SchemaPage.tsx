import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import {
  useSchemaDescription,
  useSchemaHistory,
  useUpdateSchemaDescription,
  useSchemaTables,
} from '../hooks/useCharts'

export default function SchemaPage() {
  const { data: newDescription, refetch, isFetching, isError, error } = useSchemaDescription()
  const { data: history, isLoading: historyLoading } = useSchemaHistory()
  const { data: tablesData, isLoading: tablesLoading } = useSchemaTables()
  const updateMutation = useUpdateSchemaDescription()

  const [isEditing, setIsEditing] = useState(false)
  const [editedMarkdown, setEditedMarkdown] = useState('')
  const [currentDescription, setCurrentDescription] = useState(history)
  const [copySuccess, setCopySuccess] = useState(false)

  // Update current description when history or new description changes
  useEffect(() => {
    if (newDescription) {
      setCurrentDescription(newDescription)
      setEditedMarkdown(newDescription.markdown)
    } else if (history && !currentDescription) {
      setCurrentDescription(history)
      setEditedMarkdown(history.markdown)
    }
  }, [newDescription, history, currentDescription])

  const handleCopy = async () => {
    if (!currentDescription?.markdown) return
    try {
      await navigator.clipboard.writeText(currentDescription.markdown)
      setCopySuccess(true)
      setTimeout(() => setCopySuccess(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  const handleEdit = () => {
    setEditedMarkdown(currentDescription?.markdown || '')
    setIsEditing(true)
  }

  const handleSave = async () => {
    if (!currentDescription?.id) return
    try {
      await updateMutation.mutateAsync({
        descId: currentDescription.id,
        data: { markdown: editedMarkdown },
      })
      setIsEditing(false)
    } catch (err) {
      console.error('Failed to save:', err)
    }
  }

  const handleCancel = () => {
    setEditedMarkdown(currentDescription?.markdown || '')
    setIsEditing(false)
  }

  return (
    <div className="space-y-6">
      {/* AI Description Section */}
      <div className="card">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold">AI Schema Description</h2>
          <div className="flex gap-2">
            {currentDescription && !isEditing && (
              <>
                <button onClick={handleEdit} className="btn btn-secondary">
                  Edit
                </button>
                <button
                  onClick={handleCopy}
                  className={`btn ${copySuccess ? 'btn-success' : 'btn-secondary'}`}
                >
                  {copySuccess ? '✓ Copied!' : 'Copy All'}
                </button>
              </>
            )}
            {isEditing && (
              <>
                <button
                  onClick={handleSave}
                  disabled={updateMutation.isPending}
                  className="btn btn-primary disabled:opacity-50"
                >
                  {updateMutation.isPending ? 'Saving...' : 'Save'}
                </button>
                <button onClick={handleCancel} className="btn btn-secondary">
                  Cancel
                </button>
              </>
            )}
            {!isEditing && (
              <button
                onClick={() => refetch()}
                disabled={isFetching}
                className="btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isFetching ? 'Generating...' : 'Regenerate'}
              </button>
            )}
          </div>
        </div>

        {isError && (
          <div className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
            {(error as Error).message || 'Failed to generate description'}
          </div>
        )}

        {updateMutation.isError && (
          <div className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700 mb-4">
            Failed to save changes
          </div>
        )}

        {historyLoading && !currentDescription ? (
          <div className="flex items-center justify-center h-32 text-gray-500">
            Loading last description...
          </div>
        ) : isEditing ? (
          <textarea
            value={editedMarkdown}
            onChange={(e) => setEditedMarkdown(e.target.value)}
            className="w-full h-96 p-4 border border-gray-300 rounded font-mono text-sm"
            placeholder="Edit markdown here..."
          />
        ) : currentDescription?.markdown ? (
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown>{currentDescription.markdown}</ReactMarkdown>
          </div>
        ) : (
          <div className="text-center text-gray-400 py-8">
            Click "Regenerate" to create an AI-powered description of your database schema.
          </div>
        )}

        {currentDescription && (
          <div className="mt-4 pt-4 border-t border-gray-200 text-xs text-gray-500">
            Last updated: {new Date(currentDescription.updated_at).toLocaleString()}
          </div>
        )}
      </div>

      {/* Raw Schema Section */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Database Tables</h2>

        {tablesLoading ? (
          <div className="flex items-center justify-center h-32 text-gray-500">Loading...</div>
        ) : !tablesData?.tables.length ? (
          <div className="text-center text-gray-400 py-8">
            No CRM tables found. Run a sync first.
          </div>
        ) : (
          <div className="space-y-4">
            {tablesData.tables.map((table) => (
              <details key={table.table_name} className="border border-gray-200 rounded-lg">
                <summary className="px-4 py-3 cursor-pointer hover:bg-gray-50 flex justify-between items-center">
                  <span className="font-medium">{table.table_name}</span>
                  <span className="text-sm text-gray-500">
                    {table.columns.length} columns
                    {table.row_count != null && ` | ${table.row_count.toLocaleString()} rows`}
                  </span>
                </summary>
                <div className="px-4 pb-3">
                  <table className="min-w-full divide-y divide-gray-200 text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                          Column
                        </th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                          Type
                        </th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                          Nullable
                        </th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                          Default
                        </th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                          Description
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {table.columns.map((col) => (
                        <tr key={col.name}>
                          <td className="px-3 py-2 font-mono text-xs">{col.name}</td>
                          <td className="px-3 py-2 text-gray-600">{col.data_type}</td>
                          <td className="px-3 py-2">
                            <span
                              className={`text-xs ${col.is_nullable ? 'text-yellow-600' : 'text-green-600'}`}
                            >
                              {col.is_nullable ? 'YES' : 'NO'}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-gray-400 text-xs">{col.column_default || '-'}</td>
                          <td className="px-3 py-2 text-gray-600 text-xs">{col.description || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
