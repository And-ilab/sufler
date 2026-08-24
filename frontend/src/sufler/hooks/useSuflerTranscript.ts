import { useCallback, useEffect, useRef, useState } from 'react'
import {
  enterSuflerScenario,
  exitSuflerScenario,
  requestSuflerSuggest,
  type SuflerHint,
  type SuggestResponse,
} from '../api/suggest'

export type SuflerScenarioProgress = NonNullable<SuggestResponse['scenario']>

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
      scenario?: SuflerScenarioProgress | null
      suggested_scenario?: SuggestResponse['suggested_scenario']
    }
  | { type: 'error'; message: string; turn_id?: string }
  | { type: 'pong' }

function wsUrl(callId: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return `${protocol}//${host}/ws/sufler/${callId}/`
}

function hintMessageFor(blocked: string | null | undefined, hasHints: boolean): string {
  if (hasHints) return ''
  if (blocked === 'no_hint_needed' || blocked === 'service_mode') return ''
  if (blocked === 'sufler_unavailable') {
    return 'В выбранных базах нет проиндексированных статей. Проверьте индексацию в Центре настроек.'
  }
  if (blocked === 'no_relevant_knowledge') {
    return 'По этой реплике в выбранных базах нет близкой статьи.'
  }
  return 'Подсказок нет: модель не вернула текст по найденным статьям.'
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
  const [scenario, setScenario] = useState<SuflerScenarioProgress | null>(null)
  const [suggestedScenario, setSuggestedScenario] = useState<
    NonNullable<SuggestResponse['suggested_scenario']> | null
  >(null)
  const socketRef = useRef<WebSocket | null>(null)
  const linesRef = useRef<TranscriptLine[]>(demoMode ? demoLines : [])
  const pausedRef = useRef(false)
  const resetGenRef = useRef(0)
  const inboundEnabledRef = useRef(true)

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
    (
      turnId: string,
      hints: SuflerHint[],
      hintMessage = '',
      requestId = '',
      suppressEmptyMessage = false,
    ) => {
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
                  : suppressEmptyMessage
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
        if (pausedRef.current || !inboundEnabledRef.current) return
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
        if (pausedRef.current || !inboundEnabledRef.current) return
        setScenario(payload.scenario ?? null)
        setSuggestedScenario(payload.suggested_scenario ?? null)
        attachHints(
          payload.turn_id,
          payload.hints.slice(0, 5),
          hintMessageFor(payload.blocked_reason, payload.hints.length > 0),
          payload.request_id,
          payload.blocked_reason === 'no_hint_needed',
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
      inboundEnabledRef.current = true
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
      if (pausedRef.current) return
      const requestGen = resetGenRef.current
      const dialogContext = linesRef.current
        .map((line) =>
          `${line.speaker === 'client' ? 'Клиент' : 'Оператор'}: ${line.text}`,
        )
        .join('\n')
      void requestSuflerSuggest(message.text, 5, {
        dialogContext,
        channel: 'telephony',
        sessionId: callId,
        ...(getKbSlugs && getKbSlugs() !== undefined
          ? { kbSlugs: getKbSlugs() }
          : {}),
      })
        .then((result) => {
          if (requestGen !== resetGenRef.current) return
          const hints = result.hints.slice(0, 5)
          setScenario(result.scenario ?? null)
          setSuggestedScenario(result.suggested_scenario ?? null)
          attachHints(
            message.turn_id,
            hints,
            hintMessageFor(result.blocked_reason, hints.length > 0),
            result.request_id,
            result.blocked_reason === 'no_hint_needed',
          )
          setLatencyMs(result.latency_ms.total)
        })
        .catch((requestError: unknown) => {
          if (requestGen !== resetGenRef.current) return
          const hintMessage =
            requestError instanceof Error
              ? requestError.message
              : 'Не удалось получить подсказки'
          attachHints(message.turn_id, [], hintMessage)
          setError(hintMessage)
        })
    },
    [attachHints, callId, getKbSlugs, upsertLine],
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

  const applySuggestResult = useCallback(
    (result: SuggestResponse, turnId?: string) => {
      const hints = result.hints.slice(0, 5)
      setScenario(result.scenario ?? null)
      setSuggestedScenario(result.suggested_scenario ?? null)
      if (turnId) {
        attachHints(
          turnId,
          hints,
          hintMessageFor(result.blocked_reason, hints.length > 0),
          result.request_id,
          result.blocked_reason === 'no_hint_needed',
        )
      }
      if (result.latency_ms?.total != null) {
        setLatencyMs(result.latency_ms.total)
      }
    },
    [attachHints],
  )

  const enterSuggested = useCallback(
    async (code: string) => {
      const lastClient = [...linesRef.current]
        .reverse()
        .find((line) => line.speaker === 'client' && line.isFinal)
      const result = await enterSuflerScenario(code, {
        sessionId: callId,
        channel: 'telephony',
      })
      applySuggestResult(result, lastClient?.turnId)
    },
    [applySuggestResult, callId],
  )

  const exitActive = useCallback(async () => {
    await exitSuflerScenario(callId)
    setScenario(null)
    setSuggestedScenario(null)
  }, [callId])

  const resetConversation = useCallback(() => {
    resetGenRef.current += 1
    inboundEnabledRef.current = false
    linesRef.current = []
    setLines([])
    setScenario(null)
    setSuggestedScenario(null)
    setError('')
    setLatencyMs(null)
    void exitSuflerScenario(callId).catch(() => {})
  }, [callId])

  const setRecognitionPaused = useCallback((paused: boolean) => {
    pausedRef.current = paused
  }, [])

  return {
    lines,
    connected,
    error,
    latencyMs,
    scenario,
    suggestedScenario,
    ingestLive,
    pushAsr,
    setLines: replaceLines,
    enterSuggested,
    exitActive,
    resetConversation,
    setRecognitionPaused,
  }
}
