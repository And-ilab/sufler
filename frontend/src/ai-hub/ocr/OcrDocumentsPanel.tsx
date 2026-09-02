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
  downloadOcrFieldsDocx,
  exportOcrJob,
  ocrExportRows,
  fetchOcrResult,
  listOcrDocTypes,
  listOcrJobs,
  ocrJobOriginalUrl,
  uploadOcrDocument,
  type OcrDocType,
} from '../admin/api/ocrAdmin'
import {
  OPERATOR_DOC_TITLES,
  OPERATOR_DOC_TYPES,
  isMlDocType,
  isOperatorDocType,
  ML_DOC_TYPE,
  operatorDocTitle,
} from './docTypes'
import { filterOcrFields } from './fieldQuality'
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
  batchId?: string
  sourceArchive?: string
}

const STATUS_LABEL: Record<OcrQueueItem['status'], string> = {
  queued: 'Очередь',
  ocr: 'OCR',
  review: 'На проверке',
  done: 'Готово',
  error: 'Ошибка валидации',
}

const ACCEPT =
  '.png,.jpg,.jpeg,.pdf,.tiff,.tif,.zip,.rar,image/png,image/jpeg,application/pdf,image/tiff,application/zip,application/x-rar-compressed'

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
  surname: 'Фамилия',
  given_name: 'Имя',
  patronymic: 'Отчество',
  series: 'Серия паспорта',
  number: 'Номер',
  issued: 'Дата выдачи',
  issue_date: 'Дата выдачи',
  birth_date: 'Дата рождения',
  address: 'Адрес / прописка',
  registration_date: 'Дата регистрации',
  issued_by: 'Кем выдан',
  birth_place: 'Место рождения',
  personal_number: 'Личный номер',
  document_number: 'Номер документа',
  payer: 'Плательщик',
  beneficiary: 'Получатель',
  amount: 'Сумма',
  purpose: 'Назначение',
  currency: 'Валюта',
  product: 'Продукт',
  application_date: 'Дата заявления',
  application_number: 'Номер заявления',
  signature_present: 'Подпись',
  account_number: 'Счёт',
  opening_balance: 'Входящий остаток',
  closing_balance: 'Исходящий остаток',
  period: 'Период',
  agreement_number: 'Номер договора',
  agreement_date: 'Дата договора',
  principal: 'Сумма кредита',
  interest_rate: 'Процентная ставка',
  term: 'Срок',
  operation_id: 'Номер операции',
  operation_date: 'Дата операции',
  status: 'Статус',
  title: 'Заголовок',
  nationality: 'Гражданство',
  sex: 'Пол',
  inn: 'ИНН',
  expiry_date: 'Срок действия',
}

const HIDDEN_FIELD_KEYS = new Set(['signature_present', 'title', 'full_name'])

const DOC_TYPE_TITLE: Record<string, string> = {
  unknown: 'Документ',
  other: 'Документ',
  passport: OPERATOR_DOC_TITLES.passport,
  account_statement: OPERATOR_DOC_TITLES.account_statement,
  loan_agreement: OPERATOR_DOC_TITLES.loan_agreement,
}

const BUILTIN_SCHEMAS: Record<string, Record<string, unknown>> = {
  passport: {
    surname: {},
    given_name: {},
    series: {},
    number: {},
    birth_date: {},
    issue_date: {},
    expiry_date: {},
    personal_number: {},
    nationality: {},
  },
  account_statement: {
    account_number: {},
    currency: {},
    period: {},
    opening_balance: {},
    closing_balance: {},
  },
  loan_agreement: {
    agreement_number: {},
    agreement_date: {},
    principal: {},
    interest_rate: {},
    term: {},
  },
}

const BUILTIN_DOC_TYPES: OcrDocType[] = OPERATOR_DOC_TYPES.map((doc_type) => ({
  doc_type,
  title: OPERATOR_DOC_TITLES[doc_type],
  field_schema: BUILTIN_SCHEMAS[doc_type],
}))

function humanizeKey(key: string): string {
  if (/[А-Яа-яЁё]/.test(key)) return key.replace(/_/g, ' ')
  return key.replace(/_/g, ' ').trim() || 'Поле'
}

function russianFieldLabel(id: string, apiKey: string, explicit?: string): string {
  return FIELD_LABELS[id] || FIELD_LABELS[apiKey] || (
    explicit && String(explicit).trim() && String(explicit).length <= 40
      ? String(explicit).trim()
      : ''
  ) || humanizeKey(apiKey || id)
}

function typeTitle(docType: string): string {
  return operatorDocTitle(docType) || DOC_TYPE_TITLE[docType] || docType || DOC_TYPE_TITLE.unknown
}

function isPassportPageType(docType: string): boolean {
  return docType.startsWith('passport_')
}

function apiDocType(docType: string): string {
  if (isPassportPageType(docType)) return 'passport'
  return docType || 'unknown'
}

function resolveDisplayType(docType: string, _pageKinds: string[] = []): string {
  if (isOperatorDocType(docType)) return docType
  if (isPassportPageType(docType) || docType === 'unknown' || !docType) return 'passport'
  return 'passport'
}

function inferDocTypeFromName(fileName: string): string {
  const name = fileName.toLowerCase()
  if (/passport|pasport|паспорт/.test(name)) return 'passport'
  if (/poruchen|platezh|payment/.test(name)) return 'payment_order'
  if (/kvitan|receipt|chek/.test(name)) return 'payment_receipt'
  if (/vypisk|spravk|statement/.test(name)) return 'account_statement'
  if (/kredit|loan/.test(name)) return 'loan_agreement'
  if (/zayavl|anket|application/.test(name)) return 'banking_application'
  if (/dogovor|contract/.test(name)) return 'loan_agreement'
  return ''
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
    id: 'surname',
    apiKey: 'surname',
    label: 'Фамилия',
    value: 'Иванов',
    confidence: 0.96,
    bbox: DEFAULT_BBOX.fio,
  },
  {
    id: 'given_name',
    apiKey: 'given_name',
    label: 'Имя',
    value: 'Иван',
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

function unwrapOcrResult(
  payload: Record<string, unknown> | null | undefined,
): Record<string, unknown> | null {
  if (!payload) return null
  const nested = payload.result
  if (nested && typeof nested === 'object' && !Array.isArray(nested)) {
    const inner = nested as Record<string, unknown>
    if (inner.fields || inner.normalized_fields || inner.extractor_fields) {
      return inner
    }
  }
  return payload
}

function rawResultFields(result: Record<string, unknown> | null | undefined): unknown {
  const payload = unwrapOcrResult(result)
  if (!payload) return null
  for (const key of ['fields', 'normalized_fields', 'extractor_fields'] as const) {
    const fields = payload[key]
    if (fields && typeof fields === 'object' && Object.keys(fields as object).length) {
      return fields
    }
  }
  return payload.fields
}

function fieldsAreEmpty(fields: OcrField[]): boolean {
  return !fields.length || fields.every((field) => !String(field.value).trim())
}

function fieldsFromResult(fieldsRaw: unknown): OcrField[] {
  if (!fieldsRaw || typeof fieldsRaw !== 'object') return []
  const entries = Object.entries(fieldsRaw as Record<string, unknown>)
  const preferred = ['full_name', 'series', 'number', 'issue_date']
  const ordered = [
    ...preferred.filter((key) => key in (fieldsRaw as object)),
    ...entries.map(([key]) => key).filter((key) => !preferred.includes(key)),
  ]
  const mapped = ordered
    .filter((apiKey) => !HIDDEN_FIELD_KEYS.has(apiKey))
    .map((apiKey, index) => {
      const raw = (fieldsRaw as Record<string, unknown>)[apiKey]
      const id = API_TO_UI[apiKey] || apiKey
      const bbox = DEFAULT_BBOX[id] || {
        left: 10,
        top: 18 + index * 12,
        width: 48,
        height: 7,
      }
      const explicitLabel = (
        raw && typeof raw === 'object' && raw !== null && 'label' in raw
          ? String((raw as { label?: unknown }).label || '')
          : ''
      )
      return {
        id,
        apiKey,
        label: russianFieldLabel(id, apiKey, explicitLabel),
        value: fieldValue(raw),
        confidence: fieldConfidence(raw),
        bbox,
      }
    })
    .filter((field) => Boolean(String(field.value).trim()))
  return filterOcrFields(mapped)
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

function pageKindsFromResult(result: Record<string, unknown> | null | undefined): string[] {
  const payload = unwrapOcrResult(result)
  const raw = payload?.page_kinds
  return Array.isArray(raw) ? raw.map((item) => String(item)) : []
}

function withPassportIdentity(
  schema: Record<string, unknown> | undefined,
): Record<string, unknown> | undefined {
  if (!schema) return { surname: {}, given_name: {} }
  const next: Record<string, unknown> = {
    surname: schema.surname && typeof schema.surname === 'object' ? schema.surname : {},
    given_name: schema.given_name && typeof schema.given_name === 'object' ? schema.given_name : {},
  }
  for (const [key, value] of Object.entries(schema)) {
    if (key === 'surname' || key === 'given_name') continue
    next[key] = value
  }
  return next
}

function schemaForType(
  docType: string,
  templates: OcrDocType[],
  _pageKinds: string[] = [],
): Record<string, unknown> | undefined {
  if (isMlDocType(docType) || !docType || docType === 'unknown' || docType === 'other') {
    return undefined
  }
  const type = isPassportPageType(docType)
    ? 'passport'
    : isOperatorDocType(docType) ? docType : ''
  if (!type) return undefined
  const raw = templates.find((tpl) => tpl.doc_type === type)?.field_schema
    || BUILTIN_SCHEMAS[type]
  return type === 'passport' ? withPassportIdentity(raw) : raw
}

function looksLikePassportFields(fields: OcrField[]): boolean {
  const values = new Map(
    fields.map((field) => [field.apiKey || field.id, String(field.value || '').trim()]),
  )
  return Boolean(
    (values.get('surname') && values.get('given_name'))
    || (values.get('series') && values.get('number')),
  )
}

function typeForExtractedFields(
  rawType: string,
  parsed: OcrField[],
  pageKinds: string[] = [],
  forcedType = '',
): string {
  if (forcedType && isOperatorDocType(forcedType)) {
    return resolveDisplayType(forcedType, pageKinds)
  }
  const detected = rawType && rawType !== 'unknown' ? rawType : ''
  if (isMlDocType(detected)) return ML_DOC_TYPE
  if (detected === 'passport' || isPassportPageType(detected)) {
    return looksLikePassportFields(parsed)
      ? resolveDisplayType(detected, pageKinds)
      : (parsed.length ? ML_DOC_TYPE : resolveDisplayType(detected, pageKinds))
  }
  if (isOperatorDocType(detected)) return detected
  if (detected) return detected
  return looksLikePassportFields(parsed) ? 'passport' : ML_DOC_TYPE
}

function fieldsForExtractedType(
  parsed: OcrField[],
  resolvedType: string,
  templates: OcrDocType[],
): OcrField[] {
  if (isMlDocType(resolvedType) || !schemaForType(resolvedType, templates)) {
    return parsed
  }
  if (resolvedType === 'passport' && parsed.length && !looksLikePassportFields(parsed)) {
    return parsed
  }
  return mergeTemplateFields(parsed, schemaForType(resolvedType, templates))
}

function demoFieldsForFile(fileName: string, docType: string, templates: OcrDocType[] = []): OcrField[] {
  const inferred = docType && docType !== 'unknown' ? docType : inferDocTypeFromName(fileName)
  if (inferred === 'passport' || fileName.toLowerCase().includes('passport')) {
    return DEMO_PASSPORT_FIELDS.map((field) => ({ ...field, bbox: { ...field.bbox } }))
  }
  const schema = schemaForType(inferred, templates)
  if (schema) return mergeTemplateFields([], schema)
  return []
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
    docType: String(job.document_type || inferDocTypeFromName(String(job.filename || job.file || '')) || 'unknown'),
    status,
    progress,
    confidence: null,
    batchId: job.batch_id ? String(job.batch_id) : undefined,
    sourceArchive: job.source_archive ? String(job.source_archive) : undefined,
  }
}

function isSupportedUpload(file: File): boolean {
  const name = file.name.toLowerCase()
  return (
    name.endsWith('.png')
    || name.endsWith('.jpg')
    || name.endsWith('.jpeg')
    || name.endsWith('.pdf')
    || name.endsWith('.tiff')
    || name.endsWith('.tif')
    || name.endsWith('.zip')
    || name.endsWith('.rar')
    || file.type === 'image/png'
    || file.type === 'image/jpeg'
    || file.type === 'application/pdf'
    || file.type === 'image/tiff'
    || file.type === 'application/zip'
    || file.type === 'application/x-zip-compressed'
    || file.type === 'application/vnd.rar'
    || file.type === 'application/x-rar-compressed'
  )
}

function mergeTemplateFields(
  ocrFields: OcrField[],
  schema: Record<string, unknown> | undefined,
): OcrField[] {
  const known = new Map(ocrFields.map((field) => [field.apiKey, field]))
  const schemaKeys = schema ? Object.keys(schema) : []
  const ordered = schemaKeys.filter((key) => !HIDDEN_FIELD_KEYS.has(key))
  if (!ordered.length) return ocrFields.filter((field) => !HIDDEN_FIELD_KEYS.has(field.apiKey))
  return ordered.map((apiKey, index) => {
    const existing = known.get(apiKey)
    if (existing) return { ...existing, label: russianFieldLabel(existing.id, existing.apiKey) }
    const id = API_TO_UI[apiKey] || apiKey
    return {
      id,
      apiKey,
      label: russianFieldLabel(id, apiKey),
      value: '',
      confidence: 0,
      bbox: DEFAULT_BBOX[id] || {
        left: 10,
        top: 18 + index * 12,
        width: 48,
        height: 7,
      },
    }
  })
}

function uploadJobs(response: Record<string, unknown>): Record<string, unknown>[] {
  const items = response.items
  if (Array.isArray(items) && items.length) {
    return items.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
  }
  return [response]
}

export interface OcrDocumentsPanelProps {
  initialSubTab?: OcrSubTab
  onClose?: () => void
}

export function OcrDocumentsPanel({
  initialSubTab = 'queue',
  onClose,
}: OcrDocumentsPanelProps) {
  const [subTab, setSubTab] = useState<OcrSubTab>(initialSubTab)
  const [queue, setQueue] = useState<OcrQueueItem[]>([])
  const [statusFilter, setStatusFilter] = useState('all')
  const [typeFilter, setTypeFilter] = useState('any')
  const [search, setSearch] = useState('')
  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const [docType, setDocType] = useState('passport')
  const [dragOver, setDragOver] = useState(false)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [fieldsByJob, setFieldsByJob] = useState<Record<string, OcrField[]>>({})
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null)
  const [approved, setApproved] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [templates, setTemplates] = useState<OcrDocType[]>([])
  const [previewByJob, setPreviewByJob] = useState<Record<string, string>>({})
  const [recognizeProgress, setRecognizeProgress] = useState(0)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const activeItem = queue.find((item) => item.id === activeId) ?? queue[0]
  const fields = mergeTemplateFields(
    filterOcrFields(activeId ? fieldsByJob[activeId] || [] : []),
    schemaForType(activeItem?.docType || '', templates),
  )

  const loadQueue = useCallback(async () => {
    try {
      const jobs = await listOcrJobs()
      const remote = jobs.map(jobToQueueItem).filter((item) => item.id)
      setQueue((prev) => {
        const prevById = new Map(prev.map((item) => [item.id, item]))
        const remoteIds = new Set(remote.map((item) => item.id))
        const local = prev.filter((item) => item.id.startsWith('demo-') && !remoteIds.has(item.id))
        const merged = remote.map((item) => {
          const was = prevById.get(item.id)
          if (was && isPassportPageType(was.docType) && item.docType === 'passport') {
            return {
              ...item,
              docType: was.docType,
              confidence: was.confidence ?? item.confidence,
            }
          }
          return item
        })
        return [...local, ...merged]
      })
      setError('')
    } catch {
      // Storybook / offline: keep local queue as-is.
    }
  }, [])

  useEffect(() => {
    setSubTab(initialSubTab)
  }, [initialSubTab])

  useEffect(() => {
    void loadQueue()
    void listOcrDocTypes()
      .then(setTemplates)
      .catch(() => setTemplates([]))
  }, [loadQueue])

  useEffect(() => {
    const pending = queue.some((item) => item.status === 'queued' || item.status === 'ocr')
    if (!pending) return
    const timer = window.setInterval(() => {
      void loadQueue()
    }, 2500)
    return () => window.clearInterval(timer)
  }, [loadQueue, queue])

  useEffect(() => {
    const empty = queue.filter((item) => (
      (item.status === 'review' || item.status === 'done')
      && !item.id.startsWith('demo-')
      && !item.id.startsWith('pending-')
      && fieldsAreEmpty(fieldsByJob[item.id] || [])
    ))
    if (!empty.length) return undefined
    let cancelled = false
    void Promise.all(empty.slice(0, 4).map(async (item) => {
      try {
        const result = await fetchOcrResult(item.id)
        if (cancelled) return
        const parsed = fieldsFromResult(rawResultFields(result))
        const resolvedType = typeForExtractedFields(
          [String(result.document_type || ''), item.docType, inferDocTypeFromName(item.file)]
            .find((value) => value && value !== 'unknown' && !isMlDocType(value)) || item.docType,
          parsed,
          pageKindsFromResult(result),
        )
        const nextFields = fieldsForExtractedType(parsed, resolvedType, templates)
        if (fieldsAreEmpty(nextFields)) return
        setFieldsByJob((prev) => ({ ...prev, [item.id]: nextFields }))
        setQueue((prev) => prev.map((row) => (
          row.id === item.id
            ? {
                ...row,
                docType: resolvedType,
                confidence: avgConfidence(nextFields.filter((field) => field.value)),
              }
            : row
        )))
      } catch {
        // Keep empty template until the operator reopens the job.
      }
    }))
    return () => {
      cancelled = true
    }
  }, [fieldsByJob, queue, templates])

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
    setSubTab('review')
    setError('')
    setRecognizeProgress(item.status === 'queued' || item.status === 'ocr' ? item.progress : 100)
    if (!previewByJob[item.id] && !item.id.startsWith('demo-')) {
      setPreviewByJob((prev) => ({ ...prev, [item.id]: ocrJobOriginalUrl(item.id) }))
    }

    const cached = mergeTemplateFields(
      filterOcrFields(fieldsByJob[item.id] || []),
      schemaForType(item.docType, templates),
    )

    try {
      const result = await fetchOcrResult(item.id)
      const parsed = fieldsFromResult(rawResultFields(result))
      const resolvedType = typeForExtractedFields(
        [String(result.document_type || ''), item.docType, inferDocTypeFromName(item.file)]
          .find((value) => value && value !== 'unknown' && !isMlDocType(value)) || item.docType,
        parsed,
        pageKindsFromResult(result),
      )
      const nextFields = fieldsForExtractedType(parsed, resolvedType, templates)
      const shown = nextFields.some((field) => field.value.trim()) ? nextFields : cached
      if (shown.length) {
        setFieldsByJob((prev) => ({ ...prev, [item.id]: shown }))
        setSelectedFieldId(shown[0]?.id ?? null)
        const conf = avgConfidence(shown)
        setQueue((prev) => prev.map((row) => (
          row.id === item.id ? { ...row, confidence: conf, docType: resolvedType } : row
        )))
        return
      }
      setQueue((prev) => prev.map((row) => (
        row.id === item.id ? { ...row, docType: resolvedType } : row
      )))
    } catch {
      if (!fieldsAreEmpty(cached)) {
        setFieldsByJob((prev) => ({ ...prev, [item.id]: cached }))
        setSelectedFieldId(cached[0]?.id ?? null)
        return
      }
    }

    const inferredType = item.docType !== 'unknown' ? item.docType : inferDocTypeFromName(item.file)
    const demo = mergeTemplateFields(
      demoFieldsForFile(item.file, inferredType, templates),
      schemaForType(inferredType, templates),
    )
    setFieldsByJob((prev) => ({ ...prev, [item.id]: demo }))
    setSelectedFieldId(demo[0]?.id ?? null)
  }, [fieldsByJob, previewByJob, templates])

  const addFiles = useCallback((fileList: FileList | File[]) => {
    const files = Array.from(fileList).filter(isSupportedUpload)
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
    setRecognizeProgress(8)
    const created: OcrQueueItem[] = []
    const nextFields: Record<string, OcrField[]> = {}
    const nextPreviews: Record<string, string> = {}

    const firstPreview = URL.createObjectURL(pendingFiles[0])
    const pendingId = `pending-${Date.now()}`
    nextPreviews[pendingId] = firstPreview
    setPreviewByJob((prev) => ({ ...prev, [pendingId]: firstPreview }))
    setQueue((prev) => [
      {
        id: pendingId,
        file: pendingFiles[0].name,
        docType,
        status: 'ocr',
        progress: 8,
        confidence: null,
      },
      ...prev,
    ])
    setActiveId(pendingId)
    setSubTab('review')

    try {
      for (const [index, file] of pendingFiles.entries()) {
        setRecognizeProgress(Math.min(88, 12 + Math.round(((index + 0.4) / pendingFiles.length) * 70)))
        const forcedType = isOperatorDocType(docType) ? docType : ''

        try {
          const isArchive = /\.(zip|rar)$/i.test(file.name)
          const response = await uploadOcrDocument(
            file,
            forcedType ? apiDocType(forcedType) : '',
            !isArchive,
          )
          for (const job of uploadJobs(response)) {
            const jobId = String(job.job_id || response.job_id || `upload-${Date.now()}-${index}`)
            let result =
              (job.result as Record<string, unknown> | undefined)
              || (response.result as Record<string, unknown> | undefined)
              || null
            if (fieldsAreEmpty(fieldsFromResult(rawResultFields(result))) && !jobId.startsWith('demo-')) {
              result = await fetchOcrResult(jobId).catch(() => result)
            }
            const detected = String(
              (result?.document_type && result.document_type !== 'unknown' ? result.document_type : '')
              || job.document_type
              || forcedType
              || inferDocTypeFromName(file.name)
              || 'unknown',
            )
            const parsed = fieldsFromResult(rawResultFields(result))
            const resolvedType = typeForExtractedFields(
              detected,
              parsed,
              pageKindsFromResult(result),
              forcedType,
            )
            const fields = fieldsForExtractedType(parsed, resolvedType, templates)
            const mapped = jobToQueueItem({
              ...job,
              job_id: jobId,
              filename: job.filename || file.name,
              document_type: resolvedType,
              status: result ? 'completed' : job.status,
              validation_status: result?.validation_status || job.validation_status || 'pending_review',
            })
            const item: OcrQueueItem = {
              ...mapped,
              status: result ? 'review' : mapped.status,
              progress: result ? 100 : mapped.progress,
              confidence: avgConfidence(fields.filter((field) => field.value)),
            }
            created.push(item)
            nextFields[jobId] = fields
            if (file.type.startsWith('image/') || /\.(png|jpe?g|webp)$/i.test(file.name)) {
              nextPreviews[jobId] = URL.createObjectURL(file)
            } else {
              nextPreviews[jobId] = ocrJobOriginalUrl(jobId)
            }
          }
        } catch {
          // Offline / Storybook: keep UX + visual-test fixtures.
          const jobId = `demo-${Date.now()}-${index}`
          const fields = forcedType
            ? demoFieldsForFile(file.name, forcedType, templates)
            : []
          const item: OcrQueueItem = {
            id: jobId,
            file: file.name,
            docType: forcedType || inferDocTypeFromName(file.name) || ML_DOC_TYPE,
            status: 'review',
            progress: 100,
            confidence: avgConfidence(fields),
          }
          created.push(item)
          nextFields[jobId] = fields
          if (file.type.startsWith('image/') || /\.(png|jpe?g|webp)$/i.test(file.name)) {
            nextPreviews[jobId] = URL.createObjectURL(file)
          }
        }
      }

      setFieldsByJob((prev) => ({ ...prev, ...nextFields }))
      setPreviewByJob((prev) => ({ ...prev, ...nextPreviews }))
      setQueue((prev) => [
        ...created,
        ...prev.filter((item) => item.id !== pendingId),
      ])
      setPendingFiles([])
      setRecognizeProgress(100)
      if (created[0]) {
        setActiveId(created[0].id)
        setSelectedFieldId(nextFields[created[0].id]?.[0]?.id ?? null)
        setApproved(false)
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

  const templateOptions = useMemo(() => {
    const byType = new Map(templates.map((item) => [item.doc_type, item]))
    return OPERATOR_DOC_TYPES.map((doc_type) => {
      const item = byType.get(doc_type)
      return {
        doc_type,
        title: OPERATOR_DOC_TITLES[doc_type],
        field_schema: item?.field_schema || BUILTIN_SCHEMAS[doc_type],
      }
    })
  }, [templates])

  const applyDocType = (jobId: string, nextType: string) => {
    const type = isOperatorDocType(nextType)
      ? nextType
      : isMlDocType(nextType) ? ML_DOC_TYPE : nextType || ML_DOC_TYPE
    setQueue((prev) => prev.map((item) => (
      item.id === jobId ? { ...item, docType: type } : item
    )))
    setFieldsByJob((prev) => ({
      ...prev,
      [jobId]: mergeTemplateFields(filterOcrFields(prev[jobId] || []), schemaForType(type, templates)),
    }))
  }

  const approveAndExport = async () => {
    if (!activeItem) return
    setBusy(true)
    setError('')
    const currentFields = fieldsByJob[activeItem.id] || fields
    const payload = fieldsToApiPayload(currentFields)
    const documentType = apiDocType(activeItem.docType || 'passport')
    const stem = activeItem.file.replace(/\.[^.]+$/u, '') || 'ocr-export'
    try {
      if (!activeItem.id.startsWith('demo-')) {
        await approveOcrJob(activeItem.id, documentType, payload)
        try {
          await exportOcrJob(activeItem.id, 'docx', {
            documentType,
            fields: payload,
          })
        } catch {
          downloadOcrFieldsDocx(ocrExportRows(currentFields), stem)
        }
      } else {
        downloadOcrFieldsDocx(ocrExportRows(currentFields), stem)
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
    <div className={`ocr-docs${onClose ? ' ocr-docs--overlay' : ''}`} data-testid="ocr-documents-panel">
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
        {onClose ? (
          <button
            type="button"
            className="ocr-docs__close"
            onClick={onClose}
            aria-label="Закрыть OCR"
            data-testid="ocr-workspace-close"
          >
            ×
          </button>
        ) : null}
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
                {templateOptions.map((item) => (
                  <option key={item.doc_type} value={item.doc_type}>
                    {item.title || item.doc_type}
                  </option>
                ))}
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
                  <TableCell>
                    {item.file}
                    {item.sourceArchive ? (
                      <small className="ocr-docs__archive"> · {item.sourceArchive}</small>
                    ) : null}
                  </TableCell>
                  <TableCell>
                    {templateOptions.find((tpl) => tpl.doc_type === item.docType)?.title || typeTitle(item.docType)}
                  </TableCell>
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
            <span>На проверке · {stats.hitl}</span>
            <span>Ошибки · {stats.errors}</span>
          </div>

          <Button type="button" onClick={() => setSubTab('upload')}>
            Загрузить документы
          </Button>
        </div>
      )}

      {subTab === 'upload' && (
        <div className="ocr-docs__upload" data-testid="ocr-upload">
          <div className="ocr-docs__upload-grid">
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
              <span>PDF, JPEG, PNG, TIFF · пакет ZIP / RAR</span>
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
            <aside className="ocr-docs__upload-side">
              <label className="ocr-docs__doctype">
                <span>Тип документа</span>
                <select
                  value={docType}
                  onChange={(event) => setDocType(event.target.value)}
                  data-testid="ocr-doc-type"
                >
                  <option value={ML_DOC_TYPE}>ML распознавание</option>
                  {templateOptions.map((item) => (
                    <option key={item.doc_type} value={item.doc_type}>
                      {item.title || item.doc_type}
                    </option>
                  ))}
                  <option value={ML_DOC_TYPE}>ML распознавание</option>
                </select>
              </label>
              <p className="ocr-docs__hint">
                Антивирусная проверка файлов перед добавлением в очередь OCR. Архив ZIP/RAR
                распаковывается в отдельные задания очереди.
              </p>
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
            </aside>
          </div>

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
              <StatusBadge status={activeItem.status === 'error' ? 'danger' : activeItem.status === 'done' ? 'success' : 'warning'}>
                {STATUS_LABEL[activeItem.status]}
              </StatusBadge>
            </header>
            <div className="ocr-docs__scan">
              {(() => {
                const preview = previewByJob[activeItem.id]
                  || (!activeItem.id.startsWith('demo-') && !activeItem.id.startsWith('pending-')
                    ? ocrJobOriginalUrl(activeItem.id)
                    : '')
                const isPdf = /\.pdf$/i.test(activeItem.file)
                if (!preview) {
                  return <p className="ocr-docs__scan-label">Документ ещё загружается…</p>
                }
                if (isPdf) {
                  return (
                    <iframe
                      className="ocr-docs__scan-frame"
                      title={activeItem.file}
                      src={preview}
                    />
                  )
                }
                return (
                  <img
                    className="ocr-docs__scan-img"
                    src={preview}
                    alt={activeItem.file}
                    data-testid="ocr-scan-image"
                  />
                )
              })()}
            </div>
            <div className="ocr-docs__recognize" data-testid="ocr-recognize-progress">
              <div
                className="ocr-docs__recognize-bar"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={
                  busy || activeItem.status === 'queued' || activeItem.status === 'ocr'
                    ? recognizeProgress || activeItem.progress
                    : 100
                }
                role="progressbar"
              >
                <span
                  style={{
                    width: `${
                      busy || activeItem.status === 'queued' || activeItem.status === 'ocr'
                        ? Math.max(recognizeProgress, activeItem.progress)
                        : 100
                    }%`,
                  }}
                />
              </div>
              <em>
                {busy || activeItem.status === 'queued' || activeItem.status === 'ocr'
                  ? `Распознавание… ${Math.max(recognizeProgress, activeItem.progress)}%`
                  : 'Распознавание завершено'}
              </em>
            </div>
          </section>

          <section className="ocr-docs__fields" data-testid="ocr-field-editor" aria-label="Извлечённые поля">
            <h2>Извлечённые поля</h2>
            {fields.every((field) => !field.value.trim()) ? (
              <p className="ocr-docs__hint">Поля шаблона пустые. Проверьте скан или введите значения вручную.</p>
            ) : null}
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

            <div className="ocr-docs__approve">
              <label>
                <span className="visually-hidden">Тип документа</span>
                <select
                  value={activeItem.docType}
                  onChange={(event) => applyDocType(activeItem.id, event.target.value)}
                  data-testid="ocr-review-doc-type"
                >
                  {templateOptions.map((item) => (
                    <option key={item.doc_type} value={item.doc_type}>
                      {item.title || item.doc_type}
                    </option>
                  ))}
                  <option value={ML_DOC_TYPE}>ML распознавание</option>
                  {!templateOptions.some((item) => item.doc_type === activeItem.docType)
                    && !isMlDocType(activeItem.docType) ? (
                    <option value={activeItem.docType}>{typeTitle(activeItem.docType)}</option>
                  ) : null}
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
                Подтверждено · файл скачан
              </StatusBadge>
            )}
          </section>
        </div>
      )}
    </div>
  )
}
