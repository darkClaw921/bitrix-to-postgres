import { useState } from 'react'
import { copyToClipboard } from '../../utils/clipboard'
import { useTranslation } from '../../i18n'

interface IframeCopyButtonProps {
  chartId: number
}

export default function IframeCopyButton({ chartId }: IframeCopyButtonProps) {
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState(false)
  const { t } = useTranslation()

  const handleCopy = async () => {
    const html = `<iframe src="${window.location.origin}/embed/chart/${chartId}" width="100%" height="400" frameborder="0" style="border: none;"></iframe>`
    const ok = await copyToClipboard(html)
    if (ok) {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } else {
      setError(true)
      setTimeout(() => setError(false), 2000)
    }
  }

  return (
    <button
      onClick={handleCopy}
      className={`p-1.5 rounded text-sm ${
        error
          ? 'bg-red-50 text-red-600'
          : 'bg-blue-50 text-blue-600 hover:bg-blue-100'
      }`}
      title={t('charts.embedCode')}
    >
      {error ? t('charts.embedCopyError') : copied ? t('common.copied') : t('charts.embed')}
    </button>
  )
}
