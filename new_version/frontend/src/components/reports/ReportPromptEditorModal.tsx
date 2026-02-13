import { useState, useEffect } from 'react'
import { useTranslation } from '../../i18n'
import { useReportPromptTemplate, useUpdateReportPromptTemplate } from '../../hooks/useReports'

interface ReportPromptEditorModalProps {
  isOpen: boolean
  onClose: () => void
}

export default function ReportPromptEditorModal({ isOpen, onClose }: ReportPromptEditorModalProps) {
  const { t } = useTranslation()
  const { data: template, isLoading } = useReportPromptTemplate()
  const updateTemplate = useUpdateReportPromptTemplate()
  const [content, setContent] = useState('')

  useEffect(() => {
    if (template) {
      setContent(template.content)
    }
  }, [template])

  if (!isOpen) return null

  const handleSave = () => {
    updateTemplate.mutate(content, {
      onSuccess: () => onClose(),
    })
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[80vh] flex flex-col">
        <div className="flex justify-between items-center p-4 border-b">
          <h3 className="text-lg font-semibold">{t('reports.promptEditor')}</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-auto p-4">
          {isLoading ? (
            <div className="text-center text-gray-500 py-8">{t('common.loading')}</div>
          ) : (
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="w-full h-96 px-3 py-2 text-sm font-mono border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 resize-none"
              placeholder="System prompt for report generation..."
            />
          )}
        </div>

        <div className="flex justify-end gap-3 p-4 border-t">
          <button onClick={onClose} className="btn btn-secondary">
            {t('common.cancel')}
          </button>
          <button
            onClick={handleSave}
            disabled={updateTemplate.isPending || !content.trim()}
            className="btn btn-primary disabled:opacity-50"
          >
            {updateTemplate.isPending ? t('common.saving') : t('common.save')}
          </button>
        </div>
      </div>
    </div>
  )
}
