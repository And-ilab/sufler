import { useEffect, useState } from 'react'
import {
  findDemoRole,
  readStoredDemoRole,
  storeDemoRole,
  type DemoRoleDefinition,
} from '../../auth/demoRoles'
import { PortalLauncher, RolePicker } from '../../components'
import './AiHubPanel.css'

export interface AiHubPortalHostProps {
  username?: string | null
}

export function AiHubPortalHost({
  username = 'Демо-пользователь',
}: AiHubPortalHostProps) {
  const [role, setRole] = useState<DemoRoleDefinition | null>(
    () => findDemoRole(readStoredDemoRole()) ?? null,
  )
  const [picking, setPicking] = useState(() => role == null)

  useEffect(() => {
    storeDemoRole(role?.code ?? null)
  }, [role])

  const selectRole = (next: DemoRoleDefinition) => {
    storeDemoRole(next.code)
    setRole(next)
    setPicking(false)
  }

  if (picking || !role) {
    return (
      <div className="hub-panel-host hub-panel-host--role-pick">
        <header>
          <img src="/assets/belarusbank-logo.png" alt="Беларусбанк" />
          <span>Корпоративный портал · AI Hub · выбор роли</span>
        </header>
        <main>
          <p>Тестовый вход</p>
          <h1>Матрица ролей I.4</h1>
        </main>
        <RolePicker
          selectedCode={role?.code}
          onSelect={selectRole}
        />
      </div>
    )
  }

  return (
    <PortalLauncher
      roles={[role.code]}
      username={username}
      roleLabel={role.label}
      menuVariant="compact"
      onChangeRole={() => setPicking(true)}
    />
  )
}
