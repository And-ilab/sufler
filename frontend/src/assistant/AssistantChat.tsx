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
import {
  extractChatAttachment,
  type ChatAttachmentPayload,
} from './api/attachments'
import {
  fetchLocalLlmModels,
  selectLocalLlmModel,
  type LocalLlmModel,
} from './api/localModels'
import {
  formatDialogDate,
  type ChatDialogSummary,
} from './chatPersistence'
import { useAssistantChat } from './useAssistantChat'
import './AssistantChat.css'

const ATTACH_ACCEPT = '.pdf,.doc,.docx,.txt,.rtf,.jpg,.jpeg,.png,.tiff,.tif'
const ATTACH_MAX_FILES = 5

const OCR_CONFIDENCE_TONE = (pct: number | null): 'success' | 'warning' | 'danger' | 'neutral' => {
  if (pct == null) return 'neutral'
  if (pct >= 85) return 'success'
  if (pct >= 60) return 'warning'
  return 'danger'
}

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
  if (message.feedback) {
    return (
      <div
        className="asst-feedback asst-feedback--saved"
        aria-label="Оценка ответа"
        data-testid={`feedback-${message.id}`}
      >
        <span className="asst-feedback__saved" data-testid={`feedback-saved-${message.id}`}>
          Оценка сохранена
        </span>
      </div>
    )
  }
  return (
    <div className="asst-feedback" aria-label="Оценить ответ" data-testid={`feedback-${message.id}`}>
      {(Object.keys(FEEDBACK_LABELS) as FeedbackKind[]).map((kind) => {
        const meta = FEEDBACK_LABELS[kind]
        return (
          <Button
            key={kind}
            type="button"
            variant="ghost"
            title={meta.title}
            data-testid={`feedback-${kind}-${message.id}`}
            onClick={() => onFeedback(message.id, kind)}
          >
            {meta.label}
          </Button>
        )
      })}
    </div>
  )
}

function sourceHref(source: AssistantSource): string | null {
  const articleId =
    source.article_id != null && String(source.article_id).trim()
      ? String(source.article_id)
      : (/:(\d+):/.exec(source.id)?.[1] || '')
  if (source.kb_slug && articleId) {
    return (
      `/api/v1/assistant/sources/download`
      + `?kb_slug=${encodeURIComponent(source.kb_slug)}`
      + `&article_id=${encodeURIComponent(articleId)}`
    )
  }
  const link = (source.permalink || '').trim()
  if (!link || link === '#') return null
  return link
}

function SourceItem({ source }: { source: AssistantSource }) {
  const [open, setOpen] = useState(false)
  const [fileError, setFileError] = useState('')
  const href = sourceHref(source)
  const hasQuote = Boolean(source.snippet?.trim())
  const isDownloadApi = Boolean(href?.includes('/api/v1/assistant/sources/download'))

  const openSourceFile = async () => {
    if (!href) return
    setFileError('')
    if (!isDownloadApi) {
      window.open(href, '_blank', 'noopener,noreferrer')
      return
    }
    try {
      const response = await fetch(href, { credentials: 'include' })
      if (!response.ok) {
        let detail = `HTTP ${response.status}`
        try {
          const payload = (await response.json()) as {
            details?: { file?: string[]; request?: string[] }
            error?: string
          }
          detail =
            payload.details?.file?.[0]
            || payload.details?.request?.[0]
            || payload.error
            || detail
        } catch {
          /* ignore */
        }
        throw new Error(detail)
      }
      const blob = await response.blob()
      const header = response.headers.get('Content-Disposition') || ''
      const matched = /filename="?([^"]+)"?/i.exec(header)
      const filename =
        matched?.[1]
        || source.title
        || 'document'
      const objectUrl = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = objectUrl
      anchor.download = filename
      anchor.rel = 'noopener'
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      // Also try open in new tab (PDF/txt); browsers may still download office files.
      window.setTimeout(() => {
        window.open(objectUrl, '_blank', 'noopener,noreferrer')
        window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
      }, 50)
    } catch (err) {
      setFileError(err instanceof Error ? err.message : 'Не удалось открыть файл')
    }
  }

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
            title="Открыть файл источника"
            data-testid={`source-link-${source.id}`}
            onClick={(event) => {
              event.preventDefault()
              void openSourceFile()
            }}
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
      {fileError ? (
        <p className="asst-source-item__error" role="alert">{fileError}</p>
      ) : null}
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
            <div className="asst-turn__user-block">
              {message.attachments?.length ? (
                <ul className="asst-turn__files" aria-label="Вложения">
                  {message.attachments.map((file) => (
                    <li key={file.name}>{file.name}</li>
                  ))}
                </ul>
              ) : null}
              <p className="asst-turn__user">{message.content}</p>
            </div>
          ) : (
            <Card className="asst-turn__card">
              {message.pending && !message.content && !message.ocr ? (
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
              {message.ocr ? (
                <div className="asst-ocr" data-testid={`ocr-card-${message.id}`}>
                  <header className="asst-ocr__head">
                    <strong>OCR · {message.ocr.documentType}</strong>
                    <StatusBadge
                      status={
                        message.ocr.validationStatus === 'valid' ? 'success' : 'warning'
                      }
                    >
                      {message.ocr.validationStatus || 'pending_review'}
                    </StatusBadge>
                  </header>
                  <ul className="asst-ocr__fields">
                    {message.ocr.fields.map((field) => (
                      <li key={field.id} data-testid={`ocr-field-${field.id}`}>
                        <span>{field.label}</span>
                        <strong>{field.value || '—'}</strong>
                        <StatusBadge status={OCR_CONFIDENCE_TONE(field.confidence)}>
                          {field.confidence == null ? '—' : `${field.confidence}%`}
                        </StatusBadge>
                      </li>
                    ))}
                  </ul>
                  <small className="asst-ocr__meta">
                    job {message.ocr.jobId}
                  </small>
                </div>
              ) : null}
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

const TOOL_DESCRIPTIONS: Record<ToolId, string> = {
  code: 'Черновик фрагмента кода по запросу из чата.',
  sql: 'Read-only запросы к разрешённым витринам. Изменения запрещены.',
  rpa: 'Запуск роботов только после явного подтверждения оператора.',
  document: 'Сформировать или разобрать документ (в т.ч. OCR-поля).',
  translate: 'Перевод фрагмента ответа или вложения RU ↔ EN.',
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
  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose, open])

  if (!open) return null

  return (
    <div
      className="asst-tools is-open"
      data-testid="asst-tools-shell"
      role="presentation"
    >
      <button
        type="button"
        className="asst-tools__backdrop"
        aria-label="Закрыть инструменты"
        onClick={onClose}
      />
      <aside
        id="asst-tools-panel"
        className="asst-tools__drawer"
        data-testid="asst-tools-panel"
        role="dialog"
        aria-modal="true"
        aria-label="Инструменты ассистента"
      >
        <header className="asst-tools__header">
          <div>
            <strong>Инструменты ассистента</strong>
            <span>SQL и RPA — только с RBAC и аудитом. SQL — read-only.</span>
          </div>
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            aria-label="Закрыть инструменты"
            data-testid="asst-tools-close"
          >
            ×
          </Button>
        </header>

        <div className="asst-tools__body">
          <ul className="asst-tools__actions" data-testid="asst-tools-list">
            {tools.map((tool) => (
              <li key={tool.id}>
                <button
                  type="button"
                  className="asst-tools__action"
                  disabled={tool.state === 'running'}
                  data-testid={`tool-run-${tool.id}`}
                  onClick={() => onRun(tool.id)}
                >
                  <span className="asst-tools__action-main">
                    <span className="asst-tools__action-label">{tool.label}</span>
                    <small className="asst-tools__action-desc">
                      {TOOL_DESCRIPTIONS[tool.id]}
                    </small>
                    {tool.detail ? (
                      <small className="asst-tools__action-detail">{tool.detail}</small>
                    ) : null}
                  </span>
                  <StatusBadge
                    status={toolBadgeStatus(tool.state)}
                    data-testid={`tool-state-${tool.id}`}
                    title={tool.detail || toolStateLabel(tool.state)}
                  >
                    {/* visual.spec: tool-state-sql must contain «SQL» */}
                    {tool.id === 'sql'
                      ? `SQL · ${toolStateLabel(tool.state)}`
                      : toolStateLabel(tool.state)}
                  </StatusBadge>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  )
}

function HistoryDrawer({
  open,
  dialogs,
  activeId,
  onClose,
  onOpen,
  onNew,
  onDelete,
}: {
  open: boolean
  dialogs: readonly ChatDialogSummary[]
  activeId: string
  onClose: () => void
  onOpen: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
}) {
  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose, open])

  return (
    <div
      className={`asst-history${open ? ' is-open' : ''}`}
      data-testid="asst-history-shell"
      aria-hidden={!open}
    >
      <button
        type="button"
        className="asst-history__backdrop"
        aria-label="Закрыть историю диалогов"
        tabIndex={open ? 0 : -1}
        onClick={onClose}
      />
      <aside
        id="asst-history-drawer"
        className="asst-history__drawer"
        role="dialog"
        aria-modal="true"
        aria-label="История диалогов"
        data-testid="asst-history-drawer"
      >
        <header className="asst-history__header">
          <div>
            <strong>История диалогов</strong>
            <span>Название — по первым словам вопроса</span>
          </div>
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            aria-label="Закрыть историю"
            data-testid="asst-history-close"
          >
            ×
          </Button>
        </header>
        <div className="asst-history__toolbar">
          <Button
            type="button"
            variant="secondary"
            onClick={onNew}
            data-testid="asst-history-new"
          >
            + Новый диалог
          </Button>
        </div>
        <ul className="asst-history__list" data-testid="asst-history-list">
          {dialogs.length === 0 ? (
            <li className="asst-history__empty">Пока нет сохранённых диалогов</li>
          ) : (
            dialogs.map((dialog) => {
              const active = dialog.id === activeId
              return (
                <li key={dialog.id}>
                  <button
                    type="button"
                    className={`asst-history__item${active ? ' is-active' : ''}`}
                    onClick={() => onOpen(dialog.id)}
                    data-testid={`asst-history-item-${dialog.id}`}
                  >
                    <strong>{dialog.title}</strong>
                    <span>{formatDialogDate(dialog.updatedAt)}</span>
                    <small>{dialog.preview}</small>
                  </button>
                  <button
                    type="button"
                    className="asst-history__delete"
                    aria-label={`Удалить диалог «${dialog.title}»`}
                    title="Удалить"
                    data-testid={`asst-history-delete-${dialog.id}`}
                    onClick={(event) => {
                      event.stopPropagation()
                      onDelete(dialog.id)
                    }}
                  >
                    ×
                  </button>
                </li>
              )
            })
          )}
        </ul>
      </aside>
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
  const [historyOpen, setHistoryOpen] = useState(false)
  const [attachments, setAttachments] = useState<ChatAttachmentPayload[]>([])
  const [attachBusy, setAttachBusy] = useState(false)
  const [attachError, setAttachError] = useState('')
  const kbRootRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [kbCatalog, setKbCatalog] = useState<AssistantKbOption[]>(
    () => (knowledgeBasesProp ? [...knowledgeBasesProp] : []),
  )
  const [kbStatus, setKbStatus] = useState<'loading' | 'ready' | 'error'>(
    () => (knowledgeBasesProp ? 'ready' : 'loading'),
  )
  const [kbSelected, setKbSelected] = useState<Record<string, boolean>>(() =>
    Object.fromEntries((knowledgeBasesProp ?? []).map((kb) => [kb.id, true])),
  )
  const [modelCatalog, setModelCatalog] = useState<LocalLlmModel[]>([])
  const [activeModelId, setActiveModelId] = useState('')
  const [modelStatus, setModelStatus] = useState<
    'loading' | 'ready' | 'switching' | 'error'
  >('loading')
  const [modelError, setModelError] = useState('')
  const kbSlugsRef = useRef<string[]>([])
  kbSlugsRef.current = kbCatalog
    .filter((kb) => kbSelected[kb.id])
    .map((kb) => kb.slug)

  const {
    messages,
    dialogs,
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
    openDialog,
    deleteDialog,
    sessionId,
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
    let cancelled = false
    setModelStatus('loading')
    void (async () => {
      try {
        await ensureDevSession()
        const status = await fetchLocalLlmModels()
        if (cancelled) return
        setModelCatalog(status.models)
        setActiveModelId(status.active_model_id ?? status.models[0]?.id ?? '')
        setModelError(
          status.manager_reachable === false
            ? status.last_error || 'Ollama недоступна'
            : status.last_error || '',
        )
        setModelStatus(
          status.manager_reachable === false || !status.models.length
            ? 'error'
            : 'ready',
        )
      } catch (loadError) {
        if (cancelled) return
        setModelCatalog([])
        setActiveModelId('')
        setModelError(
          loadError instanceof Error
            ? loadError.message
            : 'Не удалось загрузить список моделей Ollama',
        )
        setModelStatus('error')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const onModelChange = async (modelId: string) => {
    if (!modelId || modelId === activeModelId || modelStatus === 'switching') {
      return
    }
    const previous = activeModelId
    setActiveModelId(modelId)
    setModelStatus('switching')
    setModelError('')
    try {
      await ensureDevSession()
      const status = await selectLocalLlmModel(modelId)
      setModelCatalog(status.models)
      setActiveModelId(status.active_model_id ?? modelId)
      setModelError('')
      setModelStatus('ready')
    } catch (switchError) {
      setActiveModelId(previous)
      setModelError(
        switchError instanceof Error
          ? switchError.message
          : 'Не удалось переключить модель',
      )
      setModelStatus('error')
    }
  }

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

  useEffect(() => {
    if (!kbOpen) return
    const onPointerDown = (event: PointerEvent) => {
      const root = kbRootRef.current
      if (root && !root.contains(event.target as Node)) {
        setKbOpen(false)
      }
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [kbOpen])

  const onPickFiles = async (fileList: FileList | null) => {
    if (!fileList?.length || readOnly) return
    const remaining = Math.max(0, ATTACH_MAX_FILES - attachments.length)
    if (!remaining) {
      setAttachError(`Можно прикрепить не больше ${ATTACH_MAX_FILES} файлов`)
      return
    }
    const files = Array.from(fileList).slice(0, remaining)
    setAttachBusy(true)
    setAttachError('')
    try {
      await ensureDevSession()
      const extracted: ChatAttachmentPayload[] = []
      for (const file of files) {
        extracted.push(await extractChatAttachment(file))
      }
      setAttachments((current) => [...current, ...extracted].slice(0, ATTACH_MAX_FILES))
    } catch (error) {
      setAttachError(
        error instanceof Error ? error.message : 'Не удалось прочитать файл',
      )
    } finally {
      setAttachBusy(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (readOnly || streaming || attachBusy) return
    if (!draft.trim() && !attachments.length) return
    const text = draft
    const files = attachments
    setDraft('')
    setAttachments([])
    setAttachError('')
    void sendMessage(text, files)
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
        <label className="asst-model" data-testid="asst-model">
          <span className="asst-model__label">Модель</span>
          <select
            className="asst-model__select"
            value={activeModelId}
            disabled={
              readOnly ||
              modelStatus === 'loading' ||
              modelStatus === 'switching' ||
              modelCatalog.length === 0
            }
            onChange={(event) => void onModelChange(event.target.value)}
            data-testid="asst-model-select"
            title={modelError || 'Модели из Ollama (ollama list)'}
          >
            {modelStatus === 'loading' ? (
              <option value="">Загрузка…</option>
            ) : modelCatalog.length === 0 ? (
              <option value="">Нет моделей в Ollama</option>
            ) : (
              <>
                {/* Keep controlled <select> valid if active id is briefly missing */}
                {activeModelId &&
                !modelCatalog.some((model) => model.id === activeModelId) ? (
                  <option value={activeModelId}>{activeModelId}</option>
                ) : null}
                {modelCatalog.map((model) => (
                  <option
                    key={model.id}
                    value={model.id}
                    disabled={model.available === false}
                  >
                    {model.label}
                    {model.description ? ` · ${model.description}` : ''}
                  </option>
                ))}
              </>
            )}
          </select>
          {modelStatus === 'switching' ? (
            <span className="asst-model__hint" data-testid="asst-model-switching">
              Переключение…
            </span>
          ) : null}
        </label>
        {modelError ? (
          <span className="asst-model__error" data-testid="asst-model-error" title={modelError}>
            {modelError}
          </span>
        ) : null}
        <div className="asst-kb" data-testid="asst-kb" ref={kbRootRef}>
          <button
            type="button"
            className="asst-kb__trigger"
            aria-expanded={kbOpen}
            disabled={readOnly}
            onClick={() => {
              setKbOpen((value) => !value)
              setToolsOpen(false)
            }}
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
          onClick={() => {
            newDialog()
            setHistoryOpen(false)
            setAttachments([])
            setAttachError('')
          }}
          disabled={readOnly}
          data-testid="asst-new"
        >
          + Новый
        </Button>
        <Button
          type="button"
          variant={historyOpen ? 'secondary' : 'ghost'}
          disabled={readOnly}
          aria-expanded={historyOpen}
          aria-controls="asst-history-drawer"
          onClick={() => {
            setHistoryOpen((value) => !value)
            setKbOpen(false)
            setToolsOpen(false)
          }}
          data-testid="asst-history"
        >
          История диалогов
        </Button>
      </div>

      <HistoryDrawer
        open={historyOpen}
        dialogs={dialogs}
        activeId={sessionId}
        onClose={() => setHistoryOpen(false)}
        onOpen={(id) => {
          openDialog(id)
          setHistoryOpen(false)
        }}
        onNew={() => {
          newDialog()
          setHistoryOpen(false)
          setAttachments([])
          setAttachError('')
        }}
        onDelete={deleteDialog}
      />

      {!readOnly ? (
        <ToolsPanel
          tools={tools}
          open={toolsOpen}
          onClose={() => setToolsOpen(false)}
          onRun={runTool}
        />
      ) : null}

      <MessageLenta
        messages={messages}
        streaming={streaming}
        readOnly={readOnly}
        onFeedback={setFeedback}
        onStop={stopStreaming}
      />

      {error && !readOnly ? (
        <Card className="asst-error" role="alert">
          <StatusBadge status="danger">Ошибка</StatusBadge>
          <p>{error}</p>
          <Button
            type="button"
            onClick={() =>
              (draft.trim() || attachments.length)
              && void sendMessage(draft, attachments)
            }
          >
            Повторить
          </Button>
        </Card>
      ) : null}

      <form className="asst-composer" onSubmit={onSubmit} data-testid="asst-composer">
        <div className="asst-composer__extras">
          <Button
            type="button"
            variant={toolsOpen ? 'secondary' : 'ghost'}
            aria-expanded={toolsOpen}
            aria-controls="asst-tools-panel"
            disabled={readOnly}
            onClick={() => {
              setToolsOpen((value) => !value)
              setKbOpen(false)
              setHistoryOpen(false)
            }}
            data-testid="asst-composer-tools"
          >
            Инструменты
          </Button>
        </div>
        {attachments.length > 0 ? (
          <ul className="asst-composer__attachments" data-testid="asst-attach-list">
            {attachments.map((file) => (
              <li key={`${file.name}-${file.size_bytes ?? 0}`}>
                <span>{file.name}</span>
                <button
                  type="button"
                  aria-label={`Убрать ${file.name}`}
                  onClick={() =>
                    setAttachments((current) =>
                      current.filter((item) => item.name !== file.name),
                    )
                  }
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        {attachError ? (
          <p className="asst-composer__attach-error" role="alert" data-testid="asst-attach-error">
            {attachError}
          </p>
        ) : null}
        <label className="visually-hidden" htmlFor="asst-draft">
          Сообщение ассистенту
        </label>
        <input
          ref={fileInputRef}
          type="file"
          className="asst-composer__file"
          accept={ATTACH_ACCEPT}
          multiple
          hidden
          disabled={readOnly || attachBusy || streaming}
          onChange={(event) => void onPickFiles(event.target.files)}
          data-testid="asst-attach-input"
        />
        <div className="asst-composer__field">
          <textarea
            id="asst-draft"
            value={draft}
            maxLength={maxChars}
            placeholder={
              readOnly
                ? 'Отправка сообщений недоступна для аналитика'
                : attachments.length
                  ? 'Добавьте вопрос к файлу или отправьте для саммари…'
                  : 'Задайте вопрос…'
            }
            data-testid="asst-draft"
            disabled={readOnly}
            readOnly={readOnly}
            onChange={(event) => setDraft(event.target.value)}
          />
          <button
            type="button"
            className="asst-composer__attach"
            disabled={readOnly || attachBusy || streaming || attachments.length >= ATTACH_MAX_FILES}
            onClick={() => fileInputRef.current?.click()}
            data-testid="asst-attach"
            title={
              attachBusy
                ? 'Читаю файл…'
                : 'Прикрепить файл · PDF, DOC, DOCX, TXT, RTF, JPG, PNG · до 10 МБ'
            }
            aria-label={attachBusy ? 'Читаю файл' : 'Прикрепить файл'}
          >
            {attachBusy ? (
              <span className="asst-composer__attach-busy" aria-hidden>
                …
              </span>
            ) : (
              <svg
                className="asst-composer__attach-icon"
                width="22"
                height="22"
                viewBox="0 0 24 24"
                fill="none"
                aria-hidden
              >
                <path
                  d="M21.44 11.05l-8.49 8.49a5.25 5.25 0 01-7.42-7.42l8.49-8.49a3.5 3.5 0 014.95 4.95l-8.49 8.49a1.75 1.75 0 01-2.47-2.47l7.78-7.78"
                  stroke="currentColor"
                  strokeWidth="1.85"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            )}
          </button>
        </div>
        <div className="asst-composer__footer">
          <span data-testid="asst-char-count">
            {charCount} / {maxChars} символов
          </span>
          <Button
            type="submit"
            disabled={
              readOnly
              || streaming
              || attachBusy
              || (!draft.trim() && !attachments.length)
            }
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
