import type { CSSProperties, ReactNode } from 'react'
import type { ArmTheme } from '../theme'
import { Button, Row, Text } from '../primitives'
import type { ModuleSchemePalette } from './types'

export function ArmModuleFrame({
  t,
  scheme,
  title,
  subtitle,
  onBack,
  actions,
  children,
  bodyStyle,
}: {
  t: ArmTheme
  scheme: ModuleSchemePalette
  title: string
  subtitle?: string
  onBack: () => void
  actions?: ReactNode
  children: ReactNode
  bodyStyle?: CSSProperties
}) {
  return (
    <div
      style={{
        flex: 1,
        minWidth: 0,
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
        background: t.bg.elevated,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '12px 16px',
          borderBottom: `1px solid ${scheme.accentWeak}`,
          background: scheme.headerBg,
          flexShrink: 0,
        }}
      >
        <Button variant="secondary" size="sm" onClick={onBack} title="Вернуться к диалогам">
          ← Диалоги
        </Button>
        <div style={{ minWidth: 0, flex: 1 }}>
          <Text weight="semibold" style={{ fontSize: 16, letterSpacing: '-0.01em' }}>
            {title}
          </Text>
          {subtitle ? (
            <Text style={{ fontSize: 12, color: t.text.secondary, marginTop: 2 }}>{subtitle}</Text>
          ) : null}
        </div>
        {actions ? <Row style={{ gap: 8, flexShrink: 0 }}>{actions}</Row> : null}
      </div>
      <div style={{ flex: 1, minHeight: 0, overflow: 'auto', ...bodyStyle }}>{children}</div>
    </div>
  )
}

export function ModuleEmpty({
  t,
  title,
  hint,
}: {
  t: ArmTheme
  title: string
  hint?: string
}) {
  return (
    <div
      style={{
        flex: 1,
        display: 'grid',
        placeItems: 'center',
        padding: 32,
        color: t.text.secondary,
        textAlign: 'center',
      }}
    >
      <div>
        <div style={{ fontSize: 15, fontWeight: 600, color: t.text.primary, marginBottom: 6 }}>{title}</div>
        {hint ? <div style={{ fontSize: 13, lineHeight: 1.45, maxWidth: 360 }}>{hint}</div> : null}
      </div>
    </div>
  )
}

export function presenceColor(presence: string): string {
  if (presence === 'online') return '#2E7D32'
  if (presence === 'busy') return '#E65100'
  if (presence === 'away' || presence === 'break' || presence === 'lunch') return '#F9A825'
  return '#90A4AE'
}

export function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

export function formatDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}
