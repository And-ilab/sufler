export type CcChannel = 'telephony' | 'online_chat'

export interface CcAnalyticsFilters {
  date_from?: string
  date_to?: string
  channel?: CcChannel | ''
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

export async function fetchCcAnalytics(
  filters: CcAnalyticsFilters = {},
): Promise<CcAnalyticsPayload> {
  const response = await fetch(`/api/reports/cc/analytics/${toQuery(filters)}`, {
    credentials: 'include',
  })
  return parseJson(response)
}

export async function downloadCcExport(
  filters: CcAnalyticsFilters,
  format: 'csv' | 'xlsx',
): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch(
    `/api/reports/cc/export/${toQuery(filters, { format })}`,
    { credentials: 'include' },
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
  const filename =
    match?.[1] ||
    `cc-analytics.${format}`
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
