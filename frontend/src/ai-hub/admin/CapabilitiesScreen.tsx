import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ensureDevSession,
  isAuthErrorMessage,
  resetDevSessionCache,
} from '../../auth/ensureDevSession'
import { Button, Card, StatusBadge } from '../../components'
import {
  AssistantAdminApiError,
  TASK_EVENT_TRIGGERS,
  createAssistantPrompt,
  deleteAssistantPrompt,
  listAssistantCapabilities,
  listAssistantPrompts,
  setCapabilityEnabled,
  updateAssistantPrompt,
  type AssistantCapability,
  type AssistantPrompt,
  type PromptStatus,
} from './api/assistantAdmin'
import './AssistantAdminScreens.css'

interface CapabilitiesScreenProps {
  canEdit?: boolean
}

function formatAdminError(error: unknown, fallback: string): string {
  if (error instanceof AssistantAdminApiError) {
    const detail =
      error.details.request?.[0] ||
      Object.values(error.details).flat()[0]
    if (detail) return detail
  }
  const message = error instanceof Error ? error.message : ''
  if (message === 'authentication_required') {
    return 'Нет сессии Django. Нажмите «Обновить» — в DEV выполнится вход как dev-role-01.'
  }
  if (message === 'csrf_failed') {
    return 'Сбой CSRF после входа. Нажмите «Обновить» — токен обновится автоматически.'
  }
  if (message === 'permission_denied') {
    return 'Недостаточно прав для этой операции.'
  }
  if (message && isAuthErrorMessage(message)) {
    return 'Нет сессии Django. Нажмите «Обновить» — в DEV выполнится вход как dev-role-01.'
  }
  return message || fallback
}

function openAdminScreen(screenId: string) {
  window.history.pushState({}, '', `/ai-hub/admin/${screenId}`)
  window.dispatchEvent(new PopStateEvent('popstate'))
  window.location.assign(`/ai-hub/admin/${screenId}`)
}

function statusLabel(status: PromptStatus): string {
  return status === 'published' ? 'опубликован' : 'черновик'
}

function SkillTaskPromptsPanel({ canEdit }: { canEdit: boolean }) {
  const [prompts, setPrompts] = useState<AssistantPrompt[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [body, setBody] = useState('')
  const [eventTrigger, setEventTrigger] = useState<string>(TASK_EVENT_TRIGGERS[0])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(true)

  const taskPrompts = useMemo(
    () => prompts.filter((item) => item.prompt_type === 'task'),
    [prompts],
  )
  const selected = taskPrompts.find((item) => item.id === selectedId) ?? null

  const applySelected = (item: AssistantPrompt | null) => {
    if (!item) {
      setSelectedId(null)
      setName('')
      setBody('')
      setEventTrigger(TASK_EVENT_TRIGGERS[0])
      return
    }
    setSelectedId(item.id)
    setName(item.name)
    setBody(item.body)
    setEventTrigger(item.event_trigger || TASK_EVENT_TRIGGERS[0])
  }

  const load = useCallback(async (preferId?: number | null) => {
    setLoading(true)
    setError('')
    try {
      await ensureDevSession()
      const items = await listAssistantPrompts()
      setPrompts(items)
      const tasks = items.filter((item) => item.prompt_type === 'task')
      const target =
        preferId
        ?? selectedId
        ?? tasks.find((item) => item.name.includes('перевод en'))?.id
        ?? tasks[0]?.id
        ?? null
      const current = tasks.find((item) => item.id === target) ?? null
      applySelected(current)
    } catch (err) {
      setError(formatAdminError(err, 'Не удалось загрузить Task-промпты'))
      setPrompts([])
      applySelected(null)
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const runAction = async (action: () => Promise<void>, fallback: string) => {
    if (busy) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await action()
    } catch (err) {
      if (isAuthErrorMessage(err instanceof Error ? err.message : '')) {
        resetDevSessionCache()
        try {
          await ensureDevSession()
          await action()
          return
        } catch (retryErr) {
          setError(formatAdminError(retryErr, fallback))
          return
        }
      }
      setError(formatAdminError(err, fallback))
    } finally {
      setBusy(false)
    }
  }

  const createTask = async () => {
    if (!canEdit) return
    await runAction(async () => {
      const created = await createAssistantPrompt({
        name: 'новый навык',
        body: 'Опишите инструкцию для события.',
        prompt_type: 'task',
        scope: 'bank',
        event_trigger: 'Начало диалога',
      })
      setNotice('Черновик Task-промпта создан')
      await load(created.id)
    }, 'Не удалось создать Task-промпт')
  }

  const saveDraft = async () => {
    if (!canEdit || !selected) return
    await runAction(async () => {
      const updated = await updateAssistantPrompt(selected.id, {
        name: name.trim() || selected.name,
        body: body.trim() || selected.body,
        prompt_type: 'task',
        event_trigger: eventTrigger,
        status: 'draft',
      })
      setNotice(`Черновик сохранён · v${updated.version}`)
      await load(updated.id)
    }, 'Не удалось сохранить черновик')
  }

  const publish = async () => {
    if (!canEdit || !selected) return
    await runAction(async () => {
      await updateAssistantPrompt(selected.id, {
        name: name.trim() || selected.name,
        body: body.trim() || selected.body,
        prompt_type: 'task',
        event_trigger: eventTrigger,
        status: 'draft',
      })
      const published = await updateAssistantPrompt(selected.id, {
        status: 'published',
      })
      setNotice(`Опубликовано · v${published.version}`)
      await load(published.id)
    }, 'Не удалось опубликовать')
  }

  const remove = async () => {
    if (!canEdit || !selected || selected.status === 'published') return
    await runAction(async () => {
      await deleteAssistantPrompt(selected.id)
      setNotice('Task-промпт удалён')
      await load(null)
    }, 'Не удалось удалить')
  }

  const triggerOptions = useMemo(() => {
    const known = new Set<string>([...TASK_EVENT_TRIGGERS])
    for (const item of taskPrompts) {
      if (item.event_trigger) known.add(item.event_trigger)
    }
    if (eventTrigger) known.add(eventTrigger)
    return [...known]
  }, [taskPrompts, eventTrigger])

  if (loading) {
    return <Card className="kb-admin-loading">Загрузка промптов типа Task…</Card>
  }

  return (
    <div className="asst-admin-task-skills" data-testid="skill-task-prompts">
      {error && (
        <Card className="kb-admin__error" role="alert">
          <div className="kb-admin__error-main">
            <strong>Уведомление</strong>
            <span>{error}</span>
          </div>
          <Button type="button" variant="ghost" onClick={() => void load()}>
            Обновить
          </Button>
        </Card>
      )}
      {notice && !error && (
        <p className="asst-admin-ok" role="status">{notice}</p>
      )}

      <div className="asst-admin-task-skills__layout">
        <aside className="asst-admin-library" data-testid="task-prompt-list">
          <Button
            type="button"
            variant="secondary"
            disabled={!canEdit || busy}
            onClick={() => void createTask()}
            data-testid="task-prompt-add"
          >
            + Добавить
          </Button>
          <ul>
            {taskPrompts.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className={item.id === selectedId ? 'is-active' : ''}
                  onClick={() => applySelected(item)}
                  data-testid={`task-prompt-${item.id}`}
                >
                  <span className="asst-admin-task-skills__row">
                    <span>{item.name}</span>
                    <StatusBadge status={item.status === 'published' ? 'success' : 'warning'}>
                      {statusLabel(item.status)}
                    </StatusBadge>
                  </span>
                </button>
              </li>
            ))}
            {!taskPrompts.length && (
              <li className="asst-admin-note">Нет Task-промптов — нажмите «+ Добавить».</li>
            )}
          </ul>
          {selected && selected.status !== 'published' ? (
            <Button
              type="button"
              variant="secondary"
              disabled={!canEdit || busy}
              onClick={() => void remove()}
              data-testid="task-prompt-delete"
            >
              Удалить
            </Button>
          ) : null}
        </aside>

        <div className="asst-admin-editor" data-testid="task-prompt-editor">
          {!selected ? (
            <p className="app-muted">Выберите Task-промпт слева или создайте новый.</p>
          ) : (
            <>
              <header>
                <StatusBadge status={selected.status === 'published' ? 'success' : 'neutral'}>
                  {selected.status === 'published' ? 'Опубликован' : 'Черновик'}
                </StatusBadge>
                <div className="asst-admin-actions">
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={!canEdit || busy}
                    onClick={() => void saveDraft()}
                    data-testid="task-prompt-save"
                  >
                    Сохранить черновик
                  </Button>
                  <Button
                    type="button"
                    variant="primary"
                    disabled={!canEdit || busy}
                    onClick={() => void publish()}
                    data-testid="task-prompt-publish"
                  >
                    Опубликовать
                  </Button>
                </div>
              </header>

              <div className="asst-admin-form">
                <label>
                  Название
                  <input
                    value={name}
                    disabled={!canEdit || busy}
                    onChange={(event) => setName(event.target.value)}
                    data-testid="task-prompt-name"
                  />
                </label>
                <div className="asst-admin-form__row">
                  <label>
                    Тип промпта
                    <select value="task" disabled>
                      <option value="task">Task — задание</option>
                    </select>
                  </label>
                  <label>
                    Событие (триггер)
                    <select
                      value={eventTrigger}
                      disabled={!canEdit || busy}
                      onChange={(event) => setEventTrigger(event.target.value)}
                      data-testid="task-prompt-trigger"
                    >
                      {triggerOptions.map((trigger) => (
                        <option key={trigger} value={trigger}>
                          {trigger}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <label>
                  Текст промпта
                  <textarea
                    rows={7}
                    value={body}
                    disabled={!canEdit || busy}
                    onChange={(event) => setBody(event.target.value)}
                    data-testid="task-prompt-body"
                  />
                </label>
              </div>

              <div className="asst-admin-preview asst-admin-task-skills__preview">
                <header>
                  <strong>Preview · тест</strong>
                </header>
                <Card>
                  <p>{body || '—'}</p>
                </Card>
                <Button type="button" disabled>
                  Запустить тест на событии
                </Button>
                <p className="asst-admin-note">
                  Переменные {'{{kb}}'}, {'{{user}}'}, {'{{dept}}'} подставляются при test-run
                  на выбранном событии.
                </p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export function CapabilitiesScreen({ canEdit = true }: CapabilitiesScreenProps) {
  const [items, setItems] = useState<AssistantCapability[]>([])
  const [busyCode, setBusyCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async (forceRelogin = false) => {
    setLoading(true)
    setError('')
    try {
      if (forceRelogin) resetDevSessionCache()
      let ok = await ensureDevSession()
      if (!ok) {
        resetDevSessionCache()
        ok = await ensureDevSession()
      }
      if (!ok) {
        setItems([])
        setError(formatAdminError(
          new Error('authentication_required'),
          'Нет сессии',
        ))
        return
      }
      setItems(await listAssistantCapabilities())
    } catch (err) {
      setItems([])
      setError(formatAdminError(err, 'Ошибка загрузки'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh(false)
  }, [refresh])

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
      if (isAuthErrorMessage(err instanceof Error ? err.message : '')) {
        resetDevSessionCache()
        try {
          const updated = await setCapabilityEnabled(item.code, !item.enabled)
          setItems((current) =>
            current.map((row) => (row.code === updated.code ? updated : row)),
          )
          return
        } catch (retryErr) {
          setError(formatAdminError(retryErr, 'Ошибка сохранения'))
          return
        }
      }
      setError(formatAdminError(err, 'Ошибка сохранения'))
    } finally {
      setBusyCode('')
    }
  }

  return (
    <section className="asst-admin-caps" data-testid="capabilities-screen">
      <p className="asst-admin-note">
        Навыки и инструменты ассистента · отдельно от skill-групп чата.
        Выключенный capability не показывается в панели ассистента.
      </p>

      {error && (
        <Card className="kb-admin__error" role="alert">
          <div className="kb-admin__error-main">
            <strong>Уведомление</strong>
            <span>{error}</span>
          </div>
          <div className="kb-admin__error-actions">
            <Button type="button" variant="ghost" onClick={() => void refresh(true)}>
              Обновить
            </Button>
            <Button type="button" variant="ghost" onClick={() => setError('')}>
              Скрыть
            </Button>
          </div>
        </Card>
      )}

      {loading ? (
        <Card className="kb-admin-loading">Загрузка навыков…</Card>
      ) : (
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
                {item.deep_link && item.deep_link !== 'capabilities' && (
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => openAdminScreen(item.deep_link)}
                  >
                    Настроить →
                  </Button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      <div className="asst-admin-task-skills__section">
        <h2>Навыки · промпты типа Task</h2>
        <p className="asst-admin-note">
          Capabilities с текстовыми инструкциями. Остальные — deep link на детальные экраны.
        </p>
        <SkillTaskPromptsPanel canEdit={canEdit} />
      </div>
    </section>
  )
}
