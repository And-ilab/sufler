import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  channelsApi,
  botsApi,
  departmentsApi,
  getAnalytics,
  operatorsApi,
  placementsApi,
  routingRulesApi,
  type AnalyticsResponse,
  type ChatChannel,
  type BotConfiguration,
  type ChatOperator,
  type Department,
  type EntityId,
  type RoutingRule,
  type WidgetFormField,
  type WidgetPlacement,
} from '../api/managementApi'
import '../shell/Management.css'

type Tab = 'operators' | 'departments' | 'placements' | 'channels' | 'routing' | 'bots' | 'analytics'

type ConfirmRequest = {
  title: string
  description: string
}

type PerformFn = (
  action: () => Promise<unknown>,
  message: string,
  confirm?: ConfirmRequest,
) => Promise<boolean>

const tabs: Array<{ id: Tab; label: string }> = [
  { id: 'operators', label: 'Операторы' },
  { id: 'departments', label: 'Отделы' },
  { id: 'placements', label: 'Размещения виджета' },
  { id: 'channels', label: 'Каналы платформы' },
  { id: 'routing', label: 'Маршрутизация' },
  { id: 'bots', label: 'Боты' },
  { id: 'analytics', label: 'Аналитика' },
]

const POPULAR_FORM_FIELDS: WidgetFormField[] = [
  { key: 'first_name', label: 'Имя', type: 'text', required: true },
  { key: 'last_name', label: 'Фамилия', type: 'text', required: false },
  { key: 'phone', label: 'Телефон', type: 'tel', required: true },
  { key: 'email', label: 'Email', type: 'email', required: false },
  { key: 'question', label: 'Тема обращения', type: 'text', required: true },
  { key: 'account', label: 'Номер счёта или карты', type: 'text', required: false },
  { key: 'city', label: 'Город', type: 'text', required: false },
  { key: 'passport', label: 'Серия и номер паспорта', type: 'text', required: false },
  { key: 'inn', label: 'УНП / ИНН', type: 'text', required: false },
  { key: 'company', label: 'Организация', type: 'text', required: false },
]

function slugHint(value: string): string {
  const ascii = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return ascii || `item-${Date.now().toString(36)}`
}

/** «Шейпа Семен Игоревич» → «Шейпа С.И.» */
function formatOperatorFio(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return ''
  if (parts.length === 1) return parts[0]
  const surname = parts[0]
  const initials = parts
    .slice(1)
    .map((part) => `${part[0]?.toUpperCase() ?? ''}.`)
    .join('')
  return `${surname} ${initials}`.trim()
}

/** ARM presence labels; map to backend OperatorPresence on save. */
const ARM_PRESENCE_OPTIONS = [
  { ui: 'online', api: 'online', label: 'в сети' },
  { ui: 'invisible', api: 'offline', label: 'невидимка' },
  { ui: 'break', api: 'break', label: 'перерыв' },
  { ui: 'lunch', api: 'lunch', label: 'обед' },
  { ui: 'tech_break', api: 'tech_issue', label: 'техперерыв' },
  { ui: 'training', api: 'training', label: 'обучение' },
  { ui: 'meeting', api: 'meeting', label: 'встреча' },
  { ui: 'offline_queue', api: 'busy', label: 'офлайн-обращения' },
  { ui: 'offline', api: 'offline', label: 'не в сети' },
] as const

function presenceToUi(presence: string): string {
  if (presence === 'tech_issue') return 'tech_break'
  if (presence === 'busy') return 'offline_queue'
  return presence
}

function presenceToApi(ui: string): ChatOperator['presence'] {
  const found = ARM_PRESENCE_OPTIONS.find((item) => item.ui === ui)
  return (found?.api ?? 'offline') as ChatOperator['presence']
}

const CANONICAL_CHANNELS: Array<{ kind: string; name: string }> = [
  { kind: 'widget', name: 'Виджет сайта' },
  { kind: 'telegram', name: 'Telegram' },
  { kind: 'viber', name: 'Viber' },
  { kind: 'vk', name: 'ВКонтакте' },
  { kind: 'ok', name: 'Одноклассники' },
  { kind: 'api', name: 'API-канал' },
]

const emptyPlacement: Partial<WidgetPlacement> = {
  name: '',
  allowed_domains: [],
  welcome_message: 'Здравствуйте! Чем можем помочь?',
  offline_message: 'Сейчас операторы недоступны. Оставьте сообщение.',
  require_phone: false,
  theme_accent: '#007A43',
  form_fields: [],
  is_active: true,
}

function departmentName(
  value: Department | EntityId | null | undefined,
  departments: Department[],
) {
  if (value && typeof value === 'object') return value.name
  return departments.find((item) => String(item.id) === String(value))?.name ?? '—'
}

function entityDepartmentId(entity: {
  department?: Department | EntityId | null
  department_id?: EntityId | null
}) {
  return entity.department_id ?? (entity.department && typeof entity.department === 'object'
    ? entity.department.id
    : entity.department) ?? ''
}

export function ChatAdminApp() {
  const [tab, setTab] = useState<Tab>('operators')
  const [departments, setDepartments] = useState<Department[]>([])
  const [operators, setOperators] = useState<ChatOperator[]>([])
  const [placements, setPlacements] = useState<WidgetPlacement[]>([])
  const [channels, setChannels] = useState<ChatChannel[]>([])
  const [rules, setRules] = useState<RoutingRule[]>([])
  const [bots, setBots] = useState<BotConfiguration[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [pendingConfirm, setPendingConfirm] = useState<{
    title: string
    description: string
    action: () => Promise<unknown>
    message: string
  } | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [departmentItems, operatorItems, placementItems, channelItems, ruleItems, botItems] =
        await Promise.all([
          departmentsApi.list(),
          operatorsApi.list(),
          placementsApi.list(),
          channelsApi.list(),
          routingRulesApi.list(),
          botsApi.list(),
        ])
      setDepartments(departmentItems)
      setOperators(operatorItems)
      setPlacements(placementItems)
      setChannels(channelItems)
      setRules(ruleItems)
      setBots(botItems)
      setError('')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Не удалось загрузить настройки')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const runAction = async (action: () => Promise<unknown>, message: string) => {
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      await action()
      setSuccess(message)
      await refresh()
      return true
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Операция не выполнена')
      return false
    } finally {
      setSaving(false)
    }
  }

  const perform: PerformFn = async (action, message, confirm) => {
    if (confirm) {
      setPendingConfirm({
        title: confirm.title,
        description: confirm.description,
        action,
        message,
      })
      return false
    }
    return runAction(action, message)
  }

  return (
    <main className="chat-management">
      <div className="chat-management__inner">
        <div className="chat-management__heading">
          <div>
            <h1>Управление онлайн-чатом</h1>
            <p className="chat-management__muted">Операторы, точки входа и правила распределения</p>
          </div>
          <button className="is-secondary" onClick={() => void refresh()} disabled={loading}>
            {loading ? 'Загрузка…' : 'Обновить'}
          </button>
        </div>
        {error && <p className="chat-management__error" role="alert">{error}</p>}
        {success && <p className="chat-management__success" role="status">{success}</p>}
        {pendingConfirm ? (
          <div className="chat-management__confirm" role="dialog" aria-modal="true" aria-labelledby="admin-confirm-title">
            <div className="chat-management__confirm-card">
              <h2 id="admin-confirm-title">{pendingConfirm.title}</h2>
              <p>{pendingConfirm.description}</p>
              <div className="chat-management__actions">
                <button
                  type="button"
                  className="is-secondary"
                  onClick={() => setPendingConfirm(null)}
                  disabled={saving}
                >
                  Отмена
                </button>
                <button
                  type="button"
                  onClick={() => {
                    const current = pendingConfirm
                    setPendingConfirm(null)
                    void runAction(current.action, current.message)
                  }}
                  disabled={saving}
                >
                  Подтвердить
                </button>
              </div>
            </div>
          </div>
        ) : null}
        <div className="chat-management__tabs" role="tablist" aria-label="Настройки онлайн-чата">
          {tabs.map((item) => (
            <button
              key={item.id}
              role="tab"
              aria-selected={tab === item.id}
              className={tab === item.id ? 'is-active' : undefined}
              onClick={() => {
                setTab(item.id)
                setSuccess('')
              }}
            >
              {item.label}
            </button>
          ))}
        </div>

        {tab === 'operators' && (
          <OperatorsTab
            items={operators}
            departments={departments}
            disabled={saving}
            perform={perform}
          />
        )}
        {tab === 'departments' && (
          <DepartmentsTab items={departments} disabled={saving} perform={perform} />
        )}
        {tab === 'placements' && (
          <PlacementsTab
            items={placements}
            departments={departments}
            disabled={saving}
            perform={perform}
          />
        )}
        {tab === 'channels' && (
          <ChannelsTab items={channels} disabled={saving} perform={perform} />
        )}
        {tab === 'routing' && (
          <RoutingTab
            items={rules}
            departments={departments}
            channels={channels}
            disabled={saving}
            perform={perform}
          />
        )}
        {tab === 'bots' && (
          <BotsTab
            items={bots}
            departments={departments}
            disabled={saving}
            perform={perform}
          />
        )}
        {tab === 'analytics' && <AnalyticsTab />}
      </div>
    </main>
  )
}

function AnalyticsTab() {
  const [period, setPeriod] = useState<'day' | 'week' | 'month'>('week')
  const [data, setData] = useState<AnalyticsResponse | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    void getAnalytics(period)
      .then((response) => {
        setData(response)
        setError('')
      })
      .catch((caught) => {
        setError(caught instanceof Error ? caught.message : 'Не удалось загрузить аналитику')
      })
      .finally(() => setLoading(false))
  }, [period])

  const kpis = (data?.kpis ?? {}) as Record<string, string | number | null | undefined>

  return (
    <section className="chat-management__section" aria-labelledby="analytics-heading">
      <div className="chat-management__toolbar">
        <h2 id="analytics-heading">Оперативная аналитика</h2>
        <label>
          Период
          <select
            value={period}
            onChange={(event) => setPeriod(event.target.value as 'day' | 'week' | 'month')}
          >
            <option value="day">1 день</option>
            <option value="week">7 дней</option>
            <option value="month">30 дней</option>
          </select>
        </label>
      </div>
      {error && <p className="chat-management__error" role="alert">{error}</p>}
      {loading && <p className="chat-management__muted">Загрузка…</p>}
      <div className="chat-management__grid">
        {[
          ['Диалоги', kpis.dialogs ?? 0],
          ['Закрыто', kpis.closed ?? 0],
          ['В очереди', kpis.waiting ?? 0],
          ['Решено, %', kpis.resolution_rate ?? '—'],
          ['Среднее время первого ответа, сек', kpis.average_first_response_seconds ?? '—'],
          ['Оценка клиентов (CSAT)', kpis.average_rating == null ? '—' : Number(kpis.average_rating).toFixed(2)],
        ].map(([label, value]) => (
          <article className="chat-management__card chat-management__kpi" key={String(label)}>
            <span>{label}</span>
            <strong>{String(value)}</strong>
          </article>
        ))}
      </div>
    </section>
  )
}

interface TabProps {
  disabled: boolean
  perform: PerformFn
}

function OperatorsTab({
  items,
  departments,
  disabled,
  perform,
}: TabProps & { items: ChatOperator[]; departments: Department[] }) {
  const [fullName, setFullName] = useState('')
  const [username, setUsername] = useState('')
  const [departmentId, setDepartmentId] = useState('')
  const [capacity, setCapacity] = useState(5)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const name = formatOperatorFio(fullName)
    if (!name) return
    await perform(
      async () => {
        await operatorsApi.create({
          name,
          username,
          department_id: departmentId || null,
          capacity,
          presence: 'offline',
          is_active: true,
        })
        setFullName('')
        setUsername('')
      },
      'Оператор создан.',
      {
        title: 'Создать оператора?',
        description: `Будет создан оператор «${name}» с лимитом ${capacity} диалогов.`,
      },
    )
  }

  return (
    <div className="chat-management__split">
      <form className="chat-management__card" onSubmit={(event) => void submit(event)}>
        <h2>Новый оператор</h2>
        <div className="chat-management__form-grid">
          <label className="is-wide">
            ФИО
            <input
              required
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
            />
          </label>
          <label>Логин<input required value={username} onChange={(event) => setUsername(event.target.value)} /></label>
          <label>
            Отдел
            <select value={departmentId} onChange={(event) => setDepartmentId(event.target.value)}>
              <option value="">Без отдела</option>
              {departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label>
            Вместимость
            <input type="number" min="1" max="50" value={capacity} onChange={(event) => setCapacity(event.target.valueAsNumber)} />
          </label>
        </div>
        <div className="chat-management__actions">
          <button disabled={disabled}>Создать оператора</button>
        </div>
      </form>
      <section className="chat-management__card" aria-labelledby="operators-admin-heading">
        <h2 id="operators-admin-heading">Операторы</h2>
        <div className="chat-management__table-wrap">
          <table>
            <thead><tr><th>ФИО</th><th>Отдел</th><th>Статус</th><th>Лимит</th><th>Активен</th></tr></thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td><strong>{item.name}</strong></td>
                  <td>{item.department_name ?? departmentName(item.department_id ?? item.department, departments)}</td>
                  <td>
                    <select
                      aria-label={`Присутствие ${item.name}`}
                      value={presenceToUi(item.presence)}
                      disabled={disabled}
                      onChange={(event) => {
                        const nextUi = event.target.value
                        const label = ARM_PRESENCE_OPTIONS.find((option) => option.ui === nextUi)?.label ?? nextUi
                        void perform(
                          () => operatorsApi.setPresence(item.id, presenceToApi(nextUi)),
                          `Статус ${item.name} обновлён.`,
                          {
                            title: 'Изменить статус оператора?',
                            description: `Установить для «${item.name}» статус «${label}»?`,
                          },
                        )
                        // Keep select visually stable until refresh applies.
                        event.target.value = presenceToUi(item.presence)
                      }}
                    >
                      {ARM_PRESENCE_OPTIONS.map((option) => (
                        <option key={option.ui} value={option.ui}>{option.label}</option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      aria-label={`Лимит диалогов ${item.name}`}
                      type="number"
                      min="1"
                      max="50"
                      defaultValue={item.capacity}
                      key={`${item.id}-${item.capacity}`}
                      onBlur={(event) => {
                        const next = event.target.valueAsNumber
                        if (Number.isNaN(next) || next === item.capacity) return
                        void perform(
                          () => operatorsApi.update(item.id, { capacity: next }),
                          `Лимит ${item.name} обновлён.`,
                          {
                            title: 'Изменить лимит диалогов?',
                            description: `Для «${item.name}» лимит будет изменён с ${item.capacity} на ${next}.`,
                          },
                        )
                        event.target.value = String(item.capacity)
                      }}
                    />
                  </td>
                  <td>
                    <label className="chat-management__active-check">
                      <input
                        aria-label={`Оператор ${item.name} активен`}
                        type="checkbox"
                        checked={item.is_active !== false}
                        disabled={disabled}
                        onChange={() => void perform(
                          () => operatorsApi.update(item.id, { is_active: item.is_active === false }),
                          `Доступность ${item.name} обновлена.`,
                          {
                            title: item.is_active === false ? 'Активировать оператора?' : 'Деактивировать оператора?',
                            description: item.is_active === false
                              ? `Оператор «${item.name}» снова сможет получать диалоги.`
                              : `Оператор «${item.name}» будет недоступен для назначения.`,
                          },
                        )}
                      />
                    </label>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!items.length && <div className="chat-management__empty">Операторов пока нет.</div>}
        </div>
      </section>
    </div>
  )
}

function DepartmentsTab({ items, disabled, perform }: TabProps & { items: Department[] }) {
  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [description, setDescription] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    await perform(
      async () => {
        await departmentsApi.create({
          name,
          code: code.trim() || slugHint(name),
          description,
          is_active: true,
        })
        setName('')
        setCode('')
        setDescription('')
      },
      'Отдел создан.',
      {
        title: 'Создать отдел?',
        description: `Будет создан отдел «${name}».`,
      },
    )
  }

  return (
    <div className="chat-management__split">
      <form className="chat-management__card" onSubmit={(event) => void submit(event)}>
        <h2>Новый отдел</h2>
        <div className="chat-management__form-grid">
          <label>Название<input required value={name} onChange={(event) => setName(event.target.value)} /></label>
          <label>
            Код
            <input
              value={code}
              placeholder="авто, если пусто"
              onChange={(event) => setCode(event.target.value)}
            />
          </label>
          <label className="is-wide">Описание<textarea value={description} onChange={(event) => setDescription(event.target.value)} /></label>
        </div>
        <div className="chat-management__actions">
          <button disabled={disabled}>Создать отдел</button>
        </div>
      </form>
      <section className="chat-management__card">
        <h2>Отделы</h2>
        <ul className="chat-management__list">
          {items.map((item) => (
            <li className="chat-management__list-item" key={item.id}>
              <header><div><strong>{item.name}</strong> <small>{item.code}</small></div></header>
              <p className="chat-management__muted">{item.description || 'Без описания'}</p>
              <div className="chat-management__actions">
                <button
                  className="is-secondary"
                  disabled={disabled}
                  onClick={() => {
                    const next = window.prompt('Новое название отдела', item.name)?.trim()
                    if (next && next !== item.name) {
                      void perform(
                        () => departmentsApi.update(item.id, { name: next }),
                        'Отдел обновлён.',
                        {
                          title: 'Переименовать отдел?',
                          description: `«${item.name}» → «${next}».`,
                        },
                      )
                    }
                  }}
                >
                  Переименовать
                </button>
                <button
                  className="is-danger"
                  disabled={disabled}
                  onClick={() => void perform(
                    () => departmentsApi.remove(item.id),
                    'Отдел удалён.',
                    {
                      title: 'Удалить отдел?',
                      description: `Отдел «${item.name}» будет удалён.`,
                    },
                  )}
                >
                  Удалить
                </button>
              </div>
            </li>
          ))}
        </ul>
        {!items.length && <div className="chat-management__empty">Отделов пока нет.</div>}
      </section>
    </div>
  )
}

function FormFieldsPicker({
  value,
  onChange,
}: {
  value: WidgetFormField[]
  onChange: (fields: WidgetFormField[]) => void
}) {
  const selectedKeys = new Set(value.map((field) => field.key))
  const togglePopular = (field: WidgetFormField) => {
    if (selectedKeys.has(field.key)) {
      onChange(value.filter((item) => item.key !== field.key))
      return
    }
    onChange([...value, { ...field }])
  }
  const setRequired = (key: string, required: boolean) => {
    onChange(value.map((item) => (item.key === key ? { ...item, required } : item)))
  }
  const removeField = (key: string) => onChange(value.filter((item) => item.key !== key))

  return (
    <div className="chat-management__field-picker is-wide">
      <div className="chat-management__field-picker-head">
        <strong>Поля формы</strong>
        <span>Выберите поля для формы входа в виджет</span>
      </div>

      <div className="chat-management__field-grid" role="group" aria-label="Доступные поля">
        {POPULAR_FORM_FIELDS.map((field) => {
          const checked = selectedKeys.has(field.key)
          return (
            <label
              key={field.key}
              className={`chat-management__field-option${checked ? ' is-checked' : ''}`}
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={() => togglePopular(field)}
              />
              <span>{field.label}</span>
            </label>
          )
        })}
      </div>

      <div className="chat-management__field-selected">
        <div className="chat-management__field-selected-title">
          Выбранные поля
          <span>{value.length}</span>
        </div>
        {value.length ? (
          <ul className="chat-management__selected-fields">
            {value.map((field) => (
              <li key={field.key}>
                <span className="chat-management__selected-fields-label">{field.label}</span>
                <label className="chat-management__required-toggle">
                  <input
                    type="checkbox"
                    checked={field.required}
                    onChange={(event) => setRequired(field.key, event.target.checked)}
                  />
                  <span>Обязательное</span>
                </label>
                <button
                  type="button"
                  className="chat-management__icon-x"
                  aria-label={`Удалить поле «${field.label}»`}
                  onClick={() => removeField(field.key)}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="chat-management__field-empty">Пока ничего не выбрано</p>
        )}
      </div>
    </div>
  )
}

function PlacementsTab({
  items,
  departments,
  disabled,
  perform,
}: TabProps & { items: WidgetPlacement[]; departments: Department[] }) {
  const [editingId, setEditingId] = useState<EntityId | null>(null)
  const [form, setForm] = useState<Partial<WidgetPlacement>>(emptyPlacement)
  const [domains, setDomains] = useState('')
  const [fields, setFields] = useState<WidgetFormField[]>([
    POPULAR_FORM_FIELDS[0],
    POPULAR_FORM_FIELDS[2],
  ])

  const edit = (item: WidgetPlacement) => {
    setEditingId(item.id)
    setForm(item)
    setDomains((item.allowed_domains ?? []).join(', '))
    setFields(item.form_fields?.length ? item.form_fields : [])
  }
  const reset = () => {
    setEditingId(null)
    setForm(emptyPlacement)
    setDomains('')
    setFields([POPULAR_FORM_FIELDS[0], POPULAR_FORM_FIELDS[2]])
  }
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const payload: Partial<WidgetPlacement> = {
      ...form,
      code: (form.code || '').trim() || slugHint(form.name || 'widget'),
      allowed_domains: domains.split(',').map((value) => value.trim()).filter(Boolean),
      form_fields: fields,
    }
    await perform(
      async () => {
        if (editingId == null) await placementsApi.create(payload)
        else await placementsApi.update(editingId, payload)
        reset()
      },
      editingId == null ? 'Размещение создано.' : 'Размещение обновлено.',
      {
        title: editingId == null ? 'Создать размещение?' : 'Сохранить размещение?',
        description: editingId == null
          ? `Будет создано размещение «${form.name || ''}» с ${fields.length} полями формы.`
          : `Изменения размещения «${form.name || ''}» будут сохранены.`,
      },
    )
  }
  const set = <K extends keyof WidgetPlacement>(key: K, value: WidgetPlacement[K]) =>
    setForm((current) => ({ ...current, [key]: value }))

  return (
    <div className="chat-management__split">
      <form className="chat-management__card" onSubmit={(event) => void submit(event)}>
        <h2>{editingId == null ? 'Новое размещение' : 'Редактирование размещения'}</h2>
        <div className="chat-management__form-grid">
          <label>Название<input required value={form.name ?? ''} onChange={(event) => set('name', event.target.value)} /></label>
          <label>
            Код (widget_id)
            <input
              value={form.code ?? ''}
              placeholder="авто, если пусто"
              onChange={(event) => set('code', event.target.value)}
            />
          </label>
          <label className="is-wide">
            Разрешённые домены (через запятую)
            <input placeholder="example.by, bank.example.by" value={domains} onChange={(event) => setDomains(event.target.value)} />
          </label>
          <label className="is-wide">Приветствие<textarea value={form.welcome_message ?? ''} onChange={(event) => set('welcome_message', event.target.value)} /></label>
          <label className="is-wide">Сообщение вне графика<textarea value={form.offline_message ?? ''} onChange={(event) => set('offline_message', event.target.value)} /></label>
          <label>
            Отдел
            <select value={entityDepartmentId(form)} onChange={(event) => set('department_id', event.target.value || null)}>
              <option value="">Общий</option>
              {departments.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label>
            Акцент темы
            <input type="color" value={form.theme_accent ?? '#007A43'} onChange={(event) => set('theme_accent', event.target.value)} />
          </label>
          <FormFieldsPicker value={fields} onChange={setFields} />
          <label className="chat-management__check">
            <input type="checkbox" checked={form.is_active !== false} onChange={(event) => set('is_active', event.target.checked)} />
            Размещение активно
          </label>
        </div>
        <div className="chat-management__actions">
          <button disabled={disabled}>{editingId == null ? 'Создать' : 'Сохранить'}</button>
          {editingId != null && <button type="button" className="is-secondary" onClick={reset}>Отмена</button>}
        </div>
      </form>
      <section className="chat-management__card">
        <h2>Размещения</h2>
        <ul className="chat-management__list">
          {items.map((item) => (
            <li className="chat-management__list-item" key={item.id}>
              <header>
                <div><strong>{item.name}</strong> <span className="chat-management__pill">{item.code}</span></div>
                <span className={`chat-management__pill ${item.is_active === false ? 'is-error' : 'is-success'}`}>
                  {item.is_active === false ? 'выключено' : 'активно'}
                </span>
              </header>
              <p className="chat-management__muted">{(item.allowed_domains ?? []).join(', ') || 'Все домены'}</p>
              <div className="chat-management__actions">
                <button className="is-secondary" onClick={() => edit(item)}>Изменить</button>
                <button
                  className="is-secondary"
                  type="button"
                  onClick={() => {
                    const snippet = `<script src="/widget/widget.js" data-widget-id="${item.code ?? item.id}" data-placement="website" defer></script>`
                    void navigator.clipboard?.writeText(snippet)
                    window.alert(`Код встраивания скопирован:\n\n${snippet}`)
                  }}
                >
                  Код
                </button>
                <button
                  className="is-danger"
                  disabled={disabled}
                  onClick={() => void perform(
                    () => placementsApi.remove(item.id),
                    'Размещение удалено.',
                    {
                      title: 'Удалить размещение?',
                      description: `Размещение «${item.name}» будет удалено.`,
                    },
                  )}
                >
                  Удалить
                </button>
              </div>
            </li>
          ))}
        </ul>
        {!items.length && <div className="chat-management__empty">Размещений пока нет.</div>}
      </section>
    </div>
  )
}

function healthLabel(status?: string): { text: string; tone: string } {
  switch (status) {
    case 'ok':
      return { text: 'соединение ок', tone: 'is-success' }
    case 'not_configured':
      return { text: 'не настроен', tone: 'is-warn' }
    case 'error':
      return { text: 'ошибка', tone: 'is-error' }
    default:
      return { text: 'не проверен', tone: '' }
  }
}

function ChannelsTab({ items, disabled, perform }: TabProps & { items: ChatChannel[] }) {
  const rows = CANONICAL_CHANNELS.map((canonical) => {
    const existing = items.find((item) => (item.kind ?? item.channel ?? '') === canonical.kind)
    return { ...canonical, existing }
  })

  return (
    <section className="chat-management__card" aria-labelledby="channels-heading">
      <h2 id="channels-heading">Каналы платформы</h2>
      <ul className="chat-management__list chat-management__channel-list">
        {rows.map((row) => {
          const active = row.existing?.is_active === true
          const health = healthLabel(row.existing?.health_status)
          const counters = row.existing?.counters
          return (
            <li className="chat-management__list-item" key={row.kind}>
              <header>
                <div>
                  <strong>{row.name}</strong>
                </div>
                <span className={`chat-management__pill chat-management__pill--lg ${active ? 'is-success' : 'is-error'}`}>
                  {active ? 'активен' : 'выключен'}
                </span>
              </header>
              <div className="chat-management__channel-meta">
                <span className={`chat-management__pill ${health.tone}`}>{health.text}</span>
                {row.existing?.last_health_check_at ? (
                  <span className="chat-management__muted">
                    проверка: {new Date(row.existing.last_health_check_at).toLocaleString('ru-RU')}
                  </span>
                ) : null}
              </div>
              <dl className="chat-management__channel-counters">
                <div>
                  <dt>В очереди</dt>
                  <dd>{counters?.waiting ?? 0}</dd>
                </div>
                <div>
                  <dt>Активные</dt>
                  <dd>{counters?.active ?? 0}</dd>
                </div>
                <div>
                  <dt>Сегодня</dt>
                  <dd>{counters?.today ?? 0}</dd>
                </div>
                <div>
                  <dt>Закрыто сегодня</dt>
                  <dd>{counters?.closed_today ?? 0}</dd>
                </div>
              </dl>
              <div className="chat-management__actions">
                <button
                  className="is-secondary"
                  disabled={disabled || !row.existing}
                  onClick={() => void perform(async () => {
                    if (!row.existing) return
                    await channelsApi.checkHealth(row.existing.id)
                  }, `Проверка канала «${row.name}» выполнена.`, {
                    title: 'Проверить соединение?',
                    description: `Запустить проверку канала «${row.name}»?`,
                  })}
                >
                  Проверить соединение
                </button>
                <button
                  className={active ? 'is-danger' : 'is-secondary'}
                  disabled={disabled}
                  onClick={() => void perform(async () => {
                    if (row.existing) {
                      await channelsApi.update(row.existing.id, { is_active: !active })
                      return
                    }
                    await channelsApi.create({
                      name: row.name,
                      kind: row.kind,
                      is_active: true,
                      account: `channel-${row.kind}`,
                    })
                  }, active ? `Канал «${row.name}» выключен.` : `Канал «${row.name}» включён.`, {
                    title: active ? 'Выключить канал?' : 'Включить канал?',
                    description: `Канал «${row.name}» будет ${active ? 'выключен' : 'включён'}.`,
                  })}
                >
                  {active ? 'Выключить' : 'Включить'}
                </button>
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

function RoutingTab({
  items,
  departments,
  channels,
  disabled,
  perform,
}: TabProps & { items: RoutingRule[]; departments: Department[]; channels: ChatChannel[] }) {
  const [name, setName] = useState('')
  const [priority, setPriority] = useState(100)
  const [departmentId, setDepartmentId] = useState('')
  const [channelId, setChannelId] = useState('')
  const [maxLoad, setMaxLoad] = useState(5)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!departmentId) {
      window.alert('Выберите отдел для правила маршрутизации.')
      return
    }
    await perform(
      async () => {
        await routingRulesApi.create({
          name,
          priority,
          department_id: departmentId,
          channel_id: channelId || null,
          max_load: maxLoad,
          is_active: true,
        })
        setName('')
      },
      'Правило создано.',
      {
        title: 'Создать правило?',
        description: `Будет создано правило маршрутизации «${name}».`,
      },
    )
  }

  return (
    <div className="chat-management__split">
      <form className="chat-management__card" onSubmit={(event) => void submit(event)}>
        <h2>Новое правило</h2>
        <div className="chat-management__form-grid">
          <label>Название<input required value={name} onChange={(event) => setName(event.target.value)} /></label>
          <label>Приоритет<input type="number" min="1" value={priority} onChange={(event) => setPriority(event.target.valueAsNumber)} /></label>
          <label>
            Отдел
            <select required value={departmentId} onChange={(event) => setDepartmentId(event.target.value)}>
              <option value="">Выберите отдел</option>
              {departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label>
            Канал
            <select value={channelId} onChange={(event) => setChannelId(event.target.value)}>
              <option value="">Любой</option>
              {channels.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label>
            Максимальная нагрузка
            <input type="number" min="1" max="50" value={maxLoad} onChange={(event) => setMaxLoad(event.target.valueAsNumber)} />
          </label>
        </div>
        <div className="chat-management__actions">
          <button disabled={disabled}>Создать правило</button>
        </div>
      </form>
      <section className="chat-management__card">
        <h2>Правила маршрутизации</h2>
        <ul className="chat-management__list">
          {[...items].sort((a, b) => a.priority - b.priority).map((item) => (
            <li className="chat-management__list-item" key={item.id}>
              <header>
                <div><strong>{item.priority}. {item.name}</strong></div>
                <span className={`chat-management__pill ${item.is_active ? 'is-success' : 'is-error'}`}>
                  {item.is_active ? 'активно' : 'выключено'}
                </span>
              </header>
              <p className="chat-management__muted">
                {departmentName(entityDepartmentId(item), departments)} ·{' '}
                {channels.find((channel) => String(channel.id) === String(item.channel_id ?? item.channel))?.name ?? 'Любой канал'}
                {item.max_load ? ` · лимит ${item.max_load}` : ''}
              </p>
              <div className="chat-management__actions">
                <button
                  className="is-secondary"
                  disabled={disabled}
                  onClick={() => void perform(
                    () => routingRulesApi.update(item.id, { is_active: !item.is_active }),
                    'Правило обновлено.',
                    {
                      title: item.is_active ? 'Выключить правило?' : 'Включить правило?',
                      description: `Правило «${item.name}» будет ${item.is_active ? 'выключено' : 'включено'}.`,
                    },
                  )}
                >
                  {item.is_active ? 'Выключить' : 'Включить'}
                </button>
                <button
                  className="is-danger"
                  disabled={disabled}
                  onClick={() => void perform(
                    () => routingRulesApi.remove(item.id),
                    'Правило удалено.',
                    {
                      title: 'Удалить правило?',
                      description: `Правило «${item.name}» будет удалено.`,
                    },
                  )}
                >
                  Удалить
                </button>
              </div>
            </li>
          ))}
        </ul>
        {!items.length && <div className="chat-management__empty">Правил пока нет.</div>}
      </section>
    </div>
  )
}

type BotTriggerRow = { id: string; trigger: string; response: string }

function BotsTab({
  items,
  departments,
  disabled,
  perform,
}: TabProps & { items: BotConfiguration[]; departments: Department[] }) {
  const [name, setName] = useState('')
  const [departmentId, setDepartmentId] = useState('')
  const [welcome, setWelcome] = useState('Здравствуйте! Я виртуальный помощник банка.')
  const [handoff, setHandoff] = useState('Подключаю оператора. Пожалуйста, ожидайте.')
  const [triggerRows, setTriggerRows] = useState<BotTriggerRow[]>([
    { id: '1', trigger: 'карт', response: 'Уточните, пожалуйста, вопрос по карте.' },
    { id: '2', trigger: 'вклад', response: 'Какой вклад вас интересует?' },
  ])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const triggerResponses = Object.fromEntries(
      triggerRows
        .map((row) => [row.trigger.trim(), row.response.trim()] as const)
        .filter(([trigger, response]) => trigger && response),
    )
    await perform(
      async () => {
        await botsApi.create({
          name,
          department_id: departmentId,
          is_active: false,
          welcome_message: welcome,
          fallback_message: handoff,
          handoff_message: handoff,
          trigger_responses: triggerResponses,
          max_bot_turns: 3,
        })
        setName('')
      },
      'Бот создан.',
      {
        title: 'Создать бота?',
        description: `Бот «${name}» будет создан выключенным с ${Object.keys(triggerResponses).length} ветками ответов.`,
      },
    )
  }

  return (
    <div className="chat-management__split">
      <form className="chat-management__card" onSubmit={(event) => void submit(event)}>
        <h2>Новый бот первой линии</h2>
        <div className="chat-management__form-grid">
          <label>Название<input required value={name} onChange={(event) => setName(event.target.value)} /></label>
          <label>
            Отдел
            <select required value={departmentId} onChange={(event) => setDepartmentId(event.target.value)}>
              <option value="">Выберите отдел</option>
              {departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label className="is-wide">Приветствие<textarea value={welcome} onChange={(event) => setWelcome(event.target.value)} /></label>
          <label className="is-wide">Передача оператору<textarea value={handoff} onChange={(event) => setHandoff(event.target.value)} /></label>
          <div className="chat-management__field-picker is-wide">
            <div className="chat-management__field-picker-head">
              <strong>Автоответы</strong>
              <span>Ключевые слова и текст ответа бота</span>
            </div>
            <ul className="chat-management__trigger-list">
              {triggerRows.map((row) => (
                <li key={row.id}>
                  <label>
                    Ключ
                    <input
                      value={row.trigger}
                      placeholder="карт"
                      onChange={(event) => setTriggerRows((current) => current.map((item) => (
                        item.id === row.id ? { ...item, trigger: event.target.value } : item
                      )))}
                    />
                  </label>
                  <label>
                    Ответ
                    <input
                      value={row.response}
                      placeholder="Уточните вопрос…"
                      onChange={(event) => setTriggerRows((current) => current.map((item) => (
                        item.id === row.id ? { ...item, response: event.target.value } : item
                      )))}
                    />
                  </label>
                  <button
                    type="button"
                    className="chat-management__icon-x"
                    aria-label="Удалить автоответ"
                    onClick={() => setTriggerRows((current) => current.filter((item) => item.id !== row.id))}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
            <button
              type="button"
              className="is-secondary"
              onClick={() => setTriggerRows((current) => [
                ...current,
                { id: `${Date.now()}`, trigger: '', response: '' },
              ])}
            >
              Добавить ответ
            </button>
          </div>
        </div>
        <p className="chat-management__muted">Новый бот создаётся выключенным. Включите его после проверки сценариев.</p>
        <div className="chat-management__actions">
          <button disabled={disabled}>Создать бота</button>
        </div>
      </form>
      <section className="chat-management__card">
        <h2>Боты</h2>
        <ul className="chat-management__list">
          {items.map((item) => (
            <li className="chat-management__list-item" key={item.id}>
              <header>
                <div><strong>{item.name}</strong><br /><small>{departmentName(item.department_id, departments)}</small></div>
                <span className={`chat-management__pill ${item.is_active ? 'is-success' : 'is-error'}`}>
                  {item.is_active ? 'включён' : 'выключен'}
                </span>
              </header>
              <p className="chat-management__muted">
                Веток: {Object.keys(item.trigger_responses ?? {}).length} · до {item.max_bot_turns} ходов
              </p>
              <div className="chat-management__actions">
                <button
                  className="is-secondary"
                  disabled={disabled}
                  onClick={() => void perform(
                    () => botsApi.update(item.id, { is_active: !item.is_active }),
                    'Статус бота обновлён.',
                    {
                      title: item.is_active ? 'Выключить бота?' : 'Включить бота?',
                      description: `Бот «${item.name}» будет ${item.is_active ? 'выключен' : 'включён'}.`,
                    },
                  )}
                >
                  {item.is_active ? 'Выключить' : 'Включить'}
                </button>
                <button
                  className="is-danger"
                  disabled={disabled}
                  onClick={() => void perform(
                    () => botsApi.remove(item.id),
                    'Бот удалён.',
                    {
                      title: 'Удалить бота?',
                      description: `Бот «${item.name}» будет удалён без возможности восстановления.`,
                    },
                  )}
                >
                  Удалить
                </button>
              </div>
            </li>
          ))}
        </ul>
        {!items.length && <div className="chat-management__empty">Ботов пока нет.</div>}
      </section>
    </div>
  )
}
