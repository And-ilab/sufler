import { useEffect, useState } from 'react'
import { fetchOktellCalls, type OktellLiveCall } from '../api/oktellCalls'

function pickCall(calls: OktellLiveCall[], preferredId: string): OktellLiveCall | null {
  if (preferredId) {
    return calls.find((item) => item.Idchain === preferredId) ?? null
  }
  return calls[0] ?? null
}

export function useOktellActiveCall(preferredId = '') {
  const [call, setCall] = useState<OktellLiveCall | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      const calls = await fetchOktellCalls()
      if (!cancelled) {
        setCall(pickCall(calls, preferredId))
      }
    }
    void load()
    const timer = window.setInterval(() => {
      void load()
    }, 2000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [preferredId])

  return call
}
