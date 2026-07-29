export function canAccessCcReports(roles: readonly string[]): boolean {
  return roles.some((role) =>
    ['software_administrator', 'contact_center_analyst'].includes(role),
  )
}
