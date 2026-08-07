import type { AssistantMessage } from './types'

const STORAGE_KEY = 'sufler.assistant.chat.v1'

export interface PersistedAssistantChat {
  sessionId: string
  messages: AssistantMessage[]
  updatedAt: number
}

export function loadPersistedChat(): PersistedAssistantChat | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as PersistedAssistantChat
    if (!parsed || !Array.isArray(parsed.messages) || !parsed.sessionId) {
      return null
    }
    return parsed
  } catch {
    return null
  }
}

export function savePersistedChat(
  sessionId: string,
  messages: AssistantMessage[],
): void {
  try {
    const payload: PersistedAssistantChat = {
      sessionId,
      messages: messages.map((item) => ({
        ...item,
        pending: false,
      })),
      updatedAt: Date.now(),
    }
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
  } catch {
    /* ignore quota / private mode */
  }
}

export function clearPersistedChat(): void {
  try {
    sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    /* ignore */
  }
}
