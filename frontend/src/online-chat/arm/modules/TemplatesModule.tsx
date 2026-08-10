import { useEffect, useMemo, useState } from 'react'
import { REPLY_TEMPLATES } from '../../api/onlineChatApi'
import { Button, Pill, Row, Text, TextArea } from '../primitives'
import { ArmModuleFrame, formatDateTime, ModuleEmpty } from './ArmModuleFrame'
import { DEFAULT_TEMPLATES } from './demoData'
import type { ArmModuleProps, ReplyTemplateItem } from './types'

const STORAGE_KEY = 'arm-reply-templates-v1'
const CATEGORIES = ['Общие', 'Карты', 'Ипотека', 'Платежи', 'Прочее']

export function loadReplyTemplates(): ReplyTemplateItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      const fromApi = REPLY_TEMPLATES.map((body, index) => ({
        id: `seed-${index}`,
        title: body.slice(0, 42) + (body.length > 42 ? '…' : ''),
        category: 'Общие',
        body,
        updatedAt: new Date().toISOString(),
        favorite: index < 2,
      }))
      const merged = [...DEFAULT_TEMPLATES]
      for (const item of fromApi) {
        if (!merged.some((tpl) => tpl.body === item.body)) merged.push(item)
      }
      return merged
    }
    const parsed = JSON.parse(raw) as ReplyTemplateItem[]
    return parsed.length ? parsed : DEFAULT_TEMPLATES
  } catch {
    return DEFAULT_TEMPLATES
  }
}

export function TemplatesModule({ t, scheme, operatorName, onBack }: ArmModuleProps) {
  const [items, setItems] = useState<ReplyTemplateItem[]>(() => loadReplyTemplates())
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('all')
  const [draft, setDraft] = useState<ReplyTemplateItem | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items))
    } catch {
      /* ignore */
    }
  }, [items])

  useEffect(() => {
    if (!selectedId && items[0]) setSelectedId(items[0].id)
  }, [items, selectedId])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return items.filter((item) => {
      if (category !== 'all' && item.category !== category) return false
      if (!q) return true
      return (
        item.title.toLowerCase().includes(q)
        || item.body.toLowerCase().includes(q)
        || item.category.toLowerCase().includes(q)
      )
    })
  }, [items, query, category])

  const selected = items.find((item) => item.id === selectedId) ?? null
  const editing = draft ?? selected

  const startCreate = () => {
    const blank: ReplyTemplateItem = {
      id: `tpl-${Date.now()}`,
      title: 'Новый шаблон',
      category: 'Общие',
      body: 'Здравствуйте, {{client_name}}!',
      updatedAt: new Date().toISOString(),
    }
    setDraft(blank)
    setSelectedId(blank.id)
  }

  const saveDraft = () => {
    if (!draft) return
    const next = { ...draft, updatedAt: new Date().toISOString() }
    setItems((prev) => {
      const exists = prev.some((item) => item.id === next.id)
      return exists ? prev.map((item) => (item.id === next.id ? next : item)) : [next, ...prev]
    })
    setSelectedId(next.id)
    setDraft(null)
    setNotice('Шаблон сохранён. Он доступен в конструкторе и в композере диалогов (после интеграции).')
  }

  const removeSelected = () => {
    if (!selected) return
    setItems((prev) => prev.filter((item) => item.id !== selected.id))
    setDraft(null)
    setSelectedId(null)
    setNotice('Шаблон удалён')
  }

  const toggleFavorite = () => {
    if (!selected) return
    setItems((prev) =>
      prev.map((item) =>
        item.id === selected.id ? { ...item, favorite: !item.favorite } : item,
      ),
    )
  }

  const previewBody = (body: string) =>
    body
      .replaceAll('{{client_name}}', 'Анна')
      .replaceAll('{{operator_name}}', operatorName)

  const copyBody = async () => {
    if (!editing) return
    try {
      await navigator.clipboard.writeText(previewBody(editing.body))
      setNotice('Текст скопирован в буфер')
    } catch {
      setNotice('Не удалось скопировать')
    }
  }

  return (
    <ArmModuleFrame
      t={t}
      scheme={scheme}
      title="Шаблоны ответов"
      onBack={onBack}
      bodyStyle={{ overflow: 'hidden', display: 'flex' }}
      actions={
        <>
          <Button
            variant="primary"
            onClick={startCreate}
            style={{ padding: '8px 16px', fontSize: 14, fontWeight: 700 }}
          >
            + Новый
          </Button>
          {draft ? (
            <Button variant="secondary" onClick={saveDraft}>Сохранить</Button>
          ) : null}
        </>
      }
    >
      <aside
        style={{
          width: 320,
          flexShrink: 0,
          borderRight: `1px solid ${t.stroke.secondary}`,
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0,
          background: t.bg.editor,
        }}
      >
        <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Поиск шаблонов"
            style={{
              width: '100%',
              padding: '8px 10px',
              borderRadius: 8,
              border: `1px solid ${t.stroke.secondary}`,
              background: t.bg.elevated,
              color: t.text.primary,
              fontFamily: 'inherit',
              fontSize: 13,
            }}
          />
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            style={{
              padding: '8px 10px',
              borderRadius: 8,
              border: `1px solid ${t.stroke.secondary}`,
              background: t.bg.elevated,
              color: t.text.primary,
              fontFamily: 'inherit',
              fontSize: 13,
            }}
          >
            <option value="all">Все категории</option>
            {CATEGORIES.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: '0 8px 12px' }}>
          {filtered.length === 0 ? (
            <Text style={{ fontSize: 12, color: t.text.secondary, padding: 8 }}>Нет шаблонов</Text>
          ) : (
            filtered.map((item) => {
              const active = item.id === (draft?.id ?? selectedId)
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => {
                    setSelectedId(item.id)
                    setDraft(null)
                  }}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    padding: '10px 12px',
                    marginBottom: 4,
                    borderRadius: 8,
                    border: `1px solid ${active ? scheme.accent : 'transparent'}`,
                    background: active ? t.fill.tertiary : 'transparent',
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                    color: t.text.primary,
                  }}
                >
                  <Row style={{ justifyContent: 'space-between', gap: 6 }}>
                    <Text weight="semibold" style={{ fontSize: 13 }}>
                      {item.favorite ? '★ ' : ''}
                      {item.title}
                    </Text>
                    <Pill size="sm">{item.category}</Pill>
                  </Row>
                  <Text
                    style={{
                      fontSize: 11,
                      color: t.text.secondary,
                      marginTop: 4,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {item.body}
                  </Text>
                </button>
              )
            })
          )}
        </div>
      </aside>

      <section style={{ flex: 1, minWidth: 0, overflowY: 'auto', padding: 16 }}>
        {!editing ? (
          <ModuleEmpty t={t} title="Выберите шаблон или создайте новый" />
        ) : (
          <div style={{ maxWidth: 640, display: 'flex', flexDirection: 'column', gap: 12 }}>
            {notice ? (
              <div
                style={{
                  padding: '8px 10px',
                  borderRadius: 8,
                  background: t.fill.tertiary,
                  fontSize: 12,
                  color: t.text.secondary,
                }}
              >
                {notice}
              </div>
            ) : null}

            <label style={{ display: 'grid', gap: 4 }}>
              <Text style={{ fontSize: 11, color: t.text.tertiary }}>Название</Text>
              <input
                value={editing.title}
                onChange={(e) =>
                  setDraft({ ...(draft ?? editing), title: e.target.value })
                }
                style={inputStyle(t)}
              />
            </label>

            <label style={{ display: 'grid', gap: 4 }}>
              <Text style={{ fontSize: 11, color: t.text.tertiary }}>Категория</Text>
              <select
                value={editing.category}
                onChange={(e) =>
                  setDraft({ ...(draft ?? editing), category: e.target.value })
                }
                style={inputStyle(t)}
              >
                {CATEGORIES.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>

            <label style={{ display: 'grid', gap: 4 }}>
              <Text style={{ fontSize: 11, color: t.text.tertiary }}>Текст шаблона</Text>
              <TextArea
                value={editing.body}
                onChange={(value) => setDraft({ ...(draft ?? editing), body: value })}
                rows={6}
              />
            </label>

            <div
              style={{
                padding: 12,
                borderRadius: 8,
                border: `1px solid ${t.stroke.secondary}`,
                background: t.fill.secondary,
              }}
            >
              <Text style={{ fontSize: 11, color: t.text.tertiary, marginBottom: 6 }}>Предпросмотр</Text>
              <Text style={{ fontSize: 13, lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
                {previewBody(editing.body)}
              </Text>
            </div>

            <Row style={{ gap: 8, flexWrap: 'wrap' }}>
              {draft ? (
                <Button variant="primary" size="sm" onClick={saveDraft}>Сохранить</Button>
              ) : (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setDraft({ ...editing })}
                >
                  Редактировать
                </Button>
              )}
              <Button variant="secondary" size="sm" onClick={copyBody}>Копировать</Button>
              {!draft && selected ? (
                <Button variant="ghost" size="sm" onClick={toggleFavorite}>
                  {selected.favorite ? 'Убрать из избранного' : 'В избранное'}
                </Button>
              ) : null}
              {!draft && selected ? (
                <Button variant="ghost" size="sm" onClick={removeSelected}>Удалить</Button>
              ) : null}
            </Row>
            {selected && !draft ? (
              <Text style={{ fontSize: 11, color: t.text.tertiary }}>
                Обновлён: {formatDateTime(selected.updatedAt)}
              </Text>
            ) : null}
          </div>
        )}
      </section>
    </ArmModuleFrame>
  )
}

function inputStyle(t: ArmModuleProps['t']) {
  return {
    width: '100%',
    padding: '8px 10px',
    borderRadius: 8,
    border: `1px solid ${t.stroke.secondary}`,
    background: t.bg.editor,
    color: t.text.primary,
    fontFamily: 'inherit',
    fontSize: 13,
  } as const
}
