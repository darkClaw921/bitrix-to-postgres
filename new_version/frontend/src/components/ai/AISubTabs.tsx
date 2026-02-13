import { Link, useLocation } from 'react-router-dom'
import { useTranslation } from '../../i18n'

export default function AISubTabs() {
  const location = useLocation()
  const { t } = useTranslation()

  const tabs = [
    { name: t('ai.chartsTab'), href: '/ai/charts' },
    { name: t('ai.reportsTab'), href: '/ai/reports' },
  ]

  return (
    <div className="border-b border-gray-200 mb-6">
      <nav className="-mb-px flex space-x-8">
        {tabs.map((tab) => {
          const isActive = location.pathname === tab.href
          return (
            <Link
              key={tab.href}
              to={tab.href}
              className={`py-2 px-1 border-b-2 text-sm font-medium ${
                isActive
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {tab.name}
            </Link>
          )
        })}
      </nav>
    </div>
  )
}
