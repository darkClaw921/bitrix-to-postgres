import { useState } from 'react'
import { useTranslation } from '../../i18n'
import { useUpdateReportSchedule } from '../../hooks/useReports'
import type { Report } from '../../services/api'

interface ScheduleSelectorProps {
  report: Report
  onClose: () => void
}

const DAYS_OF_WEEK = [
  { value: 'mon', label: 'Пн' },
  { value: 'tue', label: 'Вт' },
  { value: 'wed', label: 'Ср' },
  { value: 'thu', label: 'Чт' },
  { value: 'fri', label: 'Пт' },
  { value: 'sat', label: 'Сб' },
  { value: 'sun', label: 'Вс' },
]

export default function ScheduleSelector({ report, onClose }: ScheduleSelectorProps) {
  const { t } = useTranslation()
  const updateSchedule = useUpdateReportSchedule()

  const existingConfig = (report.schedule_config || {}) as Record<string, unknown>
  const [scheduleType, setScheduleType] = useState(report.schedule_type)
  const [hour, setHour] = useState(Number(existingConfig.hour ?? 9))
  const [minute, setMinute] = useState(Number(existingConfig.minute ?? 0))
  const [dayOfWeek, setDayOfWeek] = useState(String(existingConfig.day_of_week ?? 'mon'))
  const [day, setDay] = useState(Number(existingConfig.day ?? 1))
  const [status, setStatus] = useState(report.status)

  const handleSave = () => {
    const config: Record<string, unknown> = { hour, minute }
    if (scheduleType === 'weekly') config.day_of_week = dayOfWeek
    if (scheduleType === 'monthly') config.day = day

    updateSchedule.mutate(
      {
        reportId: report.id,
        data: {
          schedule_type: scheduleType,
          schedule_config: scheduleType !== 'once' ? config : undefined,
          status,
        },
      },
      { onSuccess: () => onClose() },
    )
  }

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium">{t('reports.schedule')}</h4>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-500 block mb-1">Тип</label>
          <select
            value={scheduleType}
            onChange={(e) => setScheduleType(e.target.value)}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-lg"
          >
            <option value="once">{t('reports.scheduleOnce')}</option>
            <option value="daily">{t('reports.scheduleDaily')}</option>
            <option value="weekly">{t('reports.scheduleWeekly')}</option>
            <option value="monthly">{t('reports.scheduleMonthly')}</option>
          </select>
        </div>

        <div>
          <label className="text-xs text-gray-500 block mb-1">Статус</label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-lg"
          >
            <option value="draft">{t('reports.statusDraft')}</option>
            <option value="active">{t('reports.statusActive')}</option>
            <option value="paused">{t('reports.statusPaused')}</option>
          </select>
        </div>
      </div>

      {scheduleType !== 'once' && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-500 block mb-1">{t('reports.scheduleTime')}</label>
            <div className="flex items-center gap-1">
              <input
                type="number"
                min={0}
                max={23}
                value={hour}
                onChange={(e) => setHour(Number(e.target.value))}
                className="w-16 px-2 py-1.5 text-sm border border-gray-300 rounded-lg text-center"
              />
              <span>:</span>
              <input
                type="number"
                min={0}
                max={59}
                value={minute}
                onChange={(e) => setMinute(Number(e.target.value))}
                className="w-16 px-2 py-1.5 text-sm border border-gray-300 rounded-lg text-center"
              />
            </div>
          </div>

          {scheduleType === 'weekly' && (
            <div>
              <label className="text-xs text-gray-500 block mb-1">{t('reports.scheduleDayOfWeek')}</label>
              <select
                value={dayOfWeek}
                onChange={(e) => setDayOfWeek(e.target.value)}
                className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-lg"
              >
                {DAYS_OF_WEEK.map((d) => (
                  <option key={d.value} value={d.value}>
                    {d.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          {scheduleType === 'monthly' && (
            <div>
              <label className="text-xs text-gray-500 block mb-1">{t('reports.scheduleDay')}</label>
              <input
                type="number"
                min={1}
                max={31}
                value={day}
                onChange={(e) => setDay(Number(e.target.value))}
                className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-lg"
              />
            </div>
          )}
        </div>
      )}

      <div className="flex gap-2 pt-1">
        <button
          onClick={handleSave}
          disabled={updateSchedule.isPending}
          className="btn btn-primary text-sm px-4 py-1.5 disabled:opacity-50"
        >
          {updateSchedule.isPending ? t('common.saving') : t('reports.updateSchedule')}
        </button>
        <button onClick={onClose} className="btn btn-secondary text-sm px-4 py-1.5">
          {t('common.cancel')}
        </button>
      </div>
    </div>
  )
}
