import { useEffect, useState, type ReactNode } from 'react'
import { operatorsApi } from '../api/managementApi'
import { ChatPlatformShell } from './ChatPlatformShell'
import type { ThemeKind } from '../arm/theme'

type ShellProps = React.ComponentProps<typeof ChatPlatformShell>

/**
 * Loads operator avatar for the shell header and persists uploads
 * both locally and to OperatorProfile when a matching operator exists.
 */
export function ChatPlatformShellWithAvatar({
  displayName,
  photoUrl: photoUrlProp,
  onPhotoChange: onPhotoChangeProp,
  ...rest
}: ShellProps & { children: ReactNode; themeKind?: ThemeKind }) {
  const storageKey = displayName ? `oc-avatar:${displayName}` : null
  const [photoUrl, setPhotoUrl] = useState<string | null>(() => {
    if (photoUrlProp) return photoUrlProp
    if (!storageKey) return null
    try {
      return localStorage.getItem(storageKey)
    } catch {
      return null
    }
  })

  useEffect(() => {
    if (photoUrlProp) {
      setPhotoUrl(photoUrlProp)
      return
    }
    if (!displayName) return
    let cancelled = false
    void operatorsApi
      .list()
      .then((items) => {
        if (cancelled) return
        const match = items.find((item) => item.name === displayName)
        if (match?.photo_url) {
          setPhotoUrl(match.photo_url)
          return
        }
        if (storageKey) {
          try {
            const cached = localStorage.getItem(storageKey)
            if (cached) setPhotoUrl(cached)
          } catch {
            /* ignore */
          }
        }
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [displayName, photoUrlProp, storageKey])

  const onPhotoChange = (dataUrl: string) => {
    setPhotoUrl(dataUrl)
    if (storageKey) {
      try {
        localStorage.setItem(storageKey, dataUrl)
      } catch {
        /* quota */
      }
    }
    onPhotoChangeProp?.(dataUrl)
    if (!displayName) return
    void operatorsApi
      .list()
      .then(async (items) => {
        const match = items.find((item) => item.name === displayName)
        if (match) await operatorsApi.update(match.id, { photo_url: dataUrl })
      })
      .catch(() => undefined)
  }

  return (
    <ChatPlatformShell
      {...rest}
      displayName={displayName}
      photoUrl={photoUrl}
      onPhotoChange={onPhotoChange}
    />
  )
}
