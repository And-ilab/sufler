import { useCallback, useEffect, useRef, useState } from 'react'
import {
  requestSuflerSuggest,
  type SuflerHint,
} from '../api/suggest'

export interface TranscriptLine {
  id: string
  speaker: 'client' | 'operator'
  text: string
  isFinal: boolean
  turnId: string
  hints?: SuflerHint[]
}

interface UseSuflerTranscriptOptions {
  enabled?: boolean
  callId?: string
  demoMode?: boolean
  demoLines?: TranscriptLine[]
}

type WsInbound =
  | {
      type: 'status'
      status: string
      call_id?: string
      asr?: string
    }
  | {
      type: 'transcript'
      speaker: 'client' | 'operator'
      text: string
      is_final: boolean
      turn_id: string
    }
  | {
      type: 'hints'
      turn_id: string
      hints: SuflerHint[]
      latency_ms?: Record<string, number>
      request_id?: string
    }
  | { type: 'error'; message: string; turn_id?: string }
  | { type: 'pong' }

function wsUrl(callId: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return `${protocol}//${host}/ws/sufler/${callId}/`
}

export function useSuflerTranscript({
  enabled = true,
  callId = 'live',
  demoMode = false,
  demoLines = [],
}: UseSuflerTranscriptOptions) {
  const [lines, setLines] = useState<TranscriptLine[]>(demoMode ? demoLines : [])
  const [connected, setConnected] = useState(demoMode)
  const [error, setError] = useState('')
  const [latencyMs, setLatencyMs] = useState<number | null>(null)
  const socketRef = useRef<WebSocket | null>(null)
  const linesRef = useRef<TranscriptLine[]>(demoMode ? demoLines : [])

  const upsertLine = useCallback((line: TranscriptLine) => {
    setLines((current) => {
      const index = current.findIndex(
        (item) => item.turnId === line.turnId && item.speaker === line.speaker,
      )
      const next =
        index === -1
          ? [...current, line]
          : current.map((item, itemIndex) =>
              itemIndex === index
                ? { ...item, ...line, hints: line.hints ?? item.hints }
                : item,
            )
      linesRef.current = next
      return next
    })
  }, [])

  const attachHints = useCallback((turnId: string, hints: SuflerHint[]) => {
    setLines((current) => {
      const next = current.map((line) =>
        line.turnId === turnId && line.speaker === 'client'
          ? { ...line, hints }
          : line,
      )
      linesRef.current = next
      return next
    })
  }, [])

  useEffect(() => {
    if (!enabled || demoMode) {
      setConnected(demoMode)
      if (demoMode) {
        linesRef.current = demoLines
        setLines(demoLines)
      }
      return
    }

    const socket = new WebSocket(wsUrl(callId))
    socketRef.current = socket

    socket.onopen = () => {
      setConnected(true)
      setError('')
    }
    socket.onclose = () => {
      setConnected(false)
    }
    socket.onerror = () => {
      setError('WebSocket соединение недоступно')
    }
    socket.onmessage = (event) => {
      let payload: WsInbound
      try {
        payload = JSON.parse(String(event.data)) as WsInbound
      } catch {
        setError('Некорректное WS-сообщение')
        return
      }
      if (payload.type === 'transcript') {
        upsertLine({
          id: `${payload.turn_id}-${payload.speaker}`,
          speaker: payload.speaker,
          text: payload.text,
          isFinal: payload.is_final,
          turnId: payload.turn_id,
        })
        return
      }
      if (payload.type === 'hints') {
        attachHints(payload.turn_id, payload.hints.slice(0, 5))
        if (payload.latency_ms?.total != null) {
          setLatencyMs(payload.latency_ms.total)
        }
        return
      }
      if (payload.type === 'error') {
        setError(payload.message)
      }
    }

    return () => {
      socket.close()
      socketRef.current = null
    }
  }, [attachHints, callId, demoLines, demoMode, enabled, upsertLine])

  const pushAsr = useCallback(
    (message: {
      type: 'asr.partial' | 'asr.final'
      speaker: 'client' | 'operator'
      text: string
      turn_id: string
    }) => {
      if (demoMode) {
        upsertLine({
          id: `${message.turn_id}-${message.speaker}`,
          speaker: message.speaker,
          text: message.text,
          isFinal: message.type === 'asr.final',
          turnId: message.turn_id,
        })
        if (message.type === 'asr.final' && message.speaker === 'client') {
          const dialogContext = linesRef.current
            .map((line) =>
              `${line.speaker === 'client' ? 'Клиент' : 'Оператор'}: ${line.text}`,
            )
            .join('\n')
          void requestSuflerSuggest(message.text, 3, { dialogContext })
            .then((result) => {
              attachHints(message.turn_id, result.hints.slice(0, 5))
              setLatencyMs(result.latency_ms.total)
            })
            .catch((requestError: unknown) => {
              setError(
                requestError instanceof Error
                  ? requestError.message
                  : 'Suggest failed',
              )
            })
        }
        return
      }
      socketRef.current?.send(JSON.stringify(message))
    },
    [attachHints, demoMode, upsertLine],
  )

  const replaceLines = useCallback(
    (next: TranscriptLine[] | ((current: TranscriptLine[]) => TranscriptLine[])) => {
      setLines((current) => {
        const resolved = typeof next === 'function' ? next(current) : next
        linesRef.current = resolved
        return resolved
      })
    },
    [],
  )

  return {
    lines,
    connected,
    error,
    latencyMs,
    pushAsr,
    setLines: replaceLines,
  }
}
