import { useCallback, useEffect, useRef, useState, type DragEvent, type FormEvent } from 'react'
import {
  ensureDevSession,
  isAuthErrorMessage,
  resetDevSessionCache,
} from '../../auth/ensureDevSession'
import { Button, Card, StatusBadge } from '../../components'
import {
  createAssistantKb,
  deleteAssistantKb,
  deleteAssistantKbDocument,
  getAssistantKb,
  listAssistantKbs,
  reindexAssistantKb,
  uploadAssistantKbDocument,
  type AssistantKb,
  type AssistantKbDocument,
} from './api/assistantAdmin'
import {
  deleteKnowledgeBase,
  deleteKnowledgeDocument,
  getKnowledgeBase,
  KnowledgeBaseApiError,
  listKnowledgeBases,
  reindexKnowledgeBase,
  uploadKnowledgeDocument,
  type KnowledgeBase,
  type KnowledgeBaseDocument,
  type KnowledgeBaseStatus,
  type WebhookStatus,
} from './api/kbAdmin'

interface KbAdminScreenProps {
  canEdit?: boolean
}

type KbKind = 'cc' | 'assistant'
type UnifiedKey = `${KbKind}:${number}`

interface UnifiedDocument {
  id: number
  filename: string
  size_bytes: number
  status: string
  index_percent: number
  source_label: string
  readonly?: boolean
}

interface UnifiedKb {
  key: UnifiedKey
  kind: KbKind
  id: number
  name: string
  description: string
  source: string
  source_label: string
  module_label: string
  status: KnowledgeBaseStatus | string
  status_message: string
  document_count: number
  index_percent: number
  webhook_status: WebhookStatus | string
  webhook_label: string
  readonly?: boolean
  documents?: UnifiedDocument[]
}

function statusBadge(status: string): 'success' | 'warning' | 'danger' | 'info' | 'neutral' {
  if (status === 'ready') return 'success'
  if (status === 'indexing') return 'info'
  if (status === 'error') return 'danger'
  if (status === 'idle') return 'warning'
  return 'neutral'
}

function statusLabel(status: string): string {
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

function webhookBadge(status: string): 'success' | 'warning' | 'danger' | 'neutral' {
  if (status === 'OK') return 'success'
  if (status === 'ERROR') return 'danger'
  return 'neutral'
}

function sourceBadge(source: string): 'info' | 'neutral' {
  return source === 'suz_bitrix' ? 'info' : 'neutral'
}

function docPercent(status: string, explicit?: number): number {
  if (typeof explicit === 'number') return explicit
  return status === 'indexed' ? 100 : 0
}

function indexFromDocs(docs: { status: string; index_percent?: number }[], fallbackStatus: string, docCount: number): number {
  if (docs.length) {
    const total = docs.reduce((sum, doc) => sum + docPercent(doc.status, doc.index_percent), 0)
    return Math.round(total / docs.length)
  }
  if (fallbackStatus === 'ready' && docCount > 0) return 100
  if (fallbackStatus === 'indexing') return 0
  return 0
}

function fromCcKb(kb: KnowledgeBase): UnifiedKb {
  const documents = (kb.documents ?? []).map((doc: KnowledgeBaseDocument) => ({
    id: doc.id,
    filename: doc.filename,
    size_bytes: doc.size_bytes,
    status: doc.status,
    index_percent: docPercent(doc.status, doc.index_percent),
    source_label: doc.source_label || kb.source_label || 'Ручная загрузка',
    readonly: doc.readonly || kb.source === 'suz_bitrix',
  }))
  const isSuz = kb.source === 'suz_bitrix'
  return {
    key: `cc:${kb.id}`,
    kind: 'cc',
    id: kb.id,
    name: kb.name,
    description: kb.description,
    source: kb.source,
    source_label: kb.source_label || (isSuz ? 'СУЗ Битрикс' : 'Ручная загрузка'),
    module_label: isSuz ? 'СУЗ' : 'КЦ',
    status: kb.status,
    status_message: kb.status_message || '',
    document_count: kb.document_count,
    index_percent: typeof kb.index_percent === 'number'
      ? kb.index_percent
      : indexFromDocs(documents, kb.status, kb.document_count),
    webhook_status: kb.webhook_status || 'IDLE',
    webhook_label: kb.webhook_label || '—',
    readonly: Boolean(kb.readonly || isSuz),
    documents: kb.documents ? documents : undefined,
  }
}

function fromAssistantKb(kb: AssistantKb): UnifiedKb {
  const documents = (kb.documents ?? []).map((doc: AssistantKbDocument) => ({
    id: doc.id,
    filename: doc.filename,
    size_bytes: doc.size_bytes,
    status: doc.status,
    index_percent: docPercent(doc.status),
    source_label: 'Ручная загрузка',
    readonly: false,
  }))
  return {
    key: `assistant:${kb.id}`,
    kind: 'assistant',
    id: kb.id,
    name: kb.name,
    description: kb.description || '',
    source: 'manual',
    source_label: 'Ручная загрузка',
    module_label: 'Ассистент',
    status: kb.status,
    status_message: kb.status_message || '',
    document_count: kb.document_count,
    index_percent: indexFromDocs(documents, String(kb.status), kb.document_count),
    webhook_status: 'IDLE',
    webhook_label: '—',
    readonly: false,
    documents: kb.documents ? documents : undefined,
  }
}

function formatKbError(error: unknown, fallback: string): string {
  if (error instanceof KnowledgeBaseApiError) {
    if (error.message === 'authentication_required') {
      return 'Нет сессии Django. Нажмите «Повторить» — в DEV выполнится вход как dev-role-01.'
    }
    if (error.message === 'csrf_failed') {
      return 'Сбой CSRF-токена после входа. Нажмите «Повторить».'
    }
    if (error.message === 'permission_denied') {
      return 'Недостаточно прав для этой операции.'
    }
    return error.message
  }
  if (error instanceof Error && error.message) return error.message
  return fallback
}

function makeKey(kind: KbKind, id: number): UnifiedKey {
  return `${kind}:${id}`
}

export function KbAdminScreen({ canEdit = true }: KbAdminScreenProps) {
  const [items, setItems] = useState<UnifiedKb[]>([])
  const [selectedKey, setSelectedKey] = useState<UnifiedKey | null>(null)
  const [selected, setSelected] = useState<UnifiedKb | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const selectedKeyRef = useRef<UnifiedKey | null>(null)

  useEffect(() => {
    selectedKeyRef.current = selectedKey
  }, [selectedKey])

  const loadDetail = useCallback(async (key: UnifiedKey): Promise<UnifiedKb> => {
    const [kind, rawId] = key.split(':') as [KbKind, string]
    const id = Number(rawId)
    if (kind === 'assistant') {
      return fromAssistantKb(await getAssistantKb(id))
    }
    return fromCcKb(await getKnowledgeBase(id))
  }, [])

  const refreshList = useCallback(async (preferKey?: UnifiedKey | null) => {
    const [ccItems, assistantItems] = await Promise.all([
      listKnowledgeBases(),
      listAssistantKbs(),
    ])
    const next = [
      ...assistantItems.map(fromAssistantKb),
      ...ccItems.map(fromCcKb),
    ].sort((a, b) => a.name.localeCompare(b.name, 'ru'))
    setItems(next)
    const targetKey = preferKey ?? selectedKeyRef.current ?? next[0]?.key ?? null
    setSelectedKey(targetKey)
    if (targetKey == null) {
      setSelected(null)
      return null
    }
    const detail = await loadDetail(targetKey)
    setSelected(detail)
    setItems((current) =>
      current.map((item) => (item.key === detail.key
        ? {
            ...item,
            status: detail.status,
            status_message: detail.status_message,
            document_count: detail.document_count,
            index_percent: detail.index_percent,
            source_label: detail.source_label,
            webhook_status: detail.webhook_status,
            webhook_label: detail.webhook_label,
          }
        : item)),
    )
    return detail
  }, [loadDetail])

  const loadInitial = useCallback(async (forceRelogin = false) => {
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
        setError(
          'Нет сессии Django. Проверьте, что API на :8001 запущен и VITE_DEV_AUTH_PASSWORD совпадает с AUTH_MOCK_LDAP_DEFAULT_PASSWORD из infra/.env.',
        )
        setItems([])
        setSelected(null)
        return
      }
      await refreshList()
    } catch (requestError) {
      setError(formatKbError(requestError, 'Не удалось загрузить базы знаний'))
      setItems([])
      setSelected(null)
    } finally {
      setLoading(false)
    }
  }, [refreshList])

  useEffect(() => {
    void loadInitial(false)
  }, [loadInitial])

  useEffect(() => {
    if (!selected || selected.status !== 'indexing') return
    const timer = window.setInterval(() => {
      void (async () => {
        try {
          const detail = await loadDetail(selected.key)
          setSelected(detail)
          setItems((current) =>
            current.map((item) =>
              item.key === detail.key
                ? {
                    ...item,
                    status: detail.status,
                    status_message: detail.status_message,
                    document_count: detail.document_count,
                    index_percent: detail.index_percent,
                  }
                : item,
            ),
          )
          if (detail.status === 'ready') {
            setNotice('Индексация завершена. Документы доступны для поиска.')
          }
        } catch {
          /* keep polling */
        }
      })()
    }, 1500)
    return () => window.clearInterval(timer)
  }, [selected, loadDetail])

  const runKbAction = async (
    action: () => Promise<void>,
    fallback: string,
  ) => {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await action()
    } catch (requestError) {
      const message = formatKbError(requestError, fallback)
      const raw = requestError instanceof Error ? requestError.message : ''
      if (isAuthErrorMessage(message) || isAuthErrorMessage(raw)) {
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

  const selectKb = async (key: UnifiedKey) => {
    setSelectedKey(key)
    setNotice('')
    await runKbAction(async () => {
      setSelected(await loadDetail(key))
    }, 'Не удалось открыть базу знаний')
  }

  const createKb = async (event: FormEvent) => {
    event.preventDefault()
    if (!canEdit || !name.trim() || busy) return
    const nextName = name.trim()
    const nextDescription = description.trim()
    await runKbAction(async () => {
      const created = await createAssistantKb({
        name: nextName,
        description: nextDescription,
      })
      setName('')
      setDescription('')
      setShowCreate(false)
      await refreshList(makeKey('assistant', created.id))
      setNotice(`БЗ «${created.name}» создана (появится в чате).`)
    }, 'Не удалось создать базу знаний')
  }

  const uploadFiles = async (files: FileList | File[] | null | undefined) => {
    if (!canEdit || !selected || selected.readonly || busy) return
    const list = files ? [...files] : []
    if (!list.length) return
    const current = selected
    await runKbAction(async () => {
      if (current.kind === 'assistant') {
        for (let index = 0; index < list.length; index += 1) {
          await uploadAssistantKbDocument(current.id, list[index], { reindex: false })
        }
        const indexed = await reindexAssistantKb(current.id)
        setSelected(fromAssistantKb(indexed))
      } else {
        let last = current
        for (const file of list) {
          const result = await uploadKnowledgeDocument(current.id, file)
          last = fromCcKb(result.knowledge_base)
        }
        setSelected(last)
      }
      await refreshList(current.key)
      setNotice(
        list.length === 1
          ? `Файл «${list[0].name}» загружен. Индексация выполняется автоматически.`
          : `Загружено файлов: ${list.length}. Индексация выполняется автоматически.`,
      )
    }, 'Не удалось загрузить документ')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const onReindex = async () => {
    if (!canEdit || !selected || selected.readonly || busy) return
    const current = selected
    await runKbAction(async () => {
      if (current.kind === 'assistant') {
        setSelected(fromAssistantKb(await reindexAssistantKb(current.id)))
      } else {
        setSelected(fromCcKb(await reindexKnowledgeBase(current.id)))
      }
      await refreshList(current.key)
      setNotice('Переиндексация запущена. Дождитесь статуса «Индекс актуален».')
    }, 'Не удалось выполнить переиндексацию')
  }

  const onDeleteKb = async () => {
    if (!canEdit || !selected || selected.readonly || busy) return
    const current = selected
    await runKbAction(async () => {
      if (current.kind === 'assistant') {
        await deleteAssistantKb(current.id)
      } else {
        await deleteKnowledgeBase(current.id)
      }
      await refreshList()
      setNotice('База знаний удалена.')
    }, 'Не удалось удалить базу знаний')
  }

  const onDeleteDocument = async (documentId: number) => {
    if (!canEdit || !selected || selected.readonly || busy) return
    const current = selected
    await runKbAction(async () => {
      if (current.kind === 'assistant') {
        setSelected(fromAssistantKb(await deleteAssistantKbDocument(current.id, documentId)))
      } else {
        setSelected(fromCcKb(await deleteKnowledgeDocument(current.id, documentId)))
      }
      await refreshList(current.key)
    }, 'Не удалось удалить документ')
  }

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragOver(false)
    void uploadFiles(event.dataTransfer.files)
  }

  if (loading) {
    return <Card className="kb-admin-loading">Загрузка баз знаний…</Card>
  }

  const webhookStatus = selected?.webhook_status ?? 'IDLE'
  const webhookLabel = selected?.webhook_label ?? '—'
  const indexPercent = selected?.index_percent ?? 0
  const isSuz = Boolean(selected?.readonly || selected?.source === 'suz_bitrix')

  return (
    <div className="kb-admin" data-testid="kb-admin-screen">
      {error && (
        <Card className="kb-admin__error" role="alert" data-testid="kb-admin-error">
          <div className="kb-admin__error-main">
            <strong>Уведомление</strong>
            <span>{error}</span>
          </div>
          <div className="kb-admin__error-actions">
            <Button type="button" variant="ghost" onClick={() => void loadInitial(true)}>
              Повторить
            </Button>
            <Button type="button" variant="ghost" onClick={() => setError('')}>
              Скрыть
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
              <h2>Базы знаний</h2>
              <p>Ассистент, КЦ и СУЗ Битрикс — один список</p>
            </div>
            <Button
              type="button"
              variant="ghost"
              disabled={busy || loading}
              onClick={() => void loadInitial(true)}
              data-testid="kb-refresh-list"
            >
              Обновить
            </Button>
          </header>

          <div className="kb-admin__create-bar">
            <Button
              type="button"
              disabled={!canEdit || busy}
              onClick={() => setShowCreate((value) => !value)}
              data-testid="kb-create-toggle"
            >
              + Создать БЗ
            </Button>
          </div>

          {showCreate && (
            <form className="kb-admin__create" onSubmit={(event) => void createKb(event)}>
              <label>
                <span>Название</span>
                <input
                  value={name}
                  disabled={!canEdit || busy}
                  placeholder="Например: HR policies"
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
                Создать
              </Button>
            </form>
          )}

          <ul className="kb-admin__kb-list" data-testid="kb-list">
            {items.map((item) => (
              <li key={item.key}>
                <button
                  type="button"
                  className={item.key === selectedKey ? 'is-active' : undefined}
                  onClick={() => void selectKb(item.key)}
                  data-testid={`kb-item-${item.key}`}
                >
                  <span className="kb-admin__kb-meta">
                    <strong>{item.name}</strong>
                    <span className="kb-admin__kb-tags">
                      <StatusBadge status="neutral">{item.module_label}</StatusBadge>
                      <StatusBadge status={sourceBadge(item.source)}>
                        {item.source_label}
                      </StatusBadge>
                    </span>
                  </span>
                  <StatusBadge status={statusBadge(String(item.status))}>
                    {`${item.index_percent}%`}
                  </StatusBadge>
                </button>
              </li>
            ))}
            {!items.length && (
              <li className="kb-admin__empty">
                <p>Список пуст или не загрузился с сервера.</p>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={busy || loading}
                  onClick={() => void loadInitial(true)}
                >
                  Обновить список
                </Button>
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
                    {selected.description
                      || (isSuz
                        ? 'Статьи из интеграции СУЗ Битрикс (webhook).'
                        : selected.kind === 'assistant'
                          ? 'Документы для ИИ-чата ассистента.'
                          : 'Документы для индекса суфлёра КЦ.')}
                  </p>
                </div>
                <span className="kb-admin__kb-tags">
                  <StatusBadge status="neutral">{selected.module_label}</StatusBadge>
                  <StatusBadge status={sourceBadge(selected.source)}>
                    {selected.source_label}
                  </StatusBadge>
                </span>
              </header>

              <section className="kb-admin__detail-stats admin-stats" aria-label="Статус выбранной БЗ">
                <Card>
                  <span>Индекс</span>
                  <strong data-testid="kb-stat-index">{indexPercent}%</strong>
                  <small>{statusLabel(String(selected.status))}</small>
                </Card>
                <Card>
                  <span>Документов</span>
                  <strong data-testid="kb-stat-docs">{selected.document_count}</strong>
                  <small>В выбранной БЗ</small>
                </Card>
                <Card>
                  <span>Webhook СУЗ</span>
                  <strong data-testid="kb-stat-webhook">
                    <StatusBadge status={webhookBadge(String(webhookStatus))}>
                      {webhookLabel}
                    </StatusBadge>
                  </strong>
                  <small>{isSuz ? 'Интеграция Битрикс' : 'для СУЗ-БЗ'}</small>
                </Card>
              </section>

              {isSuz ? (
                <div className="kb-admin__suz-note" data-testid="kb-suz-readonly">
                  <strong>Источник: СУЗ Битрикс</strong>
                  <p>
                    Документы поступают через webhook. Ручная загрузка недоступна.
                    БЗ ассистента (те, что в выпадашке чата) — в этом же списке слева с меткой «Ассистент».
                  </p>
                </div>
              ) : (
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
                    accept=".pdf,.doc,.docx,.txt,.rtf,.xlsx,.pptx,.png,.jpg,.jpeg"
                    multiple
                    hidden
                    disabled={!canEdit || busy}
                    onChange={(event) => void uploadFiles(event.target.files)}
                    data-testid="kb-upload-input"
                  />
                  <strong>Ручная загрузка документов</strong>
                  <p>
                    {selected.kind === 'assistant'
                      ? 'Файлы попадут в чат ассистента (выпадающий список БЗ).'
                      : 'Файлы попадут в индекс КЦ / суфлёра.'}
                  </p>
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
              )}

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
                      <th scope="col">Источник</th>
                      <th scope="col">%</th>
                      {!isSuz && <th scope="col">Действия</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {(selected.documents ?? []).map((document) => (
                      <tr key={document.id}>
                        <td>
                          <strong>{document.filename}</strong>
                          {document.size_bytes > 0 && (
                            <small>{Math.round(document.size_bytes / 1024)} КБ</small>
                          )}
                        </td>
                        <td>
                          <StatusBadge status="neutral">{document.source_label}</StatusBadge>
                        </td>
                        <td>{document.index_percent}</td>
                        {!isSuz && (
                          <td>
                            <Button
                              variant="ghost"
                              disabled={!canEdit || busy || document.readonly}
                              onClick={() => void onDeleteDocument(document.id)}
                            >
                              Удалить
                            </Button>
                          </td>
                        )}
                      </tr>
                    ))}
                    {!(selected.documents ?? []).length && (
                      <tr>
                        <td colSpan={isSuz ? 3 : 4} className="kb-admin__empty">
                          {isSuz
                            ? 'Статей из СУЗ пока нет — ожидается webhook Битрикс.'
                            : 'Документов пока нет — загрузите PDF или DOCX в зону выше.'}
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
              <p>Ассистент (чат), КЦ и СУЗ Битрикс — в одном списке.</p>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
