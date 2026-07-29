import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Button, Card, StatusBadge } from '../../components'
import {
  createKnowledgeBase,
  deleteKnowledgeBase,
  deleteKnowledgeDocument,
  getKnowledgeBase,
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

export function KbAdminScreen({ canEdit = true }: KbAdminScreenProps) {
  const [items, setItems] = useState<KnowledgeBase[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [selected, setSelected] = useState<KnowledgeBase | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const refreshList = async (preferId?: number | null) => {
    const next = await listKnowledgeBases()
    setItems(next)
    const targetId = preferId ?? selectedId ?? next[0]?.id ?? null
    setSelectedId(targetId)
    if (targetId == null) {
      setSelected(null)
      return
    }
    setSelected(await getKnowledgeBase(targetId))
  }

  useEffect(() => {
    let cancelled = false
    void (async () => {
      setLoading(true)
      setError('')
      try {
        const next = await listKnowledgeBases()
        if (cancelled) return
        setItems(next)
        const targetId = next[0]?.id ?? null
        setSelectedId(targetId)
        if (targetId == null) {
          setSelected(null)
        } else {
          setSelected(await getKnowledgeBase(targetId))
        }
      } catch (requestError) {
        if (!cancelled) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : 'Не удалось загрузить базы знаний',
          )
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const selectKb = async (id: number) => {
    setSelectedId(id)
    setError('')
    setBusy(true)
    try {
      setSelected(await getKnowledgeBase(id))
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Не удалось открыть базу знаний',
      )
    } finally {
      setBusy(false)
    }
  }

  const createKb = async (event: FormEvent) => {
    event.preventDefault()
    if (!canEdit || !name.trim() || busy) return
    setBusy(true)
    setError('')
    try {
      const created = await createKnowledgeBase({
        name: name.trim(),
        description: description.trim(),
        scope: 'contact_center',
      })
      setName('')
      setDescription('')
      await refreshList(created.id)
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Не удалось создать базу знаний',
      )
    } finally {
      setBusy(false)
    }
  }

  const onUpload = async (file: File | undefined) => {
    if (!canEdit || !selected || !file || busy) return
    setBusy(true)
    setError('')
    try {
      const result = await uploadKnowledgeDocument(selected.id, file)
      setSelected(result.knowledge_base)
      await refreshList(selected.id)
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Не удалось загрузить документ',
      )
    } finally {
      setBusy(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const onReindex = async () => {
    if (!canEdit || !selected || busy) return
    setBusy(true)
    setError('')
    try {
      const updated = await reindexKnowledgeBase(selected.id)
      setSelected(updated)
      await refreshList(selected.id)
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Не удалось выполнить переиндексацию',
      )
    } finally {
      setBusy(false)
    }
  }

  const onDeleteKb = async () => {
    if (!canEdit || !selected || busy) return
    setBusy(true)
    setError('')
    try {
      await deleteKnowledgeBase(selected.id)
      await refreshList(null)
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Не удалось удалить базу знаний',
      )
    } finally {
      setBusy(false)
    }
  }

  const onDeleteDocument = async (documentId: number) => {
    if (!canEdit || !selected || busy) return
    setBusy(true)
    setError('')
    try {
      const updated = await deleteKnowledgeDocument(selected.id, documentId)
      setSelected(updated)
      await refreshList(selected.id)
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Не удалось удалить документ',
      )
    } finally {
      setBusy(false)
    }
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

      {error && (
        <Card className="kb-admin__error" role="alert">
          <strong>Операция недоступна</strong>
          <span>{error}</span>
        </Card>
      )}

      <div className="kb-admin__layout">
        <Card className="kb-admin__list">
          <header>
            <div>
              <h2>Базы знаний КЦ</h2>
              <p>CRUD без программирования · FR-CC-08</p>
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
            <Button type="submit" disabled={!canEdit || busy || !name.trim()}>
              + Создать БЗ
            </Button>
          </form>
          <ul className="kb-admin__kb-list">
            {items.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className={item.id === selectedId ? 'is-active' : undefined}
                  onClick={() => void selectKb(item.id)}
                >
                  <strong>{item.name}</strong>
                  <StatusBadge status={statusBadge(item.status)}>
                    {statusLabel(item.status)}
                  </StatusBadge>
                </button>
              </li>
            ))}
            {!items.length && (
              <li className="kb-admin__empty">Пока нет баз знаний. Создайте первую.</li>
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

              <div className="kb-admin__actions">
                <div>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.docx,.txt,.rtf,.xlsx,.pptx,.png,.jpg,.jpeg"
                    hidden
                    disabled={!canEdit || busy}
                    onChange={(event) => void onUpload(event.target.files?.[0])}
                  />
                  <Button
                    disabled={!canEdit || busy}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    Загрузить pdf/docx
                  </Button>
                  <Button
                    variant="secondary"
                    disabled={!canEdit || busy}
                    onClick={() => void onReindex()}
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

              {selected.status_message && (
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
                            {document.status}
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
                          Загрузите PDF или DOCX — индексация запустится автоматически.
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
              <p>Управление документами КЦ без программирования (FR-CC-08, FR-CC-13).</p>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
