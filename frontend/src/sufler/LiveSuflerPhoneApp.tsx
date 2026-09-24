import { useEffect, useMemo, useState } from 'react'
import {
  ensureOktellListen,
  fetchOktellCall,
  type OktellCallEvent,
  type OktellLiveCall,
} from './api/oktellCalls'
import { SuflerPhoneApp } from './SuflerPhoneApp'
import { useOktellActiveCall } from './hooks/useOktellActiveCall'
import type { TranscriptLine } from './hooks/useSuflerTranscript'
import type { SuflerHint } from './api/suggest'
import { emptySuflerHintMessage } from './emptyHintCopy'

function linesFromEvents(events: OktellCallEvent[] | undefined): TranscriptLine[] {
  const lines: TranscriptLine[] = []
  for (const event of events || []) {
    if (event.type === 'transcript' && event.speaker && event.text && event.turn_id) {
      lines.push({
        id: `${event.turn_id}-${event.speaker}`,
        speaker: event.speaker,
        text: event.text,
        isFinal: event.is_final !== false,
        turnId: event.turn_id,
        ...(event.speaker === 'client' && event.is_final !== false
          ? { hintStatus: 'loading' as const, hintMessage: 'Подсказки загружаются…' }
          : {}),
      })
    }
    if (event.type === 'hints' && event.turn_id) {
      const hints = (Array.isArray(event.hints) ? event.hints : []) as SuflerHint[]
      const target = lines.find(
        (line) => line.turnId === event.turn_id && line.speaker === 'client',
      )
      if (target) {
        target.hints = hints.slice(0, 5)
        target.hintStatus = hints.length ? 'ready' : 'empty'
        target.hintMessage = hints.length
          ? ''
          : emptySuflerHintMessage(event.blocked_reason, false)
      }
    }
  }
  return lines
}

export function LiveSuflerPhoneApp({
  operatorName,
  embedded = false,
}: {
  operatorName?: string
  embedded?: boolean
}) {
  const polled = useOktellActiveCall('')
  const [started, setStarted] = useState<OktellLiveCall | null>(null)
  const live = polled || started
  const [detail, setDetail] = useState<OktellLiveCall | null>(null)
  const callId = live?.Idchain || ''
  const seedLines = useMemo(
    () => linesFromEvents(detail?.events || live?.events),
    [detail?.events, live?.events],
  )

  useEffect(() => {
    if (polled?.Idchain) {
      setStarted(polled)
      return
    }
    let cancelled = false
    void ensureOktellListen().then((call) => {
      if (!cancelled && call) setStarted(call)
    })
    return () => {
      cancelled = true
    }
  }, [polled?.Idchain])

  useEffect(() => {
    if (!callId) {
      setDetail(null)
      return
    }
    void fetchOktellCall(callId).then((call) => {
      setDetail(call)
    })
  }, [callId])

  return (
    <SuflerPhoneApp
      demoMode={false}
      callId={callId || undefined}
      clientPhone={detail?.CallerID || live?.CallerID || ''}
      seedLines={seedLines}
      operatorName={operatorName}
      embedded={embedded}
    />
  )
}
