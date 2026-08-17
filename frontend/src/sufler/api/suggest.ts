export interface SuflerHintCitation {
  article_id: number
  chunk_index: number
  title: string
  permalink: string
}

export interface SuflerHint {
  rank: number
  text: string
  operator_tip?: string
  relevance_score: number
  relevance_percent: number
  citations: SuflerHintCitation[]
}

export interface SuggestResponse {
  query: string
  profile: string
  kb_id: string
  hints: SuflerHint[]
  citations_enabled: boolean
  blocked_reason: string | null
  min_relevance: number
  latency_ms: {
    qu: number
    rag: number
    llm: number
    total: number
  }
  request_id: string
  gateway_model?: string
}

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

function friendlySuggestError(raw: string, status: number): string {
  const code = (raw || '').toLowerCase()
  if (
    status === 401
    || status === 403
    || code.includes('authentication_required')
    || code.includes('permission_denied')
  ) {
    return 'Ошибка суфлёра. Повторите попытку позже.'
  }
  if (code.includes('no_relevant_knowledge') || code.includes('sufler_unavailable')) {
    return 'Ошибка суфлёра. Повторите попытку позже.'
  }
  if (!raw || raw === 'validation_error' || /^[a-z0-9_]+$/i.test(raw)) {
    return 'Ошибка суфлёра. Повторите попытку позже.'
  }
  return raw
}

export async function requestSuflerSuggest(
  text: string,
  limit = 3,
  options?: { clientHistory?: string; dialogContext?: string },
): Promise<SuggestResponse> {
  // Online-chat ARM is often opened without a prior admin/login bootstrap.
  try {
    const { ensureDevSession } = await import('../../auth/ensureDevSession')
    await ensureDevSession()
  } catch {
    /* ignore — suggest will surface a friendly error if auth still missing */
  }
  const safeLimit = Math.min(5, Math.max(1, Math.round(limit) || 3))
  const response = await fetch('/api/v1/sufler/suggest', {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken(),
    },
    body: JSON.stringify({
      text,
      limit: safeLimit,
      client_history: options?.clientHistory ?? '',
      dialog_context: options?.dialogContext ?? '',
    }),
  })
  const body = await response.json().catch(() => ({} as { error?: string; details?: { request?: string[] } }))
  if (!response.ok) {
    const raw =
      body.details?.request?.[0]
      ?? body.error
      ?? `Suggest failed (${response.status})`
    throw new Error(friendlySuggestError(String(raw), response.status))
  }
  return body as SuggestResponse
}
