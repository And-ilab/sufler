import { useState } from 'react'
import { StatusBadge } from '../components'
import { AssistantChat } from './AssistantChat'
import './AssistantWindowApp.css'

export interface AssistantWindowAppProps {
  username?: string
  demoMode?: boolean
  readOnly?: boolean
  initiallyOpen?: boolean
}

export function AssistantWindowApp({
  username = 'Пользователь ИИ-ассистента',
  demoMode = false,
  readOnly = false,
  initiallyOpen = true,
}: AssistantWindowAppProps) {
  const [open, setOpen] = useState(initiallyOpen)
  const [maximized, setMaximized] = useState(false)

  if (!open) {
    return (
      <main className="asst-window-page" data-testid="assistant-window-app">
        <button
          type="button"
          className="asst-window-reopen"
          data-testid="asst-window-reopen"
          onClick={() => setOpen(true)}
        >
          Открыть окно ИИ-ассистента
        </button>
      </main>
    )
  }

  return (
    <main className="asst-window-page" data-testid="assistant-window-app">
      <section
        className={`asst-window${maximized ? ' asst-window--maximized' : ''}`}
        data-testid="assistant-window"
        aria-label="ИИ-ассистент"
      >
        <header className="asst-window__titlebar">
          <div>
            <p className="asst-window__brand">Беларусбанк AI</p>
            <h1>ИИ-ассистент</h1>
            <p className="asst-window__user">{username}</p>
          </div>
          <div className="asst-window__controls" aria-label="Управление окном">
            <button type="button" title="Свернуть" onClick={() => setOpen(false)} data-testid="asst-minimize">
              ─
            </button>
            <button
              type="button"
              title={maximized ? 'Восстановить' : 'Развернуть'}
              onClick={() => setMaximized((value) => !value)}
              data-testid="asst-maximize"
            >
              {maximized ? '❐' : '□'}
            </button>
            <button type="button" title="Закрыть" onClick={() => setOpen(false)} data-testid="asst-close">
              ×
            </button>
          </div>
        </header>

        <nav className="asst-window__tabs" aria-label="Модули окна">
          <span className="is-active">Ассистент</span>
          <span aria-disabled="true">Документы</span>
        </nav>

        <div className="asst-window__body">
          <AssistantChat demoMode={demoMode} username={username} readOnly={readOnly} />
        </div>

        <footer className="asst-window__status">
          <StatusBadge status="success">Подключено</StatusBadge>
          <span>БЗ обновлена · assistant_bank · SSE</span>
        </footer>
      </section>
    </main>
  )
}
