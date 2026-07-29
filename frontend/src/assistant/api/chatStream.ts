import { DEMO_STUB_ANSWER } from '../types'

export interface ChatStreamChunk {
  content: string
  done: boolean
}

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

function parseSseBlock(block: string): ChatStreamChunk | null {
  const lines = block.split('\n')
  let data = ''
  for (const line of lines) {
    if (line.startsWith(':')) continue
    if (line.startsWith('data:')) {
      data += line.slice(5).trimStart()
    }
  }
  if (!data) return null
  if (data === '[DONE]') return { content: '', done: true }
  try {
    const payload = JSON.parse(data) as {
      choices?: Array<{ delta?: { content?: string | null } }>
    }
    const content = payload.choices?.[0]?.delta?.content ?? ''
    return { content: content || '', done: false }
  } catch {
    return null
  }
}

/** Consume OpenAI-compatible SSE from POST /api/v1/assistant/chat. */
export async function* streamAssistantChat(input: {
  message: string
  sessionId?: string
  signal?: AbortSignal
}): AsyncGenerator<ChatStreamChunk> {
  const response = await fetch('/api/v1/assistant/chat', {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      'X-CSRFToken': csrfToken(),
    },
    body: JSON.stringify({
      message: input.message,
      session_id: input.sessionId,
      stream: true,
    }),
    signal: input.signal,
  })

  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const body = (await response.json()) as { error?: string }
      if (body.error) detail = body.error
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }

  if (!response.body) {
    throw new Error('Streaming body unavailable')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''
    for (const part of parts) {
      const chunk = parseSseBlock(part)
      if (!chunk) continue
      yield chunk
      if (chunk.done) return
    }
  }

  if (buffer.trim()) {
    const chunk = parseSseBlock(buffer)
    if (chunk) yield chunk
  }
}

/** Deterministic token stream for Storybook / offline demo. */
export async function* streamDemoChat(
  _message: string,
  signal?: AbortSignal,
): AsyncGenerator<ChatStreamChunk> {
  const text = DEMO_STUB_ANSWER
  const step = 18
  for (let index = 0; index < text.length; index += step) {
    if (signal?.aborted) {
      throw new DOMException('Aborted', 'AbortError')
    }
    yield { content: text.slice(index, index + step), done: false }
    await new Promise((resolve) => setTimeout(resolve, 20))
  }
  yield { content: '', done: true }
}
