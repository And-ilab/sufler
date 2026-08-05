import { useMemo, useState, type CSSProperties } from 'react'
import {
  ArmOperatorView,
  CLOSE_TOPICS,
  getSchemePalette,
  type OperatorPresence,
} from './arm/ArmOperatorView'
import { ARM_THEME_DARK, ARM_THEME_LIGHT, type ThemeKind } from './arm/theme'
import './ChatArmApp.css'

export interface ChatArmAppProps {
  operatorName?: string
  demoMode?: boolean
  initialPresence?: OperatorPresence
}

/** Emerald ARM: light mockup by default, optional dark toggle. */
export function ChatArmApp({
  initialPresence = 'online',
}: ChatArmAppProps) {
  const [themeKind, setThemeKind] = useState<ThemeKind>('light')
  const t = themeKind === 'light' ? ARM_THEME_LIGHT : ARM_THEME_DARK
  const scheme = useMemo(() => getSchemePalette(t, 'belarusbank_emerald'), [t])

  const [selectedQueue, setSelectedQueue] = useState('1')
  const [reply, setReply] = useState('')
  const [toast, setToast] = useState<string | null>(null)
  const [presence, setPresence] = useState<OperatorPresence>(initialPresence)
  const [viewMode, setViewMode] = useState<'active' | 'colleague'>('active')
  const [closeTopic, setCloseTopic] = useState<string>(CLOSE_TOPICS[0])

  const cssVars = {
    '--arm-accent': scheme.accent,
    '--arm-accent-weak': scheme.accentWeak,
    '--arm-accent-control': scheme.accentControl,
    '--arm-header-bg': scheme.headerBg,
    '--arm-panel-bg': scheme.panelBg,
    '--arm-badge': scheme.badge,
    '--arm-on-accent': t.text.onAccent,
    '--arm-fill-secondary': t.fill.secondary,
    '--arm-fill-tertiary': t.fill.tertiary,
    '--arm-fill-quaternary': t.fill.quaternary,
    '--arm-stroke-secondary': t.stroke.secondary,
    '--arm-stroke-tertiary': t.stroke.tertiary,
    '--arm-t-primary': t.text.primary,
    '--arm-t-secondary': t.text.secondary,
    '--arm-t-tertiary': t.text.tertiary,
    '--arm-bg-elevated': t.bg.elevated,
    '--arm-bg-editor': t.bg.editor,
  } as CSSProperties

  return (
    <main
      className="chat-arm-page"
      data-testid="chat-arm-app"
      data-scheme="belarusbank_emerald"
      data-theme={themeKind}
      style={{
        ...cssVars,
        background: scheme.panelBg,
        color: t.text.primary,
      }}
    >
      <div
        className="chat-arm-page__frame"
        style={{
          border: `1px solid ${scheme.accentWeak}`,
          background: scheme.panelBg,
        }}
      >
        <ArmOperatorView
          t={t}
          scheme={scheme}
          selectedQueue={selectedQueue}
          onSelectQueue={setSelectedQueue}
          reply={reply}
          onReplyChange={setReply}
          onInsertSufler={(answerText) => {
            setReply(answerText)
            setToast('Подсказка суфлёра вставлена в черновик ответа.')
          }}
          toast={toast}
          onClearToast={() => setToast(null)}
          presence={presence}
          onPresenceChange={setPresence}
          viewMode={viewMode}
          onViewModeChange={setViewMode}
          closeTopic={closeTopic}
          onCloseTopicChange={setCloseTopic}
          onToggleTheme={() =>
            setThemeKind((kind) => (kind === 'light' ? 'dark' : 'light'))
          }
        />
      </div>
    </main>
  )
}
