export type ModelParamsProfile = 'assistant_bank' | 'sufler_cc'

export interface ModelParamsData {
  profile: ModelParamsProfile
  slot: string
  generation: {
    temperature: number
    top_p: number
    max_tokens: number
    response_chars_max: number
  }
  rag: {
    chunk_size_tokens: number
    chunk_overlap_tokens: number
    context_inclusion: number
    deterministic_answer: number
  }
  read_only: {
    dev_model: string | null
    prod_candidate: string | null
    status: string
  }
  constraints: {
    temperature: { min: number; max: number; step: number }
    top_p: { min: number; max: number; step: number }
    max_tokens: { min: number; max: number }
    response_chars_max: { min: number; max: number }
  }
  revision: number
  updated_at: string
  updated_by: string
}

export interface ModelParamsPayload {
  generation: ModelParamsData['generation']
  rag: ModelParamsData['rag']
}

interface ApiErrorPayload {
  error?: string
  details?: Record<string, string[]>
}

export class ModelParamsApiError extends Error {
  readonly details: Record<string, string[]>

  constructor(
    message: string,
    details: Record<string, string[]> = {},
  ) {
    super(message)
    this.details = details
  }
}

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

async function parseResponse(response: Response): Promise<ModelParamsData> {
  const body = await response.json() as ModelParamsData | ApiErrorPayload
  if (!response.ok) {
    const error = body as ApiErrorPayload
    throw new ModelParamsApiError(
      error.error ?? `Request failed with status ${response.status}`,
      error.details ?? {},
    )
  }
  return body as ModelParamsData
}

export async function loadModelParams(
  profile: ModelParamsProfile,
): Promise<ModelParamsData> {
  const response = await fetch(
    `/api/admin/model-registry/model-params/?profile=${profile}`,
    { credentials: 'include' },
  )
  return parseResponse(response)
}

export async function saveModelParams(
  profile: ModelParamsProfile,
  payload: ModelParamsPayload,
): Promise<ModelParamsData> {
  const response = await fetch(
    `/api/admin/model-registry/model-params/?profile=${profile}`,
    {
      method: 'PUT',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken(),
      },
      body: JSON.stringify(payload),
    },
  )
  return parseResponse(response)
}
