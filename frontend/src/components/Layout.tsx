import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { useHealth } from '../hooks/useSync'
import { useTranslation } from '../i18n'
import LanguageSwitcher from './LanguageSwitcher'
import { UI_VERSION } from '../version'

export default function Layout() {
  const location = useLocation()
  const navigate = useNavigate()
  const logout = useAuthStore((state) => state.logout)
  const user = useAuthStore((state) => state.user)
  const { data: health } = useHealth()
  const { t } = useTranslation()

  const navigation = [
    { name: t('nav.dashboard'), href: '/' },
    { name: t('nav.ai'), href: '/ai' },
    { name: t('nav.configuration'), href: '/config' },
    { name: t('nav.monitoring'), href: '/monitoring' },
    { name: t('nav.validation'), href: '/validation' },
    { name: t('nav.schema'), href: '/schema' },
  ]

  const isActive = (href: string) => {
    if (href === '/') return location.pathname === '/'
    return location.pathname.startsWith(href)
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex">
              <div className="flex-shrink-0 flex items-center">
                <h1 className="text-xl font-bold text-primary-600">Bitrix24 Sync</h1>
              </div>
              <nav className="ml-6 flex space-x-4">
                {navigation.map((item) => (
                  <Link
                    key={item.href}
                    to={item.href}
                    className={`inline-flex items-center px-3 py-2 text-sm font-medium rounded-md ${
                      isActive(item.href)
                        ? 'bg-primary-100 text-primary-700'
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                    }`}
                  >
                    {item.name}
                  </Link>
                ))}
              </nav>
            </div>
            <div className="flex items-center space-x-4">
              <LanguageSwitcher />
              {/* Health indicator */}
              <div className="flex items-center space-x-2">
                <span
                  className={`w-2 h-2 rounded-full ${
                    health?.status === 'healthy' ? 'bg-green-500' : 'bg-red-500'
                  }`}
                />
                <span className="text-sm text-gray-500">
                  {health?.status === 'healthy' ? t('health.connected') : t('health.disconnected')}
                </span>
              </div>
              {/* User info */}
              <span className="text-sm text-gray-600">{user?.email}</span>
              <button
                onClick={() => { logout(); navigate('/login') }}
                className="btn btn-secondary text-sm"
              >
                {t('auth.logout')}
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex justify-end">
          <span className="text-xs text-gray-400">{t('footer.version')} {UI_VERSION}</span>
        </div>
      </footer>
    </div>
  )
}
