import { useCallback, useRef, useState } from 'react'
import { streamAssistantChat, streamDemoChat } from './api/chatStream'
import {
  DEFAULT_TOOLS,
  SEED_MESSAGES,
  type AssistantMessage,
  type AssistantToolState,
  type FeedbackKind,
  type ToolId,
} from './types'

function uid(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
}

export interface UseAssistantChatOptions {
  demoMode?: boolean
  initialMessages?: AssistantMessage[]
  sessionId?: string
}

export function useAssistantChat({
  demoMode = false,
  initialMessages = SEED_MESSAGES,
  sessionId = `sess-${Date.now()}`,
}: UseAssistantChatOptions = {}) {
  const [messages, setMessages] = useState<AssistantMessage[]>(initialMessages)
  const [tools, setTools] = useState<AssistantToolState[]>(DEFAULT_TOOLS)
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState('')
  const [toolsOpen, setToolsOpen] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setStreaming(false)
  }, [])

  const setFeedback = useCallback((messageId: string, feedback: FeedbackKind) => {
    setMessages((current) =>
      current.map((item) =>
        item.id === messageId && item.role === 'assistant' && !item.feedback
          ? { ...item, feedback }
          : item,
      ),
    )
  }, [])

  const runTool = useCallback((toolId: ToolId) => {
    setTools((current) =>
      current.map((tool) => {
        if (tool.id !== toolId) return tool
        if (tool.state === 'running') return tool
        if (toolId === 'sql') {
          return { ...tool, state: 'running', detail: 'read-only · executing' }
        }
        if (toolId === 'rpa') {
          return { ...tool, state: 'running', detail: 'awaiting confirm' }
        }
        return { ...tool, state: 'running' }
      }),
    )
    window.setTimeout(() => {
      setTools((current) =>
        current.map((tool) =>
          tool.id === toolId
            ? {
                ...tool,
                state: toolId === 'rpa' ? 'blocked' : 'done',
                detail:
                  toolId === 'sql'
                    ? 'read-only · ok'
                    : toolId === 'rpa'
                      ? 'confirm required'
                      : tool.detail,
              }
            : tool,
        ),
      )
    }, 450)
  }, [])

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || streaming) return

      const userId = uid('user')
      const assistantId = uid('asst')
      setError('')
      setMessages((current) => [
        ...current,
        { id: userId, role: 'user', content: trimmed },
        {
          id: assistantId,
          role: 'assistant',
          content: '',
          pending: true,
          sources: demoMode
            ? [
                {
                  id: 'demo-src',
                  title: 'Регламент HR-12',
                  relevance_percent: 92,
                  permalink: 'https://suz.local/articles/hr-12',
                },
              ]
            : [],
          feedback: null,
        },
      ])
      setStreaming(true)

      const controller = new AbortController()
      abortRef.current = controller

      try {
        const stream = demoMode
          ? streamDemoChat(trimmed, controller.signal)
          : streamAssistantChat({
              message: trimmed,
              sessionId,
              signal: controller.signal,
            })

        for await (const chunk of stream) {
          if (chunk.content) {
            setMessages((current) =>
              current.map((item) =>
                item.id === assistantId
                  ? { ...item, content: item.content + chunk.content }
                  : item,
              ),
            )
          }
          if (chunk.done) break
        }

        setMessages((current) =>
          current.map((item) =>
            item.id === assistantId ? { ...item, pending: false } : item,
          ),
        )
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          setMessages((current) =>
            current.map((item) =>
              item.id === assistantId
                ? {
                    ...item,
                    pending: false,
                    content: item.content || 'Генерация остановлена.',
                  }
                : item,
            ),
          )
        } else {
          const message = err instanceof Error ? err.message : 'Ошибка стриминга'
          setError(message)
          setMessages((current) =>
            current.filter((item) => item.id !== assistantId),
          )
        }
      } finally {
        abortRef.current = null
        setStreaming(false)
      }
    },
    [demoMode, sessionId, streaming],
  )

  const newDialog = useCallback(() => {
    stopStreaming()
    setMessages([])
    setError('')
    setTools(DEFAULT_TOOLS)
  }, [stopStreaming])

  return {
    messages,
    tools,
    streaming,
    error,
    toolsOpen,
    setToolsOpen,
    sendMessage,
    stopStreaming,
    setFeedback,
    runTool,
    newDialog,
    sessionId,
  }
}
