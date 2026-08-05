/** HTTP + helpers for Django online_chat API (`/api/v1/online-chat/`). */

export type DialogStatus = 'waiting' | 'active' | 'closed' | 'blocked'

export type DialogSpeaker = 'client' | 'operator' | 'system'

export type OnlineChatDialog = {
  id: string
  widget_id: string
  placement: string
  channel: string
  status: DialogStatus
  client_first_name: string
  client_last_name: string
  client_phone: string
  client_name: string
  operator_name: string
  preview: string
  created_at: string
  updated_at: string
  accepted_at: string | null
  closed_at: string | null
  wait_seconds: number
  messages?: OnlineChatMessage[]
}

export type OnlineChatMessage = {
  id: string
  dialog_id: string
  speaker: DialogSpeaker
  text: string
  created_at: string
}

async function parseJson<T>(response: Response): Promise<T> {
  const body = (await response.json()) as T & { detail?: string; error?: string }
  if (!response.ok) {
    throw new Error(body.detail || body.error || `HTTP ${response.status}`)
  }
  return body
}

export function formatWaitMmSs(totalSeconds: number): string {
  const sec = Math.max(0, Math.floor(totalSeconds))
  const mm = String(Math.floor(sec / 60)).padStart(2, '0')
  const ss = String(sec % 60).padStart(2, '0')
  return `${mm}:${ss}`
}

export function maskPhone(phone: string): string {
  const digits = phone.replace(/\D/g, '')
  if (digits.length < 4) return phone || '—'
  return `+${digits.slice(0, 3)} ** ***-**-${digits.slice(-2)}`
}

export async function listDialogs(status?: DialogStatus): Promise<OnlineChatDialog[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : ''
  const response = await fetch(`/api/v1/online-chat/dialogs/${query}`)
  const body = await parseJson<{ ok: boolean; items: OnlineChatDialog[] }>(response)
  return body.items
}

export async function getDialog(dialogId: string): Promise<OnlineChatDialog> {
  const response = await fetch(`/api/v1/online-chat/dialogs/${dialogId}/`)
  const body = await parseJson<{ ok: boolean; dialog: OnlineChatDialog }>(response)
  return body.dialog
}

export async function acceptDialog(
  dialogId: string,
  operatorName = 'Иванов И.И.',
): Promise<OnlineChatDialog> {
  const response = await fetch(`/api/v1/online-chat/dialogs/${dialogId}/accept/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_name: operatorName }),
  })
  const body = await parseJson<{ ok: boolean; dialog: OnlineChatDialog }>(response)
  return body.dialog
}

export async function closeDialogRemote(dialogId: string): Promise<OnlineChatDialog> {
  const response = await fetch(`/api/v1/online-chat/dialogs/${dialogId}/close/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })
  const body = await parseJson<{ ok: boolean; dialog: OnlineChatDialog }>(response)
  return body.dialog
}

export async function blockDialogRemote(dialogId: string): Promise<OnlineChatDialog> {
  const response = await fetch(`/api/v1/online-chat/dialogs/${dialogId}/block/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })
  const body = await parseJson<{ ok: boolean; dialog: OnlineChatDialog }>(response)
  return body.dialog
}

export async function sendOperatorMessage(
  dialogId: string,
  text: string,
): Promise<OnlineChatMessage> {
  const response = await fetch(`/api/v1/online-chat/dialogs/${dialogId}/messages/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, speaker: 'operator' }),
  })
  const body = await parseJson<{ ok: boolean; message: OnlineChatMessage }>(response)
  return body.message
}

export function onlineChatArmWsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}/ws/online-chat/arm/`
}
