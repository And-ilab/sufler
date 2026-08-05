/**
 * Local/dev bootstrap: establish Django session via mock_ldap so admin APIs
 * (KB upload/create, …) do not fail with authentication_required.
 */

let inFlight: Promise<boolean> | null = null

function isDevRuntime(): boolean {
  return Boolean(import.meta.env.DEV || import.meta.env.VITE_SUFLER_DEMO === '1')
}

async function fetchAuthMe(): Promise<{ authenticated: boolean }> {
  const response = await fetch('/api/auth/me/', { credentials: 'include' })
  if (!response.ok) return { authenticated: false }
  return (await response.json()) as { authenticated: boolean }
}

async function tryLogin(username: string, password: string): Promise<boolean> {
  const response = await fetch('/api/auth/login/', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!response.ok) return false
  const body = (await response.json()) as { ok?: boolean; authenticated?: boolean }
  return Boolean(body.ok || body.authenticated)
}

async function loginDevUser(): Promise<boolean> {
  const username = String(
    import.meta.env.VITE_DEV_AUTH_USER ?? 'dev-role-01',
  ).trim()
  const configured = String(
    import.meta.env.VITE_DEV_AUTH_PASSWORD ?? '',
  ).trim()
  // Try configured password first, then common local/docker placeholders.
  const passwords = [
    configured,
    'dev-only-password',
    'replace-with-dev-only-password',
  ].filter(Boolean)
  const unique = [...new Set(passwords)]
  for (const password of unique) {
    if (await tryLogin(username, password).catch(() => false)) {
      return true
    }
  }
  return false
}

/** Drop cached in-flight promise so the next call re-checks / re-logins. */
export function resetDevSessionCache(): void {
  inFlight = null
}

/** Returns true when the browser has an authenticated Django session (+ CSRF cookie). */
export async function ensureDevSession(): Promise<boolean> {
  if (inFlight) return inFlight

  inFlight = (async () => {
    // GET /me/ also ensures csrftoken cookie for subsequent POST/upload.
    const me = await fetchAuthMe().catch(() => ({ authenticated: false }))
    if (me.authenticated) return true

    if (!isDevRuntime()) return false

    const loggedIn = await loginDevUser().catch(() => false)
    if (!loggedIn) return false

    const again = await fetchAuthMe().catch(() => ({ authenticated: false }))
    return again.authenticated
  })()

  try {
    const ok = await inFlight
    if (!ok) inFlight = null
    return ok
  } catch {
    inFlight = null
    return false
  }
}

export function isAuthErrorMessage(message: string): boolean {
  return /authentication_required|permission_denied|csrf|401|403/i.test(message)
}
