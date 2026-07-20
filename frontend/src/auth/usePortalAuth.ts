import { useEffect, useState } from 'react'

interface AuthContextResponse {
  authenticated: boolean
  username: string | null
  roles: string[]
  tabs: string[]
}

export interface PortalAuthState {
  status: 'loading' | 'ready' | 'unavailable'
  username: string | null
  roles: string[]
  tabs: string[]
}

function devRoles(): string[] {
  if (!import.meta.env.DEV) {
    return []
  }
  return String(import.meta.env.VITE_DEV_RBAC_ROLES ?? '')
    .split(',')
    .map((role) => role.trim())
    .filter(Boolean)
}

export function usePortalAuth(): PortalAuthState {
  const [state, setState] = useState<PortalAuthState>({
    status: 'loading',
    username: null,
    roles: [],
    tabs: [],
  })

  useEffect(() => {
    const controller = new AbortController()
    void fetch('/api/auth/me/', {
      credentials: 'include',
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Auth context failed: ${response.status}`)
        }
        return (await response.json()) as AuthContextResponse
      })
      .then((payload) => {
        setState({
          status: 'ready',
          username: payload.username,
          roles: payload.authenticated ? payload.roles : [],
          tabs: payload.authenticated ? payload.tabs : [],
        })
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }
        const fallbackRoles = devRoles()
        setState({
          status: fallbackRoles.length ? 'ready' : 'unavailable',
          username: fallbackRoles.length ? 'Development user' : null,
          roles: fallbackRoles,
          tabs: [],
        })
      })
    return () => controller.abort()
  }, [])

  return state
}
