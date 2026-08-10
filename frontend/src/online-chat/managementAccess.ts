const ONLINE_CHAT_SUPERVISOR_ROLES = new Set([
  'software_administrator',
  'contact_center_module_administrator',
  'contact_center_supervisor',
  'contact_center_analyst',
])

const ONLINE_CHAT_ADMIN_ROLES = new Set([
  'software_administrator',
  'contact_center_module_administrator',
])

export function canAccessOnlineChatSupervisor(roles: readonly string[]): boolean {
  return roles.some((role) => ONLINE_CHAT_SUPERVISOR_ROLES.has(role))
}

export function canAccessOnlineChatAdmin(roles: readonly string[]): boolean {
  return roles.some((role) => ONLINE_CHAT_ADMIN_ROLES.has(role))
}
