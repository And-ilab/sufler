export type LauncherModule = 'sufler' | 'assistant'

/** Roles that may open Суфлёр (operators + admins who need preview in DEV). */
const SUFLER_ROLES = new Set([
  'software_administrator',
  'contact_center_module_administrator',
  'contact_center_telephony_operator',
  'contact_center_online_chat_operator',
  // DEV preview: KB admin configures CC content and needs to open S/A
  'llm_knowledge_base_administrator',
])

/** Roles that may open Ассистент. */
const ASSISTANT_ROLES = new Set([
  'software_administrator',
  'llm_knowledge_base_administrator',
  'ai_assistant_module_administrator',
  'ai_assistant_user',
  'contact_center_telephony_operator',
  'contact_center_online_chat_operator',
])

const ADMIN_CENTER_ROLES = new Set([
  'software_administrator',
  'llm_knowledge_base_administrator',
  'contact_center_module_administrator',
  'ai_assistant_module_administrator',
  'document_recognition_module_administrator',
])

export function getAllowedLauncherModules(
  roles: readonly string[],
): LauncherModule[] {
  const roleSet = new Set(roles)
  const modules: LauncherModule[] = []
  if ([...SUFLER_ROLES].some((role) => roleSet.has(role))) {
    modules.push('sufler')
  }
  if ([...ASSISTANT_ROLES].some((role) => roleSet.has(role))) {
    modules.push('assistant')
  }
  return modules
}

export function roleHasLauncherModules(roles: readonly string[]): boolean {
  return getAllowedLauncherModules(roles).length > 0
}

export function canOpenAdminCenter(roles: readonly string[]): boolean {
  return roles.some((role) => ADMIN_CENTER_ROLES.has(role))
}
