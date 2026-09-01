import { ensureCsrfToken, ensureDevSession } from '../../../auth/ensureDevSession'

export type PromptType = 'system' | 'task' | 'scope'
export type PromptStatus = 'draft' | 'published'

export type AssistantKbStatus = 'idle' | 'indexing' | 'ready' | 'error'
export type AssistantDocumentStatus = 'uploaded' | 'indexed' | 'error'

export interface AssistantKbDocument {
  id: number
  filename: string
  content_type: string
  size_bytes: number
  status: AssistantDocumentStatus
  status_message: string
  chunk_count: number
  uploaded_at: string
  indexed_at: string | null
  uploaded_by: string
}

export interface AssistantKb {
  id: number
  name: string
  slug: string
  namespace: string
  isolated_from: string
  scope: string
  description: string
  status: AssistantKbStatus | string
  status_message?: string
  document_count: number
  chunk_count?: number
  last_reindexed_at?: string | null
  created_at?: string
  updated_at?: string
  created_by?: string
  documents?: AssistantKbDocument[]
}

export interface AssistantPrompt {
  id: number
  name: string
  prompt_type: PromptType
  scope: string
  event_trigger: string
  body: string
  status: PromptStatus
  version: number
  kb_slug: string
  updated_by: string
  created_at: string
  updated_at: string
}

/** Orchestration events for Task skills on Capabilities screen. */
export const TASK_EVENT_TRIGGERS = [
  'Начало сессии',
  'Ответ в чате',
  'Запрос уточнения (QU)',
  'Контекст истории (auto/manual)',
  'Перевод EN→RU',
  'Перевод RU→EN',
  'Начало диалога',
] as const

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

async function parseJson<T>(response: Response): Promise<T> {
  const text = await response.text()
  let body: T | ApiErrorPayload | null = null
  try {
    body = text ? (JSON.parse(text) as T | ApiErrorPayload) : null
  } catch {
    if (
      response.status === 403
      && /csrf|CSRF verification failed/i.test(text)
    ) {
      throw new AssistantAdminApiError('csrf_failed')
    }
    throw new AssistantAdminApiError(
      response.status === 401
        ? 'authentication_required'
        : response.status === 403
          ? 'permission_denied'
          : `Неверный ответ API (HTTP ${response.status}): ${text.trim().slice(0, 80) || 'пусто'}`,
    )
  }
  if (!response.ok) {
    const error = (body ?? {}) as ApiErrorPayload
    if (error.error) {
      throw new AssistantAdminApiError(error.error, error.details || {})
    }
    if (response.status === 401) {
      throw new AssistantAdminApiError('authentication_required')
    }
    if (response.status === 403) {
      throw new AssistantAdminApiError('permission_denied')
    }
    throw new AssistantAdminApiError(`HTTP ${response.status}`)
  }
  if (body == null) {
    throw new AssistantAdminApiError('empty_response')
  }
  return body as T
}

async function authedFetch(
  input: string,
  init: RequestInit & { csrf?: boolean } = {},
): Promise<Response> {
  const { csrf = false, headers: initHeaders, ...rest } = init
  await ensureDevSession()
  const headers = new Headers(initHeaders)
  if (csrf) {
    const token = await ensureCsrfToken()
    if (!token) {
      throw new AssistantAdminApiError('csrf_failed')
    }
    headers.set('X-CSRFToken', token)
  }
  return fetch(input, {
    ...rest,
    credentials: 'include',
    headers,
  })
}

export async function listAssistantKbs(): Promise<AssistantKb[]> {
  const response = await authedFetch('/api/admin/assistant/kb/', {
    method: 'GET',
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
  const response = await authedFetch('/api/admin/assistant/kb/', {
    method: 'POST',
    csrf: true,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return parseJson(response)
}

export async function getAssistantKb(id: number): Promise<AssistantKb> {
  const response = await authedFetch(`/api/admin/assistant/kb/${id}/`, {
    method: 'GET',
  })
  return parseJson(response)
}

export async function deleteAssistantKb(id: number): Promise<void> {
  const response = await authedFetch(`/api/admin/assistant/kb/${id}/`, {
    method: 'DELETE',
    csrf: true,
  })
  await parseJson<{ ok: boolean }>(response)
}

export async function uploadAssistantKbDocument(
  kbId: number,
  file: File,
  options: { reindex?: boolean } = {},
): Promise<{ knowledge_base: AssistantKb; document: AssistantKbDocument }> {
  const form = new FormData()
  form.append('file', file)
  // Default false: batch upload then one reindex (avoids N full CPU embeds).
  form.append('reindex', options.reindex ? '1' : '0')
  const response = await authedFetch(`/api/admin/assistant/kb/${kbId}/upload/`, {
    method: 'POST',
    csrf: true,
    body: form,
  })
  return parseJson(response)
}

export async function deleteAssistantKbDocument(
  kbId: number,
  documentId: number,
): Promise<AssistantKb> {
  const response = await authedFetch(
    `/api/admin/assistant/kb/${kbId}/documents/${documentId}/`,
    {
      method: 'DELETE',
      csrf: true,
    },
  )
  return parseJson(response)
}

export async function reindexAssistantKb(kbId: number): Promise<AssistantKb> {
  const response = await authedFetch(`/api/admin/assistant/kb/${kbId}/reindex/`, {
    method: 'POST',
    csrf: true,
  })
  return parseJson(response)
}

export async function listAssistantPrompts(): Promise<AssistantPrompt[]> {
  const response = await authedFetch('/api/admin/assistant/prompts/', {
    method: 'GET',
  })
  const body = await parseJson<{ items: AssistantPrompt[] }>(response)
  return body.items
}

export async function createAssistantPrompt(payload: {
  name: string
  body: string
  prompt_type?: PromptType
  scope?: string
  event_trigger?: string
  kb_slug?: string
}): Promise<AssistantPrompt> {
  const response = await authedFetch('/api/admin/assistant/prompts/', {
    method: 'POST',
    csrf: true,
    headers: { 'Content-Type': 'application/json' },
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
    event_trigger: string
    kb_slug: string
    status: PromptStatus
  }>,
): Promise<AssistantPrompt> {
  const response = await authedFetch(`/api/admin/assistant/prompts/${id}/`, {
    method: 'PUT',
    csrf: true,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return parseJson(response)
}

export async function deleteAssistantPrompt(id: number): Promise<void> {
  const response = await authedFetch(`/api/admin/assistant/prompts/${id}/`, {
    method: 'DELETE',
    csrf: true,
  })
  await parseJson<{ ok: boolean }>(response)
}

export async function listAssistantCapabilities(): Promise<AssistantCapability[]> {
  const response = await authedFetch('/api/admin/assistant/capabilities/', {
    method: 'GET',
  })
  const body = await parseJson<{ items: AssistantCapability[] }>(response)
  return body.items
}

export type DocTemplateFormat = 'docx' | 'pdf' | 'xlsx' | 'pptx' | 'bpmn' | 'txt' | 'mmd'

export interface DocTemplateField {
  id: string
  label: string
  required?: boolean
}

export interface AssistantDocTemplate {
  id: number
  name: string
  category: string
  output_format: DocTemplateFormat
  format_label: string
  body: string
  fields: DocTemplateField[]
  active: boolean
  updated_by: string
  created_at: string
  updated_at: string
}

export async function listAssistantDocTemplates(): Promise<AssistantDocTemplate[]> {
  const response = await authedFetch('/api/admin/assistant/doc-templates/', {
    method: 'GET',
  })
  const body = await parseJson<{ items: AssistantDocTemplate[] }>(response)
  return body.items
}

export async function createAssistantDocTemplate(payload: {
  name: string
  category?: string
  output_format?: DocTemplateFormat
  body: string
  fields?: DocTemplateField[]
  active?: boolean
}): Promise<AssistantDocTemplate> {
  const response = await authedFetch('/api/admin/assistant/doc-templates/', {
    method: 'POST',
    csrf: true,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return parseJson(response)
}

export async function updateAssistantDocTemplate(
  id: number,
  payload: Partial<{
    name: string
    category: string
    output_format: DocTemplateFormat
    body: string
    fields: DocTemplateField[]
    active: boolean
  }>,
): Promise<AssistantDocTemplate> {
  const response = await authedFetch(`/api/admin/assistant/doc-templates/${id}/`, {
    method: 'PUT',
    csrf: true,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return parseJson(response)
}

export async function deleteAssistantDocTemplate(id: number): Promise<void> {
  const response = await authedFetch(`/api/admin/assistant/doc-templates/${id}/`, {
    method: 'DELETE',
    csrf: true,
  })
  await parseJson<{ ok: boolean }>(response)
}

export async function setCapabilityEnabled(
  code: string,
  enabled: boolean,
): Promise<AssistantCapability> {
  const response = await authedFetch(
    `/api/admin/assistant/capabilities/${code}/`,
    {
      method: 'PATCH',
      csrf: true,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    },
  )
  return parseJson(response)
}
