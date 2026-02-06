import { useState } from 'react'

interface IframeCopyButtonProps {
  chartId: number
}

export default function IframeCopyButton({ chartId }: IframeCopyButtonProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    const html = `<iframe src="${window.location.origin}/embed/chart/${chartId}" width="100%" height="400" frameborder="0" style="border: none;"></iframe>`

    navigator.clipboard.writeText(html).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <button
      onClick={handleCopy}
      className="p-1.5 rounded text-sm bg-blue-50 text-blue-600 hover:bg-blue-100"
      title="Copy embed code"
    >
      {copied ? 'Copied!' : 'Embed'}
    </button>
  )
}
