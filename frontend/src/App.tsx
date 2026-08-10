import { useState } from 'react'
import { readStoredDemoRole } from './auth/demoRoles'
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
import {
  canOperateOnlineChatArm,
  canViewOnlineChatArm,
} from './online-chat/chatArmAccess'
import { ChatAdminApp } from './online-chat/admin/ChatAdminApp'
import {
  canAccessOnlineChatAdmin,
  canAccessOnlineChatSupervisor,
  canTransferInOnlineChatView,
} from './online-chat/managementAccess'
import { OperatorPicker } from './online-chat/OperatorPicker'
import { ChatSimulatorApp } from './online-chat/simulator/ChatSimulatorApp'
import { ChatPlatformShell } from './online-chat/shell/ChatPlatformShell'
import { SupervisorApp } from './online-chat/supervisor/SupervisorApp'
import type { ThemeKind } from './online-chat/arm/theme'
import {
  Button,
  Card,
  PortalLauncher,
  StatusBadge,
  canWriteAssistantChat,
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

function employeeDisplayName(username: string | null | undefined) {
  if (username && username !== 'Development user') return username
  return 'Иванов И.И.'
}

/** RolePicker selection narrows FE gates in DEV/demo without changing /api/auth/me. */
function rolesForUi(authRoles: readonly string[]): string[] {
  const demo = readStoredDemoRole()
  if (
    demo
    && (import.meta.env.DEV || import.meta.env.VITE_SUFLER_DEMO === '1')
  ) {
    return [demo]
  }
  return [...authRoles]
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
      demoMode={import.meta.env.VITE_SUFLER_DEMO === '1'}
      readOnly={!canWriteAssistantChat(roles)}
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
    const roles = rolesForUi(auth.roles)
    const isSupervisorRoute = route === '/online-chat/supervisor'
    const isAdminRoute = route === '/online-chat/admin'
    const isSimulatorRoute = route === '/online-chat/simulator'
    const canOperateArm = canOperateOnlineChatArm(roles)
    const canViewArm = canViewOnlineChatArm(roles)
    const canSupervisor = canAccessOnlineChatSupervisor(roles)
    const canAdmin = canAccessOnlineChatAdmin(roles)
    const allowed = isSupervisorRoute
      ? canSupervisor
      : isAdminRoute
        ? canAdmin
        : isSimulatorRoute
          ? import.meta.env.DEV || import.meta.env.VITE_SUFLER_DEMO === '1'
          : route === '/online-chat' && canViewArm

    if (!allowed) {
      return (
        <main className="standalone-module standalone-module--denied">
          <Card>
            <StatusBadge status="danger">403</StatusBadge>
            <h1>Нет доступа к разделу онлайн-чата</h1>
            <p>Для выбранного маршрута требуется соответствующая роль Контакт-центра.</p>
            <Button onClick={() => window.location.assign('/ai-hub')}>Выбрать роль</Button>
          </Card>
        </main>
      )
    }

    const params = new URLSearchParams(window.location.search)
    const operatorFromQuery = params.get('operator')?.trim() || ''
    const forcedView = params.get('mode') === 'view' || (!canOperateArm && canViewArm)
    const allowTransferView = canTransferInOnlineChatView(roles)
    const viewerName = employeeDisplayName(auth.username)
    const armRole = canAdmin ? 'admin' as const : canSupervisor && !canOperateArm ? 'supervisor' as const : 'operator' as const

    const shellProps = {
      currentPath: route,
      displayName: forcedView && operatorFromQuery
        ? `Просмотр · ${operatorFromQuery}`
        : viewerName,
      jobTitle: jobTitleFromRoles(roles),
      showArm: canViewArm,
      showSupervisor: canSupervisor,
      showAdmin: canAdmin,
      showSimulator: import.meta.env.DEV || import.meta.env.VITE_SUFLER_DEMO === '1',
      themeKind: chatThemeKind,
      onToggleTheme: () =>
        setChatThemeKind((kind) => (kind === 'light' ? 'dark' : 'light')),
      showMenuButton: route === '/online-chat' && canOperateArm && !forcedView,
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

    if (forcedView && !operatorFromQuery) {
      return (
        <ChatPlatformShell {...shellProps} showMenuButton={false}>
          <OperatorPicker allowTransfer={allowTransferView} />
        </ChatPlatformShell>
      )
    }

    return (
      <ChatPlatformShell {...shellProps}>
        <ChatArmApp
          demoMode={import.meta.env.VITE_SUFLER_DEMO === '1'}
          operatorName={forcedView ? operatorFromQuery : viewerName}
          themeKind={chatThemeKind}
          statsDrawerOpen={armMenuOpen}
          onStatsDrawerOpenChange={setArmMenuOpen}
          armRole={armRole}
          viewOnly={forcedView}
          allowTransferInView={forcedView && allowTransferView}
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
            <p>
              Нужна админ-роль I.4 (п.1–3, 8, 11) или аналитик с отчётностью
              (п.7 КЦ / п.10 ассистент / п.13 OCR).
            </p>
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
