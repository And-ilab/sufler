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
}

export function ScenarioTestScreen({ canEdit: _canEdit, initialCode = '' }: ScenarioTestScreenProps) {
  const [items, setItems] = useState<ScenarioListItem[]>([])
  const [code, setCode] = useState(initialCode)
  const [script, setScript] = useState(
    'надо отправить деньги в россию маме на карту сбера\nна карту сбера\nчерез мобильный банк',
  )
  const [result, setResult] = useState<ScenarioTestRun | null>(null)
  const [error, setError] = useState('')
  const [running, setRunning] = useState(false)

  useEffect(() => {
    void listDialogScenarios()
      .then((payload) => {
        setItems(payload.items)
        setCode((current) => current || payload.items[0]?.code || '')
      })
      .catch((caught: unknown) => {
        setError(caught instanceof Error ? caught.message : 'Не удалось загрузить сценарии')
      })
  }, [])

  useEffect(() => {
    if (initialCode) setCode(initialCode)
  }, [initialCode])

  const run = async () => {
    if (!code) return
    setRunning(true)
    setError('')
    try {
      const lines = script
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean)
      setResult(await testDialogScenario(code, lines))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Не удалось выполнить прогон')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="scr-test" data-testid="scenario-test">
      <section>
        <h2>Sandbox диалог</h2>
        <label>
          <span>Сценарий</span>
          <select value={code} onChange={(event) => setCode(event.target.value)}>
            {items.map((item) => (
              <option key={item.code} value={item.code}>
                {item.code} · {item.title}
              </option>
            ))}
          </select>
        </label>
        <textarea
          rows={10}
          value={script}
          onChange={(event) => setScript(event.target.value)}
          aria-label="Реплики клиента"
        />
        <Button disabled={!code || running} onClick={() => void run()}>
          {running ? 'Прогон…' : 'Запустить test-run'}
        </Button>
      </section>
      <section>
        <h2>Отчёт test-run</h2>
        {error ? <Card>{error}</Card> : null}
        {result ? (
          <>
            <p className="scr-test__path">{result.path.join(' → ') || 'Путь пуст'}</p>
            {result.ok ? <p>Все шаги распознаны.</p> : null}
            {result.errors.map((item) => (
              <p key={item}>{item}</p>
            ))}
            <ol>
              {result.steps.map((step) => (
                <li key={step.index}>
                  <strong>{step.label}</strong>
                  <div>{step.input}</div>
                  <small>{step.hint_text || step.clarify_text}</small>
                </li>
              ))}
            </ol>
          </>
        ) : (
          <p className="app-muted">Запустите прогон, чтобы увидеть ветки и ошибки формулировок.</p>
        )}
      </section>
    </div>
  )
}
