import type { CSSProperties, ReactNode } from 'react'
import { ARM_THEME_DARK, ARM_THEME_LIGHT, type ThemeKind } from '../arm/theme'
import './ChatPlatformShell.css'

interface ChatPlatformShellProps {
  children: ReactNode
  currentPath: string
  displayName?: string | null
  jobTitle?: string | null
  showSupervisor?: boolean
  showAdmin?: boolean
  showSimulator?: boolean
  themeKind?: ThemeKind
  onToggleTheme?: () => void
  showMenuButton?: boolean
  menuOpen?: boolean
  onMenuToggle?: () => void
}

const routes = [
  { href: '/online-chat', label: 'АРМ оператора', access: 'arm' },
  { href: '/online-chat/supervisor', label: 'Супервизор', access: 'supervisor' },
  { href: '/online-chat/admin', label: 'Управление', access: 'admin' },
  { href: '/online-chat/simulator', label: 'Симулятор', access: 'simulator' },
] as const

export function ChatPlatformShell({
  children,
  currentPath,
  displayName,
  jobTitle,
  showSupervisor = false,
  showAdmin = false,
  showSimulator = false,
  themeKind = 'light',
  onToggleTheme,
  showMenuButton = false,
  menuOpen = false,
  onMenuToggle,
}: ChatPlatformShellProps) {
  const t = themeKind === 'light' ? ARM_THEME_LIGHT : ARM_THEME_DARK
  const style = {
    '--arm-accent': t.accent.primary,
    '--arm-accent-control': t.accent.control,
    '--arm-accent-weak': t.fill.tertiary,
    '--arm-header-bg': '#006b3c',
    '--arm-panel-bg': t.fill.secondary,
    '--arm-on-accent': t.text.onAccent,
    '--arm-fill-secondary': t.fill.secondary,
    '--arm-fill-tertiary': t.fill.tertiary,
    '--arm-fill-quaternary': t.fill.quaternary,
    '--arm-stroke-secondary': t.stroke.secondary,
    '--arm-stroke-tertiary': t.stroke.tertiary,
    '--arm-t-primary': t.text.primary,
    '--arm-t-secondary': t.text.secondary,
    '--arm-t-tertiary': t.text.tertiary,
    '--arm-bg-elevated': t.bg.elevated,
    '--arm-bg-editor': t.bg.editor,
  } as CSSProperties

  const visible = (access: typeof routes[number]['access']) =>
    access === 'arm'
    || (access === 'supervisor' && showSupervisor)
    || (access === 'admin' && showAdmin)
    || (access === 'simulator' && showSimulator)

  const userLine = [displayName, jobTitle].filter(Boolean).join(' · ')

  return (
    <div className="chat-platform-shell" style={style} data-theme={themeKind}>
      <header className="chat-platform-shell__header">
        <div className="chat-platform-shell__lead">
          {showMenuButton && (
            <button
              type="button"
              className={`chat-platform-shell__menu${menuOpen ? ' is-open' : ''}`}
              aria-expanded={menuOpen}
              aria-label={menuOpen ? 'Скрыть меню' : 'Открыть меню'}
              title={menuOpen ? 'Скрыть меню' : 'Меню'}
              onClick={onMenuToggle}
            >
              <span aria-hidden="true" />
              <span aria-hidden="true" />
              <span aria-hidden="true" />
            </button>
          )}
          <a className="chat-platform-shell__brand" href="/online-chat" aria-label="Онлайн-чат — главная">
            <span className="chat-platform-shell__mark" aria-hidden="true">ББ</span>
            <span>
              <strong>Онлайн-чат</strong>
              <small>Беларусбанк</small>
            </span>
          </a>
          {onToggleTheme && (
            <button
              type="button"
              className="chat-platform-shell__theme"
              title={themeKind === 'light' ? 'Включить тёмную тему' : 'Включить светлую тему'}
              aria-label={themeKind === 'light' ? 'Тёмная тема' : 'Светлая тема'}
              onClick={onToggleTheme}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
                <circle cx="12" cy="12" r="4.2" stroke="currentColor" strokeWidth="1.8" />
                <path
                  d="M12 3v1.6M12 19.4V21M4.6 12H3M21 12h-1.6M6.2 6.2l1.1 1.1M16.7 16.7l1.1 1.1M6.2 17.8l1.1-1.1M16.7 7.3l1.1-1.1"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          )}
        </div>
        <nav className="chat-platform-shell__nav" aria-label="Разделы онлайн-чата">
          {routes.filter(({ access }) => visible(access)).map(({ href, label }) => {
            const active = currentPath === href
            return (
              <a
                key={href}
                href={href}
                className={active ? 'is-active' : undefined}
                aria-current={active ? 'page' : undefined}
              >
                {label}
              </a>
            )
          })}
        </nav>
        <div className="chat-platform-shell__user" title={userLine || undefined}>
          {displayName && <strong>{displayName}</strong>}
          {jobTitle && <small>{jobTitle}</small>}
          {!displayName && !jobTitle && 'Пользователь'}
        </div>
      </header>
      <div className="chat-platform-shell__content">{children}</div>
    </div>
  )
}
