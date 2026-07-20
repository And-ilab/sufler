import {
  useEffect,
  useMemo,
  useState,
  type PointerEvent as ReactPointerEvent,
} from 'react'
import { Button, Card, Fab, HintCard, StatusBadge } from '../../components'
import {
  getHubPanelTabs,
  isHubAdminRole,
  type HubPanelTab,
} from './hubAccess'
import './AiHubPanel.css'

type DocumentSubTab = 'queue' | 'upload' | 'review'

export interface AiHubPanelProps {
  roles: readonly string[]
  rbacTabs?: readonly string[]
  username?: string | null
  callActive?: boolean
  initialOpen?: boolean
  initialTab?: HubPanelTab
  initialPinned?: boolean
}

const TAB_LABELS: Record<HubPanelTab, string> = {
  assistant: 'Ассистент',
  documents: 'Документы',
  sufler: 'Суфлёр',
}

export function AiHubPanel({
  roles,
  rbacTabs = [],
  username = 'Пользователь банка',
  callActive = false,
  initialOpen = false,
  initialTab,
  initialPinned = false,
}: AiHubPanelProps) {
  const roleTabs = useMemo(
    () => getHubPanelTabs(roles, rbacTabs),
    [rbacTabs, roles],
  )
  const visibleTabs = callActive
    ? roleTabs.filter((tab) => tab === 'sufler')
    : roleTabs
  const [open, setOpen] = useState(initialOpen)
  const [pinned, setPinned] = useState(initialPinned)
  const [menuOpen, setMenuOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<HubPanelTab>(
    initialTab && visibleTabs.includes(initialTab)
      ? initialTab
      : visibleTabs[0] ?? 'assistant',
  )
  const [size, setSize] = useState({ width: 400, height: 560 })

  useEffect(() => {
    if (!visibleTabs.includes(activeTab) && visibleTabs[0]) {
      setActiveTab(visibleTabs[0])
    }
  }, [activeTab, visibleTabs])

  if (!visibleTabs.length) return null

  const togglePin = () => {
    const next = !pinned
    setPinned(next)
    if (next) {
      setSize({
        width: Math.min(960, window.innerWidth - 32),
        height: Math.min(860, window.innerHeight - 32),
      })
    }
  }

  const startResize = (event: ReactPointerEvent<HTMLButtonElement>) => {
    event.preventDefault()
    setPinned(false)
    const startX = event.clientX
    const startY = event.clientY
    const startSize = size
    const move = (moveEvent: PointerEvent) => {
      setSize({
        width: Math.min(
          Math.min(960, window.innerWidth - 24),
          Math.max(360, startSize.width + startX - moveEvent.clientX),
        ),
        height: Math.min(
          Math.min(860, window.innerHeight - 24),
          Math.max(420, startSize.height + startY - moveEvent.clientY),
        ),
      })
    }
    const stop = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', stop)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', stop)
  }

  return (
    <div className="hub-panel-layer" data-testid="hub-panel-layer">
      {open && (
        <aside
          className={`hub-panel ${pinned ? 'hub-panel--pinned' : ''}`}
          style={{ width: size.width, height: size.height }}
          role="dialog"
          aria-label="Беларусбанк AI Hub"
          data-testid="hub-panel"
        >
          <header className="hub-panel__header">
            <div className="hub-panel__identity">
              <span className="hub-panel__logo">AI</span>
              <div>
                <strong>Беларусбанк AI</strong>
                <small>{username || 'Авторизованный пользователь'}</small>
              </div>
            </div>
            <div className="hub-panel__controls">
              <button
                type="button"
                aria-label="Открыть меню AI Hub"
                aria-expanded={menuOpen}
                onClick={() => setMenuOpen((value) => !value)}
              >
                ≡
              </button>
              <button
                type="button"
                aria-label={pinned ? 'Открепить панель' : 'Закрепить панель'}
                aria-pressed={pinned}
                onClick={togglePin}
              >
                {pinned ? '◆' : '◇'}
              </button>
              <button type="button" aria-label="Свернуть панель" onClick={() => setOpen(false)}>
                —
              </button>
              <button type="button" aria-label="Закрыть панель" onClick={() => setOpen(false)}>
                ×
              </button>
            </div>
            {menuOpen && (
              <Card className="hub-panel__menu" role="menu">
                {isHubAdminRole(roles) && (
                  <a role="menuitem" href="/ai-hub/admin">Центр настроек</a>
                )}
                {roles.some((role) => ['software_administrator', 'llm_knowledge_base_administrator'].includes(role)) && (
                  <a role="menuitem" href="/ai-hub/admin/kb_admin">БЗ · полное окно</a>
                )}
                <button type="button" role="menuitem" onClick={() => setMenuOpen(false)}>
                  Закрыть меню
                </button>
              </Card>
            )}
          </header>

          <div className="hub-panel__tabs" role="tablist" aria-label="Модули AI Hub">
            {visibleTabs.map((tab) => (
              <button
                type="button"
                role="tab"
                key={tab}
                aria-selected={activeTab === tab}
                onClick={() => setActiveTab(tab)}
              >
                {TAB_LABELS[tab]}
                {tab === 'sufler' && callActive && <span>Звонок</span>}
              </button>
            ))}
          </div>

          <main className="hub-panel__body">
            {activeTab === 'assistant' && <AssistantPanel />}
            {activeTab === 'documents' && <DocumentsPanel />}
            {activeTab === 'sufler' && <SuflerPanel callActive={callActive} />}
          </main>

          <footer className="hub-panel__footer">
            <StatusBadge status="success">Подключено</StatusBadge>
            <span>БЗ / СУЗ обновлена · 12:34</span>
          </footer>

          {!pinned && (
            <button
              type="button"
              className="hub-panel__resize"
              aria-label="Изменить размер панели"
              onPointerDown={startResize}
            />
          )}
        </aside>
      )}

      <div className="hub-panel__fab">
        <Fab
          badge={callActive ? 1 : visibleTabs.length}
          aria-label={open ? 'Скрыть AI Hub' : 'Открыть AI Hub'}
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
          data-testid="hub-panel-fab"
        >
          AI
        </Fab>
      </div>
    </div>
  )
}

function AssistantPanel() {
  const [query, setQuery] = useState('')
  return (
    <div className="hub-tab-content">
      <div className="hub-panel__toolbar">
        <select aria-label="База знаний" defaultValue="bank">
          <option value="bank">Общая база знаний</option>
          <option value="hr">HR и внутренние процессы</option>
        </select>
        <Button variant="ghost">История</Button>
      </div>
      <div className="hub-assistant-thread">
        <p className="hub-assistant-thread__user">Как оформить командировку?</p>
        <Card>
          <strong>Ассистент</strong>
          <p>Создайте заявку в HR-портале и приложите согласование руководителя.</p>
          <div><StatusBadge status="info">Регламент · 96%</StatusBadge><Button variant="ghost">Открыть</Button></div>
        </Card>
      </div>
      <div className="hub-panel__feedback" aria-label="Оценить ответ">
        <Button variant="ghost">Полезно</Button>
        <Button variant="ghost">Неполный</Button>
        <Button variant="ghost">Неверно</Button>
      </div>
      <label className="hub-panel__composer">
        <span>Сообщение ассистенту</span>
        <textarea value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Введите запрос" />
        <Button disabled={!query.trim()}>Отправить</Button>
      </label>
    </div>
  )
}

function DocumentsPanel() {
  const [subTab, setSubTab] = useState<DocumentSubTab>('queue')
  return (
    <div className="hub-tab-content">
      <div className="hub-document-tabs" role="tablist" aria-label="Документы">
        {([
          ['queue', 'Очередь'],
          ['upload', 'Загрузить'],
          ['review', 'Проверка'],
        ] as const).map(([id, label]) => (
          <button type="button" role="tab" aria-selected={subTab === id} key={id} onClick={() => setSubTab(id)}>
            {label}
          </button>
        ))}
      </div>
      {subTab === 'queue' && (
        <div className="hub-document-list">
          <Card><strong>passport_ivanov.pdf</strong><span>Паспорт · HITL</span><StatusBadge status="warning">96%</StatusBadge></Card>
          <Card><strong>application_042.pdf</strong><span>Кредитная заявка</span><StatusBadge status="success">Готово</StatusBadge></Card>
          <Button onClick={() => setSubTab('upload')}>Загрузить документы</Button>
        </div>
      )}
      {subTab === 'upload' && (
        <div className="hub-document-upload">
          <strong>Перетащите документы</strong>
          <span>PDF, JPG, PNG, TIFF · до 10 МБ</span>
          <Button>Выбрать файлы</Button>
        </div>
      )}
      {subTab === 'review' && (
        <Card className="hub-document-review">
          <strong>Проверка полей</strong>
          <label>Серия / номер<input defaultValue="MP1234567" /></label>
          <label>Дата рождения<input defaultValue="01.01.1990" /></label>
          <Button>Утвердить и экспортировать</Button>
        </Card>
      )}
    </div>
  )
}

function SuflerPanel({ callActive }: { callActive: boolean }) {
  return (
    <div className="hub-tab-content">
      <div className="hub-call-status">
        <div><small>Клиент</small><strong>Иван Петров · 03:42</strong></div>
        <StatusBadge status={callActive ? 'danger' : 'neutral'}>
          {callActive ? 'Активный звонок' : 'Ожидание'}
        </StatusBadge>
      </div>
      <Card className="hub-call-transcript">
        <small>Клиент · 10:16</small>
        <p>Можно ли изменить лимит международного перевода?</p>
      </Card>
      <HintCard title="Повышение лимита перевода" relevance="94%">
        Временное повышение лимита доступно после проверки операции. Постоянное
        изменение оформляется в отделении с документом.
      </HintCard>
      <HintCard title="Лимиты международных операций" relevance="88%">
        Проверьте текущий лимит в разделе «Настройки» → «Лимиты».
      </HintCard>
      <p className="hub-sufler-note">Ответ озвучивает оператор. Автоотправка клиенту отключена.</p>
    </div>
  )
}

export function AiHubPanelHost(props: AiHubPanelProps) {
  return (
    <div className="hub-panel-host">
      <header><img src="/assets/belarusbank-logo.png" alt="Беларусбанк" /><span>Корпоративный портал · Рабочее место</span></header>
      <main><p>AI Hub доступен из правого нижнего угла</p><h1>Рабочий стол сотрудника</h1></main>
      <AiHubPanel {...props} />
    </div>
  )
}
