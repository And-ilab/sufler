import { usePortalAuth } from './auth/usePortalAuth'
import { AiHubAdminApp } from './ai-hub/admin/AiHubAdminApp'
import { isAdminCenterRole } from './ai-hub/admin/adminNav'
import { AiHubPortalHost } from './ai-hub/panel/AiHubPortalHost'
import { AiHubReportsApp } from './ai-hub/reports/AiHubReportsApp'
import { canAccessCcReports } from './ai-hub/reports/reportsAccess'
import { InternalKcDialogApp } from './internal-kc/InternalKcDialogApp'
import { canAccessInternalKc } from './internal-kc/internalKcAccess'
import { AssistantWindowApp } from './assistant/AssistantWindowApp'
import { SuflerPhoneApp } from './sufler/SuflerPhoneApp'
import { ChatArmApp } from './online-chat/ChatArmApp'
import { canAccessOnlineChatArm } from './online-chat/chatArmAccess'
import {
  Button,
  Card,
  PortalLauncher,
  StatusBadge,
  getAllowedLauncherModules,
  type LauncherModule,
} from './components'
import './App.css'

function StandaloneModule({
  module,
  roles,
  username,
}: {
  module: LauncherModule
  roles: readonly string[]
  username?: string | null
}) {
  const allowed = getAllowedLauncherModules(roles).includes(module)
  const label = module === 'sufler' ? 'Суфлёр' : 'Ассистент'

  if (!allowed) {
    return (
      <main className="standalone-module standalone-module--denied">
        <Card>
          <StatusBadge status="danger">403</StatusBadge>
          <h1>Нет доступа</h1>
          <p>Роль пользователя не разрешает открывать модуль «{label}».</p>
          <Button onClick={() => window.location.assign('/')}>Вернуться на портал</Button>
        </Card>
      </main>
    )
  }

  if (module === 'sufler') {
    return (
      <SuflerPhoneApp
        demoMode={import.meta.env.VITE_SUFLER_DEMO === '1' || import.meta.env.DEV}
        operatorName="Иванова М.П."
      />
    )
  }

  return (
    <AssistantWindowApp
      username={username ?? 'Пользователь ИИ-ассистента'}
      demoMode={import.meta.env.VITE_SUFLER_DEMO === '1' || import.meta.env.DEV}
    />
  )
}

function App() {
  const auth = usePortalAuth()
  const route = window.location.pathname.replace(/\/+$/, '') || '/'

  if (auth.status === 'loading') {
    return (
      <main className="standalone-module" aria-busy="true">
        <Card>Проверяем права доступа…</Card>
      </main>
    )
  }

  if (route === '/sufler' || route === '/assistant') {
    return (
      <StandaloneModule
        module={route.slice(1) as LauncherModule}
        roles={auth.roles}
        username={auth.username}
      />
    )
  }

  if (route === '/online-chat' || route.startsWith('/online-chat/')) {
    if (!canAccessOnlineChatArm(auth.roles)) {
      return (
        <main className="standalone-module standalone-module--denied">
          <Card>
            <StatusBadge status="danger">403</StatusBadge>
            <h1>Нет доступа к АРМ онлайн-чата</h1>
            <p>Требуется роль оператора онлайн-чата Контакт-центра.</p>
            <Button onClick={() => window.location.assign('/')}>Вернуться на портал</Button>
          </Card>
        </main>
      )
    }
    return (
      <ChatArmApp
        demoMode={import.meta.env.VITE_SUFLER_DEMO === '1'}
        operatorName={auth.username ?? 'Оператор КЦ'}
      />
    )
  }

  if (
    route === '/internal-kc'
    || route.startsWith('/internal-kc/')
    || route === '/ai-hub/internal-kc'
    || route.startsWith('/ai-hub/internal-kc/')
  ) {
    if (!canAccessInternalKc(auth.roles)) {
      return (
        <main className="standalone-module standalone-module--denied">
          <Card>
            <StatusBadge status="danger">403</StatusBadge>
            <h1>Нет доступа к тест-диалогу КЦ</h1>
            <p>Требуется роль внутреннего пользователя Контакт-центра (cc.test_dialog.use).</p>
            <Button onClick={() => window.location.assign('/')}>Вернуться на портал</Button>
          </Card>
        </main>
      )
    }
    return (
      <InternalKcDialogApp
        username={auth.username ?? undefined}
        demoMode={import.meta.env.VITE_SUFLER_DEMO === '1' || import.meta.env.DEV}
      />
    )
  }

  if (route === '/ai-hub') {
    return <AiHubPortalHost username={auth.username} />
  }

  if (route === '/ai-hub/admin' || route.startsWith('/ai-hub/admin/')) {
    if (!isAdminCenterRole(auth.roles)) {
      return (
        <main className="standalone-module standalone-module--denied">
          <Card>
            <StatusBadge status="danger">403</StatusBadge>
            <h1>Нет доступа к Центру настроек</h1>
            <p>Для этого маршрута требуется одна из административных ролей I.4.</p>
            <Button onClick={() => window.location.assign('/')}>Вернуться на портал</Button>
          </Card>
        </main>
      )
    }
    return (
      <AiHubAdminApp
        roles={auth.roles}
        demoRoleSwitcher={import.meta.env.DEV}
      />
    )
  }

  if (
    route === '/ai-hub/reports'
    || route.startsWith('/ai-hub/reports/')
    || route === '/admin/reports'
    || route.startsWith('/admin/reports/')
  ) {
    if (!canAccessCcReports(auth.roles)) {
      return (
        <main className="standalone-module standalone-module--denied">
          <Card>
            <StatusBadge status="danger">403</StatusBadge>
            <h1>Нет доступа к отчётности КЦ</h1>
            <p>Требуется роль аналитика Контакт-центра (cc.reports.view).</p>
            <Button onClick={() => window.location.assign('/')}>Вернуться на портал</Button>
          </Card>
        </main>
      )
    }
    const section =
      route.includes('/asr') ? 'asr-qa' as const : 'overview' as const
    return (
      <AiHubReportsApp
        username={auth.username ?? undefined}
        section={section}
      />
    )
  }

  return (
    <div className="portal-route">
      {auth.status === 'unavailable' && (
        <div className="portal-route__auth-status" role="status">
          Launcher скрыт: авторизация недоступна
        </div>
      )}
      {canAccessCcReports(auth.roles) && (
        <div className="portal-route__reports-entry">
          <Card>
            <StatusBadge status="info">Отчётность · II.6</StatusBadge>
            <h2>Отчёты Контакт-центра</h2>
            <p className="app-muted">
              Таблицы FR-RPT-CC, фильтры периода, экспорт CSV/XLSX и графики качества ASR.
            </p>
            <Button onClick={() => window.location.assign('/ai-hub/reports')}>
              Открыть отчёты
            </Button>
            <Button
              variant="ghost"
              onClick={() => window.location.assign('/ai-hub/reports/asr')}
            >
              QA ASR
            </Button>
          </Card>
        </div>
      )}
      {canAccessInternalKc(auth.roles) && (
        <div className="portal-route__reports-entry">
          <Card>
            <StatusBadge status="info">II.3.5.5 · II-KC</StatusBadge>
            <h2>Тест-диалог внутреннего пользователя КЦ</h2>
            <p className="app-muted">
              Проверка промптов и сценариев без клиентского канала: ответ LLM и % релевантности.
            </p>
            <Button onClick={() => window.location.assign('/internal-kc')}>
              Открыть тест-диалог
            </Button>
          </Card>
        </div>
      )}
      <PortalLauncher roles={auth.roles} />
    </div>
  )
}

export default App
