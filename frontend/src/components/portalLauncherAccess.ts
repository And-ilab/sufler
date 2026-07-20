import type { LauncherModule } from './PortalLauncher'

const SUFLER_ROLES = new Set([
  'software_administrator',
  'contact_center_telephony_operator',
  'contact_center_online_chat_operator',
])

const ASSISTANT_ROLES = new Set([
  'software_administrator',
  'contact_center_telephony_operator',
  'contact_center_online_chat_operator',
  'ai_assistant_module_administrator',
  'ai_assistant_user',
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
