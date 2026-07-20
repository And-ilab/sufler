export type HubPanelTab = 'assistant' | 'documents' | 'sufler'

const ASSISTANT_ROLES = new Set([
  'software_administrator',
  'contact_center_telephony_operator',
  'contact_center_online_chat_operator',
  'contact_center_internal_user',
  'ai_assistant_module_administrator',
  'ai_assistant_user',
])

const DOCUMENT_ROLES = new Set([
  'software_administrator',
  'document_recognition_module_administrator',
  'document_recognition_user',
])

const SUFLER_ROLES = new Set([
  'software_administrator',
  'contact_center_telephony_operator',
])

export function getHubPanelTabs(
  roles: readonly string[],
  rbacTabs: readonly string[] = [],
): HubPanelTab[] {
  const roleSet = new Set(roles)
  const isSystemAdmin = roleSet.has('software_administrator')
  const hasRole = (allowed: Set<string>) => (
    [...allowed].some((role) => roleSet.has(role))
  )
  const hasTab = (tab: string, fallbackRoles: Set<string>) => (
    isSystemAdmin
    || rbacTabs.includes(tab)
    || (!rbacTabs.length && hasRole(fallbackRoles))
  )

  const tabs: HubPanelTab[] = []
  if (hasTab('assistant', ASSISTANT_ROLES)) tabs.push('assistant')
  if (hasTab('ocr', DOCUMENT_ROLES)) tabs.push('documents')
  if (hasTab('sufler_telephony', SUFLER_ROLES)) tabs.push('sufler')
  return tabs
}

export function isHubAdminRole(roles: readonly string[]): boolean {
  return roles.some((role) => [
    'software_administrator',
    'llm_knowledge_base_administrator',
    'contact_center_module_administrator',
    'ai_assistant_module_administrator',
    'document_recognition_module_administrator',
  ].includes(role))
}
