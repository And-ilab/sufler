import { useMemo, useState } from 'react'
import { Button } from '../../components'
import {
  testDialogScenario,
  type ScenarioChannel,
  type ScenarioDetail,
  type ScenarioEdge,
  type ScenarioNode,
  type ScenarioTestRun,
} from './api/scenarios'
import { reachableScenarioNodes, scenarioStartNode } from './scenarioGraphAdapter'

const STEP_TYPES = [
  ['start', 'Начало сценария'],
  ['clarify', 'Уточняющий вопрос'],
  ['answer', 'Готовый ответ'],
  ['branch', 'Выбор продолжения'],
  ['escalate', 'Передача специалисту'],
  ['end', 'Завершение'],
] as const

interface ConstructorProps {
  detail: ScenarioDetail
  activeNode: ScenarioNode
  activeIndex: number
  canEdit: boolean
  onDetailChange: (patch: Partial<ScenarioDetail>) => void
  onNodeChange: (patch: Partial<ScenarioNode>) => void
  onEdgeChange: (index: number, patch: Partial<ScenarioEdge>) => void
  onClientVariantChange: (index: number, text: string) => void
  onAddEdge: () => void
  onRemoveEdge: (index: number) => void
  onSelectNode: (id: string) => void
  onAddNode: () => void
  onDuplicateNode: () => void
  onDeleteNode: () => void
}

export function ScenarioConstructor({
  detail,
  activeNode,
  activeIndex,
  canEdit,
  onDetailChange,
  onNodeChange,
  onEdgeChange,
  onClientVariantChange,
  onAddEdge,
  onRemoveEdge,
  onSelectNode,
  onAddNode,
  onDuplicateNode,
  onDeleteNode,
}: ConstructorProps) {
  const nodes = detail.graph.nodes
  const previous = nodes[activeIndex - 1]
  const next = nodes[activeIndex + 1]

  return (
    <div className="scr-constructor">
      <section className="scr-basics" aria-label="Основные настройки сценария">
        <label>
          <span>Название сценария</span>
          <input
            value={detail.title}
            disabled={!canEdit}
            onChange={(event) => onDetailChange({ title: event.target.value })}
          />
        </label>
        <label className="scr-basics__root">
          <span>Стартовая реплика клиента</span>
          <input
            value={detail.root_question}
            disabled={!canEdit}
            placeholder="Например: Хочу перевести деньги"
            onChange={(event) => onDetailChange({ root_question: event.target.value })}
          />
        </label>
        <label>
          <span>Каналы</span>
          <select
            value={detail.channels}
            disabled={!canEdit}
            onChange={(event) =>
              onDetailChange({ channels: event.target.value as ScenarioChannel })
            }
          >
            <option value="both">Телефония и чат</option>
            <option value="telephony">Телефония</option>
            <option value="online_chat">Онлайн-чат</option>
          </select>
        </label>
      </section>

      <div className="scr-step-nav">
        <Button
          variant="ghost"
          disabled={!previous}
          onClick={() => previous && onSelectNode(previous.id)}
        >
          ← Предыдущий
        </Button>
        <label>
          <span>Текущий шаг</span>
          <select value={activeNode.id} onChange={(event) => onSelectNode(event.target.value)}>
            {nodes.map((node, index) => (
              <option key={node.id} value={node.id}>
                {index + 1}. {node.label || 'Без названия'}
              </option>
            ))}
          </select>
        </label>
        <span className="scr-step-nav__count">Шаг {activeIndex + 1} из {nodes.length}</span>
        <Button variant="ghost" disabled={!next} onClick={() => next && onSelectNode(next.id)}>
          Следующий →
        </Button>
      </div>

      <section className="scr-step-editor">
        <header className="scr-step-editor__header">
          <div>
            <small>Настройка шага {activeIndex + 1}</small>
            <input
              aria-label="Название шага"
              value={activeNode.label}
              disabled={!canEdit}
              placeholder="Понятное название шага"
              onChange={(event) => onNodeChange({ label: event.target.value })}
            />
          </div>
          <div className="scr-step-actions">
            <Button variant="ghost" disabled={!canEdit} onClick={onAddNode}>+ Добавить</Button>
            <Button variant="ghost" disabled={!canEdit} onClick={onDuplicateNode}>Дублировать</Button>
            <Button
              className="scr-danger-button"
              variant="ghost"
              disabled={!canEdit || nodes.length <= 1}
              onClick={onDeleteNode}
            >
              Удалить
            </Button>
          </div>
        </header>

        <div className="scr-sequence">
          <section>
            <div className="scr-sequence__title"><span>1</span><div><h3>Активация шага</h3><p>Фразы клиента, по которым подходит этот шаг.</p></div></div>
            <textarea
              rows={3}
              value={activeNode.examples.join('\n')}
              disabled={!canEdit}
              placeholder={'хочу сделать перевод\nкак отправить деньги'}
              onChange={(event) =>
                onNodeChange({
                  examples: event.target.value.split('\n').map((line) => line.trim()).filter(Boolean),
                })
              }
            />
          </section>

          <section>
            <div className="scr-sequence__title"><span>2</span><div><h3>Вопрос клиенту</h3><p>Оператор увидит эту фразу как следующий вопрос.</p></div></div>
            <textarea
              rows={3}
              value={activeNode.clarify_text}
              disabled={!canEdit}
              placeholder="Например: Карта у вас уже есть?"
              onChange={(event) => onNodeChange({ clarify_text: event.target.value })}
            />
          </section>

          <section>
            <div className="scr-sequence__title"><span>3</span><div><h3>Ответ оператора</h3><p>Готовая формулировка для суфлёра.</p></div></div>
            <textarea
              rows={5}
              value={activeNode.hint_text}
              disabled={!canEdit}
              placeholder="Введите готовый ответ оператору"
              onChange={(event) => onNodeChange({ hint_text: event.target.value })}
            />
          </section>

          <section>
            <div className="scr-sequence__title"><span>4</span><div><h3>Варианты ответа клиента</h3><p>Для каждого варианта выберите продолжение.</p></div></div>
            <div className="scr-routes">
              {activeNode.edges.map((edge, index) => (
                <div className="scr-route" key={`${activeNode.id}-${index}`}>
                  <header>
                    <strong>Вариант {index + 1}</strong>
                    <button type="button" disabled={!canEdit} onClick={() => onRemoveEdge(index)}>
                      Удалить
                    </button>
                  </header>
                  <label>
                    <span>Что отвечает клиент</span>
                    <input
                      value={edge.label}
                      disabled={!canEdit}
                      placeholder="Например: Карта уже есть"
                      onChange={(event) => onClientVariantChange(index, event.target.value)}
                    />
                  </label>
                  <label>
                    <span>Куда продолжить</span>
                    <select
                      value={edge.to}
                      disabled={!canEdit}
                      onChange={(event) => onEdgeChange(index, { to: event.target.value })}
                    >
                      <option value="">Выберите следующий шаг</option>
                      {nodes.filter((node) => node.id !== activeNode.id).map((node, nodeIndex) => (
                        <option key={node.id} value={node.id}>
                          {nodeIndex + 1}. {node.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              ))}
              {!activeNode.edges.length && (
                <p className="scr-empty-route">Нет вариантов — сценарий завершится на этом шаге.</p>
              )}
            </div>
            <Button variant="ghost" disabled={!canEdit} onClick={onAddEdge}>
              + Добавить вариант
            </Button>
          </section>
        </div>

        <details className="scr-advanced">
          <summary>Технические настройки</summary>
          <div>
            <label>
              <span>Тип шага</span>
              <select
                value={activeNode.type}
                disabled={!canEdit}
                onChange={(event) => onNodeChange({ type: event.target.value })}
              >
                {STEP_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label>
              <span>Идентификатор шага</span>
              <input value={activeNode.id} readOnly />
            </label>
            <label>
              <span>Intent ID</span>
              <input
                value={activeNode.intent_id}
                disabled={!canEdit}
                onChange={(event) => onNodeChange({ intent_id: event.target.value })}
              />
            </label>
            <label className="scr-advanced__wide">
              <span>Системная инструкция</span>
              <textarea
                rows={6}
                value={detail.system_prompt}
                disabled={!canEdit}
                onChange={(event) => onDetailChange({ system_prompt: event.target.value })}
              />
            </label>
          </div>
        </details>
      </section>
    </div>
  )
}

interface SchemeProps {
  detail: ScenarioDetail
  selectedId: string
  onOpenNode: (id: string) => void
}

export function ScenarioScheme({ detail, selectedId, onOpenNode }: SchemeProps) {
  const reachable = useMemo(() => reachableScenarioNodes(detail.graph), [detail.graph])
  const reachableIds = new Set(reachable.map((node) => node.id))
  const labels = new Map(reachable.map((node, index) => [node.id, `${index + 1}. ${node.label}`]))
  const hiddenCount = detail.graph.nodes.length - reachable.length

  return (
    <section className="scr-scheme">
      <header>
        <div><h3>Схема разговора</h3><p>Показаны шаги, доступные от начала. Нажмите шаг, чтобы изменить его в конструкторе.</p></div>
        {hiddenCount > 0 && <span>{hiddenCount} недоступн. шаг(а)</span>}
      </header>
      {!reachable.length ? <p className="app-muted">В сценарии пока нет шагов.</p> : (
        <div className="scr-scheme__canvas">
          {reachable.map((node, index) => (
            <div className="scr-scheme__row" key={node.id}>
              <button
                type="button"
                className={node.id === selectedId ? 'is-active' : ''}
                onClick={() => onOpenNode(node.id)}
              >
                <small>{node.id === scenarioStartNode(detail.graph)?.id ? 'Начало' : `Шаг ${index + 1}`}</small>
                <strong>{node.label}</strong>
                <span>{node.clarify_text || node.hint_text || 'Содержимое не заполнено'}</span>
              </button>
              {node.edges.some((edge) => reachableIds.has(edge.to)) ? (
                <div className="scr-scheme__links">
                  {node.edges.filter((edge) => reachableIds.has(edge.to)).map((edge, edgeIndex) => (
                    <button type="button" key={`${node.id}-${edgeIndex}`} onClick={() => onOpenNode(edge.to)}>
                      <span>{edge.label || edge.keywords.join(', ') || 'Далее'}</span>
                      <b>→ {labels.get(edge.to)}</b>
                    </button>
                  ))}
                </div>
              ) : <div className="scr-scheme__end">Завершение</div>}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

export function ScenarioTestPreview({ code }: { code: string }) {
  const [script, setScript] = useState('')
  const [result, setResult] = useState<ScenarioTestRun | null>(null)
  const [error, setError] = useState('')
  const [running, setRunning] = useState(false)

  const run = async () => {
    const lines = script.split('\n').map((line) => line.trim()).filter(Boolean)
    if (!lines.length) return
    setRunning(true)
    setError('')
    try {
      setResult(await testDialogScenario(code, lines))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Не удалось выполнить проверку')
    } finally {
      setRunning(false)
    }
  }

  return (
    <details className="scr-preview">
      <summary>Проверить диалог</summary>
      <p>Введите реплики клиента по одной в строке. Проверяется последняя сохранённая версия.</p>
      <textarea
        rows={5}
        value={script}
        placeholder={'Хочу перевести деньги\nКарта уже есть'}
        onChange={(event) => setScript(event.target.value)}
      />
      <Button disabled={running || !script.trim()} onClick={() => void run()}>
        {running ? 'Проверяем…' : 'Запустить проверку'}
      </Button>
      {error && <p className="scr-preview__error">{error}</p>}
      {result && (
        <div className={`scr-preview__result ${result.ok ? 'is-ok' : 'is-error'}`}>
          <strong>{result.ok ? 'Диалог пройден' : 'Найдены проблемы'}</strong>
          <p>{result.path.join(' → ') || 'Путь не определён'}</p>
          {result.errors.map((item) => <span key={item}>{item}</span>)}
          {result.steps.map((step) => (
            <button type="button" key={step.index}>
              <b>{step.label}</b><span>{step.input}</span><small>{step.hint_text || step.clarify_text}</small>
            </button>
          ))}
        </div>
      )}
    </details>
  )
}
