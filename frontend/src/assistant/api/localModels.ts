/** Optional status helper for Ollama (UI switcher removed). */

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

export async function fetchLocalLlmModels(): Promise<LocalLlmStatus> {
  const response = await fetch('/api/v1/assistant/models/', {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    throw new Error(await parseError(response))
  }
  return (await response.json()) as LocalLlmStatus
}

/** @deprecated Model switching via UI is disabled — use OPENAI_MODEL + ollama pull. */
export async function selectLocalLlmModel(_modelId: string): Promise<LocalLlmStatus> {
  throw new Error(
    'Переключение модели в UI отключено. '
      + 'docker compose exec ollama ollama pull <name>, '
      + 'затем OPENAI_MODEL=<name> в .env и restart backend.',
  )
}
