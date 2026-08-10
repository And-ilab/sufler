import { useMemo, useState } from 'react'
import { BarChartView, DataTable, PieChartView } from './charts'
import {
  CHANNEL_OPTIONS,
  CLOSE_TOPICS,
  DEPARTMENT_OPTIONS,
  REPORT_TYPES,
  getReportPreview,
  type ReportTypeId,
  type ReportViewMode,
} from './demoData'

function downloadText(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

export function CcReportsScreen({
  initialPanel = 'reports',
}: {
  initialPanel?: 'reports' | 'builder'
}) {
  const [panel, setPanel] = useState<'reports' | 'builder'>(initialPanel)
  const [reportType, setReportType] = useState<ReportTypeId>('chat-period')
  const [viewMode, setViewMode] = useState<ReportViewMode>('bar')
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [periodFrom, setPeriodFrom] = useState('2026-08-01')
  const [periodTo, setPeriodTo] = useState('2026-08-06')
  const [channel, setChannel] = useState('all')
  const [department, setDepartment] = useState('all')
  const [topic, setTopic] = useState('all')
  const [dialogueStatus, setDialogueStatus] = useState('closed')

  const selected = REPORT_TYPES.find((item) => item.id === reportType) ?? REPORT_TYPES[0]
  const preview = useMemo(
    () => getReportPreview(reportType, viewMode),
    [reportType, viewMode],
  )

  const channelLabel =
    CHANNEL_OPTIONS.find((item) => item.value === channel)?.label ?? 'Все каналы'
  const statusLabel =
    {
      closed: 'Закрыт',
      active: 'В работе',
      offline: 'Офлайн',
      lost: 'Потерянный',
      declined: 'Отказ клиента',
    }[dialogueStatus] || dialogueStatus
  const filtersSummary = `${periodFrom} — ${periodTo} · ${channelLabel} · ${statusLabel}`

  const exportTable = () => {
    const headers = preview.table?.headers ?? ['Показатель', 'Значение']
    const rows = preview.table?.rows ?? [['Нет строк', '—']]
    const csv = [headers, ...rows]
      .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(','))
      .join('\n')
    downloadText(`${selected.label}.csv`, `\uFEFF${csv}`, 'text/csv;charset=utf-8')
  }

  if (panel === 'builder') {
    return <BuilderPanel onBack={() => setPanel('reports')} />
  }

  return (
    <div className="rpt-body" data-testid="cc-reports-screen">
      <div className="rpt-row rpt-row--end">
        <button type="button" className="rpt-pill is-active" onClick={() => setPanel('reports')}>
          Готовые отчёты
        </button>
        <button type="button" className="rpt-pill" onClick={() => setPanel('builder')}>
          Конструктор
        </button>
      </div>

      <div className="rpt-card">
        <div className="rpt-card__head">
          <span>Фильтры отчёта</span>
          <div className="rpt-row">
            {!filtersOpen ? <span className="rpt-muted">{filtersSummary}</span> : null}
            <button
              type="button"
              className="rpt-btn rpt-btn--ghost"
              onClick={() => setFiltersOpen((open) => !open)}
            >
              {filtersOpen ? 'Свернуть' : 'Настроить фильтры'}
            </button>
          </div>
        </div>
        {filtersOpen ? (
          <div className="rpt-card__body">
            <div className="rpt-grid-2">
              <label className="rpt-field">
                Тип отчёта
                <select
                  value={reportType}
                  onChange={(event) => {
                    const next = event.target.value as ReportTypeId
                    setReportType(next)
                    const meta = REPORT_TYPES.find((item) => item.id === next)
                    if (meta) setViewMode(meta.defaultView)
                  }}
                >
                  {REPORT_TYPES.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="rpt-field">
                Период с
                <input type="date" value={periodFrom} onChange={(e) => setPeriodFrom(e.target.value)} />
              </label>
              <label className="rpt-field">
                Период по
                <input type="date" value={periodTo} onChange={(e) => setPeriodTo(e.target.value)} />
              </label>
              <label className="rpt-field">
                Канал
                <select value={channel} onChange={(e) => setChannel(e.target.value)}>
                  {CHANNEL_OPTIONS.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="rpt-field">
                Отдел / скилл-группа
                <select value={department} onChange={(e) => setDepartment(e.target.value)}>
                  {DEPARTMENT_OPTIONS.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="rpt-field">
                Тематика закрытия
                <select value={topic} onChange={(e) => setTopic(e.target.value)}>
                  <option value="all">Все тематики</option>
                  {CLOSE_TOPICS.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>
              <label className="rpt-field">
                Статус диалога
                <select value={dialogueStatus} onChange={(e) => setDialogueStatus(e.target.value)}>
                  <option value="closed">Закрыт</option>
                  <option value="active">В работе</option>
                  <option value="offline">Офлайн</option>
                  <option value="lost">Потерянный</option>
                  <option value="declined">Отказ клиента</option>
                </select>
              </label>
            </div>
          </div>
        ) : null}
      </div>

      <div className="rpt-row">
        <span className="rpt-muted">Представление:</span>
        {(['table', 'pie', 'bar'] as ReportViewMode[]).map((mode) => (
          <button
            key={mode}
            type="button"
            className={`rpt-pill${viewMode === mode ? ' is-active' : ''}`}
            onClick={() => setViewMode(mode)}
          >
            {mode === 'table' ? 'Таблица' : mode === 'pie' ? 'Круговая' : 'Столбчатая'}
          </button>
        ))}
        <span className="rpt-spacer" />
        <span className="rpt-muted">
          {selected.label} · {filtersSummary}
        </span>
        <button type="button" className="rpt-btn" onClick={() => setFiltersOpen(true)}>
          Сформировать
        </button>
        <button type="button" className="rpt-btn rpt-btn--primary" onClick={exportTable}>
          Экспорт xlsx
        </button>
        <button type="button" className="rpt-btn" onClick={exportTable}>
          Экспорт pdf
        </button>
      </div>

      <div className="rpt-card">
        <div className="rpt-card__head">
          <span>{preview.title}</span>
          <span className="rpt-badge rpt-badge--info">{selected.group}</span>
        </div>
        <div className="rpt-card__body">
          {viewMode === 'table' && preview.table ? (
            <DataTable headers={preview.table.headers} rows={preview.table.rows} />
          ) : null}
          {viewMode === 'pie' && preview.pie ? <PieChartView data={preview.pie} /> : null}
          {viewMode === 'bar' && preview.bar ? (
            <BarChartView
              categories={preview.bar.categories}
              series={preview.bar.series}
              valueSuffix={preview.bar.valueSuffix}
            />
          ) : null}
          {viewMode === 'pie' && !preview.pie && preview.bar ? (
            <BarChartView categories={preview.bar.categories} series={preview.bar.series} />
          ) : null}
          {viewMode === 'table' && !preview.table && preview.bar ? (
            <DataTable
              headers={['Категория', ...preview.bar.series.map((s) => s.name)]}
              rows={preview.bar.categories.map((cat, index) => [
                cat,
                ...preview.bar!.series.map((series) => String(series.data[index])),
              ])}
            />
          ) : null}
        </div>
      </div>
    </div>
  )
}

function BuilderPanel({ onBack }: { onBack: () => void }) {
  const [filters, setFilters] = useState([
    { id: 'f1', field: 'period', operator: 'between', value: '2026-08-01 — 2026-08-06' },
    { id: 'f2', field: 'channel', operator: 'in', value: 'Виджет, Telegram' },
  ])
  const [metrics, setMetrics] = useState([
    { id: 'm1', metric: 'dialogs_total', aggregate: 'count' },
    { id: 'm2', metric: 'sla_pct', aggregate: 'avg' },
    { id: 'm3', metric: 'csat', aggregate: 'avg' },
  ])
  const [templateName, setTemplateName] = useState('Сводка КЦ — месяц')
  const [schedule, setSchedule] = useState(true)

  return (
    <div className="rpt-body">
      <div className="rpt-row rpt-row--end">
        <button type="button" className="rpt-pill" onClick={onBack}>
          Готовые отчёты
        </button>
        <button type="button" className="rpt-pill is-active">
          Конструктор
        </button>
      </div>

      <div className="rpt-builder-grid">
        <div style={{ display: 'grid', gap: 16 }}>
          <div className="rpt-card">
            <div className="rpt-card__head">
              <span>Динамические фильтры</span>
              <button
                type="button"
                className="rpt-btn rpt-btn--ghost"
                onClick={() =>
                  setFilters((prev) => [
                    ...prev,
                    {
                      id: `f-${Date.now()}`,
                      field: 'department',
                      operator: 'eq',
                      value: '',
                    },
                  ])
                }
              >
                + Фильтр
              </button>
            </div>
            <div className="rpt-card__body rpt-filter-list">
              {filters.map((row) => (
                <div key={row.id} className="rpt-inline-selects">
                  <select
                    value={row.field}
                    onChange={(e) =>
                      setFilters((prev) =>
                        prev.map((item) =>
                          item.id === row.id ? { ...item, field: e.target.value } : item,
                        ),
                      )
                    }
                  >
                    <option value="period">Период</option>
                    <option value="channel">Канал</option>
                    <option value="department">Отдел</option>
                    <option value="topic">Тематика</option>
                    <option value="operator">Оператор</option>
                  </select>
                  <select
                    value={row.operator}
                    onChange={(e) =>
                      setFilters((prev) =>
                        prev.map((item) =>
                          item.id === row.id ? { ...item, operator: e.target.value } : item,
                        ),
                      )
                    }
                  >
                    <option value="eq">=</option>
                    <option value="in">в списке</option>
                    <option value="between">между</option>
                  </select>
                  <input
                    value={row.value}
                    onChange={(e) =>
                      setFilters((prev) =>
                        prev.map((item) =>
                          item.id === row.id ? { ...item, value: e.target.value } : item,
                        ),
                      )
                    }
                    placeholder="Значение…"
                  />
                  <button
                    type="button"
                    className="rpt-btn rpt-btn--ghost"
                    onClick={() => setFilters((prev) => prev.filter((item) => item.id !== row.id))}
                  >
                    Удалить
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="rpt-card">
            <div className="rpt-card__head">
              <span>Динамические показатели</span>
              <button
                type="button"
                className="rpt-btn rpt-btn--ghost"
                onClick={() =>
                  setMetrics((prev) => [
                    ...prev,
                    { id: `m-${Date.now()}`, metric: 'aht', aggregate: 'avg' },
                  ])
                }
              >
                + Поле
              </button>
            </div>
            <div className="rpt-card__body rpt-metric-list">
              {metrics.map((row) => (
                <div key={row.id} className="rpt-inline-selects">
                  <select
                    value={row.metric}
                    onChange={(e) =>
                      setMetrics((prev) =>
                        prev.map((item) =>
                          item.id === row.id ? { ...item, metric: e.target.value } : item,
                        ),
                      )
                    }
                  >
                    <option value="dialogs_total">Обращений всего</option>
                    <option value="dialogs_closed">Закрытых диалогов</option>
                    <option value="sla_pct">% соблюдения SLA</option>
                    <option value="aht">AHT</option>
                    <option value="csat">Средняя оценка клиента</option>
                    <option value="sufler_used_pct">% использования суфлёра</option>
                  </select>
                  <select
                    value={row.aggregate}
                    onChange={(e) =>
                      setMetrics((prev) =>
                        prev.map((item) =>
                          item.id === row.id ? { ...item, aggregate: e.target.value } : item,
                        ),
                      )
                    }
                  >
                    <option value="count">COUNT</option>
                    <option value="sum">SUM</option>
                    <option value="avg">AVG</option>
                    <option value="p95">P95</option>
                  </select>
                  <button
                    type="button"
                    className="rpt-btn rpt-btn--ghost"
                    onClick={() => setMetrics((prev) => prev.filter((item) => item.id !== row.id))}
                  >
                    Удалить
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="rpt-card">
            <div className="rpt-card__head">Сохранение шаблона</div>
            <div className="rpt-card__body" style={{ display: 'grid', gap: 10 }}>
              <label className="rpt-field">
                Название
                <input value={templateName} onChange={(e) => setTemplateName(e.target.value)} />
              </label>
              <label className="rpt-row" style={{ fontSize: 13 }}>
                <input
                  type="checkbox"
                  checked={schedule}
                  onChange={(e) => setSchedule(e.target.checked)}
                />
                Периодическая рассылка (день / неделя / месяц)
              </label>
              {schedule ? (
                <select defaultValue="monthly">
                  <option value="daily">Ежедневно — 08:00</option>
                  <option value="weekly">Еженедельно — пн 09:00</option>
                  <option value="monthly">Ежемесячно — 1-е число</option>
                </select>
              ) : null}
              <div className="rpt-row">
                <button type="button" className="rpt-btn rpt-btn--primary">
                  Сохранить шаблон
                </button>
                <button type="button" className="rpt-btn">
                  Предпросмотр
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="rpt-card">
          <div className="rpt-card__head">Предпросмотр конструктора</div>
          <div className="rpt-card__body" style={{ display: 'grid', gap: 14 }}>
            <div className="rpt-stats" style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
              {[
                ['Обращений всего', '1 284'],
                ['SLA', '94.8%'],
                ['CSAT', '4.6'],
                ['AHT', '6.1 мин'],
              ].map(([label, value]) => (
                <div key={label} className="rpt-stat rpt-stat--info">
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
            <BarChartView
              categories={['Виджет', 'Telegram', 'Viber', 'ВК', 'Телефония']}
              series={[
                { name: 'Обращений', data: [620, 210, 86, 54, 314] },
                { name: 'Закрыто', data: [582, 198, 79, 51, 288], tone: 'success' },
              ]}
            />
            <PieChartView
              data={[
                { label: 'Воспользовался', value: 58, tone: 'success' },
                { label: 'Неполный ответ', value: 24, tone: 'warning' },
                { label: 'Не воспользовался', value: 18, tone: 'danger' },
              ]}
            />
            <DataTable
              headers={['Фильтр', 'Условие', 'Значение']}
              rows={filters.map((row) => [row.field, row.operator, row.value || '—'])}
            />
            <div className="rpt-row">
              <button type="button" className="rpt-btn rpt-btn--primary">
                Экспорт xlsx
              </button>
              <button type="button" className="rpt-btn">
                Экспорт pdf
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
