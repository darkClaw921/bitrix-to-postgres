import ChartRenderer from './ChartRenderer'
import type { ChartSpec } from '../../services/api'

interface AvailableChartTypesModalProps {
  isOpen: boolean
  onClose: () => void
}

interface ChartTypeInfo {
  type: ChartSpec['chart_type']
  title: string
  description: string
  example: string
  spec: ChartSpec
  data: Record<string, unknown>[]
}

// Общие демо-данные «продажи по стадиям» — переиспользуются для большинства типов
const STAGE_DATA: Record<string, unknown>[] = [
  { stage: 'Новые', deals: 120 },
  { stage: 'Квалификация', deals: 95 },
  { stage: 'Предложение', deals: 64 },
  { stage: 'Переговоры', deals: 38 },
  { stage: 'Выиграно', deals: 22 },
]

const TIME_DATA: Record<string, unknown>[] = [
  { month: 'Янв', revenue: 420 },
  { month: 'Фев', revenue: 510 },
  { month: 'Мар', revenue: 480 },
  { month: 'Апр', revenue: 640 },
  { month: 'Май', revenue: 720 },
  { month: 'Июн', revenue: 880 },
]

const SOURCE_DATA: Record<string, unknown>[] = [
  { source: 'Сайт', deals: 45 },
  { source: 'Звонок', deals: 30 },
  { source: 'Email', deals: 18 },
  { source: 'Реклама', deals: 12 },
]

const SCATTER_DATA: Record<string, unknown>[] = [
  { duration: 5, amount: 120 },
  { duration: 9, amount: 280 },
  { duration: 14, amount: 340 },
  { duration: 21, amount: 510 },
  { duration: 30, amount: 720 },
  { duration: 45, amount: 1100 },
]

const TABLE_DATA: Record<string, unknown>[] = [
  { manager: 'Иванов', deals: 24, amount: 1240000 },
  { manager: 'Петров', deals: 18, amount: 980000 },
  { manager: 'Сидоров', deals: 15, amount: 760000 },
  { manager: 'Кузнецов', deals: 11, amount: 540000 },
]

const CHART_TYPES: ChartTypeInfo[] = [
  {
    type: 'bar',
    title: 'Столбчатая (bar)',
    description: 'Сравнение значений по категориям. Подходит для сравнения количества/сумм между группами.',
    example: 'Покажи количество сделок по стадиям в виде столбчатой диаграммы',
    spec: {
      title: 'Сделки по стадиям',
      chart_type: 'bar',
      sql_query: '',
      data_keys: { x: 'stage', y: 'deals' },
    },
    data: STAGE_DATA,
  },
  {
    type: 'horizontal_bar',
    title: 'Горизонтальная столбчатая (horizontal_bar)',
    description: 'То же, что bar, но горизонтально. Удобно для длинных названий категорий.',
    example: 'Топ менеджеров по сумме сделок горизонтальными столбцами',
    spec: {
      title: 'Сделки по стадиям',
      chart_type: 'horizontal_bar',
      sql_query: '',
      data_keys: { x: 'stage', y: 'deals' },
    },
    data: STAGE_DATA,
  },
  {
    type: 'line',
    title: 'Линейный график (line)',
    description: 'Динамика значений во времени. Подходит для трендов и временных рядов.',
    example: 'Динамика количества новых сделок по месяцам за последний год',
    spec: {
      title: 'Выручка по месяцам',
      chart_type: 'line',
      sql_query: '',
      data_keys: { x: 'month', y: 'revenue' },
    },
    data: TIME_DATA,
  },
  {
    type: 'area',
    title: 'Площадная (area)',
    description: 'Линейный график с заливкой. Подчёркивает объём, удобно для накопительных метрик.',
    example: 'Накопительная сумма выручки по неделям',
    spec: {
      title: 'Выручка по месяцам',
      chart_type: 'area',
      sql_query: '',
      data_keys: { x: 'month', y: 'revenue' },
    },
    data: TIME_DATA,
  },
  {
    type: 'pie',
    title: 'Круговая (pie)',
    description: 'Доли частей в целом. Используется при небольшом количестве категорий (до 7).',
    example: 'Распределение сделок по источникам в виде круговой диаграммы',
    spec: {
      title: 'Сделки по источникам',
      chart_type: 'pie',
      sql_query: '',
      data_keys: { x: 'source', y: 'deals' },
    },
    data: SOURCE_DATA,
  },
  {
    type: 'scatter',
    title: 'Точечная (scatter)',
    description: 'Корреляция между двумя числовыми величинами. Каждая точка — отдельная запись.',
    example: 'Зависимость суммы сделки от срока её закрытия',
    spec: {
      title: 'Сумма vs срок',
      chart_type: 'scatter',
      sql_query: '',
      data_keys: { x: 'duration', y: 'amount' },
    },
    data: SCATTER_DATA,
  },
  {
    type: 'funnel',
    title: 'Воронка (funnel)',
    description: 'Прохождение объектов по этапам. Классическая воронка продаж.',
    example: 'Воронка сделок по стадиям',
    spec: {
      title: 'Воронка продаж',
      chart_type: 'funnel',
      sql_query: '',
      data_keys: { x: 'stage', y: 'deals' },
    },
    data: STAGE_DATA,
  },
  {
    type: 'indicator',
    title: 'KPI-индикатор (indicator)',
    description: 'Одно ключевое число с подписью. Подходит для главных метрик.',
    example: 'Общая сумма выигранных сделок за этот месяц',
    spec: {
      title: 'Выручка за месяц',
      chart_type: 'indicator',
      sql_query: '',
      data_keys: { x: '', y: 'revenue' },
    },
    data: [{ revenue: 1284500 }],
  },
  {
    type: 'table',
    title: 'Таблица (table)',
    description: 'Табличное представление данных по строкам и столбцам.',
    example: 'Таблица сделок с менеджером, суммой и стадией',
    spec: {
      title: 'Топ менеджеров',
      chart_type: 'table',
      sql_query: '',
      data_keys: { x: 'manager', y: ['deals', 'amount'] },
    },
    data: TABLE_DATA,
  },
]

export default function AvailableChartTypesModal({ isOpen, onClose }: AvailableChartTypesModalProps) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-6xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <div>
            <h2 className="text-xl font-semibold text-gray-800">
              Доступные типы графиков
            </h2>
            <p className="text-sm text-gray-500 mt-1">
              Превью на демо-данных — AI может сгенерировать любой из этих типов
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {CHART_TYPES.map((ct) => (
              <div
                key={ct.type}
                className="border border-gray-200 rounded-lg p-3 hover:border-primary-300 hover:shadow-sm transition"
              >
                <div className="mb-2">
                  <h3 className="font-semibold text-sm text-gray-800">{ct.title}</h3>
                  <p className="text-xs text-gray-500 mt-0.5">{ct.description}</p>
                </div>

                {/* Real chart preview */}
                <div className="bg-gray-50 border border-gray-100 rounded p-2 overflow-hidden">
                  <ChartRenderer spec={ct.spec} data={ct.data} height={180} />
                </div>

                <div className="mt-2 p-2 bg-blue-50 border border-blue-100 rounded text-xs text-blue-800 italic">
                  «{ct.example}»
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
          <button onClick={onClose} className="btn btn-secondary px-4 py-2">
            Закрыть
          </button>
        </div>
      </div>
    </div>
  )
}
