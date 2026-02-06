import ReactMarkdown from 'react-markdown'
import { useSchemaDescription, useSchemaTables } from '../hooks/useCharts'

export default function SchemaPage() {
  const { data: description, refetch, isFetching, isError, error } = useSchemaDescription()
  const { data: tablesData, isLoading: tablesLoading } = useSchemaTables()

  return (
    <div className="space-y-6">
      {/* AI Description Section */}
      <div className="card">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold">AI Schema Description</h2>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isFetching ? 'Generating...' : 'Generate Descriptions'}
          </button>
        </div>

        {isError && (
          <div className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
            {(error as Error).message || 'Failed to generate description'}
          </div>
        )}

        {description?.markdown ? (
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown>{description.markdown}</ReactMarkdown>
          </div>
        ) : (
          <div className="text-center text-gray-400 py-8">
            Click "Generate Descriptions" to create an AI-powered description of your database schema.
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
