export type KnowledgeBaseStatus = 'idle' | 'indexing' | 'ready' | 'error'
export type DocumentStatus = 'uploaded' | 'indexed' | 'error'

export interface KnowledgeBaseDocument {
  id: number
  filename: string
  content_type: string
  size_bytes: number
  status: DocumentStatus
  status_message: string
  chunk_count: number
  uploaded_at: string
  indexed_at: string | null
  uploaded_by: string
}

export interface KnowledgeBase {
  id: number
  name: string
  slug: string
  scope: string
  description: string
  status: KnowledgeBaseStatus
  status_message: string
  document_count: number
  chunk_count: number
  last_reindexed_at: string | null
  created_at: string
  updated_at: string
  created_by: string
  documents?: KnowledgeBaseDocument[]
}

interface ApiErrorPayload {
  error?: string
  details?: Record<string, string[]>
}

export class KnowledgeBaseApiError extends Error {
  readonly details: Record<string, string[]>

  constructor(
    message: string,
    details: Record<string, string[]> = {},
  ) {
    super(message)
    this.details = details
  }
}

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

async function parseResponse<T>(response: Response): Promise<T> {
  let body: T | ApiErrorPayload | null = null
  const text = await response.text()
  try {
    body = text ? (JSON.parse(text) as T | ApiErrorPayload) : null
  } catch {
    body = null
  }
  if (!response.ok) {
    const error = (body ?? {}) as ApiErrorPayload
    const code =
      error.error
      ?? (response.status === 403 ? 'authentication_required' : `http_${response.status}`)
    throw new KnowledgeBaseApiError(code, error.details ?? {})
  }
  if (body == null) {
    throw new KnowledgeBaseApiError('empty_response')
  }
  return body as T
}

export async function listKnowledgeBases(): Promise<KnowledgeBase[]> {
  const response = await fetch('/api/admin/kb/', {
    method: 'GET',
    credentials: 'include',
  })
  const body = await parseResponse<{ items: KnowledgeBase[] }>(response)
  return body.items
}

export async function getKnowledgeBase(id: number): Promise<KnowledgeBase> {
  const response = await fetch(`/api/admin/kb/${id}/`, {
    method: 'GET',
    credentials: 'include',
  })
  return parseResponse<KnowledgeBase>(response)
}

export async function createKnowledgeBase(payload: {
  name: string
  scope?: string
  description?: string
}): Promise<KnowledgeBase> {
  const response = await fetch('/api/admin/kb/', {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken(),
    },
    body: JSON.stringify(payload),
  })
  return parseResponse<KnowledgeBase>(response)
}

export async function deleteKnowledgeBase(id: number): Promise<void> {
  const response = await fetch(`/api/admin/kb/${id}/`, {
    method: 'DELETE',
    credentials: 'include',
    headers: { 'X-CSRFToken': csrfToken() },
  })
  await parseResponse<{ ok: boolean }>(response)
}

export async function uploadKnowledgeDocument(
  kbId: number,
  file: File,
): Promise<{ knowledge_base: KnowledgeBase; document: KnowledgeBaseDocument }> {
  const form = new FormData()
  form.append('file', file)
  const response = await fetch(`/api/admin/kb/${kbId}/upload/`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'X-CSRFToken': csrfToken() },
    body: form,
  })
  return parseResponse(response)
}

export async function deleteKnowledgeDocument(
  kbId: number,
  documentId: number,
): Promise<KnowledgeBase> {
  const response = await fetch(
    `/api/admin/kb/${kbId}/documents/${documentId}/`,
    {
      method: 'DELETE',
      credentials: 'include',
      headers: { 'X-CSRFToken': csrfToken() },
    },
  )
  return parseResponse<KnowledgeBase>(response)
}

export async function reindexKnowledgeBase(
  kbId: number,
): Promise<KnowledgeBase> {
  const response = await fetch(`/api/admin/kb/${kbId}/reindex/`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'X-CSRFToken': csrfToken() },
  })
  return parseResponse<KnowledgeBase>(response)
}
