import { useCallback, useEffect, useMemo, useState, type CSSProperties } from 'react'
import {
  fetchClientHistory,
  listDialogs,
  maskPhone,
  type OnlineChatDialog,
} from '../../api/onlineChatApi'
import {
  ClientSummaryPanel,
  historyToSummary,
  type SummaryHistoryData,
} from '../ClientSummaryCard'
import { Button, Pill, Row, Text } from '../primitives'
import { TopicChip } from '../summaryTopics'
import { ArmModuleFrame, formatDateTime, ModuleEmpty } from './ArmModuleFrame'
import { DEMO_APPEALS } from './demoData'
import type { AppealHistoryItem, ArmModuleProps } from './types'

const STATUS_LABEL: Record<AppealHistoryItem['status'], string> = {
  closed: 'Закрыт',
  active: 'В работе',
  lost: 'Потерянный',
  offline: 'Офлайн',
}

const STATUS_TONE: Record<AppealHistoryItem['status'], 'success' | 'info' | 'warning' | 'neutral'> = {
  closed: 'success',
  active: 'info',
  lost: 'warning',
  offline: 'neutral',
}

function mapDialogStatus(dialog: OnlineChatDialog): AppealHistoryItem['status'] {
  if (dialog.status === 'active' || dialog.status === 'waiting') return 'active'
  if (dialog.outcome === 'lost') return 'lost'
  if (dialog.outcome === 'offline') return 'offline'
  if (dialog.status === 'closed' || dialog.status === 'blocked') return 'closed'
  return 'closed'
}

function dialogToAppeal(dialog: OnlineChatDialog): AppealHistoryItem {
  return {
    id: dialog.id,
    clientName: dialog.client_name || 'Клиент',
    phoneMasked: maskPhone(dialog.client_phone || ''),
    channel: dialog.channel || 'Сайт',
    topic: dialog.close_topic || dialog.preview || 'Без темы',
    status: mapDialogStatus(dialog),
    operatorName: dialog.operator_name || '—',
    openedAt: dialog.created_at,
    closedAt: dialog.closed_at ?? undefined,
    summary: '',
  }
}

export function HistoryModule({ t, scheme, onBack }: ArmModuleProps) {
  const [items, setItems] = useState<AppealHistoryItem[]>(DEMO_APPEALS)
  const [usingLive, setUsingLive] = useState(false)
  const [query, setQuery] = useState('')
  const [channel, setChannel] = useState('all')
  const [status, setStatus] = useState<'all' | AppealHistoryItem['status']>('all')
  const [selectedId, setSelectedId] = useState<string | null>(DEMO_APPEALS[0]?.id ?? null)
  const [summaryById, setSummaryById] = useState<Record<string, SummaryHistoryData>>({})
  const [summaryLoadingId, setSummaryLoadingId] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [closed, active, waiting] = await Promise.all([
        listDialogs('closed'),
        listDialogs('active'),
        listDialogs('waiting'),
      ])
      const merged = Array.from(
        new Map(
          [...closed, ...active, ...waiting].map((dialog) => [dialog.id, dialog]),
        ).values(),
      ).sort((a, b) => (a.created_at < b.created_at ? 1 : -1))

      // As soon as simulation/API has real dialogs — drop demo stubs.
      if (merged.length > 0) {
        const mapped = merged.map(dialogToAppeal)
        setItems(mapped)
        setUsingLive(true)
        setSelectedId((prev) =>
          prev && mapped.some((item) => item.id === prev) ? prev : mapped[0]?.id ?? null,
        )
      } else {
        setItems(DEMO_APPEALS)
        setUsingLive(false)
      }
    } catch {
      setItems(DEMO_APPEALS)
      setUsingLive(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
    const timer = window.setInterval(() => {
      void refresh()
    }, 3000)
    return () => window.clearInterval(timer)
  }, [refresh])

  const channels = useMemo(
    () => ['all', ...Array.from(new Set(items.map((item) => item.channel)))],
    [items],
  )

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return items.filter((item) => {
      if (channel !== 'all' && item.channel !== channel) return false
      if (status !== 'all' && item.status !== status) return false
      if (!q) return true
      return (
        item.clientName.toLowerCase().includes(q)
        || item.phoneMasked.toLowerCase().includes(q)
        || item.topic.toLowerCase().includes(q)
        || item.id.toLowerCase().includes(q)
        || item.operatorName.toLowerCase().includes(q)
      )
    })
  }, [items, query, channel, status])

  const selected = filtered.find((item) => item.id === selectedId) ?? filtered[0] ?? null
  const loadedSummary = selected ? summaryById[selected.id] : undefined

  const loadSummary = async () => {
    if (!selected) return
    setSummaryLoadingId(selected.id)
    try {
      if (usingLive) {
        const response = await fetchClientHistory({ dialogId: selected.id })
        setSummaryById((prev) => ({
          ...prev,
          [selected.id]: historyToSummary({
            items: response.items ?? [],
            summary: response.summary
              || (response.items?.length
                ? `Обращений по клиенту: ${response.count}. Последнее: ${response.items[0]?.channel ?? '—'} · ${response.items[0]?.status ?? '—'}.`
                : 'Нет данных для summary.'),
            detailedSummary: response.detailed_summary ?? '',
            topics: response.summary_topics ?? [],
            blocks: response.detailed_blocks ?? [],
            isFirst: response.is_first,
            previousCount: response.previous_count,
          }),
        }))
      } else {
        // Demo stubs already carry a prepared text — load on demand only.
        const text = selected.summary || 'Summary недоступен для этой записи.'
        setSummaryById((prev) => ({
          ...prev,
          [selected.id]: historyToSummary({
            summary: text,
            detailedSummary: text,
            topics: selected.topic ? [selected.topic] : [],
            blocks: [
              {
                date_label: formatDateTime(selected.openedAt),
                topic: selected.topic || 'Прочее',
                essence: text,
                channel: selected.channel,
                operator_name: selected.operatorName,
              },
            ],
            isFirst: false,
          }),
        }))
      }
    } catch {
      setSummaryById((prev) => ({
        ...prev,
        [selected.id]: historyToSummary({
          summary: 'Не удалось загрузить summary.',
          detailedSummary: 'Не удалось загрузить summary.',
        }),
      }))
    } finally {
      setSummaryLoadingId(null)
    }
  }

  return (
    <ArmModuleFrame
      t={t}
      scheme={scheme}
      title="История обращений"
      onBack={onBack}
      bodyStyle={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}
    >
      <div
        style={{
          padding: 12,
          borderBottom: `1px solid ${t.stroke.tertiary}`,
          display: 'flex',
          gap: 10,
          flexWrap: 'wrap',
          alignItems: 'center',
          flexShrink: 0,
        }}
      >
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Клиент, телефон, тема, № обращения, оператор"
          style={{
            flex: '1 1 220px',
            minWidth: 200,
            padding: '8px 10px',
            borderRadius: 8,
            border: `1px solid ${t.stroke.secondary}`,
            background: t.bg.editor,
            color: t.text.primary,
            fontFamily: 'inherit',
            fontSize: 13,
          }}
        />
        <select
          value={channel}
          onChange={(e) => setChannel(e.target.value)}
          style={selectStyle(t)}
        >
          {channels.map((value) => (
            <option key={value} value={value}>
              {value === 'all' ? 'Все каналы' : value}
            </option>
          ))}
        </select>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as typeof status)}
          style={selectStyle(t)}
        >
          <option value="all">Все статусы</option>
          <option value="closed">Закрытые</option>
          <option value="active">В работе</option>
          <option value="lost">Потерянные</option>
          <option value="offline">Офлайн</option>
        </select>
      </div>

      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        <div
          style={{
            width: 380,
            flexShrink: 0,
            borderRight: `1px solid ${t.stroke.secondary}`,
            overflowY: 'auto',
            padding: 8,
          }}
        >
          {filtered.length === 0 ? (
            <ModuleEmpty t={t} title="Ничего не найдено" hint="Измените фильтры или поисковый запрос." />
          ) : (
            filtered.map((item) => {
              const active = selected?.id === item.id
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setSelectedId(item.id)}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    padding: '12px 12px',
                    marginBottom: 6,
                    borderRadius: 10,
                    border: `1px solid ${active ? scheme.accent : t.stroke.tertiary}`,
                    background: active ? t.fill.tertiary : t.bg.editor,
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                    color: t.text.primary,
                  }}
                >
                  <Row style={{ justifyContent: 'space-between', gap: 8 }}>
                    <Text weight="semibold" style={{ fontSize: 13 }}>{item.clientName}</Text>
                    <Pill tone={STATUS_TONE[item.status]} size="sm">{STATUS_LABEL[item.status]}</Pill>
                  </Row>
                  <Text style={{ fontSize: 12, color: t.text.secondary, marginTop: 4 }}>
                    {item.channel} · {item.topic}
                  </Text>
                  <Text style={{ fontSize: 11, color: t.text.tertiary, marginTop: 4 }}>
                    {formatDateTime(item.openedAt)} · {item.operatorName}
                  </Text>
                </button>
              )
            })
          )}
        </div>

        <div style={{ flex: 1, minWidth: 0, overflowY: 'auto', padding: 20 }}>
          {!selected ? (
            <ModuleEmpty t={t} title="Выберите обращение" />
          ) : (
            <div style={{ maxWidth: 640 }}>
              <Text weight="semibold" style={{ fontSize: 18 }}>{selected.clientName}</Text>
              <Text style={{ fontSize: 13, color: t.text.secondary, marginTop: 4 }}>
                {selected.phoneMasked} · № {selected.id.slice(0, 8).toUpperCase()}
              </Text>
              <Row style={{ gap: 8, marginTop: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                <Pill size="sm">{selected.channel}</Pill>
                <TopicChip t={t} topic={selected.topic} size="sm" />
                <Pill size="sm" tone={STATUS_TONE[selected.status]}>{STATUS_LABEL[selected.status]}</Pill>
              </Row>
              <div style={{ marginTop: 18, display: 'grid', gap: 12 }}>
                <Meta t={t} label="Оператор" value={selected.operatorName} />
                <Meta t={t} label="Открыто" value={formatDateTime(selected.openedAt)} />
                {selected.closedAt ? (
                  <Meta t={t} label="Закрыто" value={formatDateTime(selected.closedAt)} />
                ) : null}
              </div>
              <div
                style={{
                  marginTop: 20,
                  padding: 14,
                  borderRadius: 10,
                  border: `1px solid ${t.stroke.secondary}`,
                  background: t.fill.secondary,
                }}
              >
                <Text weight="semibold" style={{ fontSize: 12, color: t.text.secondary, marginBottom: 8 }}>
                  Summary клиента
                </Text>
                {loadedSummary ? (
                  <ClientSummaryPanel t={t} data={loadedSummary} />
                ) : (
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={summaryLoadingId === selected.id}
                    onClick={() => void loadSummary()}
                  >
                    {summaryLoadingId === selected.id ? 'Загрузка…' : 'Узнать summary'}
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </ArmModuleFrame>
  )
}

function Meta({ t, label, value }: { t: ArmModuleProps['t']; label: string; value: string }) {
  return (
    <div>
      <Text style={{ fontSize: 11, color: t.text.tertiary }}>{label}</Text>
      <Text style={{ fontSize: 13, marginTop: 2 }}>{value}</Text>
    </div>
  )
}

function selectStyle(t: ArmModuleProps['t']): CSSProperties {
  return {
    padding: '8px 10px',
    borderRadius: 8,
    border: `1px solid ${t.stroke.secondary}`,
    background: t.bg.editor,
    color: t.text.primary,
    fontFamily: 'inherit',
    fontSize: 13,
  }
}
