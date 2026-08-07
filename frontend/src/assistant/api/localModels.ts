function csrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

/** Browser can reach host manager even when Docker proxy cannot. */
const HOST_MANAGER_URLS = [
  'http://127.0.0.1:8070',
  'http://localhost:8070',
] as const

export interface LocalLlmModel {
  id: string
  label: string
  description?: string
  available?: boolean
}

export interface LocalLlmStatus {
  active_model_id: string | null
  switching: boolean
  llama_running: boolean
  manager_reachable?: boolean
  openai_alias?: string
  models: LocalLlmModel[]
  last_error?: string | null
}

async function parseError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as {
      details?: string | { model_id?: string[] }
      error?: string
    }
    if (typeof payload.details === 'string') return payload.details
    if (payload.details && typeof payload.details === 'object') {
      const first = payload.details.model_id?.[0]
      if (first) return first
    }
    return payload.error || `HTTP ${response.status}`
  } catch {
    return `HTTP ${response.status}`
  }
}

async function fetchHostManager(
  method: 'GET' | 'PUT',
  body?: { model_id: string },
): Promise<LocalLlmStatus | null> {
  for (const base of HOST_MANAGER_URLS) {
    try {
      const response = await fetch(`${base}/models`, {
        method,
        headers: {
          Accept: 'application/json',
          ...(body ? { 'Content-Type': 'application/json' } : {}),
        },
        body: body ? JSON.stringify(body) : undefined,
      })
      if (!response.ok) continue
      const payload = (await response.json()) as LocalLlmStatus
      return { ...payload, manager_reachable: true, last_error: null }
    } catch {
      // try next host URL
    }
  }
  return null
}

export async function fetchLocalLlmModels(): Promise<LocalLlmStatus> {
  try {
    const response = await fetch('/api/v1/assistant/models/', {
      credentials: 'include',
      headers: { Accept: 'application/json' },
    })
    if (response.ok) {
      const payload = (await response.json()) as LocalLlmStatus
      if (payload.manager_reachable !== false) {
        return payload
      }
    }
  } catch {
    // fall through to host manager
  }
  const direct = await fetchHostManager('GET')
  if (direct) return direct
  const response = await fetch('/api/v1/assistant/models/', {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    throw new Error(await parseError(response))
  }
  return (await response.json()) as LocalLlmStatus
}

export async function selectLocalLlmModel(modelId: string): Promise<LocalLlmStatus> {
  try {
    const response = await fetch('/api/v1/assistant/models/', {
      method: 'PUT',
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken(),
      },
      body: JSON.stringify({ model_id: modelId }),
    })
    if (response.ok) {
      return (await response.json()) as LocalLlmStatus
    }
    // If backend cannot reach manager, try browser→host directly.
    if (response.status === 502 || response.status === 503) {
      const direct = await fetchHostManager('PUT', { model_id: modelId })
      if (direct) return direct
    }
    throw new Error(await parseError(response))
  } catch (error) {
    if (error instanceof Error && !error.message.includes('HTTP')) {
      const direct = await fetchHostManager('PUT', { model_id: modelId })
      if (direct) return direct
    }
    throw error
  }
}
