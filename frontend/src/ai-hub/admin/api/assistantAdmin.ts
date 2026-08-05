export type PromptType = 'system' | 'task' | 'scope'
export type PromptStatus = 'draft' | 'published'

export interface AssistantKb {
  id: number
  name: string
  slug: string
  namespace: string
  isolated_from: string
  scope: string
  description: string
  status: string
  document_count: number
}

export interface AssistantPrompt {
  id: number
  name: string
  prompt_type: PromptType
  scope: string
  body: string
  status: PromptStatus
  version: number
  kb_slug: string
  updated_by: string
  created_at: string
  updated_at: string
}

export interface AssistantCapability {
  id: number
  code: string
  name: string
  description: string
  enabled: boolean
  deep_link: string
  category: string
  sort_order: number
}

interface ApiErrorPayload {
  error?: string
  details?: Record<string, string[]>
}

export class AssistantAdminApiError extends Error {
  readonly details: Record<string, string[]>

  constructor(message: string, details: Record<string, string[]> = {}) {
    super(message)
    this.details = details
  }
}

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

async function parseJson<T>(response: Response): Promise<T> {
  const text = await response.text()
  let body: T | ApiErrorPayload | null = null
  try {
    body = text ? (JSON.parse(text) as T | ApiErrorPayload) : null
  } catch {
    const snippet = text.trim().slice(0, 80)
    throw new AssistantAdminApiError(
      response.status === 401 || response.status === 403
        ? 'authentication_required'
        : `Неверный ответ API (HTTP ${response.status}): ${snippet || 'пусто'}`,
    )
  }
  if (!response.ok) {
    const error = (body ?? {}) as ApiErrorPayload
    throw new AssistantAdminApiError(
      error.error || `HTTP ${response.status}`,
      error.details || {},
    )
  }
  if (body == null) {
    throw new AssistantAdminApiError('empty_response')
  }
  return body as T
}

export async function listAssistantKbs(): Promise<AssistantKb[]> {
  const response = await fetch('/api/admin/assistant/kb/', {
    credentials: 'include',
  })
  const body = await parseJson<{ items: AssistantKb[] }>(response)
  return body.items
}

export async function createAssistantKb(payload: {
  name: string
  slug?: string
  scope?: string
  description?: string
}): Promise<AssistantKb> {
  const response = await fetch('/api/admin/assistant/kb/', {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken(),
    },
    body: JSON.stringify(payload),
  })
  return parseJson(response)
}

export async function listAssistantPrompts(): Promise<AssistantPrompt[]> {
  const response = await fetch('/api/admin/assistant/prompts/', {
    credentials: 'include',
  })
  const body = await parseJson<{ items: AssistantPrompt[] }>(response)
  return body.items
}

export async function createAssistantPrompt(payload: {
  name: string
  body: string
  prompt_type?: PromptType
  scope?: string
  kb_slug?: string
}): Promise<AssistantPrompt> {
  const response = await fetch('/api/admin/assistant/prompts/', {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken(),
    },
    body: JSON.stringify(payload),
  })
  return parseJson(response)
}

export async function updateAssistantPrompt(
  id: number,
  payload: Partial<{
    name: string
    body: string
    prompt_type: PromptType
    scope: string
    kb_slug: string
    status: PromptStatus
  }>,
): Promise<AssistantPrompt> {
  const response = await fetch(`/api/admin/assistant/prompts/${id}/`, {
    method: 'PUT',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken(),
    },
    body: JSON.stringify(payload),
  })
  return parseJson(response)
}

export async function deleteAssistantPrompt(id: number): Promise<void> {
  const response = await fetch(`/api/admin/assistant/prompts/${id}/`, {
    method: 'DELETE',
    credentials: 'include',
    headers: { 'X-CSRFToken': csrfToken() },
  })
  await parseJson<{ ok: boolean }>(response)
}

export async function listAssistantCapabilities(): Promise<AssistantCapability[]> {
  const response = await fetch('/api/admin/assistant/capabilities/', {
    credentials: 'include',
  })
  const body = await parseJson<{ items: AssistantCapability[] }>(response)
  return body.items
}

export async function setCapabilityEnabled(
  code: string,
  enabled: boolean,
): Promise<AssistantCapability> {
  const response = await fetch(`/api/admin/assistant/capabilities/${code}/`, {
    method: 'PATCH',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken(),
    },
    body: JSON.stringify({ enabled }),
  })
  return parseJson(response)
}
