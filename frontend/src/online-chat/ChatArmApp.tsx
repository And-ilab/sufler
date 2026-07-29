import { useEffect, useMemo, useState } from 'react'
import { Button, Card, StatusBadge } from '../components'
import { OperatorStatusSelector } from './OperatorStatusSelector'
import { QueuePanel } from './QueuePanel'
import { SuflerSidePanel } from './SuflerSidePanel'
import { useChatSufler } from './hooks/useChatSufler'
import {
  operatorStatusById,
  type OperatorPresence,
} from './operatorStatuses'
import {
  DEFAULT_QUEUE_SECTIONS,
  DEFAULT_SESSIONS,
  findQueueItem,
  queueItemCount,
  type ChatSession,
  type QueueItem,
  type QueueSection,
} from './sessions'
import './ChatArmApp.css'

export interface ChatArmAppProps {
  operatorName?: string
  demoMode?: boolean
  initialPresence?: OperatorPresence
  queueSections?: QueueSection[]
  sessions?: Record<string, ChatSession>
}

export function ChatArmApp({
  operatorName = 'Иванов И.И.',
  demoMode = true,
  initialPresence = 'online',
  queueSections = DEFAULT_QUEUE_SECTIONS,
  sessions: initialSessions = DEFAULT_SESSIONS,
}: ChatArmAppProps) {
  const [sections] = useState(queueSections)
  const [sessions, setSessions] = useState(initialSessions)
  const [selectedQueueId, setSelectedQueueId] = useState(
    () => findQueueItem(queueSections, '1')?.id
      ?? queueSections[0]?.items[0]?.id
      ?? '',
  )
  const [presence, setPresence] = useState<OperatorPresence>(initialPresence)
  const [draft, setDraft] = useState('')

  const selectedItem = findQueueItem(sections, selectedQueueId)
  const sessionId = selectedItem?.sessionId
  const activeSession = sessionId ? sessions[sessionId] : undefined

  const {
    messages,
    hints,
    loading,
    error,
    latencyMs,
    pushClientMessage,
    pushOperatorMessage,
    loadMessages,
  } = useChatSufler({
    demoMode,
    initialMessages: activeSession?.messages ?? [],
    autoSuggest: true,
  })

  useEffect(() => {
    if (!sessionId) return
    loadMessages(sessions[sessionId]?.messages ?? [])
    setDraft('')
    // Load transcript when operator switches queue item only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, loadMessages])

  useEffect(() => {
    if (!sessionId) return
    setSessions((current) => {
      const existing = current[sessionId]
      if (!existing) return current
      return {
        ...current,
        [sessionId]: {
          ...existing,
          messages,
        },
      }
    })
  }, [messages, sessionId])

  const latestClient = useMemo(
    () => [...messages].reverse().find((item) => item.speaker === 'client'),
    [messages],
  )

  const presenceDef = operatorStatusById(presence)
  const acceptsNew = presenceDef?.acceptsNewDialogs ?? false
  const totalInQueues = queueItemCount(sections)
  const readOnly = Boolean(selectedItem?.readOnly) || presence === 'offline'

  const selectQueueItem = (item: QueueItem) => {
    setSelectedQueueId(item.id)
  }

  const insertHint = (text: string) => {
    if (readOnly) return
    setDraft((current) => (current.trim() ? `${current.trim()}\n${text}` : text))
  }

  const sendDraft = () => {
    const text = draft.trim()
    if (!text || readOnly) return
    pushOperatorMessage(text)
    setDraft('')
  }

  return (
    <main className="chat-arm" data-testid="chat-arm-app">
      <header className="chat-arm__topbar">
        <div className="chat-arm__brand">
          <strong>Беларусбанк · Онлайн-чат</strong>
          <StatusBadge status={acceptsNew ? 'success' : 'warning'}>
            {presenceDef?.label ?? presence}
          </StatusBadge>
          <span className="app-muted" data-testid="queue-total">
            в очередях: {totalInQueues}
          </span>
        </div>
        <div className="chat-arm__operator">
          <span>{operatorName} · Оператор КЦ</span>
        </div>
      </header>

      <div className="chat-arm__status-row">
        <OperatorStatusSelector value={presence} onChange={setPresence} />
        {!acceptsNew ? (
          <p className="chat-arm__status-hint app-muted" data-testid="status-routing-hint">
            Новые диалоги из очереди «Ожидают ответа» не назначаются.
          </p>
        ) : null}
      </div>

      <div className="chat-arm__body">
        <QueuePanel
          sections={sections}
          selectedId={selectedQueueId}
          onSelect={selectQueueItem}
        />

        <section className="chat-arm__dialogue" aria-label="Активный диалог">
          <header className="chat-arm__dialogue-header">
            <div>
              <h1>{activeSession?.clientName ?? 'Диалог'}</h1>
              <p className="app-muted">
                {activeSession?.channel ?? '—'} · {activeSession?.dialogNo ?? '—'}
              </p>
            </div>
            <StatusBadge status={readOnly ? 'neutral' : 'success'}>
              {readOnly ? 'Только просмотр' : 'Активный'}
            </StatusBadge>
          </header>

          <div className="chat-arm__messages" data-testid="chat-messages">
            {messages.map((message) => (
              <article
                key={message.id}
                className={`chat-arm__bubble chat-arm__bubble--${message.speaker}`}
                data-testid={`msg-${message.turnId}-${message.speaker}`}
              >
                <Card>
                  <header>
                    <strong>
                      {message.speaker === 'client' ? 'Клиент' : 'Оператор'}
                    </strong>
                  </header>
                  <p>{message.text}</p>
                </Card>
              </article>
            ))}
            {!messages.length ? (
              <Card className="chat-arm__empty">Выберите диалог в очереди.</Card>
            ) : null}
          </div>

          <div className="chat-arm__composer">
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={readOnly ? 'Статус не позволяет отвечать' : 'Ответ клиенту…'}
              rows={3}
              disabled={readOnly}
              data-testid="chat-composer"
              onKeyDown={(event) => {
                if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
                  event.preventDefault()
                  sendDraft()
                }
              }}
            />
            <div className="chat-arm__composer-actions">
              {demoMode && !readOnly ? (
                <Button
                  variant="secondary"
                  onClick={() =>
                    pushClientMessage(
                      'А можно снять больше через отделение?',
                      `demo-${Date.now()}`,
                    )
                  }
                  data-testid="demo-client-message"
                >
                  Демо-сообщение клиента
                </Button>
              ) : null}
              <Button onClick={sendDraft} disabled={readOnly} data-testid="send-reply">
                Отправить
              </Button>
            </div>
          </div>
        </section>

        <SuflerSidePanel
          hints={hints}
          loading={loading}
          error={error}
          latencyMs={latencyMs}
          clientPreview={latestClient?.text}
          onInsert={insertHint}
          disabled={readOnly}
        />
      </div>
    </main>
  )
}
