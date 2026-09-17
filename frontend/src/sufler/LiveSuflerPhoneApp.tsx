import { useEffect, useMemo, useState } from 'react'
import { fetchOktellCall, type OktellCallEvent, type OktellLiveCall } from './api/oktellCalls'
import { SuflerPhoneApp } from './SuflerPhoneApp'
import { useOktellActiveCall } from './hooks/useOktellActiveCall'
import type { TranscriptLine } from './hooks/useSuflerTranscript'
import type { SuflerHint } from './api/suggest'
import { emptySuflerHintMessage } from './emptyHintCopy'

function queryCallId(): string {
  try {
    const params = new URLSearchParams(window.location.search)
    return (params.get('callId') || params.get('Idchain') || '').trim()
  } catch {
    return ''
  }
}

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
  const urlCallId = queryCallId()
  const live = useOktellActiveCall(urlCallId)
  const [detail, setDetail] = useState<OktellLiveCall | null>(null)
  const callId = live?.Idchain || detail?.Idchain || urlCallId
  const liveMode = Boolean(callId)
  const seedLines = useMemo(
    () => linesFromEvents(detail?.events || live?.events),
    [detail?.events, live?.events],
  )

  useEffect(() => {
    if (!urlCallId && !live?.Idchain) return
    const id = urlCallId || live?.Idchain || ''
    void fetchOktellCall(id).then((call) => {
      if (call) setDetail(call)
    })
  }, [live?.Idchain, urlCallId])

  return (
    <SuflerPhoneApp
      demoMode={!liveMode}
      callId={callId || undefined}
      clientPhone={detail?.CallerID || live?.CallerID || ''}
      seedLines={seedLines}
      operatorName={operatorName}
      embedded={embedded}
    />
  )
}
