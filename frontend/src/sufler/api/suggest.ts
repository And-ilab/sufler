export interface SuflerHintCitation {
  article_id: number
  chunk_index: number
  title: string
  permalink: string
}

export interface SuflerHint {
  rank: number
  text: string
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

export async function requestSuflerSuggest(
  text: string,
  limit = 5,
  options?: { clientHistory?: string },
): Promise<SuggestResponse> {
  const response = await fetch('/api/v1/sufler/suggest', {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken(),
    },
    body: JSON.stringify({
      text,
      limit,
      client_history: options?.clientHistory ?? '',
    }),
  })
  const body = await response.json()
  if (!response.ok) {
    throw new Error(
      body.details?.request?.[0]
        ?? body.error
        ?? `Suggest failed (${response.status})`,
    )
  }
  return body as SuggestResponse
}
