import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { Button, Card, StatusBadge, type StatusBadgeStatus } from '../components'
import {
  FEEDBACK_LABELS,
  type AssistantGeneratedDraft,
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
  downloadTranscript,
  extractChatAttachment,
  fieldConfidencePercent,
  fieldDisplayValue,
  isMediaFileName,
  type ChatAttachmentPayload,
} from './api/attachments'
import {
  displayModelLabel,
  fetchLocalLlmModels,
  selectLocalLlmModel,
  type LocalLlmModel,
} from './api/localModels'
import {
  formatDialogDate,
  type ChatDialogSummary,
} from './chatPersistence'
import { finishLastSentence } from './finishLastSentence'
import {
  downloadGeneratedDocument,
  fetchChatDocTemplates,
  generateDocDraft,
  type ChatDocTemplate,
  type DocTemplateFormat,
} from './api/docTemplates'
import {
  approveOcrJob,
  downloadOcrFieldsDocx,
  exportOcrJob,
  ocrExportRows,
} from '../ai-hub/admin/api/ocrAdmin'
import { OcrDocumentsPanel } from '../ai-hub/ocr/OcrDocumentsPanel'
import { filterOcrFields } from '../ai-hub/ocr/fieldQuality'
import { useAssistantChat } from './useAssistantChat'
import './AssistantChat.css'

const ATTACH_ACCEPT = '.pdf,.doc,.docx,.txt,.rtf,.xlsx,.jpg,.jpeg,.png,.tiff,.tif,.wav,.mp3,.m4a,.ogg,.flac,.webm,.mp4,.mov,.mkv,.avi'
const OCR_ACCEPT = '.pdf,.jpg,.jpeg,.png,.tiff,.tif'
const ATTACH_MAX_FILES = 5

function compactChatText(text: string) {
  let out = text.replace(/\r\n/g, '\n')
  out = out.replace(/\*\*([^*]+)\*\*/g, '$1')
  out = out.replace(/\*([^*\n]+)\*/g, '$1')
  out = out.replace(/\*\*/g, '')
  const lines = out.split('\n').filter((line) => {
    const trimmed = line.trim()
    if (!trimmed) return true
    if (/^источники\s*[:(\[]/i.test(trimmed)) return false
    if (/^источники\s*\(\d+\)/i.test(trimmed)) return false
    if (/^[-–—•]\s*\[\d+\]/.test(trimmed)) return false
    if (/^\[\d+\]\s+\S/.test(trimmed) && /(бз:|источник|\.txt|\.doc|\.pdf)/i.test(trimmed)) {
      return false
    }
    if (/по предоставленн\w*\s+фрагмент/i.test(trimmed)) return false
    if (/в базе знаний найдено/i.test(trimmed)) return false
    if (/^фрагменты базы знаний/i.test(trimmed)) return false
    return true
  })
  return lines
    .join('\n')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{2,}/g, '\n')
    .trim()
}

const OCR_FIELD_LABELS: Record<string, string> = {
  full_name: 'ФИО',
  surname: 'Фамилия',
  given_name: 'Имя',
  patronymic: 'Отчество',
  document_number: 'Номер документа',
  series: 'Серия',
  number: 'Номер',
  birth_date: 'Дата рождения',
  expiry_date: 'Срок действия',
  issue_date: 'Дата выдачи',
  personal_number: 'Личный номер',
  nationality: 'Гражданство',
  sex: 'Пол',
  date: 'Дата',
  payer: 'Плательщик',
  beneficiary: 'Получатель',
  amount: 'Сумма',
  purpose: 'Назначение',
  currency: 'Валюта',
  address: 'Адрес',
  issued_by: 'Кем выдан',
  birth_place: 'Место рождения',
  personal_number: 'Личный номер',
  nationality: 'Гражданство',
}
const OCR_FIELD_ORDER = Object.keys(OCR_FIELD_LABELS)

const OCR_CONFIDENCE_TONE = (pct: number | null): 'success' | 'warning' | 'danger' | 'neutral' => {
  if (pct == null) return 'neutral'
  if (pct >= 85) return 'success'
  if (pct >= 60) return 'warning'
  return 'danger'
}

interface OcrPanelField {
  id: string
  label: string
  value: string
  confidence: number | null
}

interface OcrPanelState {
  open: boolean
  busy: boolean
  error: string
  fileName: string
  previewUrl: string | null
  documentType: string
  validationStatus: string | null
  jobId: string
  fields: OcrPanelField[]
  rawText: string
  approved: boolean
  exportBusy: boolean
}

const EMPTY_OCR_PANEL: OcrPanelState = {
  open: false,
  busy: false,
  error: '',
  fileName: '',
  previewUrl: null,
  documentType: '',
  validationStatus: null,
  jobId: '',
  fields: [],
  rawText: '',
  approved: false,
  exportBusy: false,
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
        let detail = 'Не удалось открыть файл источника'
        try {
          const payload = (await response.json()) as {
            details?: { file?: string[]; request?: string[] }
            error?: string
          }
          const raw =
            payload.details?.file?.[0]
            || payload.details?.request?.[0]
            || payload.error
            || ''
          if (raw && raw !== 'not_found') {
            detail = raw
          }
        } catch {
          /* ignore */
        }
        throw new Error(detail)
      }
      const blob = await response.blob()
      const header = response.headers.get('Content-Disposition') || ''
      const starred = /filename\*=(?:UTF-8'')?([^;]+)/i.exec(header)
      const quoted = /filename="?([^"]+)"?/i.exec(header)
      const rawName =
        (starred?.[1] && decodeURIComponent(starred[1].replace(/['"]/g, '')))
        || quoted?.[1]
        || decodeURIComponent(response.headers.get('X-Source-Filename') || '')
        || source.title
        || 'document'
      const filename = rawName.includes('.') ? rawName : `${rawName}.txt`
      const objectUrl = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = objectUrl
      anchor.download = filename
      anchor.rel = 'noopener'
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 4_000)
    } catch (err) {
      setFileError(err instanceof Error ? err.message : 'Не удалось открыть файл')
    }
  }

  const toggle = () => {
    if (hasQuote) setOpen((value) => !value)
  }

  return (
    <li
      className={`asst-source-item${open ? ' is-open' : ''}${hasQuote ? ' asst-source-item--expandable' : ''}`}
      data-testid={`source-item-${source.id}`}
    >
      <div
        className="asst-source-item__row"
        role={hasQuote ? 'button' : undefined}
        tabIndex={hasQuote ? 0 : undefined}
        onClick={hasQuote ? toggle : undefined}
        onKeyDown={
          hasQuote
            ? (event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  toggle()
                }
              }
            : undefined
        }
        aria-expanded={hasQuote ? open : undefined}
        data-testid={`source-quote-${source.id}`}
        title={hasQuote ? (open ? 'Скрыть цитату' : 'Показать цитату') : undefined}
      >
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
              event.stopPropagation()
              void openSourceFile()
            }}
          >
            {source.title}
          </a>
        ) : (
          <span className="asst-source-item__title">{source.title}</span>
        )}
        {hasQuote ? (
          <span className="asst-source-item__more" aria-hidden>
            {open ? '▴' : '⋯'}
          </span>
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

function sourcesMoreLabel(count: number) {
  const mod10 = count % 10
  const mod100 = count % 100
  if (mod10 === 1 && mod100 !== 11) return `Ещё ${count} источник`
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
    return `Ещё ${count} источника`
  }
  return `Ещё ${count} источников`
}

function SourcesList({
  messageId,
  sources,
}: {
  messageId: string
  sources: AssistantSource[]
}) {
  const [showAll, setShowAll] = useState(false)
  const visible = showAll ? sources : sources.slice(0, 1)
  const hiddenCount = sources.length - visible.length

  return (
    <div className="asst-sources" data-testid={`sources-${messageId}`}>
      <strong>Источники ({sources.length})</strong>
      <ul>
        {visible.map((source) => (
          <SourceItem key={source.id} source={source} />
        ))}
      </ul>
      {sources.length > 1 ? (
        <button
          type="button"
          className="asst-sources__more"
          onClick={() => setShowAll((value) => !value)}
          data-testid={`sources-more-${messageId}`}
        >
          {showAll ? 'Скрыть источники' : sourcesMoreLabel(hiddenCount)}
        </button>
      ) : null}
    </div>
  )
}

function previousMediaTranscripts(
  messages: AssistantMessage[],
  index: number,
) {
  for (let cursor = index - 1; cursor >= 0; cursor -= 1) {
    const item = messages[cursor]
    if (item?.role !== 'user') continue
    return (item.attachments || []).filter((file) => file.mediaKind && file.text)
  }
  return []
}

function DraftCard({
  message,
  readOnly,
  onChange,
}: {
  message: AssistantMessage
  readOnly: boolean
  onChange: (text: string) => void
}) {
  const draft = message.draft
  if (!draft) return null
  const isText = draft.kind === 'text'
  return (
    <div className="asst-draft" data-testid={`asst-draft-${message.id}`}>
      <textarea
        value={draft.text}
        readOnly={readOnly}
        data-testid="asst-draft-text"
        onChange={(event) => onChange(event.target.value)}
      />
      <div className="asst-draft__actions">
        <Button
          type="button"
          variant="ghost"
          onClick={() => {
            void navigator.clipboard?.writeText(draft.text)
          }}
        >
          Копировать
        </Button>
        <Button
          type="button"
          variant={isText ? 'secondary' : 'primary'}
          data-testid="asst-draft-download"
          onClick={() => {
            if (isText) {
              const blob = new Blob([draft.text], { type: 'text/plain;charset=utf-8' })
              const url = URL.createObjectURL(blob)
              const link = document.createElement('a')
              link.href = url
              link.download = draft.filename || 'draft.txt'
              document.body.appendChild(link)
              link.click()
              link.remove()
              URL.revokeObjectURL(url)
              return
            }
            void downloadGeneratedDocument(draft.templateId, draft.fields)
          }}
        >
          Скачать {draft.formatLabel || draft.outputFormat}
        </Button>
      </div>
    </div>
  )
}

function MessageLenta({
  messages,
  streaming,
  readOnly = false,
  onFeedback,
  onExpand,
  onStop,
  onDraftChange,
}: {
  messages: AssistantMessage[]
  streaming: boolean
  readOnly?: boolean
  onFeedback: (id: string, kind: FeedbackKind) => void
  onExpand: (id: string) => void
  onStop: () => void
  onDraftChange: (id: string, text: string) => void
}) {
  const lastTurnRef = useRef<HTMLDivElement | null>(null)
  const lastMessageId = messages[messages.length - 1]?.id

  useEffect(() => {
    lastTurnRef.current?.scrollIntoView({ block: 'start', behavior: 'smooth' })
  }, [lastMessageId])

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
      {messages.map((message, index) => (
        <div
          key={message.id}
          ref={index === messages.length - 1 ? lastTurnRef : undefined}
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
                    <li key={file.name}>
                      <span>{file.name}</span>
                      {file.mediaKind && file.text ? (
                        <button
                          type="button"
                          className="asst-turn__transcript"
                          onClick={() => downloadTranscript(file.name, file.text || '')}
                        >
                          транскрипт.txt
                        </button>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : null}
              <p className="asst-turn__user">{compactChatText(message.content)}</p>
            </div>
          ) : (
            <Card padded={false} className="asst-turn__card">
              {message.pending && !message.content ? (
                <div className="asst-streaming" data-testid="asst-streaming">
                  <span>Ассистент печатает…</span>
                  <Button type="button" variant="ghost" onClick={onStop}>
                    Остановить
                  </Button>
                </div>
              ) : (
                <p className="asst-turn__text">
                  {compactChatText(
                    message.draft || message.pending || message.expanded
                      ? message.content
                      : finishLastSentence(message.content),
                  )}
                  {message.pending ? <span className="asst-cursor" aria-hidden>|</span> : null}
                </p>
              )}
              {message.draft && !message.pending ? (
                <DraftCard
                  message={message}
                  readOnly={readOnly}
                  onChange={(text) => onDraftChange(message.id, text)}
                />
              ) : null}
              {message.sources && message.sources.length > 0 ? (
                <SourcesList messageId={message.id} sources={message.sources} />
              ) : null}
              {!readOnly && !message.pending && message.content ? (
                <div className="asst-answer-actions">
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={streaming}
                    onClick={() => onExpand(message.id)}
                    data-testid={`asst-expand-${message.id}`}
                  >
                    {message.expanded ? 'Скрыть' : 'Подробнее'}
                  </Button>
                  {previousMediaTranscripts(messages, index).map((file) => (
                    <Button
                      key={`${file.name}-txt`}
                      type="button"
                      variant="ghost"
                      onClick={() => downloadTranscript(file.name, file.text || '')}
                    >
                      Скачать транскрипт
                    </Button>
                  ))}
                  <FeedbackBar message={message} onFeedback={onFeedback} />
                </div>
              ) : !readOnly ? (
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
    </div>
  )
}

const TOOL_DESCRIPTIONS: Record<ToolId, string> = {
  code: 'Черновик фрагмента кода по запросу из чата.',
  sql: 'Read-only запросы к разрешённым витринам. Изменения запрещены.',
  rpa: 'Запуск роботов только после явного подтверждения оператора.',
  document: 'Сформировать бланк банка: Word, PDF, Excel, PPT или BPMN.',
  text: 'Черновик записки, справки или отчёта — можно править в чате.',
  diagram: 'Презентация PPT или схема BPMN / ER по шаблону.',
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

function GenerateDocumentModal({
  open,
  onClose,
  onDraft,
  onDownloaded,
  formatFilter,
}: {
  open: boolean
  onClose: () => void
  onDraft: (text: string, draft?: AssistantGeneratedDraft) => void
  onDownloaded: () => void
  formatFilter?: DocTemplateFormat[]
}) {
  const [templates, setTemplates] = useState<ChatDocTemplate[]>([])
  const [templateId, setTemplateId] = useState<number | null>(null)
  const [values, setValues] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const selected = templates.find((item) => item.id === templateId) ?? null

  useEffect(() => {
    if (!open) return
    let cancelled = false
    setError('')
    void (async () => {
      try {
        await ensureDevSession()
        const items = (await fetchChatDocTemplates()).filter((item) =>
          formatFilter?.length
            ? formatFilter.includes(item.output_format)
            : true,
        )
        if (cancelled) return
        setTemplates(items)
        const first = items[0]
        setTemplateId(first?.id ?? null)
        setValues(
          Object.fromEntries((first?.fields || []).map((field) => [field.id, ''])),
        )
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Не удалось загрузить шаблоны')
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [formatFilter, open])

  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busy) onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [busy, onClose, open])

  if (!open) return null

  const run = async (mode: 'draft' | 'download') => {
    if (!selected || busy) return
    setBusy(true)
    setError('')
    try {
      if (mode === 'draft') {
        const draft = await generateDocDraft(selected.id, values)
        const kind =
          selected.output_format === 'txt'
            ? 'text'
            : selected.output_format === 'pptx'
              ? 'slides'
              : selected.output_format === 'bpmn' || selected.output_format === 'mmd'
                ? 'diagram'
                : 'text'
        onDraft(
          `Черновик «${draft.template_name}» (${draft.format_label || draft.output_format}).`,
          {
            kind,
            templateId: selected.id,
            templateName: draft.template_name,
            filename: draft.filename,
            outputFormat: draft.output_format,
            formatLabel: draft.format_label,
            text: draft.text,
            fields: values,
          },
        )
      } else {
        await downloadGeneratedDocument(selected.id, values)
        onDownloaded()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось сформировать документ')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="asst-docgen" data-testid="asst-docgen-modal" role="presentation">
      <button
        type="button"
        className="asst-docgen__backdrop"
        aria-label="Закрыть"
        disabled={busy}
        onClick={onClose}
      />
      <div
        className="asst-docgen__dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Сгенерировать документ"
      >
        <strong>Сгенерировать документ</strong>
        <label>
          Шаблон
          <select
            value={templateId ?? ''}
            data-testid="asst-docgen-template"
            disabled={busy || !templates.length}
            onChange={(event) => {
              const nextId = Number(event.target.value)
              const next = templates.find((item) => item.id === nextId) ?? null
              setTemplateId(next?.id ?? null)
              setValues(
                Object.fromEntries((next?.fields || []).map((field) => [field.id, ''])),
              )
            }}
          >
            {!templates.length ? <option value="">Нет активных шаблонов</option> : null}
            {templates.map((item) => (
              <option key={item.id} value={item.id}>
                {item.format_label} — {item.name}
              </option>
            ))}
          </select>
        </label>
        {(selected?.fields || []).map((field) => (
          <label key={field.id}>
            {field.label}{field.required ? '' : ' (необяз.)'}
            <input
              value={values[field.id] || ''}
              disabled={busy}
              data-testid={`asst-docgen-field-${field.id}`}
              onChange={(event) =>
                setValues((current) => ({ ...current, [field.id]: event.target.value }))
              }
            />
          </label>
        ))}
        {error ? <p className="asst-docgen__error" role="alert">{error}</p> : null}
        <div className="asst-docgen__actions">
          <Button type="button" variant="ghost" disabled={busy} onClick={onClose}>
            Отмена
          </Button>
          <Button
            type="button"
            variant="secondary"
            disabled={busy || !selected}
            data-testid="asst-docgen-draft"
            onClick={() => void run('draft')}
          >
            Создать черновик
          </Button>
          <Button
            type="button"
            disabled={busy || !selected}
            data-testid="asst-docgen-download"
            onClick={() => void run('download')}
          >
            Скачать
          </Button>
        </div>
      </div>
    </div>
  )
}

function ocrFieldsToApi(fields: readonly OcrPanelField[]): Record<string, unknown> {
  return Object.fromEntries(
    fields.map((field) => [
      field.id,
      {
        value: field.value,
        confidence: field.confidence == null ? undefined : field.confidence / 100,
      },
    ]),
  )
}

function OcrResultDrawer({
  panel,
  readOnly,
  onClose,
  onUpload,
  onApproveExport,
  onFieldChange,
}: {
  panel: OcrPanelState
  readOnly?: boolean
  onClose: () => void
  onUpload: () => void
  onApproveExport: () => void
  onFieldChange: (id: string, value: string) => void
}) {
  useEffect(() => {
    if (!panel.open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose, panel.open])

  const visibleOcrFields = filterOcrFields(panel.fields)
  const hasResult = Boolean(
    panel.fileName || visibleOcrFields.length || panel.rawText || panel.error,
  )
  const canExport =
    !readOnly
    && !panel.busy
    && !panel.exportBusy
    && (visibleOcrFields.length > 0 || Boolean(panel.jobId))

  return (
    <div
      className={`asst-ocr-panel${panel.open ? ' is-open' : ''}`}
      data-testid="asst-ocr-panel"
      aria-hidden={!panel.open}
    >
      <button
        type="button"
        className="asst-ocr-panel__backdrop"
        aria-label="Закрыть окно OCR"
        tabIndex={panel.open ? 0 : -1}
        onClick={onClose}
      />
      <aside
        id="asst-ocr-drawer"
        className="asst-ocr-panel__drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Распознавание документа"
        data-testid="asst-ocr-drawer"
      >
        <header className="asst-ocr-panel__header">
          <div>
            <strong>Распознавание OCR</strong>
            <span>{panel.fileName || 'Загрузите документ для проверки полей'}</span>
          </div>
          <div className="asst-ocr-panel__header-actions">
            <Button
              type="button"
              disabled={readOnly || panel.busy}
              onClick={onUpload}
              data-testid="asst-ocr-upload"
            >
              Загрузить документ
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={onClose}
              aria-label="Закрыть OCR"
              data-testid="asst-ocr-close"
            >
              ×
            </Button>
          </div>
        </header>
        <div className="asst-ocr-panel__body">
          {panel.busy ? (
            <p className="asst-ocr-panel__status" data-testid="asst-ocr-busy">
              Распознаём документ…
            </p>
          ) : null}
          {panel.error ? (
            <p className="asst-ocr-panel__error" role="alert" data-testid="asst-ocr-error">
              {panel.error}
            </p>
          ) : null}
          {!panel.busy && !hasResult ? (
            <div className="asst-ocr-panel__empty-state" data-testid="asst-ocr-empty">
              <p>Нажмите «Загрузить документ», чтобы выбрать скан или PDF.</p>
              <Button
                type="button"
                disabled={readOnly}
                onClick={onUpload}
                data-testid="asst-ocr-upload-empty"
              >
                Загрузить документ
              </Button>
            </div>
          ) : null}
          {panel.previewUrl ? (
            <div className="asst-ocr-panel__preview">
              <img
                src={panel.previewUrl}
                alt={`Скан ${panel.fileName}`}
                data-testid="asst-ocr-preview"
              />
            </div>
          ) : null}
          {!panel.busy && hasResult && !panel.error ? (
            <>
              <div className="asst-ocr-panel__meta">
                <strong>OCR · {panel.documentType || 'unknown'}</strong>
                <StatusBadge
                  status={
                    panel.approved
                      ? 'success'
                      : panel.validationStatus === 'valid'
                        ? 'success'
                        : 'warning'
                  }
                >
                  {panel.approved
                    ? 'подтверждено'
                    : panel.validationStatus || 'pending_review'}
                </StatusBadge>
              </div>
              {visibleOcrFields.length ? (
                <ul className="asst-ocr-panel__fields" data-testid="asst-ocr-fields">
                  {visibleOcrFields.map((field) => (
                    <li key={field.id} data-testid={`ocr-field-${field.id}`}>
                      <label htmlFor={`asst-ocr-field-${field.id}`}>{field.label}</label>
                      <input
                        id={`asst-ocr-field-${field.id}`}
                        value={field.value}
                        disabled={readOnly}
                        data-testid={`asst-ocr-field-input-${field.id}`}
                        onChange={(event) =>
                          onFieldChange(field.id, event.target.value)
                        }
                      />
                      <StatusBadge status={OCR_CONFIDENCE_TONE(field.confidence)}>
                        {field.confidence == null ? '—' : `${field.confidence}%`}
                      </StatusBadge>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="asst-ocr-panel__empty">
                  Поля не найдены. Ниже — сырой текст, который прочитал OCR.
                </p>
              )}
              {panel.rawText ? (
                <details className="asst-ocr-panel__raw">
                  <summary>Текст OCR</summary>
                  <pre data-testid="asst-ocr-raw">{panel.rawText}</pre>
                </details>
              ) : null}
            </>
          ) : null}
        </div>
        {hasResult && !panel.busy ? (
          <footer className="asst-ocr-panel__footer">
            <Button
              type="button"
              variant="ghost"
              disabled={readOnly || panel.busy}
              onClick={onUpload}
            >
              Загрузить другой
            </Button>
            <Button
              type="button"
              disabled={!canExport}
              onClick={onApproveExport}
              data-testid="asst-ocr-approve-export"
            >
              {panel.exportBusy ? 'Экспорт…' : 'Подтвердить и экспорт'}
            </Button>
            {panel.approved ? (
              <StatusBadge status="success" data-testid="asst-ocr-approved-badge">
                Подтверждено · файл скачан
              </StatusBadge>
            ) : null}
          </footer>
        ) : null}
      </aside>
    </div>
  )
}

function ChatSidebar({
  dialogs,
  activeId,
  readOnly,
  onOpen,
  onNew,
  onDelete,
}: {
  dialogs: readonly ChatDialogSummary[]
  activeId: string
  readOnly?: boolean
  onOpen: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
}) {
  return (
    <aside
      id="asst-history-drawer"
      className="asst-rail"
      aria-label="История диалогов"
      data-testid="asst-history-drawer"
    >
      <button
        type="button"
        className="asst-rail__new"
        onClick={onNew}
        disabled={readOnly}
        aria-label="Новый диалог"
        title="Новый диалог"
        data-testid="asst-new"
      >
        +
      </button>
      <ul className="asst-rail__list" data-testid="asst-history-list">
        {dialogs.length === 0 ? (
          <li className="asst-rail__empty">Нет диалогов</li>
        ) : (
          dialogs.map((dialog) => {
            const active = dialog.id === activeId
            return (
              <li key={dialog.id}>
                <button
                  type="button"
                  className={`asst-rail__item${active ? ' is-active' : ''}`}
                  onClick={() => onOpen(dialog.id)}
                  title={dialog.title}
                  data-testid={`asst-history-item-${dialog.id}`}
                >
                  <strong>{dialog.title}</strong>
                  <span>{formatDialogDate(dialog.updatedAt)}</span>
                </button>
                <button
                  type="button"
                  className="asst-rail__delete"
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
  /** Host window owns fullscreen OCR (Documents tab). */
  onOpenOcr?: () => void
}

export function AssistantChat({
  demoMode = false,
  compact = false,
  readOnly = false,
  initialDraft = '',
  knowledgeBases: knowledgeBasesProp,
  onOpenOcr,
}: AssistantChatProps) {
  const [draft, setDraft] = useState(initialDraft)
  const [kbOpen, setKbOpen] = useState(false)
  const [attachments, setAttachments] = useState<ChatAttachmentPayload[]>([])
  const [attachBusy, setAttachBusy] = useState(false)
  const [attachHint, setAttachHint] = useState('')
  const [attachError, setAttachError] = useState('')
  const [ocrPanel, setOcrPanel] = useState<OcrPanelState>(EMPTY_OCR_PANEL)
  const [ocrWorkspaceOpen, setOcrWorkspaceOpen] = useState(false)
  const kbRootRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const ocrFileInputRef = useRef<HTMLInputElement>(null)
  const ocrPreviewUrlRef = useRef<string | null>(null)
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
  const [docgenOpen, setDocgenOpen] = useState(false)
  const [docgenFilter, setDocgenFilter] = useState<DocTemplateFormat[] | undefined>()
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
    expandAnswer,
    stopStreaming,
    setFeedback,
    runTool,
    setToolState,
    pushLocalAssistantMessage,
    updateDraftText,
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
            ? status.last_error || 'Модель недоступна'
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
            : 'Не удалось загрузить список моделей',
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

  const revokeOcrPreview = () => {
    if (ocrPreviewUrlRef.current) {
      URL.revokeObjectURL(ocrPreviewUrlRef.current)
      ocrPreviewUrlRef.current = null
    }
  }

  const closeOcrPanel = () => {
    revokeOcrPreview()
    setOcrPanel(EMPTY_OCR_PANEL)
  }

  const onPickFiles = async (fileList: FileList | null) => {
    if (!fileList?.length || readOnly) return
    const remaining = Math.max(0, ATTACH_MAX_FILES - attachments.length)
    if (!remaining) {
      setAttachError(`Можно прикрепить не больше ${ATTACH_MAX_FILES} файлов`)
      return
    }
    const files = Array.from(fileList).slice(0, remaining)
    if (fileInputRef.current) fileInputRef.current.value = ''
    const recognizingSpeech = files.some((file) => isMediaFileName(file.name))
    const compressingVideo = files.some((file) =>
      /\.(mp4|mov|mkv|webm|avi|m4v)$/i.test(file.name),
    )
    setAttachBusy(true)
    setAttachHint(
      compressingVideo
        ? 'Распознаю речь, видео не сохраняется…'
        : recognizingSpeech
          ? 'Распознаю речь, аудио не сохраняется…'
          : 'Читаю файл…',
    )
    setAttachError('')
    try {
      await ensureDevSession()
      const extracted: ChatAttachmentPayload[] = []
      for (const file of files) {
        extracted.push(await extractChatAttachment(file))
      }
      files.splice(0)
      setAttachments((current) => [...current, ...extracted].slice(0, ATTACH_MAX_FILES))
    } catch (error) {
      setAttachError(
        error instanceof Error ? error.message : 'Не удалось прочитать файл',
      )
    } finally {
      setAttachBusy(false)
      setAttachHint('')
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const onPickOcr = async (fileList: FileList | null) => {
    if (!fileList?.length || readOnly) return
    const file = fileList[0]
    revokeOcrPreview()
    const previewUrl = file.type.startsWith('image/')
      ? URL.createObjectURL(file)
      : null
    ocrPreviewUrlRef.current = previewUrl
    setToolsOpen(false)
    setKbOpen(false)
    setOcrPanel({
      ...EMPTY_OCR_PANEL,
      open: true,
      busy: true,
      fileName: file.name,
      previewUrl,
    })
    try {
      await ensureDevSession()
      const payload = await extractChatAttachment(file, {
        forceOcr: true,
      })
      const ocr = payload.ocr
      const rawFields = ocr?.fields || {}
      const orderedIds = [
        ...OCR_FIELD_ORDER.filter((id) => id in rawFields),
        ...Object.keys(rawFields).filter((id) => !OCR_FIELD_ORDER.includes(id)),
      ]
      const fields = filterOcrFields(orderedIds.map((id) => {
        const raw = rawFields[id]
        const explicit = (
          raw && typeof raw === 'object' && raw !== null && 'label' in raw
            ? String((raw as { label?: unknown }).label || '').trim()
            : ''
        )
        return {
          id,
          label: OCR_FIELD_LABELS[id] || explicit || id,
          value: fieldDisplayValue(raw),
          confidence: fieldConfidencePercent(raw),
        }
      }))
      setOcrPanel({
        open: true,
        busy: false,
        error: '',
        fileName: file.name,
        previewUrl,
        documentType: ocr?.document_type || 'unknown',
        validationStatus: ocr?.validation_status || null,
        jobId: ocr?.job_id || '',
        fields,
        rawText: payload.text || '',
        approved: false,
        exportBusy: false,
      })
    } catch (error) {
      setOcrPanel((current) => ({
        ...current,
        open: true,
        busy: false,
        error:
          error instanceof Error ? error.message : 'Не удалось распознать документ',
      }))
    } finally {
      if (ocrFileInputRef.current) ocrFileInputRef.current.value = ''
    }
  }

  useEffect(() => () => revokeOcrPreview(), [])

  const openOcrWindow = () => {
    setToolsOpen(false)
    setKbOpen(false)
    if (onOpenOcr) {
      onOpenOcr()
      return
    }
    if (compact) {
      setOcrWorkspaceOpen(true)
      return
    }
    setOcrPanel((current) => (
      current.open ? current : { ...EMPTY_OCR_PANEL, open: true }
    ))
  }

  const approveOcrExport = async () => {
    if (readOnly || ocrPanel.busy || ocrPanel.exportBusy) return
    if (!ocrPanel.fields.length && !ocrPanel.jobId) return
    const payload = ocrFieldsToApi(ocrPanel.fields)
    const documentType = ocrPanel.documentType || 'passport'
    const stem = ocrPanel.fileName.replace(/\.[^.]+$/u, '') || 'ocr-export'
    setOcrPanel((current) => ({ ...current, exportBusy: true, error: '' }))
    try {
      if (ocrPanel.jobId && !ocrPanel.jobId.startsWith('demo-')) {
        await approveOcrJob(ocrPanel.jobId, documentType, payload)
        try {
          await exportOcrJob(ocrPanel.jobId, 'docx', {
            documentType,
            fields: payload,
          })
        } catch {
          downloadOcrFieldsDocx(ocrExportRows(ocrPanel.fields), stem)
        }
      } else {
        downloadOcrFieldsDocx(ocrExportRows(ocrPanel.fields), stem)
      }
      setOcrPanel((current) => ({
        ...current,
        approved: true,
        exportBusy: false,
      }))
    } catch (error) {
      setOcrPanel((current) => ({
        ...current,
        exportBusy: false,
        error: error instanceof Error ? error.message : 'Не удалось экспортировать',
      }))
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
      className={`asst-chat${compact ? ' asst-chat--compact' : ' asst-chat--wide'}${
        compact ? ' is-history-open' : ''
      }${readOnly ? ' asst-chat--readonly' : ''}`}
      data-testid="assistant-chat"
      data-readonly={readOnly ? 'true' : undefined}
    >
      {compact ? (
        <ChatSidebar
          dialogs={dialogs}
          activeId={sessionId}
          readOnly={readOnly}
          onOpen={openDialog}
          onNew={() => {
            newDialog()
            setAttachments([])
            setAttachError('')
          }}
          onDelete={deleteDialog}
        />
      ) : null}
      <div className="asst-chat__main">
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
            title={modelError || 'Модель для ответов'}
          >
            {modelStatus === 'loading' ? (
              <option value="">Загрузка…</option>
            ) : modelCatalog.length === 0 ? (
              <option value="">Нет доступных моделей</option>
            ) : (
              <>
                {/* Keep controlled <select> valid if active id is briefly missing */}
                {activeModelId &&
                !modelCatalog.some((model) => model.id === activeModelId) ? (
                  <option value={activeModelId}>
                    {displayModelLabel(activeModelId, activeModelId)}
                  </option>
                ) : null}
                {modelCatalog.map((model) => (
                  <option
                    key={model.id}
                    value={model.id}
                    disabled={model.available === false}
                  >
                    {displayModelLabel(model.id, model.label)}
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
        <div className="asst-toolbar__extras">
          <Button
            type="button"
            variant={toolsOpen ? 'secondary' : 'ghost'}
            aria-expanded={toolsOpen}
            aria-controls="asst-tools-panel"
            disabled={readOnly}
            onClick={() => {
              setToolsOpen((value) => !value)
              setKbOpen(false)
            }}
            data-testid="asst-composer-tools"
          >
            Инструменты
          </Button>
          <Button
            type="button"
            variant={ocrPanel.open || ocrWorkspaceOpen ? 'secondary' : 'ghost'}
            disabled={readOnly || ocrPanel.busy}
            onClick={openOcrWindow}
            data-testid="asst-composer-ocr"
            title="Открыть окно распознавания документа"
          >
            {ocrPanel.busy ? 'OCR…' : 'OCR'}
          </Button>
        </div>
      </div>

      {compact && ocrWorkspaceOpen ? (
        <div className="asst-ocr-fullscreen" data-testid="asst-ocr-fullscreen">
          <OcrDocumentsPanel
            initialSubTab="upload"
            onClose={() => setOcrWorkspaceOpen(false)}
          />
        </div>
      ) : null}
      {!onOpenOcr && !compact ? (
        <OcrResultDrawer
          panel={ocrPanel}
          readOnly={readOnly}
          onClose={closeOcrPanel}
          onUpload={() => ocrFileInputRef.current?.click()}
          onApproveExport={() => void approveOcrExport()}
          onFieldChange={(id, value) =>
            setOcrPanel((current) => ({
              ...current,
              approved: false,
              fields: current.fields.map((field) => (
                field.id === id ? { ...field, value } : field
              )),
            }))
          }
        />
      ) : null}

      {!readOnly ? (
        <ToolsPanel
          tools={tools}
          open={toolsOpen}
          onClose={() => setToolsOpen(false)}
          onRun={(id) => {
            if (id === 'document' || id === 'text' || id === 'diagram') {
              setToolsOpen(false)
              setDocgenFilter(
                id === 'text'
                  ? ['txt']
                  : id === 'diagram'
                    ? ['pptx', 'bpmn', 'mmd']
                    : undefined,
              )
              setDocgenOpen(true)
              setToolState(id, { state: 'running', detail: 'форма бланка' })
              return
            }
            runTool(id)
          }}
        />
      ) : null}

      {!readOnly ? (
        <GenerateDocumentModal
          open={docgenOpen}
          formatFilter={docgenFilter}
          onClose={() => {
            setDocgenOpen(false)
            setToolState('document', { state: 'idle', detail: undefined })
            setToolState('text', { state: 'idle', detail: undefined })
            setToolState('diagram', { state: 'idle', detail: undefined })
          }}
          onDraft={(text, draft) => {
            pushLocalAssistantMessage(text, draft)
            setToolState('document', { state: 'done', detail: 'черновик' })
            setToolState('text', { state: 'done', detail: 'черновик' })
            setToolState('diagram', { state: 'done', detail: 'черновик' })
          }}
          onDownloaded={() => {
            setToolState('document', { state: 'done', detail: 'скачан' })
            setToolState('diagram', { state: 'done', detail: 'скачан' })
          }}
        />
      ) : null}

      <MessageLenta
        messages={messages}
        streaming={streaming}
        readOnly={readOnly}
        onFeedback={setFeedback}
        onExpand={expandAnswer}
        onStop={stopStreaming}
        onDraftChange={updateDraftText}
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
        {attachments.length > 0 ? (
          <ul className="asst-composer__attachments" data-testid="asst-attach-list">
            {attachments.map((file) => (
              <li key={`${file.name}-${file.size_bytes ?? 0}`}>
                <span>
                  {file.name}
                  {file.media?.compressed ? ' · аудио' : ''}
                </span>
                {file.media && file.text ? (
                  <button
                    type="button"
                    className="asst-composer__transcript"
                    onClick={() => downloadTranscript(file.name, file.text)}
                  >
                    TXT
                  </button>
                ) : null}
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
        <input
          ref={ocrFileInputRef}
          type="file"
          className="asst-composer__file"
          accept={OCR_ACCEPT}
          hidden
          disabled={readOnly || ocrPanel.busy}
          onChange={(event) => void onPickOcr(event.target.files)}
          data-testid="asst-ocr-input"
        />
        <div className="asst-composer__row">
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
              onKeyDown={(event) => {
                if (event.key !== 'Enter' || event.shiftKey) return
                event.preventDefault()
                if (readOnly || streaming || attachBusy) return
                if (!draft.trim() && !attachments.length) return
                event.currentTarget.form?.requestSubmit()
              }}
            />
            <button
              type="button"
              className="asst-composer__attach"
              disabled={readOnly || attachBusy || streaming || attachments.length >= ATTACH_MAX_FILES}
              onClick={() => fileInputRef.current?.click()}
              data-testid="asst-attach"
              title={
                attachBusy
                  ? attachHint || 'Читаю файл…'
                  : 'Прикрепить файл · видео сожмётся в аудио, затем распознаем речь'
              }
              aria-label={attachBusy ? attachHint || 'Читаю файл' : 'Прикрепить файл'}
            >
              {attachBusy ? (
                <span className="asst-composer__attach-busy" aria-hidden>
                  …
                </span>
              ) : (
                <svg
                  className="asst-composer__attach-icon"
                  width="18"
                  height="18"
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
              {charCount}/{maxChars}
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
    </div>
  )
}
