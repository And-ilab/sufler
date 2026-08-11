import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  getSupervisorOverview,
  runRouting,
  type SupervisorOverview,
} from '../api/managementApi'
import '../shell/Management.css'

interface SupervisorAppProps {
  demoMode?: boolean
}

function formatSeconds(value?: number) {
  if (value == null) return '—'
  const minutes = Math.floor(value / 60)
  return `${minutes}:${String(Math.floor(value % 60)).padStart(2, '0')}`
}

function operatorDepartment(operator: SupervisorOverview['operators'][number]) {
  if (operator.department_name) return operator.department_name
  if (operator.department && typeof operator.department === 'object') return operator.department.name
  return operator.department ? String(operator.department) : 'Без отдела'
}

export function SupervisorApp({ demoMode = false }: SupervisorAppProps) {
  const [overview, setOverview] = useState<SupervisorOverview | null>(null)
  const [presence, setPresence] = useState('all')
  const [department, setDepartment] = useState('all')
  const [loading, setLoading] = useState(true)
  const [routing, setRouting] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null)

  const refresh = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true)
    try {
      const result = await getSupervisorOverview()
      setOverview(result)
      setUpdatedAt(new Date())
      setError('')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Не удалось загрузить оперативные данные')
    } finally {
      if (!quiet) setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
    const timer = window.setInterval(() => void refresh(true), 10_000)
    return () => window.clearInterval(timer)
  }, [refresh])

  const departments = useMemo(
    () => Array.from(new Set((overview?.operators ?? []).map(operatorDepartment))).sort(),
    [overview],
  )
  const operators = useMemo(
    () => (overview?.operators ?? []).filter((operator) =>
      (presence === 'all' || operator.presence === presence)
      && (department === 'all' || operatorDepartment(operator) === department)),
    [department, overview, presence],
  )
  const kpis = overview?.kpis ?? {}
  const isDemo = demoMode || overview?.demo === true || overview?.source === 'demo'

  const handleRouting = async () => {
    setRouting(true)
    setNotice('')
    try {
      await runRouting()
      setNotice('Маршрутизация выполнена.')
      await refresh(true)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Не удалось запустить маршрутизацию')
    } finally {
      setRouting(false)
    }
  }

  return (
    <main className="chat-management">
      <div className="chat-management__inner">
        <div className="chat-management__heading">
          <div>
            <h1>Панель супервизора</h1>
          </div>
          <div className="chat-management__actions">
            <button className="is-secondary" onClick={() => void refresh()} disabled={loading}>
              {loading ? 'Обновляем…' : 'Обновить'}
            </button>
            <button onClick={() => void handleRouting()} disabled={routing}>
              {routing ? 'Распределяем…' : 'Запустить маршрутизацию'}
            </button>
          </div>
        </div>

        {isDemo && (
          <p className="chat-management__notice" role="status">
            Локальный / демонстрационный контур: данные для проверки сценариев.
            Кнопка «Открыть» запускает АРМ выбранного оператора в режиме просмотра (без ответа от его лица).
          </p>
        )}
        {error && <p className="chat-management__error" role="alert">{error}</p>}
        {notice && <p className="chat-management__success" role="status">{notice}</p>}

        <section className="chat-management__grid" aria-label="Ключевые показатели">
          {[
            ['В очереди', kpis.waiting ?? 0],
            ['Активные диалоги', kpis.active ?? 0],
            ['Операторы онлайн', kpis.online_operators ?? 0],
            ['Среднее ожидание', formatSeconds(kpis.average_wait_seconds)],
            ['SLA', kpis.sla_percent == null ? '—' : `${kpis.sla_percent}%`],
            ['Закрыто сегодня', kpis.closed_today ?? 0],
          ].map(([label, value]) => (
            <article className="chat-management__card chat-management__kpi" key={label}>
              <span>{label}</span>
              <strong>{value}</strong>
            </article>
          ))}
        </section>

        <section className="chat-management__section chat-management__card" aria-labelledby="operators-heading">
          <div className="chat-management__toolbar">
            <div>
              <h2 id="operators-heading">Операторы</h2>
              <span className="chat-management__muted">{operators.length} отображается</span>
            </div>
            <div className="chat-management__actions">
              <label>
                Статус
                <select value={presence} onChange={(event) => setPresence(event.target.value)}>
                  <option value="all">Все</option>
                  <option value="online">Онлайн</option>
                  <option value="busy">Занят</option>
                  <option value="break">Перерыв</option>
                  <option value="lunch">Обед</option>
                  <option value="training">Обучение</option>
                  <option value="meeting">Совещание</option>
                  <option value="tech_issue">Техпроблема</option>
                  <option value="offline">Офлайн</option>
                </select>
              </label>
              <label>
                Отдел
                <select value={department} onChange={(event) => setDepartment(event.target.value)}>
                  <option value="all">Все отделы</option>
                  {departments.map((item) => <option key={item}>{item}</option>)}
                </select>
              </label>
            </div>
          </div>
          <div className="chat-management__table-wrap">
            <table>
              <thead>
                <tr><th>Оператор</th><th>Присутствие</th><th>Нагрузка</th><th>Отдел</th><th>АРМ</th></tr>
              </thead>
              <tbody>
                {operators.map((operator) => {
                  const load = operator.active_dialogs ?? operator.load ?? 0
                  return (
                    <tr key={operator.id}>
                      <td><strong>{operator.name}</strong></td>
                      <td>
                        <span className={`chat-management__pill is-${operator.presence}`}>
                          {operator.presence}
                        </span>
                      </td>
                      <td>{load} / {operator.capacity}</td>
                      <td>{operatorDepartment(operator)}</td>
                      <td>
                        <a
                          className="chat-button is-secondary"
                          href={`/online-chat?mode=view&operator=${encodeURIComponent(operator.name)}&transfer=1`}
                          target="_blank"
                          rel="noreferrer"
                          aria-label={`Просмотр АРМ оператора ${operator.name}`}
                        >
                          Открыть АРМ
                        </a>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {!loading && operators.length === 0 && <div className="chat-management__empty">Операторы не найдены.</div>}
          </div>
        </section>

        <section aria-labelledby="queues-heading">
          <div className="chat-management__toolbar">
            <h2 id="queues-heading">Очереди</h2>
            {updatedAt && <small className="chat-management__muted">Обновлено {updatedAt.toLocaleTimeString('ru-RU')}</small>}
          </div>
          <div className="chat-management__grid">
            {(overview?.queues ?? []).map((queue, index) => (
              <article className="chat-management__card" key={queue.id ?? `${queue.name}-${index}`}>
                <h3>{queue.name}</h3>
                {queue.department && <p className="chat-management__muted">{queue.department}</p>}
                <p><strong>{queue.waiting}</strong> ожидают · {queue.active ?? 0} активны</p>
                <small>Макс. ожидание: {formatSeconds(queue.longest_wait_seconds)}</small>
              </article>
            ))}
          </div>
          {!loading && (overview?.queues.length ?? 0) === 0 && (
            <div className="chat-management__card chat-management__empty">Активных очередей нет.</div>
          )}
        </section>
      </div>
    </main>
  )
}
