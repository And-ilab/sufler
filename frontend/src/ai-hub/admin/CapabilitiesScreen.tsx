import { useCallback, useEffect, useRef, useState, type DragEvent, type FormEvent } from 'react'
import {
  ensureDevSession,
  isAuthErrorMessage,
  resetDevSessionCache,
} from '../../auth/ensureDevSession'
import { Button, Card, StatusBadge } from '../../components'
import {
  AssistantAdminApiError,
  createAssistantKb,
  deleteAssistantKb,
  deleteAssistantKbDocument,
  getAssistantKb,
  listAssistantCapabilities,
  listAssistantKbs,
  reindexAssistantKb,
  setCapabilityEnabled,
  uploadAssistantKbDocument,
  type AssistantCapability,
  type AssistantKb,
  type AssistantKbStatus,
} from './api/assistantAdmin'
import './AssistantAdminScreens.css'

interface CapabilitiesScreenProps {
  canEdit?: boolean
}

function formatAdminError(error: unknown, fallback: string): string {
  if (error instanceof AssistantAdminApiError) {
    const detail =
      error.details.request?.[0] ||
      error.details.name?.[0] ||
      error.details.slug?.[0] ||
      Object.values(error.details).flat()[0]
    if (detail) return detail
  }
  const message = error instanceof Error ? error.message : ''
  if (message === 'authentication_required') {
    return 'Нет сессии Django. Нажмите «Обновить» — в DEV выполнится вход как dev-role-01 (VITE_DEV_AUTH_PASSWORD = AUTH_MOCK_LDAP_DEFAULT_PASSWORD).'
  }
  if (message === 'csrf_failed') {
    return 'Сбой CSRF после входа. Нажмите «Обновить» — токен обновится автоматически.'
  }
  if (message === 'permission_denied') {
    return 'Недостаточно прав для этой операции.'
  }
  if (message === 'validation_error') {
    return fallback
  }
  if (message && isAuthErrorMessage(message)) {
    return 'Нет сессии Django. Нажмите «Обновить» — в DEV выполнится вход как dev-role-01.'
  }
  return message || fallback
}

function statusBadge(status: AssistantKbStatus | string): 'success' | 'warning' | 'danger' | 'info' | 'neutral' {
  if (status === 'ready') return 'success'
  if (status === 'indexing') return 'info'
  if (status === 'error') return 'danger'
  if (status === 'idle') return 'warning'
  return 'neutral'
}

function statusLabel(status: AssistantKbStatus | string): string {
  switch (status) {
    case 'ready':
      return 'Индекс актуален'
    case 'indexing':
      return 'Индексация…'
    case 'error':
      return 'Ошибка индекса'
    default:
      return 'Ожидает индексации'
  }
}

function documentStatusLabel(status: string): string {
  if (status === 'indexed') return 'проиндексирован'
  if (status === 'error') return 'ошибка'
  if (status === 'uploaded') return 'загружен'
  return status
}

export function CapabilitiesScreen({ canEdit = true }: CapabilitiesScreenProps) {
  const [items, setItems] = useState<AssistantCapability[]>([])
  const [kbs, setKbs] = useState<AssistantKb[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [selected, setSelected] = useState<AssistantKb | null>(null)
  const [busyCode, setBusyCode] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [kbName, setKbName] = useState('')
  const [kbDescription, setKbDescription] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const selectedIdRef = useRef<number | null>(null)

  useEffect(() => {
    selectedIdRef.current = selectedId
  }, [selectedId])

  const refreshKbList = useCallback(async (preferId?: number | null) => {
    const next = await listAssistantKbs()
    setKbs(next)
    const targetId = preferId ?? selectedIdRef.current ?? next[0]?.id ?? null
    setSelectedId(targetId)
    if (targetId == null) {
      setSelected(null)
      return null
    }
    const detail = await getAssistantKb(targetId)
    setSelected(detail)
    return detail
  }, [])

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
        setKbs([])
        setSelected(null)
        setError(formatAdminError(
          new Error('authentication_required'),
          'Нет сессии',
        ))
        return
      }
      const caps = await listAssistantCapabilities()
      setItems(caps)
      await refreshKbList()
    } catch (err) {
      setItems([])
      setKbs([])
      setSelected(null)
      setError(formatAdminError(err, 'Ошибка загрузки'))
    } finally {
      setLoading(false)
    }
  }, [refreshKbList])

  useEffect(() => {
    void refresh(false)
  }, [refresh])

  useEffect(() => {
    if (!selected || selected.status !== 'indexing') return
    const timer = window.setInterval(() => {
      void refreshKbList(selected.id)
    }, 2000)
    return () => window.clearInterval(timer)
  }, [selected, refreshKbList])

  const runKbAction = async (action: () => Promise<void>, fallback: string) => {
    if (busy) return
    setBusy(true)
    setError('')
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

  const selectKb = async (id: number) => {
    setSelectedId(id)
    setError('')
    try {
      const detail = await getAssistantKb(id)
      setSelected(detail)
    } catch (err) {
      setError(formatAdminError(err, 'Не удалось открыть базу знаний'))
    }
  }

  const createKb = async (event: FormEvent) => {
    event.preventDefault()
    if (!canEdit || !kbName.trim() || busy) return
    await runKbAction(async () => {
      const created = await createAssistantKb({
        name: kbName.trim(),
        description: kbDescription.trim(),
      })
      setKbName('')
      setKbDescription('')
      await refreshKbList(created.id)
      setNotice(`БЗ «${created.name}» создана. Загрузите документы справа.`)
    }, 'Не удалось создать базу знаний')
  }

  const uploadFiles = async (files: FileList | File[] | null | undefined) => {
    if (!canEdit || !selected || busy) return
    // Snapshot immediately — FileList is live and clears with the input.
    const list = files ? Array.from(files) : []
    if (!list.length) return
    const kbId = selected.id
    if (fileInputRef.current) fileInputRef.current.value = ''
    await runKbAction(async () => {
      let last = selected
      for (let index = 0; index < list.length; index += 1) {
        setNotice(`Загрузка файлов: ${index + 1} / ${list.length}…`)
        const result = await uploadAssistantKbDocument(kbId, list[index], {
          reindex: false,
        })
        last = result.knowledge_base
        setSelected(last)
      }
      setNotice(
        list.length === 1
          ? `Файл «${list[0].name}» загружен. Индексация…`
          : `Загружено файлов: ${list.length}. Индексация…`,
      )
      const indexed = await reindexAssistantKb(kbId)
      setSelected(indexed)
      await refreshKbList(kbId)
      setNotice(
        list.length === 1
          ? `Файл «${list[0].name}» загружен и проиндексирован.`
          : `Загружено и проиндексировано файлов: ${list.length}.`,
      )
    }, 'Не удалось загрузить документ')
  }

  const onReindex = async () => {
    if (!canEdit || !selected || busy) return
    const kbId = selected.id
    await runKbAction(async () => {
      const updated = await reindexAssistantKb(kbId)
      setSelected(updated)
      await refreshKbList(kbId)
      setNotice('Переиндексация запущена. Дождитесь статуса «Индекс актуален».')
    }, 'Не удалось выполнить переиндексацию')
  }

  const onDeleteKb = async () => {
    if (!canEdit || !selected || busy) return
    await runKbAction(async () => {
      await deleteAssistantKb(selected.id)
      await refreshKbList()
      setNotice('База знаний удалена.')
    }, 'Не удалось удалить базу знаний')
  }

  const onDeleteDocument = async (documentId: number) => {
    if (!canEdit || !selected || busy) return
    const kbId = selected.id
    await runKbAction(async () => {
      const updated = await deleteAssistantKbDocument(kbId, documentId)
      setSelected(updated)
      await refreshKbList(kbId)
    }, 'Не удалось удалить документ')
  }

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragOver(false)
    void uploadFiles(event.dataTransfer.files)
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

      <div className="kb-admin asst-admin-kb-block" data-testid="assistant-kb-panel">
        <section className="admin-stats" aria-label="Сводка баз знаний ассистента">
          <Card>
            <span>Базы знаний</span>
            <strong>{kbs.length}</strong>
            <small>assistant_*</small>
          </Card>
          <Card>
            <span>Документы</span>
            <strong>{selected?.document_count ?? 0}</strong>
            <small>В выбранной БЗ</small>
          </Card>
          <Card>
            <span>Чанки индекса</span>
            <strong>{selected?.chunk_count ?? 0}</strong>
            <small>не cc_production</small>
          </Card>
        </section>

        <ol className="kb-admin__flow" aria-label="Сценарий работы с БЗ ассистента">
          <li className={kbs.length ? 'is-done' : 'is-current'}>1. Создать БЗ</li>
          <li className={selected ? 'is-done' : kbs.length ? 'is-current' : ''}>2. Выбрать в списке</li>
          <li className={selected && (selected.document_count ?? 0) > 0 ? 'is-done' : selected ? 'is-current' : ''}>
            3. Загрузить файлы
          </li>
          <li className={selected?.status === 'ready' ? 'is-done' : selected?.status === 'indexing' ? 'is-current' : ''}>
            4. Дождаться индексации
          </li>
        </ol>

        {error && (
          <Card className="kb-admin__error" role="alert" data-testid="asst-kb-error">
            <div className="kb-admin__error-main">
              <strong>Уведомление</strong>
              <span>{error}</span>
            </div>
            <div className="kb-admin__error-actions">
              <Button type="button" variant="ghost" onClick={() => void refresh(true)}>
                Повторить
              </Button>
              <Button type="button" variant="ghost" onClick={() => setError('')}>
                Скрыть
              </Button>
            </div>
          </Card>
        )}

        {notice && !error && (
          <Card className="kb-admin__notice" role="status" data-testid="asst-kb-notice">
            <span>{notice}</span>
            <Button type="button" variant="ghost" onClick={() => setNotice('')}>
              Закрыть
            </Button>
          </Card>
        )}

        {loading ? (
          <Card className="kb-admin-loading">Загрузка баз знаний ассистента…</Card>
        ) : (
          <div className="kb-admin__layout">
            <Card className="kb-admin__list">
              <header>
                <div>
                  <h2>Базы знаний assistant_*</h2>
                  <p>Документы для ИИ-чата, изолированы от индекса КЦ</p>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  disabled={busy || loading}
                  onClick={() => void refresh(true)}
                  data-testid="asst-kb-refresh"
                >
                  Обновить список
                </Button>
              </header>
              <form className="kb-admin__create" onSubmit={(event) => void createKb(event)}>
                <label>
                  <span>Название</span>
                  <input
                    value={kbName}
                    disabled={!canEdit || busy}
                    placeholder="Например: Регламенты HR"
                    onChange={(event) => setKbName(event.target.value)}
                    data-testid="asst-kb-name"
                  />
                </label>
                <label>
                  <span>Описание</span>
                  <input
                    value={kbDescription}
                    disabled={!canEdit || busy}
                    placeholder="Краткое описание"
                    onChange={(event) => setKbDescription(event.target.value)}
                  />
                </label>
                <Button
                  type="submit"
                  disabled={!canEdit || busy || !kbName.trim()}
                  data-testid="asst-kb-create"
                >
                  + Создать БЗ
                </Button>
              </form>
              <ul className="kb-admin__kb-list" data-testid="asst-kb-list">
                {kbs.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      className={item.id === selectedId ? 'is-active' : undefined}
                      onClick={() => void selectKb(item.id)}
                      data-testid={`asst-kb-${item.slug}`}
                    >
                      <strong>{item.name}</strong>
                      <StatusBadge status={statusBadge(item.status)}>
                        {statusLabel(item.status)}
                      </StatusBadge>
                    </button>
                  </li>
                ))}
                {!kbs.length && (
                  <li className="kb-admin__empty">
                    <p>Список пуст. Создайте БЗ — она появится в выпадашке ИИ-чата.</p>
                  </li>
                )}
              </ul>
            </Card>

            <Card className="kb-admin__detail">
              {selected ? (
                <>
                  <header>
                    <div>
                      <h2>{selected.name}</h2>
                      <p>
                        {selected.description || 'Документы для индекса ИИ-ассистента.'}
                        {' '}
                        <code>{selected.slug}</code>
                      </p>
                    </div>
                    <StatusBadge status={statusBadge(selected.status)}>
                      {statusLabel(selected.status)}
                    </StatusBadge>
                  </header>

                  <div
                    className={`kb-admin__dropzone${dragOver ? ' is-dragover' : ''}`}
                    data-testid="asst-kb-upload-zone"
                    onDragEnter={(event) => {
                      event.preventDefault()
                      setDragOver(true)
                    }}
                    onDragOver={(event) => {
                      event.preventDefault()
                      setDragOver(true)
                    }}
                    onDragLeave={(event) => {
                      event.preventDefault()
                      setDragOver(false)
                    }}
                    onDrop={onDrop}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".pdf,.doc,.docx,.txt,.rtf,.xlsx,.pptx,.png,.jpg,.jpeg"
                      multiple
                      hidden
                      disabled={!canEdit || busy}
                      onChange={(event) => void uploadFiles(event.target.files)}
                      data-testid="asst-kb-upload-input"
                    />
                    <strong>Ручная загрузка документов</strong>
                    <p>Перетащите PDF/DOCX сюда или выберите файлы. Индексация запустится автоматически.</p>
                    <div className="kb-admin__actions">
                      <div>
                        <Button
                          disabled={!canEdit || busy}
                          onClick={() => fileInputRef.current?.click()}
                          data-testid="asst-kb-upload-button"
                        >
                          Загрузить файлы
                        </Button>
                        <Button
                          variant="secondary"
                          disabled={!canEdit || busy || !(selected.documents ?? []).length}
                          onClick={() => void onReindex()}
                          data-testid="asst-kb-reindex-button"
                        >
                          Переиндексировать
                        </Button>
                      </div>
                      <Button
                        variant="ghost"
                        disabled={!canEdit || busy}
                        onClick={() => void onDeleteKb()}
                      >
                        Удалить БЗ
                      </Button>
                    </div>
                  </div>

                  {selected.status === 'indexing' && (
                    <p className="kb-admin__status-msg kb-admin__status-msg--indexing" data-testid="asst-kb-indexing">
                      Индексация выполняется… страница обновляется автоматически.
                    </p>
                  )}
                  {selected.status_message && selected.status !== 'indexing' && (
                    <p className="kb-admin__status-msg">{selected.status_message}</p>
                  )}

                  <div className="kb-admin__table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th scope="col">Документ</th>
                          <th scope="col">Статус</th>
                          <th scope="col">Чанки</th>
                          <th scope="col">Действия</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(selected.documents ?? []).map((document) => (
                          <tr key={document.id}>
                            <td>
                              <strong>{document.filename}</strong>
                              <small>{Math.round(document.size_bytes / 1024)} КБ</small>
                            </td>
                            <td>
                              <StatusBadge
                                status={
                                  document.status === 'indexed'
                                    ? 'success'
                                    : document.status === 'error'
                                      ? 'danger'
                                      : 'warning'
                                }
                              >
                                {documentStatusLabel(document.status)}
                              </StatusBadge>
                            </td>
                            <td>{document.chunk_count}</td>
                            <td>
                              <Button
                                variant="ghost"
                                disabled={!canEdit || busy}
                                onClick={() => void onDeleteDocument(document.id)}
                              >
                                Удалить
                              </Button>
                            </td>
                          </tr>
                        ))}
                        {!(selected.documents ?? []).length && (
                          <tr>
                            <td colSpan={4} className="kb-admin__empty">
                              Документов пока нет — загрузите PDF или DOCX в зону выше.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : (
                <div className="kb-admin__empty-detail">
                  <h2>Выберите или создайте базу знаний</h2>
                  <p>Управление документами ИИ-чата</p>
                  <ol>
                    <li>Создайте БЗ в форме слева</li>
                    <li>Выберите её в списке</li>
                    <li>Загрузите файлы (pdf/docx)</li>
                    <li>Дождитесь статуса «Индекс актуален»</li>
                  </ol>
                </div>
              )}
            </Card>
          </div>
        )}
      </div>
    </section>
  )
}
