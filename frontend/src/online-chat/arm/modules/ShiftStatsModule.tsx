import { Pill, Row, Text } from '../primitives'
import { ArmModuleFrame } from './ArmModuleFrame'
import type { ArmModuleProps } from './types'

const KPIS = [
  { id: 'closed', label: 'Закрыто за смену', value: '27' },
  { id: 'active', label: 'Активных сейчас', value: '3' },
  { id: 'aht', label: 'Среднее время обработки', value: '4:12' },
  { id: 'sla', label: 'Доля ответов в срок', value: '92%' },
  { id: 'fcr', label: 'Решено с первого обращения', value: '78%' },
  { id: 'csat', label: 'Оценка клиентов', value: '4.6' },
]

const TOPICS = [
  { topic: 'Карты и счета', count: 9 },
  { topic: 'Платежи и переводы', count: 6 },
  { topic: 'Мобильный банк', count: 5 },
  { topic: 'Ипотека', count: 3 },
  { topic: 'Прочее', count: 4 },
]

const PRESENCE_LOG = [
  { from: '08:00', to: '10:35', status: 'в сети' },
  { from: '10:35', to: '10:50', status: 'перерыв' },
  { from: '10:50', to: '13:10', status: 'в сети' },
  { from: '13:10', to: '13:40', status: 'обед' },
  { from: '13:40', to: 'сейчас', status: 'в сети' },
]

export function ShiftStatsModule({ t, scheme, operatorName, armRole, onBack }: ArmModuleProps) {
  const maxTopic = Math.max(...TOPICS.map((item) => item.count))

  return (
    <ArmModuleFrame
      t={t}
      scheme={scheme}
      title="Статистика смены"
      subtitle={`${operatorName} · показатели текущего рабочего дня`}
      onBack={onBack}
    >
      <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <Row style={{ gap: 8, flexWrap: 'wrap' }}>
          <Pill tone="info" size="sm">Смена с 08:00</Pill>
          <Pill size="sm">{armRole === 'supervisor' ? 'Вид супервизора' : 'Личные показатели'}</Pill>
        </Row>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
            gap: 10,
          }}
        >
          {KPIS.map((kpi) => (
            <div
              key={kpi.id}
              style={{
                padding: 14,
                borderRadius: 10,
                border: `1px solid ${t.stroke.secondary}`,
                background: t.bg.editor,
              }}
            >
              <Text style={{ fontSize: 11, color: t.text.tertiary }}>{kpi.label}</Text>
              <Text weight="semibold" style={{ fontSize: 26, marginTop: 4, letterSpacing: '-0.02em' }}>
                {kpi.value}
              </Text>
            </div>
          ))}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 12 }}>
          <section
            style={{
              padding: 14,
              borderRadius: 10,
              border: `1px solid ${t.stroke.secondary}`,
              background: t.bg.editor,
            }}
          >
            <Text weight="semibold" style={{ marginBottom: 12 }}>Тематики закрытых диалогов</Text>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {TOPICS.map((item) => (
                <div key={item.topic}>
                  <Row style={{ justifyContent: 'space-between', marginBottom: 4 }}>
                    <Text style={{ fontSize: 12 }}>{item.topic}</Text>
                    <Text style={{ fontSize: 12, color: t.text.secondary }}>{item.count}</Text>
                  </Row>
                  <div
                    style={{
                      height: 6,
                      borderRadius: 999,
                      background: t.fill.tertiary,
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        width: `${(item.count / maxTopic) * 100}%`,
                        height: '100%',
                        background: scheme.accentControl,
                        borderRadius: 999,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section
            style={{
              padding: 14,
              borderRadius: 10,
              border: `1px solid ${t.stroke.secondary}`,
              background: t.bg.editor,
            }}
          >
            <Text weight="semibold" style={{ marginBottom: 12 }}>Статусы за смену</Text>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {PRESENCE_LOG.map((row) => (
                <Row
                  key={`${row.from}-${row.status}`}
                  style={{
                    justifyContent: 'space-between',
                    padding: '8px 10px',
                    borderRadius: 8,
                    background: t.fill.secondary,
                  }}
                >
                  <Text style={{ fontSize: 12 }}>{row.status}</Text>
                  <Text style={{ fontSize: 12, color: t.text.secondary }}>
                    {row.from} – {row.to}
                  </Text>
                </Row>
              ))}
            </div>
          </section>
        </div>
      </div>
    </ArmModuleFrame>
  )
}
