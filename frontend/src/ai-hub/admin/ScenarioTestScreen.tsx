import { useEffect, useState } from 'react'
import { Button, Card } from '../../components'
import {
  listDialogScenarios,
  testDialogScenario,
  type ScenarioListItem,
  type ScenarioTestRun,
} from './api/scenarios'
import './ScenarioEditor.css'

interface ScenarioTestScreenProps {
  canEdit: boolean
  initialCode?: string
  onEditScenario?: (code: string) => void
}

export function ScenarioTestScreen({
  canEdit,
  initialCode = '',
  onEditScenario,
}: ScenarioTestScreenProps) {
  const [items, setItems] = useState<ScenarioListItem[]>([])
  const [code, setCode] = useState(initialCode)
  const [lines, setLines] = useState<string[]>([])
  const [input, setInput] = useState('')
  const [result, setResult] = useState<ScenarioTestRun | null>(null)
  const [error, setError] = useState('')
  const [running, setRunning] = useState(false)

  useEffect(() => {
    void listDialogScenarios()
      .then((payload) => {
        setItems(payload.items)
        setCode((current) => current || payload.items[0]?.code || '')
      })
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : 'Не удалось загрузить сценарии'))
  }, [])

  useEffect(() => {
    if (initialCode) setCode(initialCode)
  }, [initialCode])

  const reset = (nextCode = code) => {
    setCode(nextCode)
    setLines([])
    setResult(null)
    setInput('')
    setError('')
  }

  const send = async (replica = input) => {
    const text = replica.trim()
    if (!code || !text || running) return
    const nextLines = [...lines, text]
    setRunning(true)
    setError('')
    try {
      const nextResult = await testDialogScenario(code, nextLines)
      setLines(nextLines)
      setResult(nextResult)
      setInput('')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Не удалось выполнить ход')
    } finally {
      setRunning(false)
    }
  }

  const currentStep = result?.steps[result.steps.length - 1]
  const selectedScenario = items.find((item) => item.code === code)

  return (
    <div className="scr-dialog-test" data-testid="scenario-test">
      <header className="scr-dialog-test__toolbar">
        <label>
          <span>Сценарий для проверки</span>
          <select value={code} onChange={(event) => reset(event.target.value)}>
            {items.map((item) => <option key={item.code} value={item.code}>{item.code} · {item.title}</option>)}
          </select>
        </label>
        <div>
          {onEditScenario ? <Button variant="ghost" disabled={!code} onClick={() => onEditScenario(code)}>Редактировать сценарий</Button> : null}
          <Button variant="ghost" disabled={!lines.length} onClick={() => reset()}>Начать заново</Button>
        </div>
      </header>

      <div className="scr-dialog-test__layout">
        <section className="scr-chat" aria-label="Тестовый диалог">
          <header>
            <div><h2>Диалог</h2><p>Вводите только реплики клиента. Суфлёр покажет, что должен сказать оператор.</p></div>
            {result ? <small>Версия {result.version_number} · {result.is_published ? 'опубликована' : 'черновик'}</small> : null}
          </header>
          <div className="scr-chat__messages" aria-live="polite">
            {!result ? (
              <div className="scr-chat__welcome">
                <strong>Начните с входной реплики клиента</strong>
                <p>Например: «{selectedScenario?.root_question || 'Введите фразу, с которой клиент начинает разговор'}».</p>
              </div>
            ) : null}
            {result?.steps.map((step) => (
              <div className="scr-chat__turn" key={step.index}>
                <div className="scr-message scr-message--client"><small>Клиент</small><p>{step.input}</p></div>
                {step.ok ? (
                  <div className="scr-message scr-message--operator">
                    <small>Подсказка оператору · {step.label}</small>
                    {step.hint_text ? <p>{step.hint_text}</p> : null}
                    {step.clarify_text ? <p className="scr-message__question">{step.clarify_text}</p> : null}
                    {step.selected_edge ? <span>Распознана ветка: {step.selected_edge}</span> : null}
                    {step.terminal ? <b>Сценарий завершён</b> : null}
                  </div>
                ) : (
                  <div className="scr-message scr-message--error">
                    <small>Реплика не распознана</small>
                    <p>{result.errors.find((item) => item.startsWith(`Шаг ${step.index}:`))}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
          {currentStep?.available_choices.length ? (
            <div className="scr-chat__choices" aria-label="Примеры вариантов ответа">
              <span>Проверить вариант:</span>
              {currentStep.available_choices.map((choice) => (
                <button
                  type="button"
                  key={`${choice.label}-${choice.reply}`}
                  title={`Ветка: ${choice.label}`}
                  disabled={running}
                  onClick={() => void send(choice.reply)}
                >
                  {choice.reply}
                </button>
              ))}
            </div>
          ) : null}
          <form className="scr-chat__composer" onSubmit={(event) => { event.preventDefault(); void send() }}>
            <input
              aria-label="Следующая реплика клиента"
              value={input}
              disabled={!code || running || Boolean(currentStep?.terminal)}
              placeholder={currentStep?.terminal ? 'Диалог завершён' : 'Введите следующую реплику клиента'}
              onChange={(event) => setInput(event.target.value)}
            />
            <Button disabled={!input.trim() || running || Boolean(currentStep?.terminal)} type="submit">
              {running ? 'Проверяем…' : 'Отправить'}
            </Button>
          </form>
          {error ? <Card>{error}</Card> : null}
        </section>

        <aside className="scr-run-inspector">
          <h2>Текущий путь</h2>
          <ol>
            {(result?.path ?? []).map((item, index) => <li key={`${item}-${index}`}><span>{index + 1}</span>{item}</li>)}
          </ol>
          {!result?.path.length ? <p>Путь появится после первой реплики.</p> : null}
          {currentStep ? (
            <section>
              <small>Активный шаг</small>
              <strong>{currentStep.label}</strong>
              <span>ID: {currentStep.node_id}</span>
            </section>
          ) : null}
          {!canEdit ? <p>Редактирование недоступно для текущей роли.</p> : null}
        </aside>
      </div>
    </div>
  )
}
