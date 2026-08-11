export interface OcrFieldValue {
  value?: string | number | boolean | null
  confidence?: number
  source?: string
}

export interface ChatOcrPayload {
  job_id: string
  document_id: string
  document_type?: string | null
  fields: Record<string, OcrFieldValue | string | number | boolean | null>
  validation_status?: string | null
  pages?: Array<{ page?: number; text?: string; confidence?: number }>
}

export interface ChatAttachmentPayload {
  name: string
  type: string
  text: string
  content_type?: string
  size_bytes?: number
  ocr?: ChatOcrPayload
}

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

const OCR_EXTENSIONS = new Set([
  '.pdf',
  '.jpg',
  '.jpeg',
  '.png',
  '.tiff',
  '.tif',
])

function extensionOf(name: string): string {
  const idx = name.lastIndexOf('.')
  return idx >= 0 ? name.slice(idx).toLowerCase() : ''
}

export async function extractChatAttachment(
  file: File,
): Promise<ChatAttachmentPayload> {
  const ext = extensionOf(file.name)
  const endpoint = OCR_EXTENSIONS.has(ext) && ext !== '.pdf'
    ? '/api/v1/assistant/attachments/ocr'
    : '/api/v1/assistant/attachments/extract'

  const body = new FormData()
  body.append('file', file, file.name)
  if (ext === '.pdf' && /passport|паспорт|scan|скан/i.test(file.name)) {
    body.append('mode', 'ocr')
    body.append('document_type', 'passport')
  }

  const response = await fetch(endpoint, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'X-CSRFToken': csrfToken(),
    },
    body,
  })
  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const payload = (await response.json()) as {
        details?: { file?: string[] }
        error?: string
      }
      detail = payload.details?.file?.[0] || payload.error || detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  return (await response.json()) as ChatAttachmentPayload
}

export function fieldConfidencePercent(
  field: OcrFieldValue | string | number | boolean | null | undefined,
): number | null {
  if (field && typeof field === 'object' && 'confidence' in field) {
    const conf = field.confidence
    if (typeof conf === 'number' && Number.isFinite(conf)) {
      return Math.round(conf * 100)
    }
  }
  return null
}

export function fieldDisplayValue(
  field: OcrFieldValue | string | number | boolean | null | undefined,
): string {
  if (field == null) return ''
  if (typeof field === 'object' && 'value' in field) {
    return field.value == null ? '' : String(field.value)
  }
  return String(field)
}
