import { useEffect, useState } from 'react'
import { Button, Card, StatusBadge } from '../../components'
import {
  createAssistantKb,
  listAssistantCapabilities,
  listAssistantKbs,
  setCapabilityEnabled,
  type AssistantCapability,
  type AssistantKb,
} from './api/assistantAdmin'
import './AssistantAdminScreens.css'

interface CapabilitiesScreenProps {
  canEdit?: boolean
}

export function CapabilitiesScreen({ canEdit = true }: CapabilitiesScreenProps) {
  const [items, setItems] = useState<AssistantCapability[]>([])
  const [kbs, setKbs] = useState<AssistantKb[]>([])
  const [busyCode, setBusyCode] = useState('')
  const [error, setError] = useState('')
  const [kbName, setKbName] = useState('')
  const [creatingKb, setCreatingKb] = useState(false)

  const refresh = async () => {
    const [caps, nextKbs] = await Promise.all([
      listAssistantCapabilities(),
      listAssistantKbs(),
    ])
    setItems(caps)
    setKbs(nextKbs)
  }

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        await refresh()
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Ошибка загрузки')
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const toggle = async (item: AssistantCapability) => {
    if (!canEdit || busyCode) return
    setBusyCode(item.code)
    setError('')
    try {
      const updated = await setCapabilityEnabled(item.code, !item.enabled)
      setItems((current) =>
        current.map((row) => (row.code === updated.code ? updated : row)),
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка сохранения')
    } finally {
      setBusyCode('')
    }
  }

  const addKb = async () => {
    if (!canEdit || !kbName.trim() || creatingKb) return
    setCreatingKb(true)
    setError('')
    try {
      await createAssistantKb({ name: kbName.trim() })
      setKbName('')
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка создания KB')
    } finally {
      setCreatingKb(false)
    }
  }

  return (
    <section className="asst-admin-caps" data-testid="capabilities-screen">
      <p className="asst-admin-note">
        Агрегатор навыков (III.6 / VII.5 D4). Выключенный capability не показывается в панели ассистента.
        Индексы только <code>assistant_*</code> — без <code>cc_production</code>.
      </p>

      <div className="asst-admin-caps__grid" data-testid="capabilities-grid">
        {items.map((item) => (
          <Card key={item.code} className="asst-admin-cap-card" data-testid={`cap-${item.code}`}>
            <header>
              <div>
                <strong>{item.name}</strong>
                <p>{item.description}</p>
              </div>
              <StatusBadge status={item.enabled ? 'success' : 'neutral'}>
                {item.enabled ? 'Вкл' : 'Выкл'}
              </StatusBadge>
            </header>
            <div className="asst-admin-cap-card__meta">
              <code>{item.code}</code>
              <span>→ {item.deep_link || '—'}</span>
            </div>
            <div className="asst-admin-actions">
              <Button
                type="button"
                variant={item.enabled ? 'secondary' : 'primary'}
                disabled={!canEdit || busyCode === item.code}
                data-testid={`cap-toggle-${item.code}`}
                onClick={() => void toggle(item)}
              >
                {item.enabled ? 'Выключить' : 'Включить'}
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  if (item.deep_link) {
                    window.history.pushState({}, '', `/ai-hub/admin/${item.deep_link}`)
                    window.dispatchEvent(new PopStateEvent('popstate'))
                    window.location.assign(`/ai-hub/admin/${item.deep_link}`)
                  }
                }}
              >
                Настроить →
              </Button>
            </div>
          </Card>
        ))}
      </div>

      <Card className="asst-admin-kb-panel" data-testid="assistant-kb-panel">
        <header>
          <div>
            <h2>Базы знаний assistant_*</h2>
            <p>Отдельный namespace, изолированный от индекса КЦ cc_production.</p>
          </div>
          <StatusBadge status="info">namespace</StatusBadge>
        </header>
        <ul className="asst-admin-kb-list">
          {kbs.map((kb) => (
            <li key={kb.id} data-testid={`asst-kb-${kb.slug}`}>
              <strong>{kb.name}</strong>
              <code>{kb.slug}</code>
              <StatusBadge status="success">{kb.status}</StatusBadge>
            </li>
          ))}
        </ul>
        <div className="asst-admin-kb-create">
          <input
            value={kbName}
            disabled={!canEdit}
            placeholder="Название новой KB"
            onChange={(event) => setKbName(event.target.value)}
            data-testid="asst-kb-name"
          />
          <Button
            type="button"
            disabled={!canEdit || creatingKb || !kbName.trim()}
            onClick={() => void addKb()}
            data-testid="asst-kb-create"
          >
            + Создать KB
          </Button>
        </div>
      </Card>

      {error ? <p className="asst-admin-error" role="alert">{error}</p> : null}
    </section>
  )
}
