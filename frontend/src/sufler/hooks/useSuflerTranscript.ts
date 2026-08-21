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
  hintStatus?: 'loading' | 'ready' | 'empty'
  hintMessage?: string
  requestId?: string
}

interface UseSuflerTranscriptOptions {
  enabled?: boolean
  callId?: string
  demoMode?: boolean
  demoLines?: TranscriptLine[]
  getKbSlugs?: () => string[] | undefined
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
      blocked_reason?: string | null
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
  getKbSlugs,
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

  const attachHints = useCallback(
    (turnId: string, hints: SuflerHint[], hintMessage = '', requestId = '') => {
      setLines((current) => {
        const next = current.map((line) =>
          line.turnId === turnId && line.speaker === 'client'
            ? {
                ...line,
                hints,
                requestId: requestId || line.requestId,
                hintStatus: (hints.length ? 'ready' : 'empty') as TranscriptLine['hintStatus'],
                hintMessage: hints.length
                  ? ''
                  : hintMessage || 'Подсказок нет: модель не вернула текст.',
              }
            : line,
        )
        linesRef.current = next
        return next
      })
    },
    [],
  )

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
          ...(payload.is_final && payload.speaker === 'client'
            ? {
                hintStatus: 'loading' as const,
                hintMessage: 'Подсказки загружаются…',
              }
            : {}),
        })
        return
      }
      if (payload.type === 'hints') {
        attachHints(
          payload.turn_id,
          payload.hints.slice(0, 5),
          payload.hints.length
            ? ''
            : payload.blocked_reason === 'sufler_unavailable'
              ? 'В выбранных базах нет проиндексированных статей. Проверьте индексацию в Центре настроек.'
              : payload.blocked_reason === 'no_relevant_knowledge'
                ? 'По этой реплике в выбранных базах нет близкой статьи.'
                : 'Подсказок нет: модель не вернула текст по найденным статьям.',
          payload.request_id,
        )
        if (payload.latency_ms?.total != null) {
          setLatencyMs(payload.latency_ms.total)
        }
        return
      }
      if (payload.type === 'error') {
        if (payload.turn_id) {
          attachHints(payload.turn_id, [], payload.message)
        }
        setError(payload.message)
      }
    }

    return () => {
      socket.close()
      socketRef.current = null
    }
  }, [attachHints, callId, demoLines, demoMode, enabled, upsertLine])

  const ingestLive = useCallback(
    (message: {
      type: 'asr.partial' | 'asr.final'
      speaker: 'client' | 'operator'
      text: string
      turn_id: string
    }) => {
      const nextLine: TranscriptLine = {
        id: `${message.turn_id}-${message.speaker}`,
        speaker: message.speaker,
        text: message.text,
        isFinal: message.type === 'asr.final',
        turnId: message.turn_id,
      }
      if (message.type === 'asr.final' && message.speaker === 'client') {
        nextLine.hintStatus = 'loading'
        nextLine.hintMessage = 'Подсказки загружаются…'
      }
      upsertLine(nextLine)
      if (message.type !== 'asr.final' || message.speaker !== 'client') return
      const dialogContext = linesRef.current
        .map((line) =>
          `${line.speaker === 'client' ? 'Клиент' : 'Оператор'}: ${line.text}`,
        )
        .join('\n')
      void requestSuflerSuggest(message.text, 5, {
        dialogContext,
        channel: 'telephony',
        ...(getKbSlugs && getKbSlugs() !== undefined
          ? { kbSlugs: getKbSlugs() }
          : {}),
      })
        .then((result) => {
          const hints = result.hints.slice(0, 5)
          const blocked = result.blocked_reason
          attachHints(
            message.turn_id,
            hints,
            hints.length
              ? ''
              : blocked === 'sufler_unavailable'
                ? 'В выбранных базах нет проиндексированных статей. Проверьте индексацию в Центре настроек.'
                : blocked === 'no_relevant_knowledge'
                  ? 'По этой реплике в выбранных базах нет близкой статьи.'
                  : 'Подсказок нет: модель не вернула текст по найденным статьям.',
            result.request_id,
          )
          setLatencyMs(result.latency_ms.total)
        })
        .catch((requestError: unknown) => {
          const hintMessage =
            requestError instanceof Error
              ? requestError.message
              : 'Не удалось получить подсказки'
          attachHints(message.turn_id, [], hintMessage)
          setError(hintMessage)
        })
    },
    [attachHints, getKbSlugs, upsertLine],
  )

  const pushAsr = useCallback(
    (message: {
      type: 'asr.partial' | 'asr.final'
      speaker: 'client' | 'operator'
      text: string
      turn_id: string
    }) => {
      if (demoMode) {
        ingestLive(message)
        return
      }
      const slugs = getKbSlugs?.()
      socketRef.current?.send(
        JSON.stringify(
          slugs === undefined ? message : { ...message, kb_slugs: slugs },
        ),
      )
    },
    [demoMode, getKbSlugs, ingestLive],
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
    ingestLive,
    pushAsr,
    setLines: replaceLines,
  }
}
