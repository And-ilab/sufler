import { useMemo, useState, type FormEvent } from 'react'
import { Button, Card, StatusBadge, type StatusBadgeStatus } from '../components'
import {
  FEEDBACK_LABELS,
  KNOWLEDGE_BASES,
  DEFAULT_KB_SELECTION,
  type AssistantMessage,
  type AssistantToolState,
  type FeedbackKind,
  type KbId,
  type ToolId,
  type ToolRunState,
} from './types'
import { useAssistantChat } from './useAssistantChat'
import './AssistantChat.css'

function toolBadgeStatus(state: ToolRunState): StatusBadgeStatus {
  if (state === 'done') return 'success'
  if (state === 'running') return 'info'
  if (state === 'blocked') return 'warning'
  if (state === 'ready') return 'neutral'
  return 'neutral'
}

function toolStateLabel(state: ToolRunState): string {
  if (state === 'done') return 'выполнено'
  if (state === 'running') return 'выполняется'
  if (state === 'blocked') return 'confirm'
  if (state === 'ready') return 'готово к запуску'
  return 'ожидание'
}

function kbSummary(selected: Record<KbId, boolean>): string {
  const count = KNOWLEDGE_BASES.filter((kb) => selected[kb.id]).length
  if (count === KNOWLEDGE_BASES.length) return 'Все базы знаний'
  if (count === 0) return 'Выберите базы знаний'
  if (count === 1) {
    return KNOWLEDGE_BASES.find((kb) => selected[kb.id])?.label ?? '1 база'
  }
  return `${count} базы выбрано`
}

function FeedbackBar({
  message,
  onFeedback,
}: {
  message: AssistantMessage
  onFeedback: (id: string, kind: FeedbackKind) => void
}) {
  if (message.role !== 'assistant' || message.pending) return null
  return (
    <div className="asst-feedback" aria-label="Оценить ответ" data-testid={`feedback-${message.id}`}>
      {(Object.keys(FEEDBACK_LABELS) as FeedbackKind[]).map((kind) => {
        const meta = FEEDBACK_LABELS[kind]
        const active = message.feedback === kind
        return (
          <Button
            key={kind}
            type="button"
            variant={active ? 'primary' : 'ghost'}
            title={meta.title}
            disabled={Boolean(message.feedback)}
            aria-pressed={active}
            data-testid={`feedback-${kind}-${message.id}`}
            onClick={() => onFeedback(message.id, kind)}
          >
            {meta.label}
          </Button>
        )
      })}
      {message.feedback ? (
        <span className="asst-feedback__saved">Оценка сохранена</span>
      ) : null}
    </div>
  )
}

function MessageLenta({
  messages,
  streaming,
  onFeedback,
  onStop,
}: {
  messages: AssistantMessage[]
  streaming: boolean
  onFeedback: (id: string, kind: FeedbackKind) => void
  onStop: () => void
}) {
  if (!messages.length) {
    return (
      <div className="asst-lenta asst-lenta--empty" data-testid="asst-lenta">
        <p>Выберите базы знаний и задайте вопрос</p>
      </div>
    )
  }

  return (
    <div className="asst-lenta" data-testid="asst-lenta" aria-live="polite">
      {messages.map((message) => (
        <div
          key={message.id}
          className={`asst-turn asst-turn--${message.role}`}
          data-testid={`msg-${message.id}`}
        >
          <div className="asst-turn__meta">
            {message.role === 'user' ? 'Вы' : 'Ассистент'}
          </div>
          {message.role === 'user' ? (
            <p className="asst-turn__user">{message.content}</p>
          ) : (
            <Card className="asst-turn__card">
              {message.pending && !message.content ? (
                <div className="asst-streaming" data-testid="asst-streaming">
                  <span>Ассистент печатает…</span>
                  <Button type="button" variant="ghost" onClick={onStop}>
                    Остановить
                  </Button>
                </div>
              ) : (
                <p className="asst-turn__text">
                  {message.content}
                  {message.pending ? <span className="asst-cursor" aria-hidden>|</span> : null}
                </p>
              )}
              {message.sources && message.sources.length > 0 ? (
                <div className="asst-sources" data-testid={`sources-${message.id}`}>
                  <strong>Источники ({message.sources.length})</strong>
                  <ul>
                    {message.sources.map((source) => (
                      <li key={source.id}>
                        <StatusBadge status="success">
                          {source.title} · {source.relevance_percent}%
                        </StatusBadge>
                        {source.permalink ? (
                          <a href={source.permalink} target="_blank" rel="noreferrer">
                            Открыть
                          </a>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <FeedbackBar message={message} onFeedback={onFeedback} />
            </Card>
          )}
        </div>
      ))}
      {streaming ? (
        <div className="asst-streaming asst-streaming--footer" data-testid="asst-streaming-flag">
          Стриминг токенов…
        </div>
      ) : null}
    </div>
  )
}

function ToolsPanel({
  tools,
  open,
  onToggle,
  onRun,
}: {
  tools: AssistantToolState[]
  open: boolean
  onToggle: () => void
  onRun: (id: ToolId) => void
}) {
  return (
    <div className="asst-tools" data-testid="asst-tools">
      <div className="asst-tools__header">
        <Button
          type="button"
          variant="ghost"
          aria-expanded={open}
          onClick={onToggle}
          data-testid="asst-tools-toggle"
        >
          Инструменты
        </Button>
        <div className="asst-tools__states" aria-label="Состояния инструментов">
          {tools.map((tool) => (
            <StatusBadge
              key={tool.id}
              status={toolBadgeStatus(tool.state)}
              data-testid={`tool-state-${tool.id}`}
              title={tool.detail || toolStateLabel(tool.state)}
            >
              {tool.label}: {toolStateLabel(tool.state)}
            </StatusBadge>
          ))}
        </div>
      </div>
      {open ? (
        <div className="asst-tools__body" data-testid="asst-tools-panel">
          <p className="asst-tools__hint">
            Для SQL и RPA требуется role-based доступ и аудит действий. SQL — только read-only.
          </p>
          <div className="asst-tools__actions">
            {tools.map((tool) => (
              <Button
                key={tool.id}
                type="button"
                variant={tool.state === 'running' ? 'secondary' : 'ghost'}
                disabled={tool.state === 'running'}
                data-testid={`tool-run-${tool.id}`}
                onClick={() => onRun(tool.id)}
              >
                {tool.label}
                {tool.detail ? ` · ${tool.detail}` : ''}
              </Button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}

export interface AssistantChatProps {
  demoMode?: boolean
  compact?: boolean
  username?: string
  initialDraft?: string
}

export function AssistantChat({
  demoMode = true,
  compact = false,
  initialDraft = '',
}: AssistantChatProps) {
  const {
    messages,
    tools,
    streaming,
    error,
    toolsOpen,
    setToolsOpen,
    sendMessage,
    stopStreaming,
    setFeedback,
    runTool,
    newDialog,
  } = useAssistantChat({ demoMode })

  const [draft, setDraft] = useState(initialDraft)
  const [kbOpen, setKbOpen] = useState(false)
  const [kbSelected, setKbSelected] = useState(DEFAULT_KB_SELECTION)
  const maxChars = 500
  const charCount = draft.length

  const selectedLabel = useMemo(() => kbSummary(kbSelected), [kbSelected])

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (!draft.trim() || streaming) return
    const text = draft
    setDraft('')
    void sendMessage(text)
  }

  return (
    <div
      className={`asst-chat${compact ? ' asst-chat--compact' : ''}`}
      data-testid="assistant-chat"
    >
      <div className="asst-toolbar">
        <div className="asst-kb" data-testid="asst-kb">
          <button
            type="button"
            className="asst-kb__trigger"
            aria-expanded={kbOpen}
            onClick={() => setKbOpen((value) => !value)}
            data-testid="asst-kb-trigger"
          >
            <span>{selectedLabel}</span>
            <span aria-hidden>{kbOpen ? '▴' : '▾'}</span>
          </button>
          {kbOpen ? (
            <div className="asst-kb__menu" role="listbox" aria-label="Базы знаний">
              {KNOWLEDGE_BASES.map((kb) => (
                <label key={kb.id} className="asst-kb__option">
                  <input
                    type="checkbox"
                    checked={kbSelected[kb.id]}
                    onChange={(event) =>
                      setKbSelected((current) => ({
                        ...current,
                        [kb.id]: event.target.checked,
                      }))
                    }
                  />
                  {kb.label}
                </label>
              ))}
            </div>
          ) : null}
        </div>
        <Button type="button" variant="secondary" onClick={newDialog} data-testid="asst-new">
          + Новый
        </Button>
        <Button type="button" variant="ghost" data-testid="asst-history">
          История диалогов
        </Button>
      </div>

      <MessageLenta
        messages={messages}
        streaming={streaming}
        onFeedback={setFeedback}
        onStop={stopStreaming}
      />

      <ToolsPanel
        tools={tools}
        open={toolsOpen}
        onToggle={() => setToolsOpen((value) => !value)}
        onRun={runTool}
      />

      {error ? (
        <Card className="asst-error" role="alert">
          <StatusBadge status="danger">Ошибка</StatusBadge>
          <p>{error}</p>
          <Button type="button" onClick={() => draft.trim() && void sendMessage(draft)}>
            Повторить
          </Button>
        </Card>
      ) : null}

      <form className="asst-composer" onSubmit={onSubmit} data-testid="asst-composer">
        <div className="asst-composer__extras">
          <Button type="button" variant="ghost">
            Прикрепить
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => setToolsOpen(true)}
            data-testid="asst-composer-tools"
          >
            Инструменты
          </Button>
        </div>
        <label htmlFor="asst-draft">Сообщение ассистенту</label>
        <textarea
          id="asst-draft"
          value={draft}
          maxLength={maxChars}
          placeholder="Задайте вопрос…"
          data-testid="asst-draft"
          onChange={(event) => setDraft(event.target.value)}
        />
        <div className="asst-composer__footer">
          <span>
            {charCount} / {maxChars} символов
          </span>
          <Button
            type="submit"
            disabled={!draft.trim() || streaming}
            data-testid="asst-send"
          >
            {streaming ? 'Стриминг…' : 'Отправить'}
          </Button>
        </div>
      </form>
    </div>
  )
}
