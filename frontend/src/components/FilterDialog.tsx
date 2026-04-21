import { useState, useEffect } from 'react'
import { useTranslation } from '../i18n'
import { syncApi, type BitrixFilter } from '../services/api'

interface FilterDialogProps {
  entityType: string
  onApply: (filter: BitrixFilter) => void
  onCancel: () => void
}

const DEFAULT_FIELD_MAP: Record<string, string> = {
  task: 'CHANGED_DATE',
  user: 'TIMESTAMP_X',
  call: 'CALL_START_DATE',
  stage_history_deal: 'CREATED_TIME',
  stage_history_lead: 'CREATED_TIME',
}

const OPERATORS = ['>', '<', '>=', '<='] as const

export default function FilterDialog({ entityType, onApply, onCancel }: FilterDialogProps) {
  const { t } = useTranslation()
  const defaultField = DEFAULT_FIELD_MAP[entityType] || 'DATE_CREATE'

  const [fields, setFields] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [field, setField] = useState(defaultField)
  const [operator, setOperator] = useState<string>('>')
  const [value, setValue] = useState('')

  useEffect(() => {
    syncApi.getEntityFields(entityType)
      .then((data) => {
        setFields(data.fields)
        // If the default field exists in the list, keep it; otherwise select first
        if (data.fields.length > 0 && !data.fields.includes(defaultField)) {
          setField(data.fields[0])
        }
      })
      .catch(() => {
        // Fallback: allow manual input if API fails
        setFields([])
      })
      .finally(() => setLoading(false))
  }, [entityType, defaultField])

  const operatorLabels: Record<string, string> = {
    '>': t('syncCard.operatorGt'),
    '<': t('syncCard.operatorLt'),
    '>=': t('syncCard.operatorGte'),
    '<=': t('syncCard.operatorLte'),
  }

  const handleApply = () => {
    if (!field.trim() || !value.trim()) return
    onApply({ field: field.trim(), operator, value: value.trim() })
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md mx-4">
        <h3 className="text-lg font-semibold mb-4">{t('syncCard.filterByDate')}</h3>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('syncCard.filterField')}
            </label>
            {loading ? (
              <div className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm text-gray-400">
                {t('common.loading')}...
              </div>
            ) : fields.length > 0 ? (
              <select
                value={field}
                onChange={(e) => setField(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-primary-500 focus:border-primary-500"
              >
                {fields.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                value={field}
                onChange={(e) => setField(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-primary-500 focus:border-primary-500"
              />
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('syncCard.filterOperator')}
            </label>
            <select
              value={operator}
              onChange={(e) => setOperator(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-primary-500 focus:border-primary-500"
            >
              {OPERATORS.map((op) => (
                <option key={op} value={op}>
                  {operatorLabels[op]}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('syncCard.filterValue')}
            </label>
            <input
              type="text"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder={t('syncCard.datePlaceholder')}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-primary-500 focus:border-primary-500"
            />
          </div>
        </div>

        <div className="flex justify-end space-x-3 mt-6">
          <button
            onClick={onCancel}
            className="btn btn-secondary"
          >
            {t('syncCard.cancelFilter')}
          </button>
          <button
            onClick={handleApply}
            disabled={!field.trim() || !value.trim()}
            className="btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {t('syncCard.applyFilter')}
          </button>
        </div>
      </div>
    </div>
  )
}
