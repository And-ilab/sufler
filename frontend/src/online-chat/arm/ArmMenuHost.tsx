import { useMemo, useState, type ReactNode } from 'react'
import {
  ArmOverlayMenu,
  getSchemePalette,
  type ArmMenuContext,
} from './ArmOperatorView'
import { ARM_THEME_DARK, ARM_THEME_LIGHT, type ThemeKind } from './theme'

type ArmRole = 'operator' | 'supervisor' | 'admin'
type MenuTab = 'dialogs' | 'history' | 'stats' | 'colleagues' | 'internal' | 'templates' | 'employees' | 'settings' | 'help'

export function ArmMenuHost({
  open,
  onOpenChange,
  armRole,
  menuContext,
  themeKind = 'light',
  children,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  armRole: ArmRole
  menuContext: ArmMenuContext
  themeKind?: ThemeKind
  children: ReactNode
}) {
  const t = themeKind === 'light' ? ARM_THEME_LIGHT : ARM_THEME_DARK
  const scheme = useMemo(() => getSchemePalette(t, 'belarusbank_emerald'), [t])
  const [activeId, setActiveId] = useState<MenuTab>('employees')

  return (
    <div className="arm-menu-host" style={{ position: 'relative', height: '100%', minHeight: 0, overflow: 'auto' }}>
      <ArmOverlayMenu
        t={t}
        scheme={scheme}
        open={open}
        armRole={armRole}
        menuContext={menuContext}
        activeId={activeId}
        onSelect={(id) => {
          setActiveId(id)
          onOpenChange(false)
        }}
        onClose={() => onOpenChange(false)}
      />
      {children}
    </div>
  )
}
