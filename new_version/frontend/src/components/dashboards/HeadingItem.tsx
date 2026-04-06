import { useState, useEffect, useRef } from 'react'
import type { HeadingConfig } from '../../services/api'
import { useTranslation } from '../../i18n'

interface HeadingItemProps {
  heading: HeadingConfig
  editable?: boolean
  onChange?: (heading: HeadingConfig) => void
}

export default function HeadingItem({ heading, editable = false, onChange }: HeadingItemProps) {
  const { t } = useTranslation()
  const [editing, setEditing] = useState(false)
  const [showStyle, setShowStyle] = useState(false)
  const [textValue, setTextValue] = useState(heading.text)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setTextValue(heading.text)
  }, [heading.text])

  useEffect(() => {
    if (editing && inputRef.current) inputRef.current.focus()
  }, [editing])

  const commitText = () => {
    if (!onChange) {
      setEditing(false)
      return
    }
    if (textValue.trim() && textValue !== heading.text) {
      onChange({ ...heading, text: textValue.trim() })
    }
    setEditing(false)
  }

  const updateStyle = (patch: Partial<HeadingConfig>) => {
    if (!onChange) return
    onChange({ ...heading, ...patch })
  }

  const Tag = `h${heading.level}` as 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6'

  const sizeClasses: Record<number, string> = {
    1: 'text-3xl',
    2: 'text-2xl',
    3: 'text-xl',
    4: 'text-lg',
    5: 'text-base',
    6: 'text-sm',
  }

  const alignClass =
    heading.align === 'center' ? 'text-center' : heading.align === 'right' ? 'text-right' : 'text-left'

  const wrapperStyle: React.CSSProperties = {
    backgroundColor: heading.bg_color || undefined,
    width: '100%',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    padding: heading.bg_color ? '0.5rem 0.75rem' : undefined,
    borderRadius: heading.bg_color ? '0.375rem' : undefined,
  }

  const titleStyle: React.CSSProperties = { color: heading.color || undefined, margin: 0 }

  return (
    <div style={wrapperStyle} className={editable ? 'group relative' : ''}>
      {editing && editable ? (
        <input
          ref={inputRef}
          type="text"
          value={textValue}
          onChange={(e) => setTextValue(e.target.value)}
          onBlur={commitText}
          onKeyDown={(e) => {
            if (e.key === 'Enter') commitText()
            if (e.key === 'Escape') {
              setTextValue(heading.text)
              setEditing(false)
            }
          }}
          onMouseDown={(e) => e.stopPropagation()}
          className={`w-full bg-transparent border-b border-blue-400 outline-none font-semibold ${sizeClasses[heading.level]} ${alignClass}`}
          style={titleStyle}
        />
      ) : (
        <Tag
          className={`font-semibold ${sizeClasses[heading.level]} ${alignClass} ${editable ? 'cursor-text' : ''}`}
          style={titleStyle}
          onClick={() => editable && setEditing(true)}
          title={editable ? t('editor.clickToEditTitle') : undefined}
        >
          {heading.text || (editable ? t('editor.headingPlaceholder') : '')}
        </Tag>
      )}
      {heading.divider && <div className="mt-2 border-b border-gray-300" />}
      {editable && !editing && (
        <button
          onClick={(e) => {
            e.stopPropagation()
            setShowStyle(!showStyle)
          }}
          onMouseDown={(e) => e.stopPropagation()}
          className="absolute top-1 right-1 px-1.5 py-0.5 text-xs rounded bg-gray-100 text-gray-600 opacity-0 group-hover:opacity-100 hover:bg-gray-200"
          title={t('editor.headingStyle')}
        >
          ⚙
        </button>
      )}
      {showStyle && editable && (
        <div
          className="absolute top-8 right-1 z-50 bg-white border border-gray-200 rounded-lg shadow-lg p-3 w-56 space-y-2"
          onMouseDown={(e) => e.stopPropagation()}
          onClick={(e) => e.stopPropagation()}
        >
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t('editor.headingLevel')}</label>
            <select
              value={heading.level}
              onChange={(e) => updateStyle({ level: Number(e.target.value) as HeadingConfig['level'] })}
              className="w-full px-2 py-1 border border-gray-300 rounded text-xs"
            >
              {[1, 2, 3, 4, 5, 6].map((l) => (
                <option key={l} value={l}>
                  H{l}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t('editor.headingAlign')}</label>
            <div className="flex space-x-1">
              {(['left', 'center', 'right'] as const).map((a) => (
                <button
                  key={a}
                  onClick={() => updateStyle({ align: a })}
                  className={`flex-1 px-2 py-1 text-xs rounded border ${
                    heading.align === a
                      ? 'bg-blue-500 text-white border-blue-500'
                      : 'bg-white text-gray-600 border-gray-300'
                  }`}
                >
                  {a === 'left' ? '⟸' : a === 'center' ? '↔' : '⟹'}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t('editor.headingColor')}</label>
            <input
              type="color"
              value={heading.color || '#1f2937'}
              onChange={(e) => updateStyle({ color: e.target.value })}
              className="w-full h-7 cursor-pointer rounded"
            />
            {heading.color && (
              <button
                onClick={() => updateStyle({ color: null })}
                className="mt-1 text-xs text-gray-400 hover:text-gray-600"
              >
                {t('common.reset')}
              </button>
            )}
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t('editor.headingBg')}</label>
            <input
              type="color"
              value={heading.bg_color || '#ffffff'}
              onChange={(e) => updateStyle({ bg_color: e.target.value })}
              className="w-full h-7 cursor-pointer rounded"
            />
            {heading.bg_color && (
              <button
                onClick={() => updateStyle({ bg_color: null })}
                className="mt-1 text-xs text-gray-400 hover:text-gray-600"
              >
                {t('common.reset')}
              </button>
            )}
          </div>
          <label className="flex items-center space-x-2 text-xs text-gray-600 cursor-pointer">
            <input
              type="checkbox"
              checked={heading.divider}
              onChange={(e) => updateStyle({ divider: e.target.checked })}
            />
            <span>{t('editor.headingDivider')}</span>
          </label>
          <div className="flex justify-end pt-1 border-t border-gray-100">
            <button
              onClick={() => setShowStyle(false)}
              className="text-xs text-gray-500 hover:text-gray-700"
            >
              {t('common.close')}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
