import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || '/api/v1'

interface FieldValidationResult {
  field_name: string
  original_key: string
  sample_values: string[]
  valid_count: number
  invalid_count: number
  errors: string[]
}

interface ValidationResponse {
  entity_type: string
  status: string
  records_tested: number
  total_fields: number
  failed_fields: number
  success_rate: string
  validation_results: FieldValidationResult[]
}

const ENTITY_TYPES = ['deal', 'contact', 'lead', 'company']

export default function ValidationPage() {
  const [selectedEntity, setSelectedEntity] = useState('deal')

  const { data, isLoading, error, refetch } = useQuery<ValidationResponse>({
    queryKey: ['validation', selectedEntity],
    queryFn: () =>
      axios
        .get(`${API_URL}/sync/validate/${selectedEntity}`)
        .then((r) => r.data),
    enabled: false, // Don't auto-run
  })

  const handleValidate = () => {
    refetch()
  }

  return (
    <div className="space-y-6">
      <div className="card">
        <h1 className="text-2xl font-bold text-gray-900 mb-4">
          Field Validation Checker
        </h1>
        <p className="text-gray-600 mb-6">
          Test field type conversion from Bitrix24 to PostgreSQL. This helps identify
          fields that fail validation before running a full sync.
        </p>

        <div className="flex gap-4 items-end">
          <div className="flex-1">
            <label className="label">Entity Type</label>
            <select
              value={selectedEntity}
              onChange={(e) => setSelectedEntity(e.target.value)}
              className="input"
            >
              {ENTITY_TYPES.map((entity) => (
                <option key={entity} value={entity}>
                  {entity.charAt(0).toUpperCase() + entity.slice(1)}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={handleValidate}
            disabled={isLoading}
            className="btn btn-primary disabled:opacity-50"
          >
            {isLoading ? 'Validating...' : 'Run Validation'}
          </button>
        </div>
      </div>

      {error && (
        <div className="card bg-red-50 border border-red-200">
          <h3 className="text-red-800 font-semibold mb-2">Error</h3>
          <p className="text-red-700">{(error as Error).message}</p>
        </div>
      )}

      {data && (
        <>
          {/* Summary */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="card bg-blue-50 border border-blue-200">
              <div className="text-sm text-blue-600">Records Tested</div>
              <div className="text-2xl font-bold text-blue-800">
                {data.records_tested}
              </div>
            </div>
            <div className="card bg-gray-50 border border-gray-200">
              <div className="text-sm text-gray-600">Total Fields</div>
              <div className="text-2xl font-bold text-gray-800">
                {data.total_fields}
              </div>
            </div>
            <div className={`card border ${
              data.failed_fields > 0
                ? 'bg-red-50 border-red-200'
                : 'bg-green-50 border-green-200'
            }`}>
              <div className={`text-sm ${
                data.failed_fields > 0 ? 'text-red-600' : 'text-green-600'
              }`}>
                Failed Fields
              </div>
              <div className={`text-2xl font-bold ${
                data.failed_fields > 0 ? 'text-red-800' : 'text-green-800'
              }`}>
                {data.failed_fields}
              </div>
            </div>
            <div className="card bg-primary-50 border border-primary-200">
              <div className="text-sm text-primary-600">Success Rate</div>
              <div className="text-2xl font-bold text-primary-800">
                {data.success_rate}
              </div>
            </div>
          </div>

          {/* Validation Results */}
          <div className="card">
            <h2 className="text-lg font-semibold mb-4">Field Validation Results</h2>

            {data.failed_fields > 0 && (
              <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded">
                <p className="text-yellow-800 text-sm">
                  ⚠️ {data.failed_fields} field(s) failed validation. Review errors below and update field type conversion logic if needed.
                </p>
              </div>
            )}

            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Field Name
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Status
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Valid / Invalid
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Sample Values
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Errors
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {data.validation_results.map((field) => (
                    <tr
                      key={field.field_name}
                      className={field.invalid_count > 0 ? 'bg-red-50' : ''}
                    >
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">
                          {field.field_name}
                        </div>
                        <div className="text-xs text-gray-500">
                          {field.original_key}
                        </div>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        {field.invalid_count > 0 ? (
                          <span className="px-2 py-1 text-xs font-semibold rounded-full bg-red-100 text-red-800">
                            Failed
                          </span>
                        ) : (
                          <span className="px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">
                            OK
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                        <span className="text-green-600 font-semibold">
                          {field.valid_count}
                        </span>
                        {' / '}
                        <span className="text-red-600 font-semibold">
                          {field.invalid_count}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500">
                        <div className="max-w-xs">
                          {field.sample_values.map((val, idx) => (
                            <div key={idx} className="truncate text-xs">
                              {val}
                            </div>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {field.errors.length > 0 ? (
                          <div className="max-w-xs">
                            {field.errors.map((err, idx) => (
                              <div key={idx} className="text-xs text-red-600 mb-1">
                                {err}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {!data && !isLoading && !error && (
        <div className="card text-center py-12">
          <p className="text-gray-500">
            Select an entity type and click "Run Validation" to test field conversion
          </p>
        </div>
      )}
    </div>
  )
}
