import { useState } from 'react'
import { useTranslation } from '../../i18n'

interface ExportButtonsProps {
  data: Record<string, unknown>[]
  title: string
}

function sanitizeFilename(name: string): string {
  return name.replace(/[^a-zA-Z0-9а-яА-ЯёЁ_-]/g, '_').substring(0, 100)
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export default function ExportButtons({ data, title }: ExportButtonsProps) {
  const { t } = useTranslation()
  const [loadingExcel, setLoadingExcel] = useState(false)

  if (!data.length) return null

  const handleCSV = () => {
    const columns = Object.keys(data[0])
    const BOM = '\uFEFF'
    const header = columns.join(',')
    const rows = data.map((row) =>
      columns.map((col) => {
        const val = row[col]
        if (val == null) return ''
        const str = String(val)
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
          return `"${str.replace(/"/g, '""')}"`
        }
        return str
      }).join(','),
    )
    const csv = BOM + [header, ...rows].join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
    downloadBlob(blob, `${sanitizeFilename(title)}.csv`)
  }

  const handleExcel = async () => {
    setLoadingExcel(true)
    try {
      const XLSX = await import('xlsx')
      const ws = XLSX.utils.json_to_sheet(data)
      const wb = XLSX.utils.book_new()
      XLSX.utils.book_append_sheet(wb, ws, 'Data')
      const wbout = XLSX.write(wb, { bookType: 'xlsx', type: 'array' })
      const blob = new Blob([wbout], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
      downloadBlob(blob, `${sanitizeFilename(title)}.xlsx`)
    } catch {
      // xlsx failed to load
    } finally {
      setLoadingExcel(false)
    }
  }

  return (
    <div className="flex space-x-1">
      <button
        onClick={handleCSV}
        className="p-1.5 rounded text-sm bg-green-50 text-green-600 hover:bg-green-100"
        title={t('charts.downloadCSV')}
      >
        {t('charts.downloadCSV')}
      </button>
      <button
        onClick={handleExcel}
        disabled={loadingExcel}
        className="p-1.5 rounded text-sm bg-green-50 text-green-600 hover:bg-green-100 disabled:opacity-50"
        title={t('charts.downloadExcel')}
      >
        {loadingExcel ? '...' : t('charts.downloadExcel')}
      </button>
    </div>
  )
}
