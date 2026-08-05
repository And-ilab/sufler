export interface AssistantKbOption {
  id: string
  slug: string
  label: string
  documentCount: number
}

interface AssistantKbApiItem {
  id: number
  name: string
  slug: string
  description?: string
  document_count?: number
}

export async function fetchAssistantKnowledgeBases(): Promise<AssistantKbOption[]> {
  const response = await fetch('/api/v1/assistant/kbs/', {
    credentials: 'include',
  })
  if (!response.ok) {
    throw new Error(`KB catalog failed: ${response.status}`)
  }
  const body = (await response.json()) as { items?: AssistantKbApiItem[] }
  return (body.items ?? []).map((item) => ({
    id: String(item.id),
    slug: item.slug,
    label: (item.name || item.slug).trim(),
    documentCount: item.document_count ?? 0,
  }))
}
