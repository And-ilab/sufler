import {
  useCallback,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from 'react'
import { Button, Card, StatusBadge, Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from '../../components'
import './OcrDocumentsPanel.css'

export type OcrSubTab = 'queue' | 'upload' | 'review'

export interface OcrField {
  id: string
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

const INITIAL_QUEUE: OcrQueueItem[] = [
  {
    id: 'q-passport',
    file: 'passport_ivanov.pdf',
    docType: 'passport',
    status: 'review',
    progress: 100,
    confidence: 0.92,
  },
  {
    id: 'q-contract',
    file: 'contract_2026-014.pdf',
    docType: 'contract',
    status: 'ocr',
    progress: 64,
    confidence: null,
  },
  {
    id: 'q-statement',
    file: 'statement_mar.zip',
    docType: 'statement',
    status: 'queued',
    progress: 0,
    confidence: null,
  },
  {
    id: 'q-invoice',
    file: 'invoice_scan.tiff',
    docType: 'invoice',
    status: 'error',
    progress: 100,
    confidence: 0.41,
  },
]

const PASSPORT_FIELDS: OcrField[] = [
  {
    id: 'fio',
    label: 'ФИО',
    value: 'Иванов Иван Иванович',
    confidence: 0.96,
    bbox: { left: 12, top: 28, width: 52, height: 7 },
  },
  {
    id: 'series',
    label: 'Серия паспорта',
    value: 'MP',
    confidence: 0.88,
    bbox: { left: 12, top: 40, width: 18, height: 7 },
  },
  {
    id: 'number',
    label: 'Номер',
    value: '4123456',
    confidence: 0.72,
    bbox: { left: 32, top: 40, width: 28, height: 7 },
  },
  {
    id: 'issued',
    label: 'Дата выдачи',
    value: '12.03.2019',
    confidence: 0.54,
    bbox: { left: 12, top: 52, width: 30, height: 7 },
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

function fieldsForDoc(file: string, docType: string): OcrField[] {
  if (docType === 'passport' || file.toLowerCase().includes('passport')) {
    return PASSPORT_FIELDS.map((field) => ({ ...field }))
  }
  return [
    {
      id: 'title',
      label: 'Заголовок',
      value: file.replace(/\.[^.]+$/, ''),
      confidence: 0.9,
      bbox: { left: 10, top: 18, width: 60, height: 8 },
    },
    {
      id: 'amount',
      label: 'Сумма',
      value: '1 500,00',
      confidence: 0.78,
      bbox: { left: 10, top: 36, width: 28, height: 7 },
    },
  ]
}

export interface OcrDocumentsPanelProps {
  initialSubTab?: OcrSubTab
}

export function OcrDocumentsPanel({
  initialSubTab = 'queue',
}: OcrDocumentsPanelProps) {
  const [subTab, setSubTab] = useState<OcrSubTab>(initialSubTab)
  const [queue, setQueue] = useState<OcrQueueItem[]>(INITIAL_QUEUE)
  const [statusFilter, setStatusFilter] = useState('all')
  const [typeFilter, setTypeFilter] = useState('any')
  const [search, setSearch] = useState('')
  const [pendingFiles, setPendingFiles] = useState<string[]>([])
  const [docType, setDocType] = useState('auto')
  const [dragOver, setDragOver] = useState(false)
  const [activeId, setActiveId] = useState('q-passport')
  const [fields, setFields] = useState<OcrField[]>(PASSPORT_FIELDS)
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>('fio')
  const [zoom, setZoom] = useState(100)
  const [approved, setApproved] = useState(false)
  const [llmAccepted, setLlmAccepted] = useState<boolean | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const activeItem = queue.find((item) => item.id === activeId) ?? queue[0]

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

  const openReview = useCallback((item: OcrQueueItem) => {
    setActiveId(item.id)
    const nextFields = fieldsForDoc(item.file, item.docType)
    setFields(nextFields)
    setSelectedFieldId(nextFields[0]?.id ?? null)
    setApproved(false)
    setLlmAccepted(null)
    setSubTab('review')
  }, [])

  const addFiles = useCallback((fileList: FileList | File[]) => {
    const names = Array.from(fileList).map((file) => file.name)
    if (!names.length) return
    setPendingFiles((prev) => [...prev, ...names])
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

  const startRecognition = () => {
    if (!pendingFiles.length) return
    const created: OcrQueueItem[] = pendingFiles.map((file, index) => {
      const inferred =
        docType !== 'auto'
          ? docType
          : file.toLowerCase().includes('passport')
            ? 'passport'
            : file.toLowerCase().includes('contract')
              ? 'contract'
              : 'unknown'
      return {
        id: `upload-${Date.now()}-${index}`,
        file,
        docType: inferred,
        status: 'review' as const,
        progress: 100,
        confidence: 0.91,
      }
    })
    setQueue((prev) => [...created, ...prev])
    setPendingFiles([])
    openReview(created[0])
  }

  const updateField = (id: string, value: string) => {
    setFields((prev) => prev.map((field) => (
      field.id === id ? { ...field, value } : field
    )))
    setApproved(false)
  }

  const acceptLlmSuggestion = () => {
    setFields((prev) => prev.map((field) => (
      field.id === 'issued' ? { ...field, value: '12.03.2019', confidence: 0.91 } : field
    )))
    setLlmAccepted(true)
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
                      onClick={() => openReview(item)}
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
            <span>PDF, JPEG, PNG, TIFF · пакет ZIP</span>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.jpg,.jpeg,.png,.tiff,.tif,.zip"
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
                {pendingFiles.map((name) => (
                  <li key={name}>{name}</li>
                ))}
              </ol>
            </Card>
          )}

          <Button
            type="button"
            data-testid="ocr-start-recognition"
            disabled={!pendingFiles.length}
            onClick={startRecognition}
          >
            Начать распознавание
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
                onClick={() => {
                  setApproved(true)
                  setQueue((prev) => prev.map((item) => (
                    item.id === activeItem.id
                      ? { ...item, status: 'done', confidence: 0.95, progress: 100 }
                      : item
                  )))
                }}
              >
                Утвердить и экспорт
              </Button>
            </div>
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
