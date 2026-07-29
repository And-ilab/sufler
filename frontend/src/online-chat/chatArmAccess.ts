const ONLINE_CHAT_ARM_ROLES = new Set([
  'software_administrator',
  'contact_center_online_chat_operator',
  'contact_center_module_administrator',
])

export function canAccessOnlineChatArm(roles: readonly string[]): boolean {
  return roles.some((role) => ONLINE_CHAT_ARM_ROLES.has(role))
}
