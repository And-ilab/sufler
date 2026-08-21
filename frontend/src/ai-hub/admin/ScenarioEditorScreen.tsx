import { useCallback, useEffect, useMemo, useState } from 'react'
import { Button, Card, StatusBadge } from '../../components'
import {
  createDialogScenario,
  getDialogScenario,
  listDialogScenarios,
  saveDialogScenario,
  type ScenarioDetail,
  type ScenarioGraph,
  type ScenarioListItem,
  type ScenarioNode,
} from './api/scenarios'
import {
  createScenarioNode,
  duplicateScenarioNode,
  removeScenarioNode,
  updateClientVariant,
  updateClientVariantTarget,
  validateScenario,
} from './scenarioGraphAdapter'
import {
  ScenarioConstructor,
  ScenarioScheme,
  ScenarioTestPreview,
} from './ScenarioEditorWorkspace'
import './ScenarioEditor.css'

interface ScenarioEditorScreenProps {
  canEdit: boolean
  onOpenTest?: (code: string) => void
}

function channelLabel(channel: string): string {
  if (channel === 'telephony') return 'Телефония'
  if (channel === 'online_chat') return 'Онлайн-чат'
  return 'Телефония и чат'
}

export function ScenarioEditorScreen({ canEdit, onOpenTest }: ScenarioEditorScreenProps) {
  const [items, setItems] = useState<ScenarioListItem[]>([])
  const [counts, setCounts] = useState({ total: 0, production: 0, draft: 0 })
  const [selected, setSelected] = useState('')
  const [detail, setDetail] = useState<ScenarioDetail | null>(null)
  const [mode, setMode] = useState<'constructor' | 'scheme'>('constructor')
  const [nodeId, setNodeId] = useState('')
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'production' | 'draft'>('all')
  const [message, setMessage] = useState('')
  const [publishIssues, setPublishIssues] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [creating, setCreating] = useState(false)

  const loadList = useCallback(async () => {
    try {
      const payload = await listDialogScenarios()
      setItems(payload.items)
      setCounts(payload.counts)
      setSelected((current) => current || payload.items[0]?.code || '')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Не удалось загрузить сценарии')
    }
  }, [])

  useEffect(() => {
    void loadList()
  }, [loadList])

  useEffect(() => {
    if (!selected) {
      setDetail(null)
      return
    }
    let cancelled = false
    void getDialogScenario(selected)
      .then((payload) => {
        if (cancelled) return
        setDetail(payload)
        setNodeId(payload.graph.nodes.find((node) => node.type === 'start')?.id ?? payload.graph.nodes[0]?.id ?? '')
        setPublishIssues([])
        setMessage('')
      })
      .catch((error: unknown) => {
        if (!cancelled) setMessage(error instanceof Error ? error.message : 'Не удалось открыть сценарий')
      })
    return () => { cancelled = true }
  }, [selected])

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return items.filter((item) => (
      (statusFilter === 'all' || item.status === statusFilter)
      && (!needle || item.code.toLowerCase().includes(needle) || item.title.toLowerCase().includes(needle))
    ))
  }, [items, query, statusFilter])

  const nodes = detail?.graph.nodes ?? []
  const activeIndex = Math.max(0, nodes.findIndex((node) => node.id === nodeId))
  const activeNode = nodes[activeIndex]

  const updateGraph = (graph: ScenarioGraph) => {
    setDetail((current) => current ? { ...current, graph } : current)
    setPublishIssues([])
  }

  const patchNode = (patch: Partial<ScenarioNode>) => {
    if (!activeNode) return
    updateGraph({ nodes: nodes.map((node) => node.id === activeNode.id ? { ...node, ...patch } : node) })
  }

  const handleSave = async (publish: boolean) => {
    if (!detail || !canEdit) return
    if (publish) {
      const validation = validateScenario(detail.title, detail.root_question, detail.graph)
      const issues = [...validation.errors, ...validation.warnings]
      setPublishIssues(issues)
      if (validation.errors.length) {
        setMessage('Исправьте обязательные поля перед публикацией.')
        return
      }
    }
    setSaving(true)
    setMessage('')
    try {
      const saved = await saveDialogScenario(detail.code, {
        title: detail.title,
        root_question: detail.root_question,
        channels: detail.channels,
        graph: detail.graph,
        system_prompt: detail.system_prompt,
        publish,
      })
      setDetail(saved)
      setMessage(publish ? 'Сценарий опубликован.' : 'Черновик сохранён.')
      setPublishIssues([])
      await loadList()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Не удалось сохранить')
    } finally {
      setSaving(false)
    }
  }

  const handleCreate = async () => {
    if (!canEdit) return
    let next = items.length + 1
    const codes = new Set(items.map((item) => item.code))
    while (codes.has(`CC-SCR-${String(next).padStart(3, '0')}`)) next += 1
    const code = `CC-SCR-${String(next).padStart(3, '0')}`
    setCreating(true)
    try {
      const created = await createDialogScenario({
        code,
        title: 'Новый сценарий',
        root_question: '',
        graph: {
          nodes: [{
            id: 'start',
            type: 'start',
            label: 'Начало разговора',
            hint_text: '',
            clarify_text: '',
            examples: [],
            intent_id: code,
            edges: [],
          }],
        },
      })
      await loadList()
      setSelected(created.code)
      setDetail(created)
      setNodeId('start')
      setMode('constructor')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Не удалось создать сценарий')
    } finally {
      setCreating(false)
    }
  }

  const addNode = () => {
    if (!detail) return
    const node = createScenarioNode(detail.graph)
    updateGraph({ nodes: [...nodes, node] })
    setNodeId(node.id)
  }

  const duplicateNode = () => {
    if (!detail || !activeNode) return
    const node = duplicateScenarioNode(detail.graph, activeNode)
    updateGraph({ nodes: [...nodes, node] })
    setNodeId(node.id)
  }

  const deleteNode = () => {
    if (!detail || !activeNode || nodes.length <= 1) return
    const nextSelected = nodes[activeIndex + 1] ?? nodes[activeIndex - 1]
    updateGraph(removeScenarioNode(detail.graph, activeNode.id))
    setNodeId(nextSelected?.id ?? '')
  }

  return (
    <div className="scr-editor" data-testid="scenario-editor">
      <section className="admin-stats" aria-label="Сводка сценариев">
        <Card><span>Всего</span><strong>{counts.total || items.length}</strong><small>В реестре</small></Card>
        <Card><span>Опубликовано</span><strong>{counts.production}</strong><small>Рабочий контур</small></Card>
        <Card><span>Черновики</span><strong>{counts.draft}</strong><small>Ожидают проверки</small></Card>
      </section>

      <div className="scr-editor__layout">
        <aside className="scr-editor__registry">
          <header className="scr-editor__registry-head">
            <div><strong>Сценарии</strong><small>{filtered.length} из {counts.total || items.length}</small></div>
            <Button variant="ghost" disabled={!canEdit || creating} onClick={() => void handleCreate()}>
              + Новый
            </Button>
          </header>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Поиск по коду или теме" aria-label="Поиск сценария" />
          <div className="scr-editor__filters" aria-label="Фильтр статуса">
            <button type="button" className={statusFilter === 'all' ? 'is-active' : ''} onClick={() => setStatusFilter('all')}>Все <span>{counts.total || items.length}</span></button>
            <button type="button" className={statusFilter === 'production' ? 'is-active' : ''} onClick={() => setStatusFilter('production')}>Готовые <span>{counts.production}</span></button>
            <button type="button" className={statusFilter === 'draft' ? 'is-active' : ''} onClick={() => setStatusFilter('draft')}>Черновики <span>{counts.draft}</span></button>
          </div>
          <ul className="scr-editor__scenario-list">
            {filtered.map((item) => (
              <li key={item.code}>
                <button type="button" className={item.code === selected ? 'is-active' : ''} onClick={() => setSelected(item.code)}>
                  <span className="scr-editor__scenario-row"><b>{item.code}</b><i className={`scr-status-dot scr-status-dot--${item.status}`} /><em>{item.status === 'production' ? 'Готов' : 'Черновик'}</em></span>
                  <strong>{item.title}</strong>
                  <small>v{item.version_number || 1} · {channelLabel(item.channels)}</small>
                </button>
              </li>
            ))}
            {!filtered.length && <li className="scr-editor__no-results">Ничего не найдено</li>}
          </ul>
        </aside>

        <main className="scr-editor__main">
          {!detail || !activeNode ? <p className="app-muted">Выберите сценарий слева или создайте новый.</p> : (
            <>
              <header className="scr-editor__head">
                <div className="scr-editor__title-row">
                  <span>{detail.code}</span>
                  <StatusBadge status={detail.status === 'production' ? 'success' : 'warning'}>
                    {detail.status === 'production' ? 'Опубликован' : 'Черновик'}
                  </StatusBadge>
                </div>
                <div className="scr-editor__head-actions">
                  <div className="scr-mode-switch" aria-label="Режим редактора">
                    <button type="button" className={mode === 'constructor' ? 'is-active' : ''} onClick={() => setMode('constructor')}>Конструктор</button>
                    <button type="button" className={mode === 'scheme' ? 'is-active' : ''} onClick={() => setMode('scheme')}>Схема</button>
                  </div>
                  {onOpenTest && <Button variant="ghost" onClick={() => onOpenTest(detail.code)}>Полный тест</Button>}
                  <Button variant="secondary" disabled={!canEdit || saving} onClick={() => void handleSave(false)}>Сохранить</Button>
                  <Button disabled={!canEdit || saving} onClick={() => void handleSave(true)}>Опубликовать</Button>
                </div>
              </header>

              {publishIssues.length > 0 && (
                <section className="scr-validation" aria-live="polite">
                  <strong>Проверка перед публикацией</strong>
                  <ul>{publishIssues.map((issue) => <li key={issue}>{issue}</li>)}</ul>
                </section>
              )}

              {mode === 'constructor' ? (
                <ScenarioConstructor
                  detail={detail}
                  activeNode={activeNode}
                  activeIndex={activeIndex}
                  canEdit={canEdit}
                  onDetailChange={(patch) => {
                    setDetail((current) => current ? { ...current, ...patch } : current)
                    setPublishIssues([])
                  }}
                  onNodeChange={patchNode}
                  onEdgeChange={(index, patch) => {
                    if (typeof patch.to === 'string') {
                      updateGraph(
                        updateClientVariantTarget(
                          detail.graph,
                          activeNode.id,
                          index,
                          patch.to,
                        ),
                      )
                      return
                    }
                    patchNode({
                      edges: activeNode.edges.map((edge, edgeIndex) =>
                        edgeIndex === index ? { ...edge, ...patch } : edge,
                      ),
                    })
                  }}
                  onClientVariantChange={(index, text) => {
                    updateGraph(updateClientVariant(detail.graph, activeNode.id, index, text))
                    setPublishIssues([])
                  }}
                  onAddEdge={() => {
                    const target = nodes.find((node) => node.id !== activeNode.id)
                    patchNode({ edges: [...activeNode.edges, { to: target?.id ?? '', label: '', keywords: [] }] })
                  }}
                  onRemoveEdge={(index) => patchNode({ edges: activeNode.edges.filter((_, edgeIndex) => edgeIndex !== index) })}
                  onSelectNode={setNodeId}
                  onAddNode={addNode}
                  onDuplicateNode={duplicateNode}
                  onDeleteNode={deleteNode}
                />
              ) : (
                <ScenarioScheme
                  detail={detail}
                  selectedId={activeNode.id}
                  onOpenNode={(id) => { setNodeId(id); setMode('constructor') }}
                />
              )}
              <ScenarioTestPreview code={detail.code} />
            </>
          )}
          {message && <p className="scr-editor__message" aria-live="polite">{message}</p>}
        </main>
      </div>
    </div>
  )
}
