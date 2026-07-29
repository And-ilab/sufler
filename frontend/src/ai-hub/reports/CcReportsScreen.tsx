import { useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  Button,
  Card,
  StatusBadge,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from '../../components'
import {
  downloadCcExport,
  fetchCcAnalytics,
  triggerBrowserDownload,
  type AsrQualityPoint,
  type CcAnalyticsFilters,
  type CcAnalyticsPayload,
  type CcChannel,
  type CcReportsApiError,
} from './api/ccReports'
import './CcReports.css'

function isoDate(daysAgo: number): string {
  const date = new Date()
  date.setHours(12, 0, 0, 0)
  date.setDate(date.getDate() - daysAgo)
  return date.toISOString().slice(0, 10)
}

function channelLabel(channel: CcChannel | string): string {
  if (channel === 'telephony') return 'Телефония'
  if (channel === 'online_chat') return 'Онлайн-чат'
  return 'Все каналы'
}

function formatPct(value: number): string {
  return `${value.toFixed(1)}%`
}

function formatConfidence(value: number): string {
  return `${Math.round(value * 100)}%`
}

function AsrQualityChart({
  series,
}: {
  series: AsrQualityPoint[]
}) {
  const maxRecognized = Math.max(
    100,
    ...series.map((point) => point.recognized_pct),
  )
  const maxConfidence = 1

  return (
    <div className="cc-reports__charts" data-testid="asr-quality-charts">
      <Card className="cc-reports__chart-card">
        <div className="cc-reports__section-title">Доля распознанных реплик</div>
        <div className="cc-reports__bars" role="img" aria-label="График распознавания ASR">
          {series.map((point) => (
            <div key={`rec-${point.date}`} className="cc-reports__bar-col">
              <div
                className="cc-reports__bar cc-reports__bar--recognized"
                style={{ height: `${(point.recognized_pct / maxRecognized) * 100}%` }}
                title={`${point.date}: ${formatPct(point.recognized_pct)}`}
              />
              <span>{point.date.slice(5)}</span>
            </div>
          ))}
        </div>
      </Card>
      <Card className="cc-reports__chart-card">
        <div className="cc-reports__section-title">Средняя уверенность ASR</div>
        <div className="cc-reports__bars" role="img" aria-label="График уверенности ASR">
          {series.map((point) => (
            <div key={`conf-${point.date}`} className="cc-reports__bar-col">
              <div
                className="cc-reports__bar cc-reports__bar--confidence"
                style={{ height: `${(point.avg_confidence / maxConfidence) * 100}%` }}
                title={`${point.date}: ${formatConfidence(point.avg_confidence)}`}
              />
              <span>{point.date.slice(5)}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

export function CcReportsScreen() {
  const [draft, setDraft] = useState<CcAnalyticsFilters>({
    date_from: isoDate(13),
    date_to: isoDate(0),
    channel: '',
  })
  const [applied, setApplied] = useState<CcAnalyticsFilters>(draft)
  const [data, setData] = useState<CcAnalyticsPayload | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState<'csv' | 'xlsx' | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    fetchCcAnalytics(applied)
      .then((payload) => {
        if (!cancelled) setData(payload)
      })
      .catch((err: CcReportsApiError | Error) => {
        if (!cancelled) setError(err.message || 'Не удалось загрузить отчёт')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [applied])

  const summaryCards = useMemo(() => {
    if (!data) return []
    const { summary } = data
    return [
      ['Сессии', String(summary.sessions), 'за период'],
      ['ASR распознано', formatPct(summary.recognized_pct), 'реплик'],
      ['Уверенность', formatConfidence(summary.avg_confidence), 'средняя'],
      ['Полезность', formatPct(summary.useful_pct), 'подсказок'],
      ['Некорректные LLM', String(summary.incorrect_llm), 'кейсов'],
      ['p95 подсказки', `${summary.hint_latency_p95_ms} мс`, 'latency'],
    ] as const
  }, [data])

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    setApplied({ ...draft })
  }

  const onExport = async (format: 'csv' | 'xlsx') => {
    setExporting(format)
    setError('')
    try {
      const { blob, filename } = await downloadCcExport(applied, format)
      triggerBrowserDownload(blob, filename)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Ошибка экспорта'
      setError(message)
    } finally {
      setExporting(null)
    }
  }

  return (
    <section className="cc-reports" data-testid="cc-reports-screen">
      <Card className="cc-reports__filters">
        <form className="cc-reports__filters-form" onSubmit={onSubmit}>
          <label>
            Дата с
            <input
              type="date"
              value={draft.date_from || ''}
              onChange={(event) =>
                setDraft((prev) => ({ ...prev, date_from: event.target.value }))
              }
            />
          </label>
          <label>
            Дата по
            <input
              type="date"
              value={draft.date_to || ''}
              onChange={(event) =>
                setDraft((prev) => ({ ...prev, date_to: event.target.value }))
              }
            />
          </label>
          <label>
            Канал
            <select
              value={draft.channel || ''}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  channel: event.target.value as CcChannel | '',
                }))
              }
            >
              <option value="">Все</option>
              <option value="telephony">Телефония</option>
              <option value="online_chat">Онлайн-чат</option>
            </select>
          </label>
          <div className="cc-reports__filter-actions">
            <Button type="submit" disabled={loading}>
              Применить
            </Button>
            <Button
              type="button"
              variant="ghost"
              disabled={exporting !== null || loading}
              onClick={() => void onExport('csv')}
            >
              {exporting === 'csv' ? 'CSV…' : 'Экспорт CSV'}
            </Button>
            <Button
              type="button"
              variant="ghost"
              disabled={exporting !== null || loading}
              onClick={() => void onExport('xlsx')}
            >
              {exporting === 'xlsx' ? 'XLSX…' : 'Экспорт XLSX'}
            </Button>
          </div>
        </form>
        <p className="cc-reports__hint">
          FR-RPT-CC · II.6 — таблицы аналитики КЦ, фильтры периода и выгрузка CSV/XLSX.
          Графики качества ASR строятся по stub-данным витрины asr_stats.
        </p>
      </Card>

      {error ? (
        <Card>
          <StatusBadge status="danger">Ошибка</StatusBadge>
          <p>{error}</p>
        </Card>
      ) : null}

      {loading && !data ? (
        <Card>
          <p className="app-muted">Загрузка отчётности…</p>
        </Card>
      ) : null}

      {data ? (
        <>
          <div className="cc-reports__stats">
            {summaryCards.map(([title, value, hint]) => (
              <Card key={title}>
                <span>{title}</span>
                <strong>{value}</strong>
                <span>{hint}</span>
              </Card>
            ))}
          </div>

          <AsrQualityChart series={data.asr_quality} />

          <Card>
            <div className="cc-reports__section-title">
              Полезность подсказок по каналам (FR-RPT-CC-08)
            </div>
            <Table caption="Полезность ответов LLM">
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Канал</TableHeaderCell>
                  <TableHeaderCell>Полезно</TableHeaderCell>
                  <TableHeaderCell>Неполно</TableHeaderCell>
                  <TableHeaderCell>Не использовано</TableHeaderCell>
                  <TableHeaderCell>Сессии</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.usefulness.map((row) => (
                  <TableRow key={row.channel}>
                    <TableCell>{row.label}</TableCell>
                    <TableCell>{formatPct(row.useful_pct)}</TableCell>
                    <TableCell>{formatPct(row.incomplete_pct)}</TableCell>
                    <TableCell>{formatPct(row.unused_pct)}</TableCell>
                    <TableCell>{row.sessions}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>

          <Card>
            <div className="cc-reports__section-title">
              Детализация по дням · {channelLabel(data.filters.channel)}
            </div>
            <Table caption="CC analytics daily">
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Дата</TableHeaderCell>
                  <TableHeaderCell>Канал</TableHeaderCell>
                  <TableHeaderCell>Оператор</TableHeaderCell>
                  <TableHeaderCell>Сессии</TableHeaderCell>
                  <TableHeaderCell>ASR %</TableHeaderCell>
                  <TableHeaderCell>Confidence</TableHeaderCell>
                  <TableHeaderCell>Полезно %</TableHeaderCell>
                  <TableHeaderCell>LLM errors</TableHeaderCell>
                  <TableHeaderCell>p95 мс</TableHeaderCell>
                  <TableHeaderCell>AHT с</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.rows.map((row) => (
                  <TableRow key={`${row.date}-${row.channel}-${row.operator}`}>
                    <TableCell>{row.date}</TableCell>
                    <TableCell>{channelLabel(row.channel)}</TableCell>
                    <TableCell>{row.operator}</TableCell>
                    <TableCell>{row.sessions}</TableCell>
                    <TableCell>{formatPct(row.recognized_pct)}</TableCell>
                    <TableCell>{formatConfidence(row.avg_confidence)}</TableCell>
                    <TableCell>{formatPct(row.useful_pct)}</TableCell>
                    <TableCell>{row.incorrect_llm}</TableCell>
                    <TableCell>{row.hint_latency_p95_ms}</TableCell>
                    <TableCell>{row.aht_sec}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {data.stub ? (
              <p className="cc-reports__hint">{data.source}</p>
            ) : null}
          </Card>
        </>
      ) : null}
    </section>
  )
}
