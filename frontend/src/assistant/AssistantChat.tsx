import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { Button, Card, StatusBadge, type StatusBadgeStatus } from '../components'
import {
  FEEDBACK_LABELS,
  type AssistantMessage,
  type AssistantSource,
  type AssistantToolState,
  type FeedbackKind,
  type ToolId,
  type ToolRunState,
} from './types'
import { ensureDevSession } from '../auth/ensureDevSession'
import {
  fetchAssistantKnowledgeBases,
  type AssistantKbOption,
} from './api/knowledgeBases'
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

function kbSummary(
  bases: readonly AssistantKbOption[],
  selected: Record<string, boolean>,
  status: 'loading' | 'ready' | 'error',
): string {
  if (status === 'loading') return 'Загрузка баз знаний…'
  if (status === 'error') return 'Базы знаний недоступны'
  if (bases.length === 0) return 'Нет баз знаний'
  const count = bases.filter((kb) => selected[kb.id]).length
  if (count === bases.length) return 'Все базы знаний'
  if (count === 0) return 'Выберите базы знаний'
  if (count === 1) {
    return bases.find((kb) => selected[kb.id])?.label ?? '1 база'
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

function sourceHref(source: AssistantSource): string | null {
  const link = (source.permalink || '').trim()
  if (!link || link === '#') return null
  if (link.includes('hub.local')) {
    // Dev placeholder — keep as document anchor for UI continuity.
    return link
  }
  return link
}

function SourceItem({ source }: { source: AssistantSource }) {
  const [open, setOpen] = useState(false)
  const href = sourceHref(source)
  const hasQuote = Boolean(source.snippet?.trim())

  return (
    <li className="asst-source-item" data-testid={`source-item-${source.id}`}>
      <div className="asst-source-item__row">
        <StatusBadge status="success">
          {source.relevance_percent}%
        </StatusBadge>
        {href ? (
          <a
            className="asst-source-item__link"
            href={href}
            target="_blank"
            rel="noreferrer"
            title="Открыть статью / документ"
          >
            {source.title}
          </a>
        ) : (
          <span className="asst-source-item__title">{source.title}</span>
        )}
        {hasQuote ? (
          <Button
            type="button"
            variant={open ? 'secondary' : 'ghost'}
            onClick={() => setOpen((value) => !value)}
            data-testid={`source-quote-${source.id}`}
          >
            {open ? 'Скрыть цитату' : 'Цитата'}
          </Button>
        ) : null}
      </div>
      {open && hasQuote ? (
        <blockquote className="asst-source-item__quote" data-testid={`source-quote-text-${source.id}`}>
          {source.snippet}
        </blockquote>
      ) : null}
    </li>
  )
}

function MessageLenta({
  messages,
  streaming,
  readOnly = false,
  onFeedback,
  onStop,
}: {
  messages: AssistantMessage[]
  streaming: boolean
  readOnly?: boolean
  onFeedback: (id: string, kind: FeedbackKind) => void
  onStop: () => void
}) {
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end', behavior: 'smooth' })
  }, [messages, streaming])

  if (!messages.length) {
    return (
      <div className="asst-lenta asst-lenta--empty" data-testid="asst-lenta">
        <p>
          {readOnly
            ? 'Просмотр чата · отправка сообщений недоступна. Откройте ≡ → отчётность.'
            : 'Выберите базы знаний и задайте вопрос'}
        </p>
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
                      <SourceItem key={source.id} source={source} />
                    ))}
                  </ul>
                </div>
              ) : null}
              {!readOnly ? (
                <FeedbackBar message={message} onFeedback={onFeedback} />
              ) : null}
            </Card>
          )}
        </div>
      ))}
      {streaming ? (
        <div className="asst-streaming asst-streaming--footer" data-testid="asst-streaming-flag">
          Стриминг токенов…
        </div>
      ) : null}
      <div ref={bottomRef} aria-hidden />
    </div>
  )
}

function ToolsPanel({
  tools,
  open,
  onClose,
  onRun,
}: {
  tools: AssistantToolState[]
  open: boolean
  onClose: () => void
  onRun: (id: ToolId) => void
}) {
  if (!open) return null

  return (
    <div
      id="asst-tools-panel"
      className="asst-tools"
      data-testid="asst-tools-panel"
      role="region"
      aria-label="Инструменты ассистента"
    >
      <div className="asst-tools__header">
        <strong>Инструменты ассистента</strong>
        <Button
          type="button"
          variant="ghost"
          onClick={onClose}
          aria-label="Закрыть инструменты"
          data-testid="asst-tools-close"
        >
          ×
        </Button>
      </div>
      <p className="asst-tools__hint">
        Для SQL и RPA требуется role-based доступ и аудит действий. SQL — только read-only.
      </p>
      <div className="asst-tools__actions">
        {tools.map((tool) => (
          <button
            key={tool.id}
            type="button"
            className="asst-tools__action"
            disabled={tool.state === 'running'}
            data-testid={`tool-run-${tool.id}`}
            onClick={() => onRun(tool.id)}
          >
            <span className="asst-tools__action-label">{tool.label}</span>
            <StatusBadge
              status={toolBadgeStatus(tool.state)}
              data-testid={`tool-state-${tool.id}`}
              title={tool.detail || toolStateLabel(tool.state)}
            >
              {toolStateLabel(tool.state)}
            </StatusBadge>
            {tool.detail ? (
              <small className="asst-tools__action-detail">{tool.detail}</small>
            ) : null}
          </button>
        ))}
      </div>
    </div>
  )
}

export interface AssistantChatProps {
  demoMode?: boolean
  compact?: boolean
  /** TZ III.2 п.10: аналитик — просмотр без отправки сообщений. */
  readOnly?: boolean
  username?: string
  initialDraft?: string
  /** Optional override (Storybook); otherwise loaded from `/api/v1/assistant/kbs/`. */
  knowledgeBases?: readonly AssistantKbOption[]
}

export function AssistantChat({
  demoMode = false,
  compact = false,
  readOnly = false,
  initialDraft = '',
  knowledgeBases: knowledgeBasesProp,
}: AssistantChatProps) {
  const [draft, setDraft] = useState(initialDraft)
  const [kbOpen, setKbOpen] = useState(false)
  const [kbCatalog, setKbCatalog] = useState<AssistantKbOption[]>(
    () => (knowledgeBasesProp ? [...knowledgeBasesProp] : []),
  )
  const [kbStatus, setKbStatus] = useState<'loading' | 'ready' | 'error'>(
    () => (knowledgeBasesProp ? 'ready' : 'loading'),
  )
  const [kbSelected, setKbSelected] = useState<Record<string, boolean>>(() =>
    Object.fromEntries((knowledgeBasesProp ?? []).map((kb) => [kb.id, true])),
  )
  const kbSlugsRef = useRef<string[]>([])
  kbSlugsRef.current = kbCatalog
    .filter((kb) => kbSelected[kb.id])
    .map((kb) => kb.slug)

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
  } = useAssistantChat({
    demoMode,
    getKbSlugs: () => kbSlugsRef.current,
  })
  const maxChars = 500
  const charCount = draft.length
  const charProgress = Math.max(0, Math.min(100, Math.round((charCount / maxChars) * 100)))
  const charMeterTone =
    charCount >= maxChars ? 'danger' : charCount >= maxChars * 0.8 ? 'warn' : 'ok'

  useEffect(() => {
    if (knowledgeBasesProp) {
      setKbCatalog([...knowledgeBasesProp])
      setKbSelected(
        Object.fromEntries(knowledgeBasesProp.map((kb) => [kb.id, true])),
      )
      setKbStatus('ready')
      return
    }

    let cancelled = false
    setKbStatus('loading')
    void (async () => {
      try {
        let ok = await ensureDevSession()
        if (!ok) {
          ok = await ensureDevSession()
        }
        if (!ok) {
          if (cancelled) return
          setKbCatalog([])
          setKbSelected({})
          setKbStatus('error')
          return
        }
        const items = await fetchAssistantKnowledgeBases()
        if (cancelled) return
        setKbCatalog(items)
        setKbSelected(Object.fromEntries(items.map((kb) => [kb.id, true])))
        setKbStatus('ready')
      } catch {
        if (cancelled) return
        setKbCatalog([])
        setKbSelected({})
        setKbStatus('error')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [knowledgeBasesProp])

  const selectedLabel = useMemo(
    () => kbSummary(kbCatalog, kbSelected, kbStatus),
    [kbCatalog, kbSelected, kbStatus],
  )
  const allKbSelected =
    kbCatalog.length > 0 && kbCatalog.every((kb) => kbSelected[kb.id])
  const someKbSelected = kbCatalog.some((kb) => kbSelected[kb.id])

  const toggleAllKb = (checked: boolean) => {
    setKbSelected(Object.fromEntries(kbCatalog.map((kb) => [kb.id, checked])))
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (readOnly || !draft.trim() || streaming) return
    const text = draft
    setDraft('')
    void sendMessage(text)
  }

  return (
    <div
      className={`asst-chat${compact ? ' asst-chat--compact' : ''}${
        readOnly ? ' asst-chat--readonly' : ''
      }`}
      data-testid="assistant-chat"
      data-readonly={readOnly ? 'true' : undefined}
    >
      {readOnly ? (
        <div className="asst-readonly-banner" role="status" data-testid="asst-readonly-banner">
          <StatusBadge status="neutral">Только просмотр</StatusBadge>
          <span>Нет права на отправку (I.4). Отчёты и настройки — через меню ≡</span>
        </div>
      ) : null}
      <div className="asst-toolbar">
        <div className="asst-kb" data-testid="asst-kb">
          <button
            type="button"
            className="asst-kb__trigger"
            aria-expanded={kbOpen}
            disabled={readOnly}
            onClick={() => setKbOpen((value) => !value)}
            data-testid="asst-kb-trigger"
          >
            <span>{selectedLabel}</span>
            <span aria-hidden>{kbOpen ? '▴' : '▾'}</span>
          </button>
          {kbOpen ? (
            <div className="asst-kb__menu" role="listbox" aria-label="Базы знаний">
              {kbCatalog.length > 0 ? (
                <>
                  <label className="asst-kb__option asst-kb__option--all">
                    <input
                      type="checkbox"
                      checked={allKbSelected}
                      ref={(node) => {
                        if (node) node.indeterminate = someKbSelected && !allKbSelected
                      }}
                      onChange={(event) => toggleAllKb(event.target.checked)}
                      data-testid="asst-kb-select-all"
                    />
                    Выбрать все
                  </label>
                  {kbCatalog.map((kb) => (
                    <label key={kb.id} className="asst-kb__option">
                      <input
                        type="checkbox"
                        checked={Boolean(kbSelected[kb.id])}
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
                </>
              ) : (
                <p className="asst-kb__empty" data-testid="asst-kb-empty">
                  {kbStatus === 'loading'
                    ? 'Загрузка…'
                    : kbStatus === 'error'
                      ? 'Не удалось загрузить базы знаний'
                      : 'Базы знаний не созданы. Добавьте их в Центре настроек (assistant_*).'}
                </p>
              )}
            </div>
          ) : null}
        </div>
        <Button
          type="button"
          variant="secondary"
          onClick={newDialog}
          disabled={readOnly}
          data-testid="asst-new"
        >
          + Новый
        </Button>
        <Button type="button" variant="ghost" disabled={readOnly} data-testid="asst-history">
          История диалогов
        </Button>
      </div>

      <MessageLenta
        messages={messages}
        streaming={streaming}
        readOnly={readOnly}
        onFeedback={setFeedback}
        onStop={stopStreaming}
      />

      {!readOnly ? (
        <ToolsPanel
          tools={tools}
          open={toolsOpen}
          onClose={() => setToolsOpen(false)}
          onRun={runTool}
        />
      ) : null}

      {error && !readOnly ? (
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
          <Button type="button" variant="ghost" disabled={readOnly}>
            Прикрепить
          </Button>
          <Button
            type="button"
            variant={toolsOpen ? 'secondary' : 'ghost'}
            aria-expanded={toolsOpen}
            aria-controls="asst-tools-panel"
            disabled={readOnly}
            onClick={() => setToolsOpen((value) => !value)}
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
          placeholder={readOnly ? 'Отправка сообщений недоступна для аналитика' : 'Задайте вопрос…'}
          data-testid="asst-draft"
          disabled={readOnly}
          readOnly={readOnly}
          onChange={(event) => setDraft(event.target.value)}
        />
        <div className="asst-composer__footer">
          <span data-testid="asst-char-count">
            {charCount} / {maxChars} символов
          </span>
          <Button
            type="submit"
            disabled={readOnly || !draft.trim() || streaming}
            data-testid="asst-send"
          >
            {streaming ? 'Стриминг…' : 'Отправить'}
          </Button>
        </div>
        <div
          className={`asst-composer__meter asst-composer__meter--${charMeterTone}`}
          role="meter"
          aria-valuemin={0}
          aria-valuemax={maxChars}
          aria-valuenow={charCount}
          aria-label="Индикатор количества введённых символов"
          data-testid="asst-char-meter"
        >
          <div
            className="asst-composer__meter-fill"
            style={{ width: `${charProgress}%` }}
          />
        </div>
      </form>
    </div>
  )
}
