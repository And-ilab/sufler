import { StatusBadge, Button } from '../../components'
import { AsrQaScreen } from './AsrQaScreen'
import { CcReportsScreen } from './CcReportsScreen'
import './AsrQa.css'
import './CcReports.css'

export type ReportsSection = 'overview' | 'asr-qa'

interface AiHubReportsAppProps {
  username?: string
  section?: ReportsSection
}

function resolveSection(pathname: string, explicit?: ReportsSection): ReportsSection {
  if (explicit) return explicit
  if (pathname.includes('/asr')) return 'asr-qa'
  return 'overview'
}

export function AiHubReportsApp({
  username = '',
  section,
}: AiHubReportsAppProps) {
  const active = resolveSection(window.location.pathname, section)
  const isOverview = active === 'overview'

  const go = (next: ReportsSection) => {
    const path = next === 'asr-qa' ? '/ai-hub/reports/asr' : '/ai-hub/reports'
    window.history.pushState({}, '', path)
    window.location.assign(path)
  }

  return (
    <main className="asr-qa-app" data-testid="reports-app">
      <header className="asr-qa-app__header">
        <div>
          <p className="app-eyebrow">Отчётность · КЦ · II.6</p>
          <h1>{isOverview ? 'Отчёты Контакт-центра' : 'QA записей ASR'}</h1>
          <p className="app-muted">
            {isOverview
              ? 'FR-RPT-CC — таблицы аналитики, фильтры периода, экспорт CSV/XLSX и графики качества ASR.'
              : 'FR-ASR-10 / UC-REP-CC-02 — каталог записей, аудио+транскрипт и учебные примеры.'}
            {username ? ` Аналитик: ${username}.` : ''}
          </p>
        </div>
        <div className="asr-qa-app__actions">
          <StatusBadge status="info">cc.reports.view</StatusBadge>
          <Button variant="ghost" onClick={() => window.location.assign('/')}>
            На портал
          </Button>
        </div>
      </header>

      <nav className="asr-qa-app__tabs" aria-label="Разделы отчётности">
        <button
          type="button"
          className={`asr-qa-app__tab${isOverview ? ' is-active' : ''}`}
          onClick={() => go('overview')}
        >
          Аналитика КЦ
        </button>
        <button
          type="button"
          className={`asr-qa-app__tab${!isOverview ? ' is-active' : ''}`}
          onClick={() => go('asr-qa')}
        >
          QA ASR
        </button>
      </nav>

      {isOverview ? <CcReportsScreen /> : <AsrQaScreen />}
    </main>
  )
}
