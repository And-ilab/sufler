function csrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

async function parseError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as {
      details?: { request?: string[] }
      error?: string
    }
    return payload.details?.request?.[0] || payload.error || `HTTP ${response.status}`
  } catch {
    return `HTTP ${response.status}`
  }
}

export interface OcrTemplateSample {
  id: number
  filename: string
  content_type?: string
  ocr_text?: string
  expected_fields?: Record<string, unknown>
  notes?: string
  created_by?: string
  created_at?: string | null
}

export interface OcrTemplate {
  id: number
  doc_type: string
  title: string
  description?: string
  template_version: number
  status: 'draft' | 'published' | 'archived' | string
  required_fields: string[]
  field_schema: Record<string, unknown>
  confidence_min: number
  sample_prompt?: string
  owner?: string
  published_at?: string | null
  updated_at?: string | null
  sample_count?: number
  samples?: OcrTemplateSample[]
}

export async function listOcrTemplates(): Promise<OcrTemplate[]> {
  const response = await fetch('/api/v1/ocr/templates/?seed=1', {
    credentials: 'include',
  })
  if (!response.ok) throw new Error(await parseError(response))
  const payload = (await response.json()) as { items?: OcrTemplate[] }
  return payload.items ?? []
}

export async function saveOcrTemplate(
  input: Partial<OcrTemplate> & { doc_type: string; publish?: boolean },
): Promise<OcrTemplate> {
  const response = await fetch('/api/v1/ocr/templates/', {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken(),
    },
    body: JSON.stringify(input),
  })
  if (!response.ok) throw new Error(await parseError(response))
  return (await response.json()) as OcrTemplate
}

export async function updateOcrTemplate(
  docType: string,
  input: Partial<OcrTemplate> & { publish?: boolean; bump_version?: boolean },
): Promise<OcrTemplate> {
  const response = await fetch(`/api/v1/ocr/templates/${encodeURIComponent(docType)}/`, {
    method: 'PUT',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken(),
    },
    body: JSON.stringify(input),
  })
  if (!response.ok) throw new Error(await parseError(response))
  return (await response.json()) as OcrTemplate
}

export async function uploadTemplateSample(
  docType: string,
  file: File,
  expectedFields?: Record<string, unknown>,
  notes = '',
): Promise<Record<string, unknown>> {
  const body = new FormData()
  body.append('file', file, file.name)
  if (expectedFields) {
    body.append('expected_fields', JSON.stringify(expectedFields))
  }
  if (notes) body.append('notes', notes)
  const response = await fetch(
    `/api/v1/ocr/templates/${encodeURIComponent(docType)}/samples/`,
    {
      method: 'POST',
      credentials: 'include',
      headers: { 'X-CSRFToken': csrfToken() },
      body,
    },
  )
  if (!response.ok) throw new Error(await parseError(response))
  return (await response.json()) as Record<string, unknown>
}

export async function listOcrJobs(limit = 40): Promise<Array<Record<string, unknown>>> {
  const response = await fetch(`/api/v1/ocr/jobs/?limit=${limit}`, {
    credentials: 'include',
  })
  if (!response.ok) throw new Error(await parseError(response))
  const payload = (await response.json()) as { items?: Array<Record<string, unknown>> }
  return payload.items ?? []
}

export async function uploadOcrDocument(
  file: File,
  documentType = '',
  sync = true,
): Promise<Record<string, unknown>> {
  const body = new FormData()
  body.append('file', file, file.name)
  if (documentType) body.append('document_type', documentType)
  if (sync) body.append('sync', '1')
  const response = await fetch('/api/v1/ocr/documents/', {
    method: 'POST',
    credentials: 'include',
    headers: { 'X-CSRFToken': csrfToken() },
    body,
  })
  if (!response.ok) throw new Error(await parseError(response))
  return (await response.json()) as Record<string, unknown>
}

export async function fetchOcrResult(jobId: string): Promise<Record<string, unknown>> {
  const response = await fetch(`/api/v1/ocr/jobs/${encodeURIComponent(jobId)}/result/`, {
    credentials: 'include',
  })
  if (!response.ok) throw new Error(await parseError(response))
  return (await response.json()) as Record<string, unknown>
}

export async function approveOcrJob(
  jobId: string,
  documentType: string,
  fields: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const response = await fetch(`/api/v1/ocr/jobs/${encodeURIComponent(jobId)}/approve/`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken(),
    },
    body: JSON.stringify({ document_type: documentType, fields }),
  })
  if (!response.ok && response.status !== 422) {
    throw new Error(await parseError(response))
  }
  return (await response.json()) as Record<string, unknown>
}
