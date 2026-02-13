# Frontend Architecture

## Технологический стек
- **React 18** + **TypeScript** + **Vite**
- **Recharts** — библиотека для графиков
- **react-grid-layout v2** — drag & drop сетка для дашбордов
- **TanStack Query (React Query)** — управление серверным состоянием
- **Tailwind CSS** — утилитарные стили
- **xlsx (SheetJS)** — экспорт Excel (динамический import для code-splitting)

## Структура проекта (`src/`)

### `main.tsx` / `App.tsx`
- Точка входа, React Router, провайдеры (Auth, I18n, QueryClient)

### `components/`

#### `components/charts/`
| Файл | Описание |
|---|---|
| `ChartRenderer.tsx` | Основной рендерер графиков (bar, line, area, pie, scatter, funnel, horizontal_bar, indicator, table). Поддерживает tooltip, animation, data labels, custom margins через `general` конфиг |
| `ChartCard.tsx` | Карточка графика на странице ChartsPage — тулбар (pin, refresh, embed, export, settings, SQL, delete), ChartSettingsPanel, ChartRenderer |
| `ChartSettingsPanel.tsx` | Панель настроек графика — visual, data format, тип-специфичные (line/area/pie/indicator/table/funnel), card style, general settings |
| `ExportButtons.tsx` | Кнопки экспорта CSV/Excel. CSV — клиентская генерация с BOM для кириллицы. Excel — динамический import xlsx |
| `IframeCopyButton.tsx` | Кнопка "Встроить" — копирование iframe HTML с fallback через execCommand |
| `PromptEditorModal.tsx` | Модальное окно редактирования AI prompt шаблона |
| `GenerationHistoryModal.tsx` | Модальное окно истории генерации — список запросов с мини-превью графиков, клик вставляет промпт в поле ввода. Хранение в localStorage (до 20 записей) |
| `cardStyleUtils.ts` | Утилиты маппинга cardStyle (borderRadius, shadow, padding) в Tailwind-классы и inline styles |
| `DesignModeOverlay.tsx` | Оверлей поверх графика для дизайн-режима — определяет позиции элементов из DOM, рендерит DraggableHandle и MarginHandle |

#### `components/charts/design/`
| Файл | Описание |
|---|---|
| `DraggableHandle.tsx` | Перетаскиваемый элемент (legend, title, axis labels, data labels) с визуальной подсветкой |
| `MarginHandle.tsx` | Перетаскиваемые границы для изменения margins (top/right/bottom/left) |
| `DesignModeToolbar.tsx` | Панель дизайн-режима — выбранный элемент, точные значения, кнопки "Сбросить"/"Применить" |

#### `components/dashboards/`
| Файл | Описание |
|---|---|
| `DashboardCard.tsx` | Карточка дашборда в списке |
| `PasswordGate.tsx` | Защита паролем для публичных дашбордов |
| `PublishModal.tsx` | Модальное окно публикации дашборда |

#### `components/selectors/`
| Файл | Описание |
|---|---|
| `SelectorBar.tsx` | Контейнер селекторов/фильтров |
| `DateRangeSelector.tsx` | Селектор диапазона дат |
| `SingleDateSelector.tsx` | Селектор одной даты |
| `DropdownSelector.tsx` | Выпадающий список |
| `MultiSelectSelector.tsx` | Множественный выбор |
| `TextSelector.tsx` | Текстовый ввод |

#### Прочие компоненты
| Файл | Описание |
|---|---|
| `Layout.tsx` | Основная обёртка (навигация, боковая панель) |
| `SyncCard.tsx` | Карточка статуса синхронизации сущности |
| `ReferenceCard.tsx` | Карточка справочных данных |
| `FilterDialog.tsx` | Диалог фильтрации |
| `LanguageSwitcher.tsx` | Переключатель языка (ru/en) |

### `pages/`
| Файл | Описание |
|---|---|
| `DashboardPage.tsx` | Главная — статистика, карточки сущностей, справочники |
| `ChartsPage.tsx` | AI генератор графиков с редактируемым SQL (подсветка синтаксиса через prismjs), история генерации, сохранённые графики, список дашбордов |
| `DashboardEditorPage.tsx` | Редактор дашборда — react-grid-layout, EditorChartCard с ChartSettingsPanel, селекторы, связанные дашборды, переключатель формата сетки (1/2/3/4 колонки) с автопересчётом layout |
| `EmbedDashboardPage.tsx` | Публичная embed-страница дашборда — пароль, табы, фильтры, авто-обновление, адаптивность (isMobile) |
| `EmbedChartPage.tsx` | Публичная embed-страница одного графика |
| `ConfigPage.tsx` | Настройки синхронизации, вебхуки |
| `MonitoringPage.tsx` | История синхронизации, статус планировщика |
| `SchemaPage.tsx` | AI описание схемы БД, список таблиц |
| `ValidationPage.tsx` | Проверка конвертации типов полей |
| `LoginPage.tsx` | Страница входа |

### `hooks/`
| Файл | Описание |
|---|---|
| `useCharts.ts` | Хуки для CRUD графиков (generate, save, list, data, delete, pin, updateConfig, promptTemplate) |
| `useDashboards.ts` | Хуки для дашбордов (list, detail, create, update, layout, overrides, links, password) |
| `useSelectors.ts` | Хуки для селекторов (create, delete, mapping, columns, generate) |
| `useSync.ts` | Хуки для синхронизации (status, trigger, history) |
| `useAuth.ts` | Хук авторизации |
| `useDesignMode.ts` | Хук дизайн-режима — управление состоянием (active, selectedElement), drag-логика (mousedown/move/up), draftLayout, apply/reset |

### `services/`
| Файл | Описание |
|---|---|
| `api.ts` | Axios-клиент, все API endpoints (charts, dashboards, public, sync), TypeScript интерфейсы (ChartDisplayConfig, ChartSpec, SavedChart, Dashboard и др.) |
| `supabase.ts` | Supabase клиент |

### `i18n/`
| Файл | Описание |
|---|---|
| `index.ts` | I18nProvider, useTranslation хук, lazy-загрузка локалей |
| `types.ts` | Интерфейс Translations — все ключи локализации |
| `locales/en.ts` | Английская локализация |
| `locales/ru.ts` | Русская локализация |

### `store/`
| Файл | Описание |
|---|---|
| `authStore.ts` | Хранилище авторизации |
| `syncStore.ts` | Хранилище синхронизации |

## Ключевые типы (`services/api.ts`)

### `ChartDisplayConfig`
Конфигурация отображения графика:
- `x`, `y` — ключи данных
- `colors`, `legend`, `grid`, `xAxis`, `yAxis` — базовые настройки
- `line`, `area`, `pie`, `indicator`, `table`, `funnel`, `horizontal_bar` — тип-специфичные
- `cardStyle` — стиль карточки (backgroundColor, borderRadius, shadow, padding)
- `general` — общие (titleFontSize, showTooltip, animate, showDataLabels, margins)
- `designLayout` — интерактивное позиционирование элементов (legend, title, xAxisLabel, yAxisLabel, dataLabels, margins)

### `DesignLayout`
Позиционирование элементов графика, задаваемое через дизайн-режим:
- `legend` — позиция в % (x, y) + layout (horizontal/vertical)
- `title` — смещение в px (dx, dy)
- `xAxisLabel`, `yAxisLabel` — смещение лейблов осей в px (dx, dy)
- `dataLabels` — смещение меток данных в px (dx, dy)
- `margins` — отступы графика в px (top, right, bottom, left)

### `ChartSpec`
Спецификация графика для ChartRenderer — включает все поля ChartDisplayConfig плюс title, chart_type, sql_query, data_keys.

## Архитектурные паттерны

- **Конфигурация через JSON**: все настройки графиков хранятся в `chart_config` (JSONB на бэкенде), изменяются через PATCH API
- **Адаптивность**: EmbedDashboardPage использует `useIsMobile()` хук (matchMedia), на мобильных — `1fr` grid вместо 12-колоночного
- **Code-splitting**: xlsx загружается через динамический `import('xlsx')`
- **Fallback копирования**: IframeCopyButton использует navigator.clipboard с fallback на execCommand
- **Drag & resize**: react-grid-layout v2 с stopPropagation для интерактивных элементов внутри карточек
- **Дизайн-режим**: интерактивное позиционирование элементов графика (кнопка "Дизайн" в EditorChartCard). Нативный mouse drag через useDesignMode хук. Overlay с pointer-events изоляцией от grid layout. Легенда — абсолютная позиция в %, остальные элементы — px смещения. Изменения видны мгновенно (draftLayout), сохраняются на сервер по кнопке "Применить". Доступен только для SVG-графиков (bar, line, area, pie, scatter, funnel, horizontal_bar)
