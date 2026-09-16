import { SuflerPhoneApp } from './SuflerPhoneApp'
import { useOktellActiveCall } from './hooks/useOktellActiveCall'

function queryCallId(): string {
  try {
    const params = new URLSearchParams(window.location.search)
    return (params.get('callId') || params.get('Idchain') || '').trim()
  } catch {
    return ''
  }
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
  const callId = live?.Idchain || urlCallId
  const liveMode = Boolean(callId)

  return (
    <SuflerPhoneApp
      demoMode={!liveMode}
      callId={callId || undefined}
      clientPhone={live?.CallerID || ''}
      operatorName={operatorName}
      embedded={embedded}
    />
  )
}
