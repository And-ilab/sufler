import { useCallback, useEffect, useMemo, useState } from 'react'
import { BarChartView, DataTable, PieChartView } from './charts'
import {
  CHANNEL_OPTIONS,
  CLOSE_TOPICS,
  SUFLER_REPORT_IDS,
  type ReportViewMode,
} from './demoData'
import {
  CcReportsApiError,
  downloadCcExport,
  fetchBuilderTemplates,
  fetchCcCatalog,
  previewBuilder,
  triggerBrowserDownload,
  type CatalogPayload,
  type CatalogReportMeta,
} from './api/ccReports'
import { fieldLabel, localizeCell, metricLabel, summaryLabel } from './labels'

function isoDaysAgo(days: number): string {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  d.setDate(d.getDate() - days)
  return d.toISOString().slice(0, 10)
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

function toneForIndex(index: number): 'success' | 'warning' | 'danger' | 'info' | 'neutral' {
  const tones = ['success', 'info', 'warning', 'danger', 'neutral'] as const
  return tones[index % tones.length]
}

function rowsToTable(rows: Record<string, unknown>[]): { headers: string[]; rows: string[][] } {
  if (!rows.length) return { headers: ['Нет данных'], rows: [['За выбранный период записей нет']] }
  const keys = Object.keys(rows[0]).filter((key) => key !== 'dialog_id' && key !== 'id')
  return {
    headers: keys.map((key) => fieldLabel(key)),
    rows: rows.map((row) => keys.map((key) => localizeCell(row[key]))),
  }
}

function downloadCsv(filename: string, headers: string[], rows: string[][]) {
  const csv = [headers, ...rows]
    .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    .join('\n')
  const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' })
  triggerBrowserDownload(blob, filename.endsWith('.csv') ? filename : `${filename}.csv`)
}

export function CcReportsScreen({
  initialPanel = 'reports',
  initialReport,
  scope = 'chat',
}: {
  initialPanel?: 'reports' | 'builder'
  initialReport?: string
  scope?: 'chat' | 'sufler'
}) {
  const sufler = scope === 'sufler'
  const channelOptions = CHANNEL_OPTIONS.filter((item) => item.value !== 'phone')
  const [panel, setPanel] = useState<'reports' | 'builder'>(initialPanel)
  const [catalogMeta, setCatalogMeta] = useState<CatalogReportMeta[]>([])
  const [reportType, setReportType] = useState(() => {
    const fromUrl = new URLSearchParams(window.location.search).get('report') || ''
    const fallback = initialReport || (sufler ? 'usefulness' : 'chat-period')
    if (sufler && fromUrl && !SUFLER_REPORT_IDS.has(fromUrl)) {
      return fallback
    }
    return fromUrl || fallback
  })
  const [viewMode, setViewMode] = useState<ReportViewMode>('bar')
  const [filtersOpen, setFiltersOpen] = useState(true)
  const [periodFrom, setPeriodFrom] = useState(isoDaysAgo(13))
  const [periodTo, setPeriodTo] = useState(todayIso())
  const [channel, setChannel] = useState('all')
  const [topic, setTopic] = useState('all')
  const [dialogueStatus, setDialogueStatus] = useState('all')
  const [payload, setPayload] = useState<CatalogPayload | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [exportBusy, setExportBusy] = useState(false)

  const selected = useMemo(() => {
    return (
      catalogMeta.find((item) => item.id === reportType)
      || payload?.report
      || {
        id: reportType,
        fr: '',
        label: reportType,
        default_view: 'table',
      }
    )
  }, [catalogMeta, payload, reportType])

  const catalogForUi = useMemo(() => {
    if (!sufler) return catalogMeta
    return catalogMeta.filter((item) => SUFLER_REPORT_IDS.has(item.id))
  }, [catalogMeta, sufler])

  const loadReport = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = sufler
        ? await fetchCcCatalog({
            date_from: periodFrom,
            date_to: periodTo,
            report: reportType,
            scope: 'sufler',
          })
        : await fetchCcCatalog({
            date_from: periodFrom,
            date_to: periodTo,
            channel: 'online_chat',
            report: reportType,
            messenger: channel === 'all' || channel === 'phone' ? '' : channel,
            topic: topic === 'all' ? '' : topic,
            status: dialogueStatus === 'all' ? '' : dialogueStatus,
          })
      setPayload(data)
      setCatalogMeta(data.catalog || [])
      const nextView = (data.report.default_view || 'table') as ReportViewMode
      if (nextView === 'table' || nextView === 'pie' || nextView === 'bar') {
        setViewMode(nextView)
      }
    } catch (err) {
      const message =
        err instanceof CcReportsApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'Не удалось загрузить отчёт'
      setError(message)
    } finally {
      setLoading(false)
    }
  }, [channel, dialogueStatus, periodFrom, periodTo, reportType, sufler, topic])

  useEffect(() => {
    if (panel === 'reports') {
      void loadReport()
    }
  }, [panel, loadReport])

  useEffect(() => {
    const url = new URL(window.location.href)
    if (reportType) {
      url.searchParams.set('report', reportType)
      window.history.replaceState({}, '', `${url.pathname}${url.search}`)
    }
  }, [reportType])

  const table = useMemo(() => rowsToTable((payload?.rows || []) as Record<string, unknown>[]), [payload])
  const chart = payload?.chart || []
  const chartUsable = chart.length >= 1
  const pieData = chart.map((item, index) => ({
    label: item.label,
    value: item.value,
    tone: toneForIndex(index),
  }))
  const barCategories = chart.map((item) => item.label)
  const barSeries = [{ name: selected.label, data: chart.map((item) => item.value) }]

  const channelLabel =
    channelOptions.find((item) => item.value === channel)?.label ?? 'Все каналы'
  const filtersSummary = sufler ? `${periodFrom} — ${periodTo}` : `${periodFrom} — ${periodTo} · ${channelLabel}`

  const exportCurrentCsv = () => {
    downloadCsv(`${selected.label}.csv`, table.headers, table.rows)
  }

  const exportServer = async (format: 'xlsx' | 'pdf') => {
    setExportBusy(true)
    setError(null)
    try {
      const { blob, filename } = await downloadCcExport(
        sufler
          ? {
              date_from: periodFrom,
              date_to: periodTo,
              report: reportType,
              scope: 'sufler',
            }
          : {
              date_from: periodFrom,
              date_to: periodTo,
              channel: 'online_chat',
              report: reportType,
            },
        format,
      )
      triggerBrowserDownload(blob, filename)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка экспорта')
    } finally {
      setExportBusy(false)
    }
  }

  if (panel === 'builder') {
    return <BuilderPanel onBack={() => setPanel('reports')} />
  }

  return (
    <div className="rpt-body" data-testid={sufler ? 'sufler-reports-screen' : 'cc-reports-screen'}>
      {sufler ? null : (
        <div className="rpt-row rpt-row--end">
          <button type="button" className="rpt-pill is-active" onClick={() => setPanel('reports')}>
            Готовые отчёты
          </button>
          <button type="button" className="rpt-pill" onClick={() => setPanel('builder')}>
            Конструктор
          </button>
        </div>
      )}

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
                  onChange={(event) => setReportType(event.target.value)}
                >
                  {(catalogForUi.length
                    ? catalogForUi
                    : [{ id: reportType, label: selected.label, fr: '', default_view: 'table' }]
                  ).map((item) => (
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
              {sufler ? null : (
                <>
                  <label className="rpt-field">
                    Канал чата
                    <select value={channel} onChange={(e) => setChannel(e.target.value)}>
                      {channelOptions.map((item) => (
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
                    Статус / outcome
                    <select value={dialogueStatus} onChange={(e) => setDialogueStatus(e.target.value)}>
                      <option value="all">Все</option>
                      <option value="closed">Закрыт</option>
                      <option value="active">В работе</option>
                      <option value="waiting">В очереди</option>
                      <option value="offline">Офлайн</option>
                      <option value="lost">Потерянный</option>
                      <option value="rejected">Отказ клиента</option>
                    </select>
                  </label>
                </>
              )}
            </div>
            {selected.description ? (
              <p className="rpt-muted" style={{ margin: '8px 0 0' }}>{selected.description}</p>
            ) : null}
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
        <button type="button" className="rpt-btn" disabled={loading} onClick={() => void loadReport()}>
          {loading ? 'Загрузка…' : 'Сформировать'}
        </button>
        <button type="button" className="rpt-btn" onClick={exportCurrentCsv}>
          CSV
        </button>
        <button
          type="button"
          className="rpt-btn rpt-btn--primary"
          disabled={exportBusy}
          onClick={() => void exportServer('xlsx')}
        >
          Экспорт xlsx
        </button>
        <button
          type="button"
          className="rpt-btn"
          disabled={exportBusy}
          onClick={() => void exportServer('pdf')}
        >
          Экспорт pdf
        </button>
      </div>

      {error ? (
        <div className="rpt-card">
          <div className="rpt-card__body" style={{ color: '#c62828' }}>
            {error}
          </div>
        </div>
      ) : null}

      <div className="rpt-stats">
        {Object.entries(payload?.summary || {})
          .filter(([key]) => !['report_id', 'note', 'period', 'rows', 'distribution', 'by_outcome'].includes(key))
          .slice(0, 6)
          .map(([key, value]) => (
            <div key={key} className="rpt-stat rpt-stat--info">
              <span>{summaryLabel(key)}</span>
              <strong>{localizeCell(value)}</strong>
            </div>
          ))}
      </div>

      <div className="rpt-card">
        <div className="rpt-card__head">
          <span>{selected.label}</span>
        </div>
        <div className="rpt-card__body">
          {loading ? <p className="rpt-muted">Загрузка данных…</p> : null}
          {!loading && viewMode === 'table' ? (
            <DataTable headers={table.headers} rows={table.rows} />
          ) : null}
          {!loading && viewMode === 'pie' && chartUsable ? (
            <PieChartView
              data={pieData}
              onSelect={
                sufler && reportType === 'usefulness'
                  ? (label) => {
                      if (label.includes('Не воспользовался')) {
                        setReportType('errors')
                      }
                    }
                  : undefined
              }
            />
          ) : null}
          {!loading && viewMode === 'bar' && chartUsable ? (
            <BarChartView categories={barCategories} series={barSeries} />
          ) : null}
          {!loading && viewMode !== 'table' && !chartUsable ? (
            <DataTable headers={table.headers} rows={table.rows} />
          ) : null}
        </div>
      </div>
    </div>
  )
}

function BuilderPanel({ onBack }: { onBack: () => void }) {
  const [metrics, setMetrics] = useState(['dialogs_total', 'sla_pct', 'csat', 'useful_pct'])
  const [templateName, setTemplateName] = useState('Онлайн-чат — неделя')
  const [viewMode, setViewMode] = useState<'table' | 'bar' | 'pie'>('table')
  const [periodFrom, setPeriodFrom] = useState(isoDaysAgo(6))
  const [periodTo, setPeriodTo] = useState(todayIso())
  const [catalog, setCatalog] = useState<{ id: string; label: string }[]>([])
  const [preview, setPreview] = useState<{
    rows: { metric: string; value: number; unit: string }[]
    chart: { label: string; value: number }[]
    message?: string
  } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    void fetchBuilderTemplates()
      .then((data) => setCatalog(data.metric_catalog || []))
      .catch(() => setCatalog([]))
  }, [])

  const runPreview = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await previewBuilder({
        name: templateName,
        metrics,
        view_mode: viewMode,
        date_from: periodFrom,
        date_to: periodTo,
      })
      setPreview(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка предпросмотра')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void runPreview()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const saveTemplateLocal = () => {
    const key = 'sufler.cc.report.templates'
    const prev = JSON.parse(localStorage.getItem(key) || '[]') as unknown[]
    prev.unshift({
      name: templateName,
      metrics,
      view_mode: viewMode,
      date_from: periodFrom,
      date_to: periodTo,
      saved_at: new Date().toISOString(),
    })
    localStorage.setItem(key, JSON.stringify(prev.slice(0, 20)))
  }

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
            <div className="rpt-card__head">Период и шаблон</div>
            <div className="rpt-card__body" style={{ display: 'grid', gap: 10 }}>
              <label className="rpt-field">
                Название
                <input value={templateName} onChange={(e) => setTemplateName(e.target.value)} />
              </label>
              <div className="rpt-grid-2">
                <label className="rpt-field">
                  С
                  <input type="date" value={periodFrom} onChange={(e) => setPeriodFrom(e.target.value)} />
                </label>
                <label className="rpt-field">
                  По
                  <input type="date" value={periodTo} onChange={(e) => setPeriodTo(e.target.value)} />
                </label>
              </div>
              <label className="rpt-field">
                Вид
                <select value={viewMode} onChange={(e) => setViewMode(e.target.value as typeof viewMode)}>
                  <option value="table">Таблица</option>
                  <option value="bar">Столбчатая</option>
                  <option value="pie">Круговая</option>
                </select>
              </label>
            </div>
          </div>

          <div className="rpt-card">
            <div className="rpt-card__head">
              <span>Показатели</span>
              <button
                type="button"
                className="rpt-btn rpt-btn--ghost"
                onClick={() => setMetrics((prev) => [...prev, catalog[0]?.id || 'dialogs_total'])}
              >
                + Поле
              </button>
            </div>
            <div className="rpt-card__body rpt-metric-list">
              {metrics.map((metric, index) => (
                <div key={`${metric}-${index}`} className="rpt-inline-selects">
                  <select
                    value={metric}
                    onChange={(e) =>
                      setMetrics((prev) =>
                        prev.map((item, i) => (i === index ? e.target.value : item)),
                      )
                    }
                  >
                    {(catalog.length
                      ? catalog
                      : [
                          { id: 'dialogs_total', label: 'Число диалогов' },
                          { id: 'sla_pct', label: 'Соблюдение SLA первого ответа, %' },
                          { id: 'csat', label: 'Средняя оценка клиента' },
                          { id: 'useful_pct', label: 'Полезность суфлёра' },
                          { id: 'aht_sec', label: 'Среднее время обработки, с' },
                        ]
                    ).map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="rpt-btn rpt-btn--ghost"
                    onClick={() => setMetrics((prev) => prev.filter((_, i) => i !== index))}
                  >
                    Удалить
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="rpt-row">
            <button type="button" className="rpt-btn rpt-btn--primary" disabled={loading} onClick={() => void runPreview()}>
              {loading ? 'Считаем…' : 'Предпросмотр'}
            </button>
            <button type="button" className="rpt-btn" onClick={saveTemplateLocal}>
              Сохранить шаблон (локально)
            </button>
          </div>
          {error ? <p style={{ color: '#c62828' }}>{error}</p> : null}
        </div>

        <div className="rpt-card">
          <div className="rpt-card__head">Предпросмотр конструктора</div>
          <div className="rpt-card__body" style={{ display: 'grid', gap: 14 }}>
            {preview?.message ? <p className="rpt-muted">{preview.message}</p> : null}
            <div className="rpt-stats" style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
              {(preview?.rows || []).map((row) => (
                <div key={row.metric} className="rpt-stat rpt-stat--info">
                  <span>{metricLabel(row.metric, catalog)}</span>
                  <strong>
                    {localizeCell(row.value)}
                    {row.unit ? ` ${row.unit}` : ''}
                  </strong>
                </div>
              ))}
            </div>
            {viewMode === 'bar' && preview?.chart?.length ? (
              <BarChartView
                categories={preview.chart.map((item) => metricLabel(item.label, catalog))}
                series={[{ name: 'Значение', data: preview.chart.map((item) => item.value) }]}
              />
            ) : null}
            {viewMode === 'pie' && preview?.chart?.length ? (
              <PieChartView
                data={preview.chart.map((item, index) => ({
                  label: metricLabel(item.label, catalog),
                  value: item.value,
                  tone: toneForIndex(index),
                }))}
              />
            ) : null}
            <DataTable
              headers={['Показатель', 'Значение', 'Ед.']}
              rows={(preview?.rows || []).map((row) => [
                metricLabel(row.metric, catalog),
                localizeCell(row.value),
                row.unit || '—',
              ])}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
