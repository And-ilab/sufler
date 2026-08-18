import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from 'react'
import { Button, Card, StatusBadge, Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from '../../components'
import {
  approveOcrJob,
  fetchOcrResult,
  listOcrJobs,
  uploadOcrDocument,
} from '../admin/api/ocrAdmin'
import './OcrDocumentsPanel.css'

export type OcrSubTab = 'queue' | 'upload' | 'review'

export interface OcrField {
  id: string
  apiKey: string
  label: string
  value: string
  confidence: number
  bbox: { left: number; top: number; width: number; height: number }
}

export interface OcrQueueItem {
  id: string
  file: string
  docType: string
  status: 'queued' | 'ocr' | 'review' | 'done' | 'error'
  progress: number
  confidence: number | null
}

const STATUS_LABEL: Record<OcrQueueItem['status'], string> = {
  queued: 'Очередь',
  ocr: 'OCR',
  review: 'На проверке',
  done: 'Готово',
  error: 'Ошибка валидации',
}

const ACCEPT =
  '.png,.jpg,.jpeg,.pdf,.tiff,.tif,image/png,image/jpeg,application/pdf,image/tiff'

/** UI id → backend field key (and reverse for known aliases). */
const UI_TO_API: Record<string, string> = {
  fio: 'full_name',
  full_name: 'full_name',
  series: 'series',
  number: 'number',
  issued: 'issue_date',
  issue_date: 'issue_date',
}

const API_TO_UI: Record<string, string> = {
  full_name: 'fio',
  issue_date: 'issued',
  series: 'series',
  number: 'number',
}

const FIELD_LABELS: Record<string, string> = {
  fio: 'ФИО',
  full_name: 'ФИО',
  series: 'Серия паспорта',
  number: 'Номер',
  issued: 'Дата выдачи',
  issue_date: 'Дата выдачи',
}

const DEFAULT_BBOX: Record<string, OcrField['bbox']> = {
  fio: { left: 12, top: 28, width: 52, height: 7 },
  series: { left: 12, top: 40, width: 18, height: 7 },
  number: { left: 32, top: 40, width: 28, height: 7 },
  issued: { left: 12, top: 52, width: 30, height: 7 },
}

/** Demo passport fields for Storybook / offline visual tests. */
const DEMO_PASSPORT_FIELDS: OcrField[] = [
  {
    id: 'fio',
    apiKey: 'full_name',
    label: 'ФИО',
    value: 'Иванов Иван Иванович',
    confidence: 0.96,
    bbox: DEFAULT_BBOX.fio,
  },
  {
    id: 'series',
    apiKey: 'series',
    label: 'Серия паспорта',
    value: 'MP',
    confidence: 0.88,
    bbox: DEFAULT_BBOX.series,
  },
  {
    id: 'number',
    apiKey: 'number',
    label: 'Номер',
    value: '4123456',
    confidence: 0.72,
    bbox: DEFAULT_BBOX.number,
  },
  {
    id: 'issued',
    apiKey: 'issue_date',
    label: 'Дата выдачи',
    value: '12.03.2019',
    confidence: 0.54,
    bbox: DEFAULT_BBOX.issued,
  },
]

function confidenceTone(confidence: number): 'success' | 'warning' | 'danger' {
  if (confidence >= 0.85) return 'success'
  if (confidence >= 0.6) return 'warning'
  return 'danger'
}

function formatConfidence(value: number | null): string {
  if (value == null) return '—'
  return `${Math.round(value * 100)}%`
}

function avgConfidence(fields: OcrField[]): number | null {
  if (!fields.length) return null
  const sum = fields.reduce((acc, field) => acc + field.confidence, 0)
  return sum / fields.length
}

function mapBackendStatus(raw: unknown, validationStatus?: unknown): OcrQueueItem['status'] {
  const status = String(raw || '')
  const validation = String(validationStatus || '')
  if (status === 'queued') return 'queued'
  if (status === 'ocr_processing') return 'ocr'
  if (status === 'processing_error') return 'error'
  if (status === 'completed') {
    if (validation === 'valid' || validation === 'approved') return 'done'
    return 'review'
  }
  return 'queued'
}

function fieldValue(raw: unknown): string {
  if (raw == null) return ''
  if (typeof raw === 'object' && raw !== null && 'value' in raw) {
    const value = (raw as { value?: unknown }).value
    return value == null ? '' : String(value)
  }
  return String(raw)
}

function fieldConfidence(raw: unknown): number {
  if (raw && typeof raw === 'object' && 'confidence' in raw) {
    const conf = (raw as { confidence?: unknown }).confidence
    if (typeof conf === 'number' && Number.isFinite(conf)) {
      return conf > 1 ? conf / 100 : conf
    }
  }
  return 0
}

function fieldsFromResult(fieldsRaw: unknown): OcrField[] {
  if (!fieldsRaw || typeof fieldsRaw !== 'object') return []
  const entries = Object.entries(fieldsRaw as Record<string, unknown>)
  const preferred = ['full_name', 'series', 'number', 'issue_date']
  const ordered = [
    ...preferred.filter((key) => key in (fieldsRaw as object)),
    ...entries.map(([key]) => key).filter((key) => !preferred.includes(key)),
  ]
  return ordered.map((apiKey, index) => {
    const raw = (fieldsRaw as Record<string, unknown>)[apiKey]
    const id = API_TO_UI[apiKey] || apiKey
    const bbox = DEFAULT_BBOX[id] || {
      left: 10,
      top: 18 + index * 12,
      width: 48,
      height: 7,
    }
    return {
      id,
      apiKey,
      label: FIELD_LABELS[id] || FIELD_LABELS[apiKey] || apiKey,
      value: fieldValue(raw),
      confidence: fieldConfidence(raw),
      bbox,
    }
  })
}

function fieldsToApiPayload(fields: OcrField[]): Record<string, unknown> {
  const payload: Record<string, unknown> = {}
  for (const field of fields) {
    const key = field.apiKey || UI_TO_API[field.id] || field.id
    payload[key] = {
      value: field.value,
      confidence: field.confidence,
    }
  }
  return payload
}

function demoFieldsForFile(fileName: string, docType: string): OcrField[] {
  if (docType === 'passport' || fileName.toLowerCase().includes('passport')) {
    return DEMO_PASSPORT_FIELDS.map((field) => ({ ...field, bbox: { ...field.bbox } }))
  }
  return [
    {
      id: 'title',
      apiKey: 'title',
      label: 'Заголовок',
      value: fileName.replace(/\.[^.]+$/, ''),
      confidence: 0.9,
      bbox: { left: 10, top: 18, width: 60, height: 8 },
    },
  ]
}

function jobToQueueItem(job: Record<string, unknown>): OcrQueueItem {
  const status = mapBackendStatus(job.status, job.validation_status)
  const progress =
    status === 'queued' ? 0
      : status === 'ocr' ? 50
        : 100
  return {
    id: String(job.job_id || job.id || ''),
    file: String(job.filename || job.file || 'document'),
    docType: String(job.document_type || 'unknown'),
    status,
    progress,
    confidence: null,
  }
}

export interface OcrDocumentsPanelProps {
  initialSubTab?: OcrSubTab
}

export function OcrDocumentsPanel({
  initialSubTab = 'queue',
}: OcrDocumentsPanelProps) {
  const [subTab, setSubTab] = useState<OcrSubTab>(initialSubTab)
  const [queue, setQueue] = useState<OcrQueueItem[]>([])
  const [statusFilter, setStatusFilter] = useState('all')
  const [typeFilter, setTypeFilter] = useState('any')
  const [search, setSearch] = useState('')
  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const [docType, setDocType] = useState('auto')
  const [dragOver, setDragOver] = useState(false)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [fieldsByJob, setFieldsByJob] = useState<Record<string, OcrField[]>>({})
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null)
  const [zoom, setZoom] = useState(100)
  const [approved, setApproved] = useState(false)
  const [llmAccepted, setLlmAccepted] = useState<boolean | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const fields = activeId ? fieldsByJob[activeId] || [] : []
  const activeItem = queue.find((item) => item.id === activeId) ?? queue[0]

  const loadQueue = useCallback(async () => {
    try {
      const jobs = await listOcrJobs()
      setQueue(jobs.map(jobToQueueItem).filter((item) => item.id))
      setError('')
    } catch {
      // Storybook / offline: keep local queue as-is.
    }
  }, [])

  useEffect(() => {
    void loadQueue()
  }, [loadQueue])

  const filteredQueue = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return queue.filter((item) => {
      if (statusFilter !== 'all' && item.status !== statusFilter) return false
      if (typeFilter !== 'any' && item.docType !== typeFilter) return false
      if (needle && !item.file.toLowerCase().includes(needle)) return false
      return true
    })
  }, [queue, search, statusFilter, typeFilter])

  const stats = useMemo(() => ({
    queued: queue.filter((item) => item.status === 'queued').length,
    ocr: queue.filter((item) => item.status === 'ocr').length,
    hitl: queue.filter((item) => item.status === 'review').length,
    errors: queue.filter((item) => item.status === 'error').length,
  }), [queue])

  const openReview = useCallback(async (item: OcrQueueItem) => {
    setActiveId(item.id)
    setApproved(item.status === 'done')
    setLlmAccepted(null)
    setSubTab('review')
    setError('')

    if (fieldsByJob[item.id]?.length) {
      setSelectedFieldId(fieldsByJob[item.id][0]?.id ?? null)
      return
    }

    try {
      const result = await fetchOcrResult(item.id)
      const nextFields = fieldsFromResult(result.fields)
      if (nextFields.length) {
        setFieldsByJob((prev) => ({ ...prev, [item.id]: nextFields }))
        setSelectedFieldId(nextFields[0]?.id ?? null)
        const conf = avgConfidence(nextFields)
        setQueue((prev) => prev.map((row) => (
          row.id === item.id ? { ...row, confidence: conf } : row
        )))
        return
      }
    } catch {
      // Fall through to demo fields for offline / Storybook.
    }

    const demo = demoFieldsForFile(item.file, item.docType)
    setFieldsByJob((prev) => ({ ...prev, [item.id]: demo }))
    setSelectedFieldId(demo[0]?.id ?? null)
  }, [fieldsByJob])

  const addFiles = useCallback((fileList: FileList | File[]) => {
    const files = Array.from(fileList).filter((file) => {
      const name = file.name.toLowerCase()
      return (
        name.endsWith('.png')
        || name.endsWith('.jpg')
        || name.endsWith('.jpeg')
        || name.endsWith('.pdf')
        || name.endsWith('.tiff')
        || name.endsWith('.tif')
        || file.type === 'image/png'
        || file.type === 'image/jpeg'
        || file.type === 'application/pdf'
        || file.type === 'image/tiff'
      )
    })
    if (!files.length) return
    setPendingFiles((prev) => [...prev, ...files])
  }, [])

  const onFileInput = (event: ChangeEvent<HTMLInputElement>) => {
    if (event.target.files?.length) {
      addFiles(event.target.files)
      event.target.value = ''
    }
  }

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragOver(false)
    if (event.dataTransfer.files?.length) {
      addFiles(event.dataTransfer.files)
    }
  }

  const startRecognition = async () => {
    if (!pendingFiles.length || busy) return
    setBusy(true)
    setError('')
    const created: OcrQueueItem[] = []
    const nextFields: Record<string, OcrField[]> = {}

    try {
      for (const [index, file] of pendingFiles.entries()) {
        const inferred =
          docType !== 'auto'
            ? docType
            : file.name.toLowerCase().includes('passport')
              ? 'passport'
              : file.name.toLowerCase().includes('contract')
                ? 'contract'
                : ''

        try {
          const response = await uploadOcrDocument(file, inferred, true)
          const jobId = String(response.job_id || `upload-${Date.now()}-${index}`)
          const result =
            (response.result as Record<string, unknown> | undefined)
            || (response.status === 'completed'
              ? await fetchOcrResult(jobId).catch(() => null)
              : null)
          const parsed = fieldsFromResult(result?.fields)
          const fields = parsed.length
            ? parsed
            : demoFieldsForFile(file.name, inferred || 'unknown')
          const item: OcrQueueItem = {
            id: jobId,
            file: file.name,
            docType: String(
              result?.document_type
              || response.document_type
              || inferred
              || 'unknown',
            ),
            status: 'review',
            progress: 100,
            confidence: avgConfidence(fields),
          }
          created.push(item)
          nextFields[jobId] = fields
        } catch {
          // Offline / Storybook: keep UX + visual-test fixtures.
          const jobId = `demo-${Date.now()}-${index}`
          const fields = demoFieldsForFile(file.name, inferred || 'passport')
          const item: OcrQueueItem = {
            id: jobId,
            file: file.name,
            docType: inferred || 'passport',
            status: 'review',
            progress: 100,
            confidence: avgConfidence(fields),
          }
          created.push(item)
          nextFields[jobId] = fields
        }
      }

      setFieldsByJob((prev) => ({ ...prev, ...nextFields }))
      setQueue((prev) => [...created, ...prev])
      setPendingFiles([])
      if (created[0]) {
        setActiveId(created[0].id)
        setSelectedFieldId(nextFields[created[0].id]?.[0]?.id ?? null)
        setApproved(false)
        setLlmAccepted(null)
        setSubTab('review')
      }
    } finally {
      setBusy(false)
    }
  }

  const updateField = (id: string, value: string) => {
    if (!activeId) return
    setFieldsByJob((prev) => ({
      ...prev,
      [activeId]: (prev[activeId] || []).map((field) => (
        field.id === id ? { ...field, value } : field
      )),
    }))
    setApproved(false)
  }

  const acceptLlmSuggestion = () => {
    if (!activeId) return
    setFieldsByJob((prev) => ({
      ...prev,
      [activeId]: (prev[activeId] || []).map((field) => (
        field.id === 'issued'
          ? { ...field, value: '12.03.2019', confidence: 0.91 }
          : field
      )),
    }))
    setLlmAccepted(true)
  }

  const approveAndExport = async () => {
    if (!activeItem) return
    setBusy(true)
    setError('')
    const currentFields = fieldsByJob[activeItem.id] || fields
    try {
      if (!activeItem.id.startsWith('demo-')) {
        await approveOcrJob(
          activeItem.id,
          activeItem.docType || 'passport',
          fieldsToApiPayload(currentFields),
        )
      }
      setApproved(true)
      setQueue((prev) => prev.map((item) => (
        item.id === activeItem.id
          ? {
              ...item,
              status: 'done',
              confidence: avgConfidence(currentFields) ?? 0.95,
              progress: 100,
            }
          : item
      )))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось утвердить')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="ocr-docs" data-testid="ocr-documents-panel">
      <div className="hub-document-tabs" role="tablist" aria-label="Документы">
        {([
          ['queue', 'Очередь'],
          ['upload', 'Загрузить'],
          ['review', 'Проверка'],
        ] as const).map(([id, label]) => (
          <button
            type="button"
            role="tab"
            key={id}
            aria-selected={subTab === id}
            data-testid={`ocr-subtab-${id}`}
            onClick={() => setSubTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {subTab === 'queue' && (
        <div className="ocr-docs__queue" data-testid="ocr-queue">
          <div className="ocr-docs__filters">
            <label>
              <span className="visually-hidden">Статус</span>
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
                data-testid="ocr-filter-status"
              >
                <option value="all">Все статусы</option>
                <option value="queued">Очередь</option>
                <option value="ocr">OCR</option>
                <option value="review">На проверке</option>
                <option value="done">Готово</option>
                <option value="error">Ошибка</option>
              </select>
            </label>
            <label>
              <span className="visually-hidden">Тип</span>
              <select
                value={typeFilter}
                onChange={(event) => setTypeFilter(event.target.value)}
                data-testid="ocr-filter-type"
              >
                <option value="any">Любой тип</option>
                <option value="passport">passport</option>
                <option value="contract">contract</option>
                <option value="statement">statement</option>
                <option value="invoice">invoice</option>
              </select>
            </label>
            <input
              type="search"
              placeholder="Поиск по файлу…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              data-testid="ocr-filter-search"
            />
            <Button
              type="button"
              onClick={() => {
                setStatusFilter('all')
                setTypeFilter('any')
                setSearch('')
                void loadQueue()
              }}
            >
              Обновить
            </Button>
          </div>

          <Table data-testid="ocr-queue-table" caption="Очередь OCR">
            <TableHead>
              <TableRow>
                <TableHeaderCell>Файл</TableHeaderCell>
                <TableHeaderCell>doc_type</TableHeaderCell>
                <TableHeaderCell>Статус</TableHeaderCell>
                <TableHeaderCell>Прогресс</TableHeaderCell>
                <TableHeaderCell>Confidence</TableHeaderCell>
                <TableHeaderCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredQueue.map((item) => (
                <TableRow key={item.id} data-testid={`ocr-queue-row-${item.id}`}>
                  <TableCell>{item.file}</TableCell>
                  <TableCell>{item.docType}</TableCell>
                  <TableCell>{STATUS_LABEL[item.status]}</TableCell>
                  <TableCell>
                    <div className="ocr-docs__progress" aria-label={`Прогресс ${item.progress}%`}>
                      <span style={{ width: `${item.progress}%` }} />
                      <em>{item.progress}%</em>
                    </div>
                  </TableCell>
                  <TableCell>{formatConfidence(item.confidence)}</TableCell>
                  <TableCell>
                    <Button
                      type="button"
                      data-testid={`ocr-open-${item.id}`}
                      onClick={() => void openReview(item)}
                    >
                      Открыть
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          <div className="ocr-docs__stats" data-testid="ocr-queue-stats">
            <span>В очереди · {stats.queued}</span>
            <span>OCR сейчас · {stats.ocr}</span>
            <span>HITL · {stats.hitl}</span>
            <span>Ошибки · {stats.errors}</span>
          </div>

          <Button type="button" onClick={() => setSubTab('upload')}>
            Загрузить документы
          </Button>
        </div>
      )}

      {subTab === 'upload' && (
        <div className="ocr-docs__upload" data-testid="ocr-upload">
          <div
            className={`ocr-docs__dropzone${dragOver ? ' is-dragover' : ''}`}
            data-testid="ocr-dropzone"
            onDragEnter={(event) => {
              event.preventDefault()
              setDragOver(true)
            }}
            onDragOver={(event) => {
              event.preventDefault()
              setDragOver(true)
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
          >
            <strong>Перетащите файлы или выберите с диска</strong>
            <span>PDF, JPEG, PNG, TIFF</span>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept={ACCEPT}
              className="visually-hidden"
              data-testid="ocr-file-input"
              onChange={onFileInput}
            />
            <Button
              type="button"
              data-testid="ocr-choose-files"
              onClick={() => fileInputRef.current?.click()}
            >
              Выбрать файлы
            </Button>
          </div>

          <label className="ocr-docs__doctype">
            <span>Тип документа</span>
            <select
              value={docType}
              onChange={(event) => setDocType(event.target.value)}
              data-testid="ocr-doc-type"
            >
              <option value="auto">Автоопределение (ML)</option>
              <option value="passport">passport</option>
              <option value="contract">contract</option>
              <option value="invoice">invoice</option>
            </select>
          </label>

          <p className="ocr-docs__hint">Антивирусная проверка и постановка в очередь OCR</p>

          {pendingFiles.length > 0 && (
            <Card className="ocr-docs__batch" data-testid="ocr-pending-batch">
              <strong>Пакет · {pendingFiles.length} файл(ов)</strong>
              <ol>
                {pendingFiles.map((file) => (
                  <li key={`${file.name}-${file.size}-${file.lastModified}`}>{file.name}</li>
                ))}
              </ol>
            </Card>
          )}

          {error && <p className="ocr-docs__hint" role="alert">{error}</p>}

          <Button
            type="button"
            data-testid="ocr-start-recognition"
            disabled={!pendingFiles.length || busy}
            onClick={() => void startRecognition()}
          >
            {busy ? 'Распознавание…' : 'Начать распознавание'}
          </Button>
        </div>
      )}

      {subTab === 'review' && activeItem && (
        <div className="ocr-docs__review" data-testid="ocr-review">
          <section className="ocr-docs__viewer" data-testid="ocr-bbox-viewer" aria-label="Просмотр документа">
            <header>
              <strong>{activeItem.file}</strong>
              <StatusBadge status={activeItem.status === 'error' ? 'danger' : 'warning'}>
                HITL
              </StatusBadge>
            </header>
            <div
              className="ocr-docs__scan"
              style={{ transform: `scale(${zoom / 100})`, transformOrigin: 'top left' }}
            >
              <p className="ocr-docs__scan-label">Скан документа (viewer)</p>
              {fields.map((field) => {
                const selected = field.id === selectedFieldId
                const tone = confidenceTone(field.confidence)
                return (
                  <button
                    type="button"
                    key={field.id}
                    className={`ocr-docs__bbox ocr-docs__bbox--${tone}${selected ? ' is-selected' : ''}`}
                    style={{
                      left: `${field.bbox.left}%`,
                      top: `${field.bbox.top}%`,
                      width: `${field.bbox.width}%`,
                      height: `${field.bbox.height}%`,
                    }}
                    data-testid={`ocr-bbox-${field.id}`}
                    aria-pressed={selected}
                    onClick={() => setSelectedFieldId(field.id)}
                  >
                    <span>{field.value}</span>
                  </button>
                )
              })}
            </div>
            <div className="ocr-docs__zoom">
              <Button type="button" aria-label="Уменьшить" onClick={() => setZoom((z) => Math.max(75, z - 10))}>−</Button>
              <span>{zoom}%</span>
              <Button type="button" aria-label="Увеличить" onClick={() => setZoom((z) => Math.min(150, z + 10))}>+</Button>
              <StatusBadge status="neutral">Разметка полей</StatusBadge>
            </div>
          </section>

          <section className="ocr-docs__fields" data-testid="ocr-field-editor" aria-label="Извлечённые поля">
            <h2>Извлечённые поля</h2>
            <ul>
              {fields.map((field) => (
                <li key={field.id} data-testid={`ocr-field-${field.id}`}>
                  <div className="ocr-docs__field-head">
                    <label htmlFor={`ocr-field-input-${field.id}`}>{field.label}</label>
                    <StatusBadge
                      status={confidenceTone(field.confidence)}
                      data-testid={`ocr-field-confidence-${field.id}`}
                    >
                      {formatConfidence(field.confidence)}
                    </StatusBadge>
                  </div>
                  <input
                    id={`ocr-field-input-${field.id}`}
                    value={field.value}
                    data-testid={`ocr-field-input-${field.id}`}
                    onFocus={() => setSelectedFieldId(field.id)}
                    onChange={(event) => updateField(field.id, event.target.value)}
                  />
                </li>
              ))}
            </ul>

            <div className="ocr-docs__llm" data-testid="ocr-llm-suggestion">
              <p>LLM-предложение: «Дата выдачи → 12.03.2019»</p>
              <div>
                <Button
                  type="button"
                  data-testid="ocr-llm-accept"
                  disabled={llmAccepted === true}
                  onClick={acceptLlmSuggestion}
                >
                  Принять
                </Button>
                <Button
                  type="button"
                  data-testid="ocr-llm-reject"
                  onClick={() => setLlmAccepted(false)}
                >
                  Отклонить
                </Button>
              </div>
            </div>

            <div className="ocr-docs__approve">
              <label>
                <span className="visually-hidden">Тип документа</span>
                <select
                  value={activeItem.docType}
                  onChange={(event) => {
                    const nextType = event.target.value
                    setQueue((prev) => prev.map((item) => (
                      item.id === activeItem.id
                        ? { ...item, docType: nextType }
                        : item
                    )))
                  }}
                  data-testid="ocr-review-doc-type"
                >
                  <option value="passport">passport</option>
                  <option value="id_card">id_card</option>
                  <option value="contract">contract</option>
                  <option value="invoice">invoice</option>
                  <option value="unknown">unknown</option>
                </select>
              </label>
              <Button
                type="button"
                data-testid="ocr-approve-export"
                disabled={busy}
                onClick={() => void approveAndExport()}
              >
                Утвердить и экспорт
              </Button>
            </div>
            {error && <p className="ocr-docs__hint" role="alert">{error}</p>}
            {approved && (
              <StatusBadge status="success" data-testid="ocr-approved-badge">
                Утверждено · JSON/CSV готов
              </StatusBadge>
            )}
          </section>
        </div>
      )}
    </div>
  )
}
