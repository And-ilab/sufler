export interface ChatAttachmentPayload {
  name: string
  type: string
  text: string
  content_type?: string
  size_bytes?: number
}

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

export async function extractChatAttachment(
  file: File,
): Promise<ChatAttachmentPayload> {
  const body = new FormData()
  body.append('file', file, file.name)
  const response = await fetch('/api/v1/assistant/attachments/extract', {
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
