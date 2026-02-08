import { useState, useEffect } from 'react'
import { useChartPromptTemplate, useUpdateChartPromptTemplate } from '../../hooks/useCharts'

interface PromptEditorModalProps {
  isOpen: boolean
  onClose: () => void
}

export default function PromptEditorModal({ isOpen, onClose }: PromptEditorModalProps) {
  const { data: templateData, isLoading } = useChartPromptTemplate()
  const updateTemplate = useUpdateChartPromptTemplate()
  const [content, setContent] = useState('')
  const [isDirty, setIsDirty] = useState(false)

  useEffect(() => {
    if (templateData) {
      setContent(templateData.content)
      setIsDirty(false)
    }
  }, [templateData])

  const handleSave = () => {
    updateTemplate.mutate(content, {
      onSuccess: () => {
        setIsDirty(false)
        onClose()
      },
    })
  }

  const handleClose = () => {
    if (isDirty && !confirm('У вас есть несохранённые изменения. Закрыть без сохранения?')) {
      return
    }
    onClose()
  }

  const handleContentChange = (value: string) => {
    setContent(value)
    setIsDirty(value !== templateData?.content)
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <div>
            <h2 className="text-xl font-semibold text-gray-800">
              Редактирование промпта для AI
            </h2>
            <p className="text-sm text-gray-500 mt-1">
              Инструкции для AI при генерации чартов из данных Bitrix24
            </p>
          </div>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {isLoading ? (
            <div className="text-center py-8 text-gray-500">
              Загрузка...
            </div>
          ) : (
            <textarea
              value={content}
              onChange={(e) => handleContentChange(e.target.value)}
              className="w-full h-[500px] p-4 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 font-mono text-sm"
              placeholder="Введите инструкции для AI..."
            />
          )}

          {updateTemplate.isError && (
            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
              Ошибка сохранения: {(updateTemplate.error as Error).message}
            </div>
          )}

          <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded text-sm text-blue-800">
            <p className="font-medium mb-2">💡 Подсказки:</p>
            <ul className="list-disc list-inside space-y-1 text-xs">
              <li>Добавьте примеры SQL-запросов для типичных задач с вашими данными</li>
              <li>Укажите связи между таблицами (например, crm_deals + stage_history_deals)</li>
              <li>Опишите важные идентификаторы и ключевые поля</li>
              <li>Добавьте формулы для расчёта метрик (конверсия, время в стадиях и т.д.)</li>
            </ul>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-between items-center">
          <div className="text-sm text-gray-500">
            {isDirty && <span className="text-orange-600">● Несохранённые изменения</span>}
            {templateData && !isDirty && (
              <span>
                Последнее обновление: {new Date(templateData.updated_at).toLocaleString('ru-RU')}
              </span>
            )}
          </div>
          <div className="flex space-x-3">
            <button
              onClick={handleClose}
              className="btn btn-secondary px-4 py-2"
            >
              Отмена
            </button>
            <button
              onClick={handleSave}
              disabled={!isDirty || updateTemplate.isPending}
              className="btn btn-primary px-6 py-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {updateTemplate.isPending ? 'Сохранение...' : 'Сохранить'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
