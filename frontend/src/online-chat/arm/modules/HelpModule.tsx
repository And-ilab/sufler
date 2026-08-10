import { useState } from 'react'
import { Button, Text } from '../primitives'
import { ArmModuleFrame } from './ArmModuleFrame'
import type { ArmModuleId, ArmModuleProps } from './types'

type HelpSection = {
  id: string
  title: string
  body: string
  jump?: ArmModuleId
}

const SECTIONS: HelpSection[] = [
  {
    id: 'dialogs',
    title: 'Диалоги и очереди',
    body:
      'Основная среда АРМ: слева очереди (ожидают ответа, мои, общая, офлайн), в центре переписка с клиентом, справа карточка клиента и суфлёр. Статусы присутствия переключаются в шапке.',
    jump: 'dialogs',
  },
  {
    id: 'history',
    title: 'История обращений',
    body:
      'Кросс-канальная история клиента (чат + телефония). Ищите по ФИО, телефону, теме и оператору. Summary помогает быстро войти в контекст повторного обращения (FR-CHAT-07).',
    jump: 'history',
  },
  {
    id: 'stats',
    title: 'Статистика смены',
    body:
      'Личные KPI смены: закрытые диалоги, AHT, SLA, FCR, CSAT, распределение тематик и журнал присутствия.',
    jump: 'stats',
  },
  {
    id: 'colleagues',
    title: 'Диалоги коллег',
    body:
      'Отдельный модуль просмотра: выберите оператора → список его активных диалогов → «Открыть АРМ просмотра». Режим только чтения (UC-O8 / FR-CHAT-14). В очереди остаётся быстрая секция «Диалоги коллег».',
    jump: 'colleagues',
  },
  {
    id: 'internal',
    title: 'Внутренний чат',
    body:
      'Канал между сотрудниками без участия клиента (UC-O6 / FR-CHAT-16). Слева поиск и закреплённые/недавние контакты, по центру переписка, справа карточка коллеги. Можно перейти к его клиентским диалогам.',
    jump: 'internal',
  },
  {
    id: 'templates',
    title: 'Шаблоны ответов',
    body:
      'Конструктор быстрых ответов с категориями и переменными {{client_name}}, {{operator_name}}. Шаблоны сохраняются локально; добавляйте, редактируйте и копируйте текст в ответ клиенту.',
    jump: 'templates',
  },
  {
    id: 'settings',
    title: 'Настройки АРМ',
    body:
      'Звук и desktop-уведомления, компактная очередь, поведение Enter, масштаб текста. Тема light/dark — в шапке платформы.',
    jump: 'settings',
  },
  {
    id: 'hotkeys',
    title: 'Горячие клавиши (план)',
    body:
      '☰ — меню АРМ · Esc — закрыть меню/модалки · в композере клиента: Ctrl+Enter — отправить (если Enter не назначен на отправку). Полный список будет расширен на приёмке.',
  },
]

export function HelpModule({ t, scheme, onBack, onNavigate }: ArmModuleProps) {
  const [openId, setOpenId] = useState<string | null>(SECTIONS[0]?.id ?? null)

  return (
    <ArmModuleFrame
      t={t}
      scheme={scheme}
      title="Справка"
      subtitle="Краткая инструкция по модулям АРМ оператора онлайн-чата"
      onBack={onBack}
    >
      <div style={{ padding: 16, maxWidth: 760, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {SECTIONS.map((section) => {
          const open = openId === section.id
          return (
            <div
              key={section.id}
              style={{
                borderRadius: 10,
                border: `1px solid ${open ? scheme.accentWeak : t.stroke.secondary}`,
                background: t.bg.editor,
                overflow: 'hidden',
              }}
            >
              <button
                type="button"
                onClick={() => setOpenId(open ? null : section.id)}
                style={{
                  width: '100%',
                  textAlign: 'left',
                  padding: '12px 14px',
                  border: 'none',
                  background: open ? t.fill.tertiary : 'transparent',
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  color: t.text.primary,
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: 12,
                }}
              >
                <Text weight="semibold" style={{ fontSize: 14 }}>{section.title}</Text>
                <span style={{ color: t.text.tertiary }}>{open ? '−' : '+'}</span>
              </button>
              {open ? (
                <div style={{ padding: '0 14px 14px' }}>
                  <Text style={{ fontSize: 13, lineHeight: 1.55, color: t.text.secondary }}>
                    {section.body}
                  </Text>
                  {section.jump ? (
                    <div style={{ marginTop: 10 }}>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => {
                          if (section.jump === 'dialogs') onBack()
                          else onNavigate?.(section.jump!)
                        }}
                      >
                        Открыть раздел
                      </Button>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          )
        })}
      </div>
    </ArmModuleFrame>
  )
}
