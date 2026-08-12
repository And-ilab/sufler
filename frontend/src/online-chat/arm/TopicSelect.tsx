import { useEffect, useId, useRef, useState, type CSSProperties, type JSX } from 'react'
import { TopicChip } from './summaryTopics'
import type { ArmTheme } from './theme'

/** Dropdown list (like a select) whose options are topic chips. */
export function TopicSelect({
  t,
  value,
  options,
  onChange,
  disabled = false,
  style,
}: {
  t: ArmTheme
  value: string
  options: string[]
  onChange: (next: string) => void
  disabled?: boolean
  style?: CSSProperties
}): JSX.Element {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement | null>(null)
  const listId = useId()

  useEffect(() => {
    if (!open) return
    const onDoc = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const selected = options.includes(value) ? value : options[0] ?? value

  return (
    <div ref={rootRef} style={{ position: 'relative', minWidth: 220, ...style }}>
      <button
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => {
          if (!disabled) setOpen((prev) => !prev)
        }}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
          padding: '5px 8px',
          borderRadius: 8,
          border: `1px solid ${t.stroke.secondary}`,
          background: t.bg.elevated,
          cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.55 : 1,
          fontFamily: 'inherit',
        }}
      >
        <TopicChip t={t} topic={selected} size="sm" />
        <span
          aria-hidden
          style={{
            color: t.text.tertiary,
            fontSize: 11,
            transform: open ? 'rotate(180deg)' : 'none',
            transition: 'transform 120ms ease',
          }}
        >
          ▼
        </span>
      </button>
      {open ? (
        <div
          id={listId}
          role="listbox"
          aria-label="Тематика закрытия"
          style={{
            position: 'absolute',
            top: 'calc(100% + 4px)',
            left: 0,
            right: 0,
            zIndex: 40,
            maxHeight: 280,
            overflowY: 'auto',
            padding: 6,
            borderRadius: 10,
            border: `1px solid ${t.stroke.secondary}`,
            background: t.bg.elevated,
            boxShadow: t.kind === 'light'
              ? '0 12px 28px rgba(20, 40, 30, 0.14)'
              : '0 12px 28px rgba(0, 0, 0, 0.35)',
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
          }}
        >
          {options.map((topic) => {
            const active = topic === selected
            return (
              <button
                key={topic}
                type="button"
                role="option"
                aria-selected={active}
                onClick={() => {
                  onChange(topic)
                  setOpen(false)
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  width: '100%',
                  textAlign: 'left',
                  padding: '6px 8px',
                  borderRadius: 8,
                  border: active ? `1px solid ${t.stroke.secondary}` : '1px solid transparent',
                  background: active ? t.fill.tertiary : 'transparent',
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                }}
              >
                <TopicChip t={t} topic={topic} size="sm" selected={active} />
              </button>
            )
          })}
        </div>
      ) : null}
    </div>
  )
}
