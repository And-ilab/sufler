import { useEffect, useState } from 'react'
import { Card, StatusBadge } from '../../components'
import { listDialogScenarios, type ScenarioListItem } from './api/scenarios'

export function ScenarioBindingsScreen() {
  const [items, setItems] = useState<ScenarioListItem[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    void listDialogScenarios()
      .then((payload) => setItems(payload.items))
      .catch((caught: unknown) => {
        setError(caught instanceof Error ? caught.message : 'Не удалось загрузить привязки')
      })
  }, [])

  const channelLabel = (value: string) => {
    if (value === 'telephony') return 'Телефония'
    if (value === 'online_chat') return 'Онлайн-чат'
    return 'Телефония / чат'
  }

  return (
    <div data-testid="scenario-bindings">
      {error ? <Card>{error}</Card> : null}
      <section className="admin-stats" aria-label="Привязки сценариев">
        <Card>
          <span>Телефония</span>
          <strong>
            {items.filter((item) => item.channels === 'both' || item.channels === 'telephony').length}
          </strong>
          <small>Канал</small>
        </Card>
        <Card>
          <span>Онлайн-чат</span>
          <strong>
            {items.filter((item) => item.channels === 'both' || item.channels === 'online_chat').length}
          </strong>
          <small>Канал</small>
        </Card>
        <Card>
          <span>Опубликовано</span>
          <strong>{items.filter((item) => item.status === 'production').length}</strong>
          <small>Production</small>
        </Card>
      </section>
      <div className="admin-form-grid" style={{ marginTop: 16 }}>
        {items.map((item) => (
          <Card key={item.code}>
            <span>{item.code}</span>
            <strong>{item.title}</strong>
            <small>
              {channelLabel(item.channels)} ·{' '}
              <StatusBadge status={item.status === 'production' ? 'success' : 'neutral'}>
                {item.status === 'production' ? 'Опубликован' : 'Черновик'}
              </StatusBadge>
            </small>
          </Card>
        ))}
      </div>
    </div>
  )
}
