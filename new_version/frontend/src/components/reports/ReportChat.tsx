import { useState, useRef, useEffect } from 'react'
import { useTranslation } from '../../i18n'
import { useReportConverse } from '../../hooks/useReports'
import type { ReportConversationResponse, ReportPreview } from '../../services/api'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

interface ReportChatProps {
  onReportReady: (sessionId: string, preview: ReportPreview) => void
}

export default function ReportChat({ onReportReady }: ReportChatProps) {
  const { t } = useTranslation()
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: 'assistant', content: t('reports.chatWelcome') },
  ])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const converse = useReportConverse()

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = () => {
    if (!input.trim() || converse.isPending) return

    const userMessage = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }])

    converse.mutate(
      { session_id: sessionId || undefined, message: userMessage },
      {
        onSuccess: (data: ReportConversationResponse) => {
          if (!sessionId) {
            setSessionId(data.session_id)
          }
          setMessages((prev) => [
            ...prev,
            { role: 'assistant', content: data.content },
          ])
          if (data.is_complete && data.report_preview) {
            onReportReady(data.session_id, data.report_preview)
          }
        },
        onError: (error: unknown) => {
          const msg =
            error && typeof error === 'object' && 'response' in error
              ? (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Ошибка'
              : 'Ошибка'
          setMessages((prev) => [
            ...prev,
            { role: 'assistant', content: `**Ошибка:** ${msg}` },
          ])
        },
      },
    )
  }

  const handleNewChat = () => {
    setSessionId(null)
    setMessages([{ role: 'assistant', content: t('reports.chatWelcome') }])
    converse.reset()
  }

  return (
    <div className="card">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-semibold">{t('reports.title')}</h2>
        {sessionId && (
          <button
            onClick={handleNewChat}
            className="text-sm text-gray-500 hover:text-primary-600"
          >
            + Новый диалог
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="bg-gray-50 rounded-lg p-4 h-80 overflow-y-auto mb-4">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`mb-3 ${msg.role === 'user' ? 'text-right' : 'text-left'}`}
          >
            <div
              className={`inline-block max-w-[80%] px-4 py-2 rounded-lg text-sm ${
                msg.role === 'user'
                  ? 'bg-primary-600 text-white'
                  : 'bg-white border border-gray-200 text-gray-800'
              }`}
            >
              <div className="whitespace-pre-wrap">{msg.content}</div>
            </div>
          </div>
        ))}
        {converse.isPending && (
          <div className="text-left mb-3">
            <div className="inline-block px-4 py-2 rounded-lg bg-white border border-gray-200 text-sm text-gray-500">
              <div className="flex items-center gap-2">
                <div className="animate-pulse">AI думает...</div>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="flex space-x-3">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder={t('reports.chatPlaceholder')}
          className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          disabled={converse.isPending}
        />
        <button
          onClick={handleSend}
          disabled={converse.isPending || !input.trim()}
          className="btn btn-primary px-6 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {converse.isPending ? t('reports.chatSending') : t('reports.chatSend')}
        </button>
      </div>
    </div>
  )
}
