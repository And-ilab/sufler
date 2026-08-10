import { CcReportsScreen } from './CcReportsScreen'
import { LiveOpsScreen } from './LiveOpsScreen'
import { AsrQaScreen } from './AsrQaScreen'
import './ReportsTheme.css'

export type ReportsSection = 'overview' | 'live' | 'builder' | 'asr-qa'

interface AiHubReportsAppProps {
  username?: string
  section?: ReportsSection
}

function resolveSection(pathname: string, explicit?: ReportsSection): ReportsSection {
  if (explicit) return explicit
  if (pathname.includes('/asr')) return 'asr-qa'
  if (pathname.includes('/live')) return 'live'
  if (pathname.includes('/builder')) return 'builder'
  return 'overview'
}

const TABS: { id: ReportsSection; label: string; path: string; subtitle: string; title: string }[] = [
  {
    id: 'overview',
    label: 'Аналитика',
    path: '/ai-hub/reports',
    title: 'Модуль «Отчётность» · аналитика КЦ',
    subtitle: 'Таблица / круговая / столбчатая · экспорт xlsx/pdf',
  },
  {
    id: 'live',
    label: 'Оперативная панель',
    path: '/ai-hub/reports/live',
    title: 'Оперативная панель',
    subtitle: 'Показатели в реальном времени',
  },
  {
    id: 'builder',
    label: 'Конструктор',
    path: '/ai-hub/reports/builder',
    title: 'Модуль «Отчётность» · аналитика КЦ',
    subtitle: 'Конструктор отчётов · шаблоны и показатели',
  },
  {
    id: 'asr-qa',
    label: 'Записи разговоров',
    path: '/ai-hub/reports/asr',
    title: 'Записи разговоров',
    subtitle: 'Каталог записей и транскриптов',
  },
]

export function AiHubReportsApp({
  section,
}: AiHubReportsAppProps) {
  const active = resolveSection(window.location.pathname, section)
  const tab = TABS.find((item) => item.id === active) || TABS[0]

  const go = (next: ReportsSection) => {
    const target = TABS.find((item) => item.id === next) || TABS[0]
    window.location.assign(target.path)
  }

  return (
    <main className="rpt-app" data-testid="reports-app" data-scheme="belarusbank_emerald">
      <div className="rpt-frame">
        <header className="rpt-header">
          <div>
            <h1>{tab.title}</h1>
            <p className="rpt-header__sub">{tab.subtitle}</p>
          </div>
          <div className="rpt-header__actions">
            <button
              type="button"
              className="rpt-btn"
              onClick={() => window.location.assign('/online-chat')}
            >
              АРМ чата
            </button>
            <button
              type="button"
              className="rpt-btn"
              onClick={() => window.location.assign('/')}
            >
              На портал
            </button>
          </div>
        </header>

        <nav className="rpt-tabs" aria-label="Разделы">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`rpt-tab${active === item.id ? ' is-active' : ''}`}
              onClick={() => go(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>

        {active === 'overview' ? <CcReportsScreen initialPanel="reports" /> : null}
        {active === 'builder' ? <CcReportsScreen initialPanel="builder" /> : null}
        {active === 'live' ? <LiveOpsScreen /> : null}
        {active === 'asr-qa' ? <AsrQaScreen /> : null}
      </div>
    </main>
  )
}
