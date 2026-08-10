import { useMemo, useState } from 'react'
import { DataTable } from './charts'
import { ASR_DEMO_ITEMS, channelLabelRu } from './demoData'

type RecognitionStatus = 'recognized' | 'partial' | 'unrecognized'

function formatDateTime(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatDuration(sec: number): string {
  const minutes = Math.floor(sec / 60)
  const seconds = sec % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

function statusLabel(status: RecognitionStatus): string {
  if (status === 'recognized') return 'Распознано'
  if (status === 'unrecognized') return 'Не распознано'
  return 'Частично'
}

const DEMO_UTTERANCES: Record<
  number,
  { speaker: string; text: string; confidence: number; start: string }[]
> = {
  1: [
    { speaker: 'Клиент', text: 'Хочу узнать лимит по карте', confidence: 0.94, start: '0:05' },
    { speaker: 'Оператор', text: 'Уточните, пожалуйста, тип карты', confidence: 0.96, start: '0:12' },
    { speaker: 'Клиент', text: 'Белкарт Маэстро', confidence: 0.89, start: '0:21' },
  ],
  2: [
    { speaker: 'Клиент', text: 'Как оплатить через ерип', confidence: 0.58, start: '0:04' },
    { speaker: 'Оператор', text: 'ЕРИП, раздел банковские услуги', confidence: 0.71, start: '0:18' },
    { speaker: 'Клиент', text: '[нераспознано]', confidence: 0.22, start: '0:35' },
  ],
  3: [
    { speaker: 'Клиент', text: 'Заблокируйте карту, пожалуйста', confidence: 1, start: '0:01' },
    { speaker: 'Оператор', text: 'Подтвердите последние 4 цифры', confidence: 1, start: '0:20' },
  ],
  4: [
    { speaker: 'Клиент', text: '[нераспознано]', confidence: 0.18, start: '0:03' },
    { speaker: 'Оператор', text: 'Вас плохо слышно, повторите', confidence: 0.66, start: '0:15' },
  ],
  5: [
    { speaker: 'Клиент', text: 'Не приходит смс-код', confidence: 1, start: '0:02' },
    { speaker: 'Оператор', text: 'Проверим настройки уведомлений', confidence: 1, start: '0:25' },
  ],
}

export function AsrQaScreen() {
  const [channel, setChannel] = useState('')
  const [status, setStatus] = useState('')
  const [lowOnly, setLowOnly] = useState(false)
  const [selectedId, setSelectedId] = useState(ASR_DEMO_ITEMS[0].id)

  const items = useMemo(() => {
    return ASR_DEMO_ITEMS.filter((item) => {
      if (channel && item.channel !== channel) return false
      if (status && item.recognition_status !== status) return false
      if (lowOnly && item.avg_confidence >= 0.75) return false
      return true
    })
  }, [channel, status, lowOnly])

  const selected = items.find((item) => item.id === selectedId) || items[0] || ASR_DEMO_ITEMS[0]
  const utterances = DEMO_UTTERANCES[selected.id] || []

  const stats = {
    total: ASR_DEMO_ITEMS.length,
    recognized: ASR_DEMO_ITEMS.filter((item) => item.recognition_status === 'recognized').length,
    problem: ASR_DEMO_ITEMS.filter((item) => item.recognition_status !== 'recognized').length,
    training: ASR_DEMO_ITEMS.filter((item) => item.has_training_candidate).length,
  }

  return (
    <div className="rpt-body" data-testid="asr-qa-screen">
      <div className="rpt-stats" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        <div className="rpt-stat"><span>Все записи</span><strong>{stats.total}</strong></div>
        <div className="rpt-stat rpt-stat--success"><span>Распознано</span><strong>{stats.recognized}</strong></div>
        <div className="rpt-stat rpt-stat--warning"><span>Проблемные</span><strong>{stats.problem}</strong></div>
        <div className="rpt-stat rpt-stat--info"><span>Учебные примеры</span><strong>{stats.training}</strong></div>
      </div>

      <div className="rpt-card">
        <div className="rpt-card__head">Фильтры</div>
        <div className="rpt-card__body">
          <div className="rpt-grid-2">
            <label className="rpt-field">
              Канал
              <select value={channel} onChange={(e) => setChannel(e.target.value)}>
                <option value="">Все</option>
                <option value="telephony">Телефония</option>
                <option value="online_chat">Онлайн-чат</option>
              </select>
            </label>
            <label className="rpt-field">
              Статус
              <select value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="">Все</option>
                <option value="recognized">Распознано</option>
                <option value="partial">Частично</option>
                <option value="unrecognized">Не распознано</option>
              </select>
            </label>
            <label className="rpt-row" style={{ fontSize: 13, alignSelf: 'end' }}>
              <input
                type="checkbox"
                checked={lowOnly}
                onChange={(e) => setLowOnly(e.target.checked)}
              />
              Только низкая уверенность
            </label>
          </div>
        </div>
      </div>

      <div className="rpt-asr-layout">
        <div className="rpt-card">
          <div className="rpt-card__head">Каталог записей</div>
          <div className="rpt-asr-list">
            {items.map((item) => (
              <button
                key={item.id}
                type="button"
                className={selected.id === item.id ? 'is-active' : ''}
                onClick={() => setSelectedId(item.id)}
              >
                <div className="rpt-row rpt-row--between">
                  <strong>{item.session_id}</strong>
                  <span className="rpt-badge">{statusLabel(item.recognition_status)}</span>
                </div>
                <div className="rpt-muted">
                  {formatDateTime(item.started_at)} · {channelLabelRu(item.channel)} ·{' '}
                  {item.operator_name}
                </div>
              </button>
            ))}
            {items.length === 0 ? (
              <p className="rpt-muted" style={{ padding: 12 }}>
                Нет записей по выбранным фильтрам.
              </p>
            ) : null}
          </div>
        </div>

        <div className="rpt-card">
          <div className="rpt-card__head">
            <span>{selected.session_id}</span>
            <span className="rpt-badge rpt-badge--info">
              {channelLabelRu(selected.channel)}
            </span>
          </div>
          <div className="rpt-card__body" style={{ display: 'grid', gap: 12 }}>
            <div className="rpt-muted">
              {formatDateTime(selected.started_at)} · {selected.operator_name} ·{' '}
              {formatDuration(selected.duration_sec)} · уверенность{' '}
              {Math.round(selected.avg_confidence * 100)}%
            </div>
            <DataTable
              headers={['Время', 'Спикер', 'Текст', 'Уверенность']}
              rows={utterances.map((row) => [
                row.start,
                row.speaker,
                row.text,
                `${Math.round(row.confidence * 100)}%`,
              ])}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
