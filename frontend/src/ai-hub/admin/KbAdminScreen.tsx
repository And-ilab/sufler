import { useCallback, useEffect, useRef, useState, type DragEvent, type FormEvent } from 'react'
import {
  ensureDevSession,
  isAuthErrorMessage,
  resetDevSessionCache,
} from '../../auth/ensureDevSession'
import { Button, Card, StatusBadge } from '../../components'
import {
  createKnowledgeBase,
  deleteKnowledgeBase,
  deleteKnowledgeDocument,
  getKnowledgeBase,
  KnowledgeBaseApiError,
  listKnowledgeBases,
  reindexKnowledgeBase,
  uploadKnowledgeDocument,
  type KnowledgeBase,
  type KnowledgeBaseStatus,
} from './api/kbAdmin'

interface KbAdminScreenProps {
  canEdit?: boolean
}

function statusBadge(status: KnowledgeBaseStatus): 'success' | 'warning' | 'danger' | 'info' | 'neutral' {
  if (status === 'ready') return 'success'
  if (status === 'indexing') return 'info'
  if (status === 'error') return 'danger'
  if (status === 'idle') return 'warning'
  return 'neutral'
}

function statusLabel(status: KnowledgeBaseStatus): string {
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

function formatKbError(error: unknown, fallback: string): string {
  if (error instanceof KnowledgeBaseApiError) {
    if (error.message === 'authentication_required') {
      return 'Нет сессии авторизации. Нажмите «Повторить» — будет выполнен вход и обновление списка.'
    }
    if (error.message === 'permission_denied') {
      return 'Недостаточно прав (kb.admin) для этой операции.'
    }
    return error.message
  }
  if (error instanceof Error && error.message) return error.message
  return fallback
}

function documentStatusLabel(status: string): string {
  if (status === 'indexed') return 'проиндексирован'
  if (status === 'error') return 'ошибка'
  if (status === 'uploaded') return 'загружен'
  return status
}

export function KbAdminScreen({ canEdit = true }: KbAdminScreenProps) {
  const [items, setItems] = useState<KnowledgeBase[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [selected, setSelected] = useState<KnowledgeBase | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const selectedIdRef = useRef<number | null>(null)

  useEffect(() => {
    selectedIdRef.current = selectedId
  }, [selectedId])

  const refreshList = useCallback(async (preferId?: number | null) => {
    await ensureDevSession()
    const next = await listKnowledgeBases()
    setItems(next)
    const targetId = preferId !== undefined
      ? preferId
      : selectedIdRef.current ?? next[0]?.id ?? null
    setSelectedId(targetId)
    if (targetId == null) {
      setSelected(null)
      return null
    }
    const detail = await getKnowledgeBase(targetId)
    setSelected(detail)
    return detail
  }, [])

  const loadInitial = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      resetDevSessionCache()
      const ok = await ensureDevSession()
      if (!ok) {
        setError(
          'Нет сессии авторизации. В DEV выполняется вход как dev-role-01; проверьте, что API доступен.',
        )
        setItems([])
        setSelected(null)
        return
      }
      await refreshList(null)
    } catch (requestError) {
      setError(formatKbError(requestError, 'Не удалось загрузить базы знаний'))
    } finally {
      setLoading(false)
    }
  }, [refreshList])

  useEffect(() => {
    void loadInitial()
  }, [loadInitial])

  // Poll while selected KB is indexing.
  useEffect(() => {
    if (!selected || selected.status !== 'indexing') return
    const timer = window.setInterval(() => {
      void (async () => {
        try {
          const detail = await getKnowledgeBase(selected.id)
          setSelected(detail)
          setItems((current) =>
            current.map((item) =>
              item.id === detail.id
                ? {
                    ...item,
                    status: detail.status,
                    status_message: detail.status_message,
                    document_count: detail.document_count,
                    chunk_count: detail.chunk_count,
                  }
                : item,
            ),
          )
          if (detail.status === 'ready') {
            setNotice('Индексация завершена. Документы доступны для поиска.')
          }
        } catch {
          /* keep polling until next success or status change */
        }
      })()
    }, 1500)
    return () => window.clearInterval(timer)
  }, [selected])

  const runKbAction = async (
    action: () => Promise<void>,
    fallback: string,
  ) => {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await ensureDevSession()
      await action()
    } catch (requestError) {
      const message = formatKbError(requestError, fallback)
      if (isAuthErrorMessage(message)) {
        resetDevSessionCache()
        const ok = await ensureDevSession()
        if (ok) {
          try {
            await action()
            return
          } catch (retryError) {
            setError(formatKbError(retryError, fallback))
            return
          }
        }
      }
      setError(message)
    } finally {
      setBusy(false)
    }
  }

  const selectKb = async (id: number) => {
    setSelectedId(id)
    setNotice('')
    await runKbAction(async () => {
      setSelected(await getKnowledgeBase(id))
    }, 'Не удалось открыть базу знаний')
  }

  const createKb = async (event: FormEvent) => {
    event.preventDefault()
    if (!canEdit || !name.trim() || busy) return
    const nextName = name.trim()
    const nextDescription = description.trim()
    await runKbAction(async () => {
      const created = await createKnowledgeBase({
        name: nextName,
        description: nextDescription,
        scope: 'contact_center',
      })
      setName('')
      setDescription('')
      await refreshList(created.id)
      setNotice(`БЗ «${created.name}» создана. Загрузите документы справа.`)
    }, 'Не удалось создать базу знаний')
  }

  const uploadFiles = async (files: FileList | File[] | null | undefined) => {
    if (!canEdit || !selected || busy) return
    const list = files ? [...files] : []
    if (!list.length) return
    const kbId = selected.id
    await runKbAction(async () => {
      let last = selected
      for (const file of list) {
        const result = await uploadKnowledgeDocument(kbId, file)
        last = result.knowledge_base
      }
      setSelected(last)
      await refreshList(kbId)
      setNotice(
        list.length === 1
          ? `Файл «${list[0].name}» загружен. Индексация выполняется автоматически.`
          : `Загружено файлов: ${list.length}. Индексация выполняется автоматически.`,
      )
    }, 'Не удалось загрузить документ')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const onReindex = async () => {
    if (!canEdit || !selected || busy) return
    const kbId = selected.id
    await runKbAction(async () => {
      const updated = await reindexKnowledgeBase(kbId)
      setSelected(updated)
      await refreshList(kbId)
      setNotice('Переиндексация запущена. Дождитесь статуса «Индекс актуален».')
    }, 'Не удалось выполнить переиндексацию')
  }

  const onDeleteKb = async () => {
    if (!canEdit || !selected || busy) return
    await runKbAction(async () => {
      await deleteKnowledgeBase(selected.id)
      await refreshList(null)
      setNotice('База знаний удалена.')
    }, 'Не удалось удалить базу знаний')
  }

  const onDeleteDocument = async (documentId: number) => {
    if (!canEdit || !selected || busy) return
    const kbId = selected.id
    await runKbAction(async () => {
      const updated = await deleteKnowledgeDocument(kbId, documentId)
      setSelected(updated)
      await refreshList(kbId)
    }, 'Не удалось удалить документ')
  }

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragOver(false)
    void uploadFiles(event.dataTransfer.files)
  }

  if (loading) {
    return <Card className="kb-admin-loading">Загрузка баз знаний КЦ…</Card>
  }

  return (
    <div className="kb-admin" data-testid="kb-admin-screen">
      <section className="admin-stats" aria-label="Сводка баз знаний КЦ">
        <Card>
          <span>Базы знаний</span>
          <strong>{items.length}</strong>
          <small>Создано в Hub</small>
        </Card>
        <Card>
          <span>Документы</span>
          <strong>{selected?.document_count ?? 0}</strong>
          <small>В выбранной БЗ</small>
        </Card>
        <Card>
          <span>Чанки индекса</span>
          <strong>{selected?.chunk_count ?? 0}</strong>
          <small>cc_production</small>
        </Card>
      </section>

      <ol className="kb-admin__flow" aria-label="Сценарий работы с БЗ">
        <li className={items.length ? 'is-done' : 'is-current'}>1. Создать БЗ</li>
        <li className={selected ? 'is-done' : items.length ? 'is-current' : ''}>2. Выбрать в списке</li>
        <li className={selected && (selected.document_count ?? 0) > 0 ? 'is-done' : selected ? 'is-current' : ''}>
          3. Загрузить файлы
        </li>
        <li className={selected?.status === 'ready' ? 'is-done' : selected?.status === 'indexing' ? 'is-current' : ''}>
          4. Дождаться индексации
        </li>
      </ol>

      {error && (
        <Card className="kb-admin__error" role="alert" data-testid="kb-admin-error">
          <div className="kb-admin__error-main">
            <strong>Уведомление</strong>
            <span>{error}</span>
          </div>
          <div className="kb-admin__error-actions">
            <Button type="button" variant="ghost" onClick={() => void loadInitial()}>
              Повторить
            </Button>
            <Button type="button" variant="ghost" onClick={() => setError('')}>
              Закрыть
            </Button>
          </div>
        </Card>
      )}

      {notice && !error && (
        <Card className="kb-admin__notice" role="status" data-testid="kb-admin-notice">
          <span>{notice}</span>
          <Button type="button" variant="ghost" onClick={() => setNotice('')}>
            Закрыть
          </Button>
        </Card>
      )}

      <div className="kb-admin__layout">
        <Card className="kb-admin__list">
          <header>
            <div>
              <h2>Базы знаний КЦ</h2>
              <p>Создание и редактирование статей БЗ</p>
            </div>
          </header>
          <form className="kb-admin__create" onSubmit={(event) => void createKb(event)}>
            <label>
              <span>Название</span>
              <input
                value={name}
                disabled={!canEdit || busy}
                placeholder="Например: Регламенты КЦ"
                onChange={(event) => setName(event.target.value)}
                data-testid="kb-create-name"
              />
            </label>
            <label>
              <span>Описание</span>
              <input
                value={description}
                disabled={!canEdit || busy}
                placeholder="Краткое описание"
                onChange={(event) => setDescription(event.target.value)}
              />
            </label>
            <Button
              type="submit"
              disabled={!canEdit || busy || !name.trim()}
              data-testid="kb-create-submit"
            >
              + Создать БЗ
            </Button>
          </form>
          <ul className="kb-admin__kb-list" data-testid="kb-list">
            {items.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className={item.id === selectedId ? 'is-active' : undefined}
                  onClick={() => void selectKb(item.id)}
                  data-testid={`kb-item-${item.id}`}
                >
                  <strong>{item.name}</strong>
                  <StatusBadge status={statusBadge(item.status)}>
                    {statusLabel(item.status)}
                  </StatusBadge>
                </button>
              </li>
            ))}
            {!items.length && (
              <li className="kb-admin__empty">Пока нет баз знаний. Создайте первую слева.</li>
            )}
          </ul>
        </Card>

        <Card className="kb-admin__detail">
          {selected ? (
            <>
              <header>
                <div>
                  <h2>{selected.name}</h2>
                  <p>{selected.description || 'Документы для индекса суфлёра КЦ.'}</p>
                </div>
                <StatusBadge status={statusBadge(selected.status)}>
                  {statusLabel(selected.status)}
                </StatusBadge>
              </header>

              <div
                className={`kb-admin__dropzone${dragOver ? ' is-dragover' : ''}`}
                data-testid="kb-upload-zone"
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
                  accept=".pdf,.docx,.txt,.rtf,.xlsx,.pptx,.png,.jpg,.jpeg"
                  multiple
                  hidden
                  disabled={!canEdit || busy}
                  onChange={(event) => void uploadFiles(event.target.files)}
                  data-testid="kb-upload-input"
                />
                <strong>Ручная загрузка документов</strong>
                <p>Перетащите PDF/DOCX сюда или выберите файлы. Индексация запустится автоматически.</p>
                <div className="kb-admin__actions">
                  <div>
                    <Button
                      disabled={!canEdit || busy}
                      onClick={() => fileInputRef.current?.click()}
                      data-testid="kb-upload-button"
                    >
                      Загрузить файлы
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={!canEdit || busy || !(selected.documents ?? []).length}
                      onClick={() => void onReindex()}
                      data-testid="kb-reindex-button"
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
                <p className="kb-admin__status-msg kb-admin__status-msg--indexing" data-testid="kb-indexing">
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
              <p>Управление документами КЦ</p>
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
    </div>
  )
}
