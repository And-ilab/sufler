import { usePortalAuth } from './auth/usePortalAuth'
import { AiHubAdminApp } from './ai-hub/admin/AiHubAdminApp'
import { isAdminCenterRole } from './ai-hub/admin/adminNav'
import { AiHubPanelHost } from './ai-hub/panel/AiHubPanel'
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
}: {
  module: LauncherModule
  roles: readonly string[]
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

  return (
    <main className="standalone-module">
      <Card className="standalone-module__window">
        <header className="standalone-module__header">
          <div>
            <p className="app-eyebrow">Отдельное окно AI Hub</p>
            <h1>{label}</h1>
          </div>
          <StatusBadge status="success">Доступ разрешён</StatusBadge>
        </header>
        <p className="app-muted">
          Маршрут работает как standalone entry point. Основной интерфейс модуля
          подключается здесь без изменения портального launcher.
        </p>
        <Button onClick={() => window.location.assign('/')}>Вернуться на портал</Button>
      </Card>
    </main>
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
      />
    )
  }

  if (route === '/ai-hub') {
    return (
      <AiHubPanelHost
        roles={auth.roles}
        rbacTabs={auth.tabs}
        username={auth.username}
        initialOpen
      />
    )
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

  return (
    <div className="portal-route">
      {auth.status === 'unavailable' && (
        <div className="portal-route__auth-status" role="status">
          Launcher скрыт: авторизация недоступна
        </div>
      )}
      <PortalLauncher roles={auth.roles} />
    </div>
  )
}

export default App
