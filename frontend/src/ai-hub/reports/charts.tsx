import type { PieSlice } from './demoData'

const TONE_COLOR: Record<string, string> = {
  success: '#2e7d32',
  warning: '#c47f17',
  danger: '#c62828',
  info: '#0c4da2',
  neutral: '#7a8a82',
}

export function BarChartView({
  categories,
  series,
}: {
  categories: string[]
  series: { name: string; data: number[]; tone?: string }[]
  valueSuffix?: string
}) {
  const max = Math.max(
    1,
    ...series.flatMap((item) => item.data),
  )
  return (
    <div>
      <div className="rpt-bars">
        {categories.map((category, index) => (
          <div key={category} className="rpt-bars__col">
            <div className="rpt-bars__stack">
              {series.map((item, seriesIndex) => (
                <div
                  key={item.name}
                  className={`rpt-bars__bar${seriesIndex > 0 ? ' rpt-bars__bar--alt' : ''}`}
                  style={{
                    height: `${(item.data[index] / max) * 100}%`,
                    background:
                      item.tone === 'success' ? TONE_COLOR.success : undefined,
                  }}
                  title={`${item.name}: ${item.data[index]}`}
                />
              ))}
            </div>
            <span className="rpt-bars__label">{category}</span>
          </div>
        ))}
      </div>
      <div className="rpt-row" style={{ marginTop: 10 }}>
        {series.map((item, index) => (
          <span key={item.name} className="rpt-muted">
            <span
              className="rpt-pie__dot"
              style={{
                display: 'inline-block',
                marginRight: 6,
                background: index === 0 ? 'var(--rpt-accent)' : '#52b896',
              }}
            />
            {item.name}
          </span>
        ))}
      </div>
    </div>
  )
}

export function PieChartView({
  data,
  onSelect,
}: {
  data: PieSlice[]
  onSelect?: (label: string) => void
}) {
  const total = data.reduce((sum, item) => sum + item.value, 0) || 1
  let cursor = 0
  const stops = data.map((item) => {
    const start = cursor
    const share = (item.value / total) * 100
    cursor += share
    const color = TONE_COLOR[item.tone || 'info'] || 'var(--rpt-accent)'
    return `${color} ${start}% ${cursor}%`
  })
  return (
    <div className="rpt-pie">
      <div
        className="rpt-pie__ring"
        style={{ background: `conic-gradient(${stops.join(', ')})` }}
      >
        <div className="rpt-pie__hole" />
      </div>
      <div className="rpt-pie__legend">
        {data.map((item) => {
          const body = (
            <>
              <span
                className="rpt-pie__dot"
                style={{ background: TONE_COLOR[item.tone || 'info'] }}
              />
              <span>
                {item.label} — {item.value} ({Math.round((item.value / total) * 100)}%)
              </span>
            </>
          )
          if (!onSelect) {
            return (
              <div key={item.label} className="rpt-pie__legend-item">
                {body}
              </div>
            )
          }
          return (
            <button
              key={item.label}
              type="button"
              className="rpt-pie__legend-item rpt-pie__legend-item--btn"
              onClick={() => onSelect(item.label)}
            >
              {body}
            </button>
          )
        })}
      </div>
    </div>
  )
}

export function DataTable({
  headers,
  rows,
}: {
  headers: string[]
  rows: string[][]
}) {
  return (
    <div className="rpt-table-wrap">
      <table className="rpt-table">
        <thead>
          <tr>
            {headers.map((header) => (
              <th key={header}>{header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${row[0]}-${index}`}>
              {row.map((cell, cellIndex) => (
                <td key={`${index}-${cellIndex}`}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
