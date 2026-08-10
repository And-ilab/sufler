import { useState } from 'react'
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
import { ChatAdminApp } from './online-chat/admin/ChatAdminApp'
import {
  canAccessOnlineChatAdmin,
  canAccessOnlineChatSupervisor,
} from './online-chat/managementAccess'
import { ChatSimulatorApp } from './online-chat/simulator/ChatSimulatorApp'
import { ChatPlatformShell } from './online-chat/shell/ChatPlatformShell'
import { SupervisorApp } from './online-chat/supervisor/SupervisorApp'
import type { ThemeKind } from './online-chat/arm/theme'
import {
  Button,
  Card,
  PortalLauncher,
  StatusBadge,
  getAllowedLauncherModules,
  type LauncherModule,
} from './components'
import './App.css'

function jobTitleFromRoles(roles: readonly string[]): string {
  if (
    roles.includes('contact_center_module_administrator')
    || roles.includes('software_administrator')
  ) {
    return 'Администратор модуля КЦ'
  }
  if (roles.includes('contact_center_supervisor')) {
    return 'Супервизор КЦ'
  }
  if (roles.includes('contact_center_analyst')) {
    return 'Аналитик КЦ'
  }
  if (roles.includes('contact_center_online_chat_operator')) {
    return 'Оператор онлайн-чата'
  }
  return 'Сотрудник КЦ'
}

function employeeDisplayName(username: string | null | undefined, operatorFromQuery?: string | null) {
  if (operatorFromQuery?.trim()) return operatorFromQuery.trim()
  if (username && username !== 'Development user') return username
  return 'Иванов И.И.'
}

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
  const [chatThemeKind, setChatThemeKind] = useState<ThemeKind>('light')
  const [armMenuOpen, setArmMenuOpen] = useState(false)

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
    const isSupervisorRoute = route === '/online-chat/supervisor'
    const isAdminRoute = route === '/online-chat/admin'
    const isSimulatorRoute = route === '/online-chat/simulator'
    const allowed = isSupervisorRoute
      ? canAccessOnlineChatSupervisor(auth.roles)
      : isAdminRoute
        ? canAccessOnlineChatAdmin(auth.roles)
        : isSimulatorRoute
          ? import.meta.env.DEV || import.meta.env.VITE_SUFLER_DEMO === '1'
          : route === '/online-chat' && canAccessOnlineChatArm(auth.roles)

    if (!allowed) {
      return (
        <main className="standalone-module standalone-module--denied">
          <Card>
            <StatusBadge status="danger">403</StatusBadge>
            <h1>Нет доступа к разделу онлайн-чата</h1>
            <p>Для выбранного маршрута требуется соответствующая роль Контакт-центра.</p>
            <Button onClick={() => window.location.assign('/')}>Вернуться на портал</Button>
          </Card>
        </main>
      )
    }

    const operatorFromQuery = new URLSearchParams(window.location.search).get('operator')?.trim()
    const operatorName = employeeDisplayName(auth.username, operatorFromQuery)
    const shellProps = {
      currentPath: route,
      displayName: operatorName,
      jobTitle: operatorFromQuery
        ? 'Оператор онлайн-чата'
        : jobTitleFromRoles(auth.roles),
      showSupervisor: canAccessOnlineChatSupervisor(auth.roles),
      showAdmin: canAccessOnlineChatAdmin(auth.roles),
      showSimulator: import.meta.env.DEV || import.meta.env.VITE_SUFLER_DEMO === '1',
      themeKind: chatThemeKind,
      onToggleTheme: () =>
        setChatThemeKind((kind) => (kind === 'light' ? 'dark' : 'light')),
      showMenuButton: route === '/online-chat',
      menuOpen: armMenuOpen,
      onMenuToggle: () => setArmMenuOpen((open) => !open),
    }

    if (isSupervisorRoute) {
      return (
        <ChatPlatformShell {...shellProps} showMenuButton={false}>
          <SupervisorApp demoMode={import.meta.env.DEV || import.meta.env.VITE_SUFLER_DEMO === '1'} />
        </ChatPlatformShell>
      )
    }
    if (isAdminRoute) {
      return (
        <ChatPlatformShell {...shellProps} showMenuButton={false}>
          <ChatAdminApp />
        </ChatPlatformShell>
      )
    }
    if (isSimulatorRoute) {
      return (
        <ChatPlatformShell {...shellProps} showMenuButton={false}>
          <ChatSimulatorApp />
        </ChatPlatformShell>
      )
    }
    return (
      <ChatPlatformShell {...shellProps}>
        <ChatArmApp
          demoMode={import.meta.env.VITE_SUFLER_DEMO === '1'}
          operatorName={operatorName}
          themeKind={chatThemeKind}
          statsDrawerOpen={armMenuOpen}
          onStatsDrawerOpenChange={setArmMenuOpen}
        />
      </ChatPlatformShell>
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
    const section = route.includes('/asr')
      ? 'asr-qa' as const
      : route.includes('/live')
        ? 'live' as const
        : route.includes('/builder')
          ? 'builder' as const
          : 'overview' as const
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
            <h2>Отчётность</h2>
            <p className="app-muted">
              Аналитика, оперативная панель, конструктор отчётов и записи разговоров.
            </p>
            <Button onClick={() => window.location.assign('/ai-hub/reports')}>
              Открыть отчёты
            </Button>
            <Button
              variant="ghost"
              onClick={() => window.location.assign('/ai-hub/reports/live')}
            >
              Оперативная панель
            </Button>
            <Button
              variant="ghost"
              onClick={() => window.location.assign('/ai-hub/reports/builder')}
            >
              Конструктор
            </Button>
            <Button
              variant="ghost"
              onClick={() => window.location.assign('/ai-hub/reports/asr')}
            >
              Записи разговоров
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
