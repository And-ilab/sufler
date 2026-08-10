/** HTTP + helpers for Django online_chat API (`/api/v1/online-chat/`). */

export type DialogStatus = 'waiting' | 'active' | 'closed' | 'blocked'

export type DialogSpeaker = 'client' | 'operator' | 'bot' | 'system'

export type ReceiptStatus = 'delivered' | 'read'

export type SlaTone = 'ok' | 'warn' | 'critical'

export type OnlineChatDialog = {
  id: string
  ref_code?: string
  widget_id: string
  placement: string
  channel: string
  status: DialogStatus
  initiated_by?: 'client' | 'operator'
  client_first_name: string
  client_last_name: string
  client_phone: string
  client_external_id?: string
  client_name: string
  client_online?: boolean
  operator_name: string
  department_id?: string | null
  department_name?: string | null
  preview: string
  close_topic: string
  created_at: string
  updated_at: string
  accepted_at: string | null
  closed_at: string | null
  client_last_seen_at?: string | null
  wait_seconds: number
  needs_reply?: boolean
  has_feedback?: boolean
  messages?: OnlineChatMessage[]
}

export type ClientHistoryItem = {
  id: string
  channel: string
  status: string
  outcome?: string
  topic?: string
  operator_name?: string
  preview?: string
  created_at: string
  closed_at?: string | null
  message_count?: number
}

export type ClientHistoryResponse = {
  ok: boolean
  items: ClientHistoryItem[]
  count: number
  summary: string
}

export type OnlineChatFeedback = {
  id: string
  dialog_id: string
  rating: number
  comment: string
  created_at: string
}

export type OnlineChatTranscriptEmail = {
  id: string
  dialog_id: string
  email: string
  status: 'pending' | 'sent' | 'failed'
  error_detail: string
  created_at: string
  sent_at: string | null
}

export type OnlineChatMessage = {
  id: string
  dialog_id: string
  speaker: DialogSpeaker
  text: string
  raw_text?: string
  receipt_status?: ReceiptStatus
  reply_to_id?: string | null
  quoted_text?: string
  edited_at?: string | null
  is_deleted?: boolean
  attachment_name?: string
  attachment_key?: string
  attachment_content_type?: string
  attachment_size?: number
  attachment_scan_status?: string
  created_at: string
}

export type OnlineChatClientBlock = {
  id: string
  phone: string
  phone_normalized: string
  reason: string
  blocked_by: string
  dialog_id: string | null
  is_active: boolean
  created_at: string
  lifted_at: string | null
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

/** SLA tiers: green < 60s, yellow 60–119s, red ≥ 120s. */
export function slaToneFromSeconds(totalSeconds: number): SlaTone {
  if (totalSeconds >= 120) return 'critical'
  if (totalSeconds >= 60) return 'warn'
  return 'ok'
}

export function maskPhone(phone: string): string {
  const digits = phone.replace(/\D/g, '')
  if (digits.length < 4) return phone || '—'
  return `+${digits.slice(0, 3)} ** ***-**-${digits.slice(-2)}`
}

export function dialogRefCode(dialog: Pick<OnlineChatDialog, 'id' | 'ref_code'>): string {
  if (dialog.ref_code) return dialog.ref_code
  return dialog.id.replace(/-/g, '').slice(0, 6).toUpperCase()
}

export async function listDialogs(
  status?: DialogStatus,
  extras?: { client_online?: boolean; initiated_by?: 'client' | 'operator' },
): Promise<OnlineChatDialog[]> {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  if (extras?.client_online === true) params.set('client_online', 'true')
  if (extras?.client_online === false) params.set('client_online', 'false')
  if (extras?.initiated_by) params.set('initiated_by', extras.initiated_by)
  const query = params.toString() ? `?${params.toString()}` : ''
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

export async function transferDialogRemote(
  dialogId: string,
  toOperatorName: string,
  fromOperatorName = '',
): Promise<OnlineChatDialog> {
  const response = await fetch(`/api/v1/online-chat/dialogs/${dialogId}/transfer/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      to_operator_name: toOperatorName,
      from_operator_name: fromOperatorName,
    }),
  })
  const body = await parseJson<{ ok: boolean; dialog: OnlineChatDialog }>(response)
  return body.dialog
}

export async function closeDialogRemote(
  dialogId: string,
  topic: string,
): Promise<OnlineChatDialog> {
  const response = await fetch(`/api/v1/online-chat/dialogs/${dialogId}/close/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic }),
  })
  const body = await parseJson<{ ok: boolean; dialog: OnlineChatDialog }>(response)
  return body.dialog
}

export async function submitDialogFeedback(
  dialogId: string,
  rating: number,
  comment = '',
): Promise<OnlineChatFeedback> {
  const response = await fetch(`/api/v1/online-chat/dialogs/${dialogId}/feedback/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rating, comment }),
  })
  const body = await parseJson<{ ok: boolean; feedback: OnlineChatFeedback }>(response)
  return body.feedback
}

export async function sendDialogTranscript(
  dialogId: string,
  email: string,
): Promise<OnlineChatTranscriptEmail> {
  const response = await fetch(
    `/api/v1/online-chat/dialogs/${dialogId}/send-transcript/`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    },
  )
  const body = await parseJson<{
    ok: boolean
    transcript_email: OnlineChatTranscriptEmail
  }>(response)
  return body.transcript_email
}

export async function blockDialogRemote(
  dialogId: string,
  extras?: { blocked_by?: string; reason?: string },
): Promise<OnlineChatDialog> {
  const response = await fetch(`/api/v1/online-chat/dialogs/${dialogId}/block/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(extras || {}),
  })
  const body = await parseJson<{ ok: boolean; dialog: OnlineChatDialog }>(response)
  return body.dialog
}

export async function listClientBlocks(activeOnly = true): Promise<OnlineChatClientBlock[]> {
  const query = activeOnly ? '?active=1' : '?active=0'
  const response = await fetch(`/api/v1/online-chat/blocks/${query}`)
  const body = await parseJson<{ ok: boolean; items: OnlineChatClientBlock[] }>(response)
  return body.items
}

export async function liftClientBlock(
  blockId: string,
  liftedBy = 'admin',
): Promise<OnlineChatClientBlock> {
  const response = await fetch(`/api/v1/online-chat/blocks/${blockId}/lift/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lifted_by: liftedBy }),
  })
  const body = await parseJson<{ ok: boolean; block: OnlineChatClientBlock }>(response)
  return body.block
}

export async function sendOperatorMessage(
  dialogId: string,
  text: string,
  extras?: {
    reply_to_id?: string
    attachment_name?: string
    operator_name?: string
    response_origin?: string
    sufler_suggestion_text?: string
  },
): Promise<OnlineChatMessage> {
  const response = await fetch(`/api/v1/online-chat/dialogs/${dialogId}/messages/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text,
      speaker: 'operator',
      reply_to_id: extras?.reply_to_id,
      attachment_name: extras?.attachment_name,
      operator_name: extras?.operator_name,
      response_origin: extras?.response_origin,
      sufler_suggestion_text: extras?.sufler_suggestion_text,
    }),
  })
  const body = await parseJson<{ ok: boolean; message: OnlineChatMessage }>(response)
  return body.message
}

export async function uploadOperatorAttachment(
  dialogId: string,
  file: File,
  operatorName = '',
): Promise<OnlineChatMessage> {
  const form = new FormData()
  form.append('file', file)
  form.append('speaker', 'operator')
  form.append('operator_name', operatorName)
  const response = await fetch(
    `/api/v1/online-chat/dialogs/${dialogId}/attachments/`,
    { method: 'POST', body: form },
  )
  const body = await parseJson<{ ok: boolean; message: OnlineChatMessage }>(response)
  return body.message
}

export function attachmentDownloadUrl(dialogId: string, messageId: string): string {
  return `/api/v1/online-chat/dialogs/${dialogId}/attachments/${messageId}/`
}

export async function fetchClientHistory(params: {
  dialogId?: string
  phone?: string
  externalId?: string
}): Promise<ClientHistoryResponse> {
  const query = new URLSearchParams()
  if (params.dialogId) query.set('dialog_id', params.dialogId)
  if (params.phone) query.set('phone', params.phone)
  if (params.externalId) query.set('external_id', params.externalId)
  const response = await fetch(`/api/v1/online-chat/history/?${query.toString()}`)
  return parseJson<ClientHistoryResponse>(response)
}

export async function editMessageRemote(
  dialogId: string,
  messageId: string,
  text: string,
): Promise<OnlineChatMessage> {
  const response = await fetch(
    `/api/v1/online-chat/dialogs/${dialogId}/messages/${messageId}/`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    },
  )
  const body = await parseJson<{ ok: boolean; message: OnlineChatMessage }>(response)
  return body.message
}

export async function deleteMessageRemote(
  dialogId: string,
  messageId: string,
): Promise<OnlineChatMessage> {
  const response = await fetch(
    `/api/v1/online-chat/dialogs/${dialogId}/messages/${messageId}/`,
    { method: 'DELETE' },
  )
  const body = await parseJson<{ ok: boolean; message: OnlineChatMessage }>(response)
  return body.message
}

export async function markDialogRead(
  dialogId: string,
  reader: 'client' | 'operator',
): Promise<{ message_ids: string[]; messages: OnlineChatMessage[] }> {
  const response = await fetch(`/api/v1/online-chat/dialogs/${dialogId}/read/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reader }),
  })
  const body = await parseJson<{
    ok: boolean
    message_ids: string[]
    messages: OnlineChatMessage[]
  }>(response)
  return { message_ids: body.message_ids, messages: body.messages }
}

export async function createOperatorInitiatedDialog(payload: {
  text: string
  first_name?: string
  last_name?: string
  phone?: string
  operator_name: string
}): Promise<OnlineChatDialog> {
  const response = await fetch('/api/v1/online-chat/dialogs/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...payload,
      initiated_by: 'operator',
      channel: 'widget',
    }),
  })
  const body = await parseJson<{ ok: boolean; dialog: OnlineChatDialog }>(response)
  return body.dialog
}

export function onlineChatArmWsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}/ws/online-chat/arm/`
}

export const REPLY_TEMPLATES = [
  'Здравствуйте! Чем могу помочь?',
  'Проверяю информацию, одну минуту.',
  'Подскажите, пожалуйста, номер карты (последние 4 цифры).',
  'Операция выполнена. Могу ещё чем-то помочь?',
  'Спасибо за обращение! Хорошего дня.',
] as const
