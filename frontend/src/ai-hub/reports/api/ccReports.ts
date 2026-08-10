import { ensureDevSession } from '../../../auth/ensureDevSession'

export type CcChannel = 'telephony' | 'online_chat'

export interface CcAnalyticsFilters {
  date_from?: string
  date_to?: string
  channel?: CcChannel | ''
  report?: string
}

export interface CcAnalyticsSummary {
  sessions: number
  recognized_pct: number
  avg_confidence: number
  useful_pct: number
  incorrect_llm: number
  hint_latency_p95_ms: number
}

export interface CcAnalyticsRow {
  date: string
  channel: CcChannel
  operator: string
  sessions: number
  recognized_pct: number
  avg_confidence: number
  useful_pct: number
  incomplete_pct: number
  unused_pct: number
  incorrect_llm: number
  hint_latency_p95_ms: number
  aht_sec: number
}

export interface CcUsefulnessRow {
  channel: CcChannel
  label: string
  useful_pct: number
  incomplete_pct: number
  unused_pct: number
  sessions: number
}

export interface AsrQualityPoint {
  date: string
  recognized_pct: number
  avg_confidence: number
  sessions: number
}

export interface CcAnalyticsPayload {
  filters: {
    date_from: string
    date_to: string
    channel: string
  }
  summary: CcAnalyticsSummary
  rows: CcAnalyticsRow[]
  usefulness: CcUsefulnessRow[]
  asr_quality: AsrQualityPoint[]
  stub: boolean
  source: string
}

export interface LiveKpis {
  in_progress: number
  in_queue: number
  avg_wait_sec: number
  operators_online: number
  sla_ok_pct: number
  hint_p95_ms: number
}

export interface LiveDashboard {
  generated_at: string
  stub: boolean
  source: string
  kpis: LiveKpis
  departments: { name: string; active: number; queue: number }[]
  operators: {
    name: string
    status: string
    active_dialogs: number
    channel: string
  }[]
  alerts: { id: string; tone: string; title: string; detail: string; at: string }[]
  llm_feed: {
    id: string
    channel: string
    operator: string
    topic: string
    relevance_pct: number
    feedback: string
    latency_ms: number
    at: string
  }[]
  chat: {
    waiting: number
    active: number
    closed_today: number
    operators_from_chat: { name: string; active_dialogs: number }[]
  }
}

export interface CatalogReportMeta {
  id: string
  fr: string
  label: string
  default_view: string
}

export interface CatalogPayload {
  filters: Record<string, string>
  catalog: CatalogReportMeta[]
  report: CatalogReportMeta
  rows: Record<string, unknown>[]
  chart: { label: string; value: number }[]
  summary: Record<string, unknown>
  stub: boolean
  source: string
  alerts: { id: string; title: string; detail: string; enabled: boolean }[]
}

export interface BuilderTemplatesPayload {
  templates: {
    id: string
    name: string
    metrics: string[]
    filters: Record<string, string>
    view_mode: string
  }[]
  metric_catalog: { id: string; label: string }[]
  stub: boolean
}

interface ApiErrorPayload {
  error?: string
  details?: Record<string, string[]>
}

export class CcReportsApiError extends Error {
  readonly details: Record<string, string[]>

  constructor(message: string, details: Record<string, string[]> = {}) {
    super(message)
    this.details = details
  }
}

function toQuery(
  filters: CcAnalyticsFilters,
  extra: Record<string, string> = {},
): string {
  const params = new URLSearchParams()
  if (filters.date_from) params.set('date_from', filters.date_from)
  if (filters.date_to) params.set('date_to', filters.date_to)
  if (filters.channel) params.set('channel', filters.channel)
  if (filters.report) params.set('report', filters.report)
  for (const [key, value] of Object.entries(extra)) {
    if (value) params.set(key, value)
  }
  const query = params.toString()
  return query ? `?${query}` : ''
}

async function parseJson<T>(response: Response): Promise<T> {
  const body = (await response.json()) as T | ApiErrorPayload
  if (!response.ok) {
    const error = body as ApiErrorPayload
    throw new CcReportsApiError(
      error.error || `HTTP ${response.status}`,
      error.details || {},
    )
  }
  return body as T
}

async function authedFetch(input: string, init?: RequestInit): Promise<Response> {
  await ensureDevSession()
  return fetch(input, { credentials: 'include', ...init })
}

export async function fetchCcAnalytics(
  filters: CcAnalyticsFilters = {},
): Promise<CcAnalyticsPayload> {
  const response = await authedFetch(`/api/reports/cc/analytics/${toQuery(filters)}`)
  return parseJson(response)
}

export async function fetchCcLive(): Promise<LiveDashboard> {
  const response = await authedFetch('/api/reports/cc/live/')
  return parseJson(response)
}

export async function fetchCcCatalog(
  filters: CcAnalyticsFilters = {},
): Promise<CatalogPayload> {
  const response = await authedFetch(`/api/reports/cc/catalog/${toQuery(filters)}`)
  return parseJson(response)
}

export async function fetchBuilderTemplates(): Promise<BuilderTemplatesPayload> {
  const response = await authedFetch('/api/reports/cc/builder/')
  return parseJson(response)
}

export async function previewBuilder(body: {
  name?: string
  metrics?: string[]
  view_mode?: string
}): Promise<{
  name: string
  view_mode: string
  rows: { metric: string; value: number; unit: string }[]
  chart: { label: string; value: number }[]
  stub: boolean
  message: string
}> {
  const response = await authedFetch('/api/reports/cc/builder/preview/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return parseJson(response)
}

export async function downloadCcExport(
  filters: CcAnalyticsFilters,
  format: 'csv' | 'xlsx' | 'pdf',
): Promise<{ blob: Blob; filename: string }> {
  const response = await authedFetch(
    `/api/reports/cc/export/${toQuery(filters, { format })}`,
  )
  if (!response.ok) {
    try {
      await parseJson(response)
    } catch (error) {
      if (error instanceof CcReportsApiError) throw error
    }
    throw new CcReportsApiError(`HTTP ${response.status}`)
  }
  const disposition = response.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="([^"]+)"/)
  const filename = match?.[1] || `cc-analytics.${format}`
  const blob = await response.blob()
  return { blob, filename }
}

export function triggerBrowserDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
