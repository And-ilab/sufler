export type OktellListenLeg = {
  speaker: 'client' | 'operator' | string
  dial: string
  sip_user: string
  status: string
}

export type OktellLiveCall = {
  CallerID: string
  CalledID: string
  Idchain: string
  op_name: string
  call_type: string
  state: string
  listen_mode: string
  legs: OktellListenLeg[]
  sufler_ws: string
}

export async function fetchOktellCalls(): Promise<OktellLiveCall[]> {
  const response = await fetch('/api/v1/telephony/oktell/calls', {
    credentials: 'include',
  })
  if (response.status === 401 || response.status === 403) {
    return []
  }
  if (!response.ok) {
    return []
  }
  const body = (await response.json()) as { calls?: OktellLiveCall[] }
  return Array.isArray(body.calls) ? body.calls : []
}
