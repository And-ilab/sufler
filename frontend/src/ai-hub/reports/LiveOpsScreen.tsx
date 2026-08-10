import { DataTable } from './charts'
import { LIVE_DEMO, statusLabelRu } from './demoData'

export function LiveOpsScreen() {
  const maxActive = Math.max(1, ...LIVE_DEMO.departments.map((item) => item.active))

  return (
    <div className="rpt-body" data-testid="cc-live-screen">
      <div className="rpt-stats">
        {LIVE_DEMO.kpis.map((kpi) => (
          <div key={kpi.label} className={`rpt-stat rpt-stat--${kpi.tone}`}>
            <span>{kpi.label}</span>
            <strong>{kpi.value}</strong>
          </div>
        ))}
      </div>

      <div className="rpt-card">
        <div className="rpt-card__head">Оповещения</div>
        <div className="rpt-card__body">
          <ul className="rpt-alerts">
            {LIVE_DEMO.alerts.map((alert) => (
              <li key={alert.title} className={`rpt-alert rpt-alert--${alert.tone}`}>
                <strong>{alert.title}</strong>
                <span>{alert.detail}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="rpt-grid-2">
        <div className="rpt-card">
          <div className="rpt-card__head">Нагрузка по отделам</div>
          <div className="rpt-card__body">
            <div className="rpt-dept">
              {LIVE_DEMO.departments.map((dept) => (
                <div key={dept.name} className="rpt-dept__row">
                  <span>{dept.name}</span>
                  <div className="rpt-dept__track">
                    <div
                      className="rpt-dept__fill"
                      style={{ width: `${(dept.active / maxActive) * 100}%` }}
                    />
                  </div>
                  <strong>{dept.active}</strong>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="rpt-card">
          <div className="rpt-card__head">Топ операторов по диалогам</div>
          <div className="rpt-card__body">
            <div style={{ display: 'grid', gap: 8 }}>
              {LIVE_DEMO.operators
                .filter((op) => op.active > 0)
                .map((op) => (
                  <div key={op.name} className="rpt-row rpt-row--between">
                    <span>{op.name}</span>
                    <span className="rpt-badge rpt-badge--success">{op.active} активных</span>
                  </div>
                ))}
            </div>
          </div>
        </div>
      </div>

      <div className="rpt-card">
        <div className="rpt-card__head">Операторы</div>
        <div className="rpt-card__body">
          <DataTable
            headers={['Оператор', 'Статус', 'Канал', 'Активных']}
            rows={LIVE_DEMO.operators.map((op) => [
              op.name,
              statusLabelRu(op.status),
              op.channel,
              String(op.active),
            ])}
          />
        </div>
      </div>

      <div className="rpt-card">
        <div className="rpt-card__head">Лента обращений</div>
        <div className="rpt-card__body">
          <DataTable
            headers={['Время', 'Канал', 'Оператор', 'Тематика', 'Релевантность', 'Оценка']}
            rows={LIVE_DEMO.feed.map((row) => [
              row.time,
              row.channel,
              row.operator,
              row.topic,
              row.relevance,
              row.feedback,
            ])}
          />
        </div>
      </div>
    </div>
  )
}
