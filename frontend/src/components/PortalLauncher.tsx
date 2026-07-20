import {
  useMemo,
  useState,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from 'react'
import { Button } from './Button'
import { Card } from './Card'
import { Fab } from './Fab'
import { HintCard } from './HintCard'
import { StatusBadge } from './StatusBadge'
import { getAllowedLauncherModules } from './portalLauncherAccess'
import './PortalLauncher.css'

export type LauncherModule = 'sufler' | 'assistant'

export interface PortalLauncherProps {
  roles: readonly string[]
  initialMenuOpen?: boolean
  initialWindows?: readonly LauncherModule[]
  onOpenModule?: (module: LauncherModule) => void
}

const MODULE_LABELS: Record<LauncherModule, string> = {
  sufler: 'Суфлёр',
  assistant: 'Ассистент',
}

function ModuleGlyph({ module }: { module: LauncherModule }) {
  return (
    <span className={`portal-launcher__glyph portal-launcher__glyph--${module}`}>
      {module === 'sufler' ? 'S' : 'A'}
    </span>
  )
}

interface ModuleWindowProps {
  module: LauncherModule
  onClose: () => void
  onMinimize: () => void
}

function ModuleWindow({ module, onClose, onMinimize }: ModuleWindowProps) {
  const initialSize =
    module === 'sufler'
      ? { width: 620, height: 390 }
      : { width: 410, height: 520 }
  const [size, setSize] = useState(initialSize)
  const [maximized, setMaximized] = useState(false)

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

  const style = maximized
    ? undefined
    : {
        width: `${size.width}px`,
        height: `${size.height}px`,
      }

  return (
    <section
      className={`portal-module-window portal-module-window--${module} ${
        maximized ? 'portal-module-window--maximized' : ''
      }`}
      style={style}
      role="dialog"
      aria-label={`${MODULE_LABELS[module]} — стартовое окно`}
      data-testid={`${module}-window`}
    >
      <header className="portal-module-window__header">
        <div className="portal-module-window__identity">
          <ModuleGlyph module={module} />
          <div>
            <strong>{MODULE_LABELS[module]}</strong>
            <span>{module === 'sufler' ? 'Активный звонок' : 'Корпоративный помощник'}</span>
          </div>
        </div>
        <div className="portal-module-window__controls">
          <a href={`/${module}`} aria-label={`Открыть ${MODULE_LABELS[module]} отдельно`}>
            ↗
          </a>
          <button type="button" onClick={onMinimize} aria-label="Свернуть окно">
            —
          </button>
          <button
            type="button"
            onClick={() => setMaximized((value) => !value)}
            aria-label={maximized ? 'Восстановить размер' : 'Развернуть окно'}
          >
            □
          </button>
          <button type="button" onClick={onClose} aria-label="Закрыть окно">
            ×
          </button>
        </div>
      </header>

      {module === 'sufler' ? <SuflerWindowContent /> : <AssistantWindowContent />}

      {!maximized && (
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
      )}
    </section>
  )
}

function SuflerWindowContent() {
  return (
    <div className="portal-module-window__body">
      <div className="portal-module-window__status-row">
        <div>
          <span className="portal-module-window__eyebrow">Клиент</span>
          <strong>Иван Петров · 03:42</strong>
        </div>
        <StatusBadge status="success">В эфире</StatusBadge>
      </div>
      <div className="portal-transcript">
        <p>
          <span>Клиент</span>
          Подскажите, можно ли изменить лимит международного перевода?
        </p>
        <p>
          <span>Оператор</span>
          Сейчас проверю доступные варианты.
        </p>
      </div>
      <HintCard title="Повышение лимита перевода" relevance="94%">
        Временное повышение лимита доступно после проверки операции. Для постоянного
        изменения клиент может обратиться в отделение с документом.
      </HintCard>
      <div className="portal-module-window__actions">
        <Button>Использовать ответ</Button>
        <Button variant="ghost">Открыть источник</Button>
      </div>
    </div>
  )
}

function AssistantWindowContent() {
  return (
    <div className="portal-module-window__body">
      <div className="portal-module-window__status-row">
        <div>
          <span className="portal-module-window__eyebrow">ИИ-ассистент</span>
          <strong>Новый диалог</strong>
        </div>
        <StatusBadge status="info">Внутренний</StatusBadge>
      </div>
      <div className="portal-assistant-thread">
        <p className="portal-assistant-thread__user">Как оформить отпуск?</p>
        <Card>
          <strong>Ассистент</strong>
          <p>
            Подайте заявление в HR-портале не позднее чем за пять рабочих дней.
            При необходимости приложите согласование руководителя.
          </p>
          <small>Источник: регламент отпусков · 96%</small>
        </Card>
      </div>
      <label className="portal-assistant-input">
        <span>Ваш запрос</span>
        <div>
          <input type="text" placeholder="Введите сообщение" />
          <Button aria-label="Отправить запрос">Отправить</Button>
        </div>
      </label>
    </div>
  )
}

function PortalBackdrop({ children }: { children: ReactNode }) {
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
        <span>Алексей Морозов</span>
      </header>
      <main className="portal-launcher__portal-content">
        <p className="portal-launcher__portal-eyebrow">Корпоративный портал</p>
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
  initialMenuOpen = false,
  initialWindows = [],
  onOpenModule,
}: PortalLauncherProps) {
  const modules = useMemo(
    () => getAllowedLauncherModules(roles),
    [roles],
  )
  const [menuOpen, setMenuOpen] = useState(initialMenuOpen)
  const [openWindows, setOpenWindows] = useState<Set<LauncherModule>>(
    () => new Set(initialWindows.filter((module) => modules.includes(module))),
  )

  if (modules.length === 0) {
    return <PortalBackdrop>{null}</PortalBackdrop>
  }

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

  return (
    <PortalBackdrop>
      {openWindows.has('sufler') && (
        <ModuleWindow
          module="sufler"
          onClose={() => closeModule('sufler')}
          onMinimize={() => closeModule('sufler')}
        />
      )}
      {openWindows.has('assistant') && (
        <ModuleWindow
          module="assistant"
          onClose={() => closeModule('assistant')}
          onMinimize={() => closeModule('assistant')}
        />
      )}

      {menuOpen && (
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

      <div className="portal-launcher__fab">
        <Fab
          aria-label="Открыть меню Суфлёр и Ассистент"
          aria-expanded={menuOpen}
          aria-controls="portal-launcher-menu"
          badge={modules.length}
          onClick={() => setMenuOpen((value) => !value)}
          data-testid="launcher-button"
        >
          <span aria-hidden="true">AI</span>
        </Fab>
      </div>
    </PortalBackdrop>
  )
}
