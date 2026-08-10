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
  type WidgetPlacement,
} from '../api/managementApi'
import '../shell/Management.css'

type Tab = 'operators' | 'departments' | 'placements' | 'channels' | 'routing' | 'bots' | 'analytics'

const tabs: Array<{ id: Tab; label: string }> = [
  { id: 'operators', label: 'Операторы' },
  { id: 'departments', label: 'Отделы' },
  { id: 'placements', label: 'Размещения виджета' },
  { id: 'channels', label: 'Каналы платформы' },
  { id: 'routing', label: 'Маршрутизация' },
  { id: 'bots', label: 'Боты' },
  { id: 'analytics', label: 'Аналитика' },
]

function slugHint(value: string): string {
  const ascii = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return ascii || `item-${Date.now().toString(36)}`
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

  const perform = async (action: () => Promise<unknown>, message: string) => {
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
            <option value="day">Сегодня / 1 день</option>
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
          ['Resolution, %', kpis.resolution_rate ?? '—'],
          ['Avg first response, сек', kpis.average_first_response_seconds ?? '—'],
          ['CSAT', kpis.average_rating == null ? '—' : Number(kpis.average_rating).toFixed(2)],
        ].map(([label, value]) => (
          <article className="chat-management__card chat-management__kpi" key={String(label)}>
            <span>{label}</span>
            <strong>{String(value)}</strong>
          </article>
        ))}
      </div>
      <p className="chat-management__muted">
        Данные из live API. Для прода достаточно настроить SMTP / MinIO / токены каналов в env —
        код отчётности менять не нужно.
      </p>
    </section>
  )
}

interface TabProps {
  disabled: boolean
  perform: (action: () => Promise<unknown>, message: string) => Promise<boolean>
}

function OperatorsTab({
  items,
  departments,
  disabled,
  perform,
}: TabProps & { items: ChatOperator[]; departments: Department[] }) {
  const [name, setName] = useState('')
  const [username, setUsername] = useState('')
  const [departmentId, setDepartmentId] = useState('')
  const [capacity, setCapacity] = useState(5)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const ok = await perform(
      () => operatorsApi.create({
        name,
        username,
        department_id: departmentId || null,
        capacity,
        presence: 'offline',
        is_active: true,
      }),
      'Оператор создан.',
    )
    if (ok) {
      setName('')
      setUsername('')
    }
  }

  return (
    <div className="chat-management__split">
      <form className="chat-management__card" onSubmit={(event) => void submit(event)}>
        <h2>Новый оператор</h2>
        <div className="chat-management__form-grid">
          <label>Имя<input required value={name} onChange={(event) => setName(event.target.value)} /></label>
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
            <thead><tr><th>Имя</th><th>Отдел</th><th>Статус</th><th>Лимит</th><th>Активен</th></tr></thead>
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
                      onChange={(event) => void perform(
                        () => operatorsApi.setPresence(item.id, presenceToApi(event.target.value)),
                        `Статус ${item.name} обновлён.`,
                      )}
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
                      onBlur={(event) => {
                        if (event.target.valueAsNumber !== item.capacity) {
                          void perform(
                            () => operatorsApi.update(item.id, { capacity: event.target.valueAsNumber }),
                            `Лимит ${item.name} обновлён.`,
                          )
                        }
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
    const ok = await perform(
      () => departmentsApi.create({
        name,
        code: code.trim() || slugHint(name),
        description,
        is_active: true,
      }),
      'Отдел создан.',
    )
    if (ok) {
      setName('')
      setCode('')
      setDescription('')
    }
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
                      void perform(() => departmentsApi.update(item.id, { name: next }), 'Отдел обновлён.')
                    }
                  }}
                >
                  Переименовать
                </button>
                <button
                  className="is-danger"
                  disabled={disabled}
                  onClick={() => {
                    if (window.confirm(`Удалить отдел «${item.name}»?`)) {
                      void perform(() => departmentsApi.remove(item.id), 'Отдел удалён.')
                    }
                  }}
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

function PlacementsTab({
  items,
  departments,
  disabled,
  perform,
}: TabProps & { items: WidgetPlacement[]; departments: Department[] }) {
  const [editingId, setEditingId] = useState<EntityId | null>(null)
  const [form, setForm] = useState<Partial<WidgetPlacement>>(emptyPlacement)
  const [domains, setDomains] = useState('')
  const [fields, setFields] = useState('Имя:name:text, Телефон:phone:tel')

  const edit = (item: WidgetPlacement) => {
    setEditingId(item.id)
    setForm(item)
    setDomains((item.allowed_domains ?? []).join(', '))
    setFields((item.form_fields ?? []).map((field) =>
      `${field.label}:${field.key}:${field.type ?? 'text'}${field.required ? ':required' : ''}`,
    ).join(', '))
  }
  const reset = () => {
    setEditingId(null)
    setForm(emptyPlacement)
    setDomains('')
    setFields('Имя:name:text, Телефон:phone:tel')
  }
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const payload: Partial<WidgetPlacement> = {
      ...form,
      code: (form.code || '').trim() || slugHint(form.name || 'widget'),
      allowed_domains: domains.split(',').map((value) => value.trim()).filter(Boolean),
      form_fields: fields.split(',').map((value) => {
        const [label, key, type, required] = value.trim().split(':')
        return { label, key, type: (type || 'text') as 'text' | 'tel' | 'email', required: required === 'required' }
      }).filter((field) => field.label && field.key),
    }
    const ok = await perform(
      () => editingId == null ? placementsApi.create(payload) : placementsApi.update(editingId, payload),
      editingId == null ? 'Размещение создано.' : 'Размещение обновлено.',
    )
    if (ok) reset()
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
          <label className="is-wide">
            Поля формы: подпись:ключ:тип[:required]
            <input value={fields} onChange={(event) => setFields(event.target.value)} placeholder="Имя:name:text:required, Телефон:phone:tel" />
          </label>
          <label className="chat-management__check">
            <input type="checkbox" checked={form.require_phone ?? false} onChange={(event) => set('require_phone', event.target.checked)} />
            Телефон обязателен
          </label>
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
                  onClick={() => {
                    if (window.confirm(`Удалить размещение «${item.name}»?`)) {
                      void perform(() => placementsApi.remove(item.id), 'Размещение удалено.')
                    }
                  }}
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
                  }, `Проверка канала «${row.name}» выполнена.`)}
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
                  }, active ? `Канал «${row.name}» выключен.` : `Канал «${row.name}» включён.`)}
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
    const ok = await perform(
      () => routingRulesApi.create({
        name,
        priority,
        department_id: departmentId,
        channel_id: channelId || null,
        max_load: maxLoad,
        is_active: true,
      }),
      'Правило создано.',
    )
    if (ok) setName('')
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
                  )}
                >
                  {item.is_active ? 'Выключить' : 'Включить'}
                </button>
                <button
                  className="is-danger"
                  disabled={disabled}
                  onClick={() => {
                    if (window.confirm(`Удалить правило «${item.name}»?`)) {
                      void perform(() => routingRulesApi.remove(item.id), 'Правило удалено.')
                    }
                  }}
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
  const [triggers, setTriggers] = useState('карт=Уточните, пожалуйста, вопрос по карте.; вклад=Какой вклад вас интересует?')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const triggerResponses = Object.fromEntries(
      triggers.split(';').map((part) => part.trim()).filter(Boolean).map((part) => {
        const index = part.indexOf('=')
        return index < 0 ? [part, ''] : [part.slice(0, index).trim(), part.slice(index + 1).trim()]
      }).filter(([trigger, response]) => trigger && response),
    )
    const ok = await perform(
      () => botsApi.create({
        name,
        department_id: departmentId,
        is_active: false,
        welcome_message: welcome,
        fallback_message: handoff,
        handoff_message: handoff,
        trigger_responses: triggerResponses,
        max_bot_turns: 3,
      }),
      'Бот создан.',
    )
    if (ok) setName('')
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
          <label className="is-wide">
            Ответы: ключ=ответ; ключ=ответ
            <textarea value={triggers} onChange={(event) => setTriggers(event.target.value)} />
          </label>
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
                  )}
                >
                  {item.is_active ? 'Выключить' : 'Включить'}
                </button>
                <button
                  className="is-danger"
                  disabled={disabled}
                  onClick={() => {
                    if (window.confirm(`Удалить бота «${item.name}»?`)) {
                      void perform(() => botsApi.remove(item.id), 'Бот удалён.')
                    }
                  }}
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
