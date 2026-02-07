import { useState } from 'react'
import { useTranslation } from '../../i18n'

interface PasswordGateProps {
  onAuthenticated: (token: string) => void
  onSubmit: (password: string) => Promise<string>
  title?: string
}

export default function PasswordGate({ onAuthenticated, onSubmit, title }: PasswordGateProps) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const { t } = useTranslation()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!password.trim()) return

    setLoading(true)
    setError(null)

    try {
      const token = await onSubmit(password)
      onAuthenticated(token)
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setError(axiosErr?.response?.data?.detail || t('passwordGate.authFailed'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50">
      <div className="w-full max-w-sm mx-auto p-8">
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-lg font-semibold text-gray-800 text-center mb-2">
            {title || t('passwordGate.dashboardAccess')}
          </h2>
          <p className="text-sm text-gray-500 text-center mb-6">
            {t('passwordGate.enterPassword')}
          </p>

          <form onSubmit={handleSubmit}>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t('passwordGate.passwordPlaceholder')}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 mb-4"
              autoFocus
            />

            {error && (
              <div className="mb-4 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-600 text-center">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !password.trim()}
              className="w-full py-2 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? t('passwordGate.verifying') : t('passwordGate.enter')}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
