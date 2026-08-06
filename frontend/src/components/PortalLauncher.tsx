import {
  useMemo,
  useState,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from 'react'
import { AssistantChat } from '../assistant/AssistantChat'
import { SuflerPhoneApp } from '../sufler/SuflerPhoneApp'
import { Button } from './Button'
import { Card } from './Card'
import { Fab } from './Fab'
import { StatusBadge } from './StatusBadge'
import {
  canOpenKbAdminDeepLink,
  canWriteAssistantChat,
  getAllowedLauncherModules,
  getSettingsMenuEntry,
  showPortalSettingsButton,
  type LauncherModule,
  type SettingsMenuEntry,
} from './portalLauncherAccess'
import './PortalLauncher.css'

export type { LauncherModule }

export interface PortalLauncherProps {
  roles: readonly string[]
  username?: string | null
  roleLabel?: string | null
  menuVariant?: 'card' | 'compact'
  initialMenuOpen?: boolean
  initialWindows?: readonly LauncherModule[]
  onOpenModule?: (module: LauncherModule) => void
  onChangeRole?: () => void
  children?: ReactNode
}

const MODULE_LABELS: Record<LauncherModule, string> = {
  sufler: 'Суфлёр',
  assistant: 'Ассистент',
}

const MODULE_GLYPH: Record<LauncherModule, string> = {
  sufler: 'S',
  assistant: 'A',
}

function ModuleGlyph({ module }: { module: LauncherModule }) {
  return (
    <span className={`portal-launcher__glyph portal-launcher__glyph--${module}`}>
      {MODULE_GLYPH[module]}
    </span>
  )
}

interface ModuleWindowProps {
  module: LauncherModule
  username?: string | null
  roleLabel?: string | null
  roles?: readonly string[]
  settingsEntry?: SettingsMenuEntry | null
  onClose: () => void
  onMinimize: () => void
}

function ModuleWindow({
  module,
  username,
  roleLabel,
  roles = [],
  settingsEntry = null,
  onClose,
  onMinimize,
}: ModuleWindowProps) {
  const initialSize =
    module === 'sufler'
      ? { width: 960, height: 580 }
      : { width: 420, height: 560 }
  const [size, setSize] = useState(initialSize)
  const [menuOpen, setMenuOpen] = useState(false)
  const showKbAdmin = canOpenKbAdminDeepLink(roles)

  const resizeBy = (widthDelta: number, heightDelta: number) => {
    const maxWidth = Math.max(320, window.innerWidth - 48)
    const maxHeight = Math.max(280, window.innerHeight - 120)
    setSize((current) => ({
      width: Math.min(maxWidth, Math.max(320, current.width + widthDelta)),
      height: Math.min(maxHeight, Math.max(280, current.height + heightDelta)),
    }))
  }

  const startResize = (event: ReactPointerEvent<HTMLButtonElement>) => {
    event.preventDefault()
    const startX = event.clientX
    const startY = event.clientY
    const startSize = size

    const onPointerMove = (moveEvent: PointerEvent) => {
      const maxWidth = Math.max(320, window.innerWidth - 48)
      const maxHeight = Math.max(280, window.innerHeight - 120)
      setSize({
        width: Math.min(maxWidth, Math.max(320, startSize.width + moveEvent.clientX - startX)),
        height: Math.min(maxHeight, Math.max(280, startSize.height + moveEvent.clientY - startY)),
      })
    }
    const onPointerUp = () => {
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerup', onPointerUp)
    }

    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp)
  }

  const title =
    module === 'sufler' ? 'Суфлёр · активный звонок' : 'Беларусбанк AI'
  const subtitle =
    module === 'sufler'
      ? `Консультация · ${username || 'Оператор КЦ'}`
      : `${username || 'Пользователь'} · ${roleLabel || 'Пользователь ИИ-ассистента'}`

  return (
    <section
      className={`portal-module-window portal-module-window--${module}`}
      style={{ width: `${size.width}px`, height: `${size.height}px` }}
      role="dialog"
      aria-label={title}
      data-testid={`${module}-window`}
    >
      <header className="portal-module-window__header">
        <div className="portal-module-window__identity">
          <ModuleGlyph module={module} />
          <div>
            <strong>{title}</strong>
            <span>{subtitle}</span>
          </div>
        </div>
        <div className="portal-module-window__controls">
          {settingsEntry && (
            <button
              type="button"
              aria-label="Открыть меню AI Hub"
              aria-expanded={menuOpen}
              data-testid="admin-center-gear"
              onClick={() => setMenuOpen((value) => !value)}
            >
              ≡
            </button>
          )}
          <a href={`/${module}`} aria-label={`Открыть ${MODULE_LABELS[module]} отдельно`}>
            ↗
          </a>
          <button type="button" onClick={onMinimize} aria-label="Свернуть окно">
            —
          </button>
          <button type="button" onClick={onClose} aria-label="Закрыть окно">
            ×
          </button>
        </div>
        {menuOpen && settingsEntry && (
          <Card className="portal-module-window__menu" role="menu">
            <a
              role="menuitem"
              href={settingsEntry.href}
              data-testid="admin-center-link"
              onClick={() => setMenuOpen(false)}
            >
              {settingsEntry.label}
            </a>
            {showKbAdmin && (
              <a
                role="menuitem"
                href="/ai-hub/admin/kb_admin"
                onClick={() => setMenuOpen(false)}
              >
                БЗ · полное окно
              </a>
            )}
            <button type="button" role="menuitem" onClick={() => setMenuOpen(false)}>
              Закрыть меню
            </button>
          </Card>
        )}
      </header>

      {module === 'sufler' ? (
        <div className="portal-module-window__body portal-module-window__body--sufler-app">
          <SuflerPhoneApp
            demoMode
            embedded
            operatorName={username || 'Иванова М.П.'}
          />
        </div>
      ) : (
        <AssistantWindowContent
          username={username}
          roleLabel={roleLabel}
          readOnly={!canWriteAssistantChat(roles)}
        />
      )}

      <button
        type="button"
        className="portal-module-window__resize"
        onPointerDown={startResize}
        onKeyDown={(event) => {
          if (event.key.startsWith('Arrow')) event.preventDefault()
          const delta = event.shiftKey ? 40 : 10
          if (event.key === 'ArrowRight') resizeBy(delta, 0)
          if (event.key === 'ArrowLeft') resizeBy(-delta, 0)
          if (event.key === 'ArrowDown') resizeBy(0, delta)
          if (event.key === 'ArrowUp') resizeBy(0, -delta)
        }}
        aria-label={`Изменить размер окна ${MODULE_LABELS[module]}`}
      />
    </section>
  )
}

function AssistantWindowContent({
  username,
  roleLabel,
  readOnly = false,
}: {
  username?: string | null
  roleLabel?: string | null
  readOnly?: boolean
}) {
  return (
    <div className="portal-module-window__body portal-module-window__body--assistant">
      <nav className="portal-assistant-tabs" aria-label="Модули окна">
        <span className="is-active">Ассистент</span>
        <span aria-disabled="true">Документы</span>
      </nav>
      <p className="portal-assistant-userline">
        {username || 'Пользователь'}
        {roleLabel ? ` · ${roleLabel}` : ''}
        {readOnly ? ' · только просмотр' : ''}
      </p>
      <AssistantChat demoMode compact readOnly={readOnly} />
    </div>
  )
}

function PortalBackdrop({
  children,
  roleLabel,
  onChangeRole,
  settingsEntry,
}: {
  children: ReactNode
  roleLabel?: string | null
  onChangeRole?: () => void
  /** ≡ on portal chrome for roles without S/A windows (analysts / OCR admin). */
  settingsEntry?: SettingsMenuEntry | null
}) {
  return (
    <div className="portal-launcher__backdrop">
      <header className="portal-launcher__portal-header">
        <img src="/assets/belarusbank-logo.png" alt="Беларусбанк" />
        <nav aria-label="Навигация корпоративного портала">
          <a href="#home">Главная</a>
          <a href="#requests">Заявки</a>
          <a href="#knowledge">База знаний</a>
          <a href="#contact-center">Контакт-центр</a>
        </nav>
        <div className="portal-launcher__portal-user">
          {settingsEntry && (
            <a
              href={settingsEntry.href}
              className="portal-launcher__settings-btn"
              aria-label={settingsEntry.label}
              title={settingsEntry.label}
              data-testid="admin-center-gear"
            >
              ≡
            </a>
          )}
          {roleLabel && (
            <button
              type="button"
              className="portal-launcher__role-chip"
              onClick={onChangeRole}
              data-testid="change-role-button"
            >
              Роль: {roleLabel}
            </button>
          )}
          <span>Алексей Морозов</span>
        </div>
      </header>
      <main className="portal-launcher__portal-content">
        <p className="portal-launcher__portal-eyebrow">
          Внутренний корпоративный портал банка · компактная кнопка AI, по клику выезжают иконки модулей
        </p>
        <h1>Добрый день, Алексей</h1>
        <div className="portal-launcher__portal-grid" aria-hidden="true">
          <Card><span>Мои задачи</span><strong>8</strong></Card>
          <Card><span>Новые заявки</span><strong>3</strong></Card>
          <Card><span>Обновления базы знаний</span><strong>12</strong></Card>
        </div>
      </main>
      {children}
    </div>
  )
}

export function PortalLauncher({
  roles,
  username = null,
  roleLabel = null,
  menuVariant = 'card',
  initialMenuOpen = false,
  initialWindows = [],
  onOpenModule,
  onChangeRole,
  children,
}: PortalLauncherProps) {
  const modules = useMemo(
    () => getAllowedLauncherModules(roles),
    [roles],
  )
  const settingsEntry = useMemo(() => getSettingsMenuEntry(roles), [roles])
  const portalSettingsEntry = useMemo(
    () => (showPortalSettingsButton(roles) ? settingsEntry : null),
    [roles, settingsEntry],
  )
  const [menuOpen, setMenuOpen] = useState(initialMenuOpen)
  const [openWindows, setOpenWindows] = useState<Set<LauncherModule>>(
    () => new Set(initialWindows.filter((module) => modules.includes(module))),
  )

  const openModule = (module: LauncherModule) => {
    setOpenWindows((current) => new Set(current).add(module))
    setMenuOpen(false)
    onOpenModule?.(module)
  }

  const closeModule = (module: LauncherModule) => {
    setOpenWindows((current) => {
      const next = new Set(current)
      next.delete(module)
      return next
    })
  }

  const handleFabClick = () => {
    setMenuOpen((value) => !value)
  }

  return (
    <PortalBackdrop
      roleLabel={roleLabel}
      onChangeRole={onChangeRole}
      settingsEntry={portalSettingsEntry}
    >
      {children}

      {openWindows.has('sufler') && (
        <ModuleWindow
          module="sufler"
          username={username}
          roleLabel={roleLabel}
          roles={roles}
          settingsEntry={settingsEntry}
          onClose={() => closeModule('sufler')}
          onMinimize={() => closeModule('sufler')}
        />
      )}
      {openWindows.has('assistant') && (
        <ModuleWindow
          module="assistant"
          username={username}
          roleLabel={roleLabel}
          roles={roles}
          settingsEntry={settingsEntry}
          onClose={() => closeModule('assistant')}
          onMinimize={() => closeModule('assistant')}
        />
      )}

      {modules.length > 0 && menuVariant === 'card' && menuOpen && (
        <Card
          className="portal-launcher__menu"
          role="menu"
          aria-label="Выбрать модуль"
          id="portal-launcher-menu"
          data-testid="launcher-menu"
        >
          <div className="portal-launcher__menu-heading">
            <strong>Выбрать модуль</strong>
            <span>Откроется отдельное стартовое окно</span>
          </div>
          <div className="portal-launcher__menu-options">
            {modules.map((module) => (
              <button
                type="button"
                role="menuitem"
                key={module}
                onClick={() => openModule(module)}
              >
                <ModuleGlyph module={module} />
                <span>
                  <strong>{MODULE_LABELS[module]}</strong>
                  <small>{openWindows.has(module) ? 'Уже открыт' : 'Открыть окно'}</small>
                </span>
              </button>
            ))}
          </div>
        </Card>
      )}

      {modules.length > 0 && (
        <div
          className={`portal-launcher__fab portal-launcher__fab--${menuVariant}${
            menuOpen && menuVariant === 'compact' ? ' is-expanded' : ''
          }`}
        >
          {menuVariant === 'compact' && menuOpen && (
            <div
              className="portal-launcher__compact-rail"
              role="menu"
              aria-label="Модули AI"
              id="portal-launcher-menu"
              data-testid="launcher-menu"
            >
              {modules.map((module) => (
                <button
                  key={module}
                  type="button"
                  role="menuitem"
                  className={`portal-launcher__compact-item${
                    openWindows.has(module) ? ' is-active' : ''
                  }`}
                  onClick={() => openModule(module)}
                  title={MODULE_LABELS[module]}
                  data-testid={`launcher-module-${module}`}
                >
                  <span className="portal-launcher__compact-label">
                    {MODULE_LABELS[module]}
                  </span>
                  <span className="portal-launcher__compact-icon" aria-hidden="true">
                    <span>{MODULE_GLYPH[module]}</span>
                  </span>
                </button>
              ))}
            </div>
          )}

          <Fab
            aria-label="Открыть меню Суфлёр и Ассистент"
            aria-expanded={menuOpen}
            aria-controls="portal-launcher-menu"
            badge={menuVariant === 'card' ? modules.length : undefined}
            onClick={handleFabClick}
            data-testid="launcher-button"
            className={menuOpen ? 'is-open' : undefined}
          >
            <span aria-hidden="true">AI</span>
          </Fab>
        </div>
      )}

      {modules.length === 0 && (
        <div className="portal-launcher__empty-modules" role="status">
          <Card>
            <StatusBadge status={settingsEntry ? 'info' : 'warning'}>
              {settingsEntry?.kind === 'reports' ? 'Отчётность I.4' : 'Нет модулей S/A'}
            </StatusBadge>
            <p>
              {settingsEntry
                ? `У роли нет окон Суфлёр/Ассистент. Доступ: «${settingsEntry.label}» через ≡ или кнопку ниже.`
                : 'У выбранной роли нет доступа к Суфлёру и Ассистенту. Выберите другую роль по матрице I.4.'}
            </p>
            {settingsEntry && (
              <Button
                onClick={() => window.location.assign(settingsEntry.href)}
                data-testid="admin-center-link"
              >
                {settingsEntry.label}
              </Button>
            )}
            {onChangeRole && (
              <Button variant="ghost" onClick={onChangeRole}>Сменить роль</Button>
            )}
          </Card>
        </div>
      )}
    </PortalBackdrop>
  )
}
