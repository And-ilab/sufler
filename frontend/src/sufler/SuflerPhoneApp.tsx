import { useMemo, useRef, useState } from 'react'
import { Button, Card, HintCard, StatusBadge } from '../components'
import { relevanceStatusFromPercent } from '../components/hintRelevance'
import {
  useSuflerTranscript,
  type TranscriptLine,
} from './hooks/useSuflerTranscript'
import { useLiveDualAsr, type DualSpeaker } from './hooks/useLiveDualAsr'
import type { SuflerHint } from './api/suggest'
import './SuflerPhoneApp.css'

export interface SuflerPhoneAppProps {
  roles?: readonly string[]
  callId?: string
  demoMode?: boolean
  demoLines?: TranscriptLine[]
  operatorName?: string
  /** Embed inside portal module window (II.3.2 / I-0b). */
  embedded?: boolean
  clientSummary?: {
    preview: string
    summary: string
    detailedSummary: string
  }
}

function hintTitle(hint: SuflerHint): string {
  return hint.citations[0]?.title || `Подсказка ${hint.rank}`
}

function hintSuz(hint: SuflerHint) {
  const citation = hint.citations[0]
  if (!citation?.permalink) return null
  return { title: citation.title, href: citation.permalink }
}

const DEFAULT_SUMMARY = {
  preview:
    '3 обращения за 90 дней: лимиты ATM (чат), перевод РФ (тел.), карта NFC (Telegram). Повторная тема: переводы.',
  summary:
    '3 обращения за 90 дней: лимиты ATM (чат), перевод РФ (тел.), карта NFC (Telegram). Повторная тема: переводы.',
  detailedSummary:
    'За 90 дней — 3 обращения по теме лимитов и переводов.\n\n12.05.2026 · онлайн-чат · лимит ATM — оператор Сидорова М.В. Разъяснены суточные лимиты карты Visa.\n\n03.04.2026 · Telegram · NFC — оператор Козлов Д.А. Проверены настройки бесконтактной оплаты.\n\n15.03.2026 · телефония (Oktell) · перевод в РФ — оператор Петрова А.С., длит. 4:12. Рекомендован раздел «Платежи → За рубеж».\n\nПовторная тема: переводы. Рекомендация: проверить актуальный лимит в мобильном банке перед ответом.',
}

/** II-2 demo: 3 hints 92% / 87% / 81% on transfer-to-RF turn. */
const DEFAULT_DEMO: TranscriptLine[] = [
  {
    id: 't1-client',
    speaker: 'client',
    text: 'Подскажите, как оформить перевод в Россию через мобильный банк?',
    isFinal: true,
    turnId: 't1',
    hints: [
      {
        rank: 1,
        text: 'Перевод в РФ доступен через «Платежи» → «За рубеж». Проверьте суточный лимит клиента и статус карты.',
        relevance_score: 0.92,
        relevance_percent: 92,
        citations: [
          {
            article_id: 201,
            chunk_index: 0,
            title: 'Переводы в РФ — лимиты',
            permalink: 'https://suz.local/articles/201',
          },
        ],
      },
      {
        rank: 2,
        text: 'Для перевода нужен действующий лимит на международные операции в интернет-банке или мобильном приложении.',
        relevance_score: 0.87,
        relevance_percent: 87,
        citations: [
          {
            article_id: 202,
            chunk_index: 0,
            title: 'Лимиты международных переводов',
            permalink: 'https://suz.local/articles/202',
          },
        ],
      },
      {
        rank: 3,
        text: 'Комиссия зависит от суммы и валюты; актуальные тарифы — в справочнике СУЗ раздела переводов.',
        relevance_score: 0.81,
        relevance_percent: 81,
        citations: [
          {
            article_id: 203,
            chunk_index: 0,
            title: 'Комиссии за переводы за рубеж',
            permalink: 'https://suz.local/articles/203',
          },
        ],
      },
    ],
  },
  {
    id: 't1-operator',
    speaker: 'operator',
    text: 'Хорошо, сейчас посмотрю условия перевода за рубеж.',
    isFinal: true,
    turnId: 't1-op',
  },
]

function ClientSummaryCard({
  preview,
  summary,
  detailedSummary,
}: {
  preview: string
  summary: string
  detailedSummary: string
}) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div
      className="sufler-phone__summary"
      tabIndex={0}
      role="group"
      aria-label="Summary клиента"
      aria-expanded={expanded}
      data-testid="client-summary"
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
      onFocus={() => setExpanded(true)}
      onBlur={(event) => {
        const next = event.relatedTarget as Node | null
        if (!next || !event.currentTarget.contains(next)) {
          setExpanded(false)
        }
      }}
    >
      <Card className="sufler-phone__summary-card">
        <strong>Summary клиента</strong>
        {expanded ? (
          <div className="sufler-phone__summary-body">
            <p>{summary}</p>
            <hr />
            <small>Детальный summary</small>
            <p className="sufler-phone__summary-detailed">{detailedSummary}</p>
          </div>
        ) : (
          <p className="sufler-phone__summary-preview">{preview}</p>
        )}
      </Card>
    </div>
  )
}

export function SuflerPhoneApp({
  callId = 'live',
  demoMode = false,
  demoLines = DEFAULT_DEMO,
  operatorName = 'Оператор КЦ',
  embedded = false,
  clientSummary = DEFAULT_SUMMARY,
}: SuflerPhoneAppProps) {
  const { lines, connected, error, latencyMs, ingestLive, pushAsr, setLines } = useSuflerTranscript({
    callId,
    demoMode,
    demoLines,
  })
  const liveTurns = useRef<Record<DualSpeaker, string>>({ client: '', operator: '' })
  const [typedLine, setTypedLine] = useState('')

  const handleUtterance = (speaker: DualSpeaker, text: string, isFinal: boolean) => {
    if (!liveTurns.current[speaker]) {
      liveTurns.current[speaker] = `${speaker}-${Date.now()}`
    }
    const turnId = liveTurns.current[speaker]
    ingestLive({
      type: isFinal ? 'asr.final' : 'asr.partial',
      speaker,
      text,
      turn_id: turnId,
    })
    if (isFinal) liveTurns.current[speaker] = ''
  }

  const live = useLiveDualAsr(handleUtterance)

  const submitTypedLine = () => {
    const text = typedLine.trim()
    if (!text) return
    handleUtterance('client', text, true)
    setTypedLine('')
  }

  const startLive = () => {
    setLines([])
    liveTurns.current = { client: '', operator: '' }
    void live.start()
  }

  const blocks = useMemo(() => lines, [lines])

  return (
    <main
      className={`sufler-phone${embedded ? ' sufler-phone--embedded' : ''}`}
      data-testid="sufler-phone-app"
    >
      <header className="sufler-phone__header">
        <div>
          <p className="sufler-phone__eyebrow">Суфлёр · активный звонок</p>
          <h1>Телефония</h1>
        </div>
        <div className="sufler-phone__meta">
          <StatusBadge status={live.recording || connected ? 'success' : 'warning'}>
            {live.recording ? 'Имитация' : connected ? 'ASR активен' : 'ASR офлайн'}
          </StatusBadge>
          <StatusBadge status="info">Консультация</StatusBadge>
          <span>{operatorName}</span>
        </div>
      </header>

      {(error || live.error) && (
        <Card className="sufler-phone__error" role="alert">
          {live.error || error}
        </Card>
      )}

      <div className="sufler-phone__workspace">
        <section className="sufler-phone__dialogue" aria-label="Диалог звонка">
          {blocks.map((line) => {
            const hints = line.speaker === 'client' ? line.hints?.slice(0, 5) ?? [] : []
            return (
              <article
                key={line.id}
                className={`sufler-phone__pair sufler-phone__pair--${line.speaker}`}
                data-testid={`turn-${line.turnId}-${line.speaker}`}
              >
                <Card
                  className={`sufler-phone__bubble sufler-phone__bubble--${line.speaker}${
                    line.speaker === 'operator' ? ' is-draft' : ''
                  }`}
                >
                  <header>
                    <strong>{line.speaker === 'client' ? 'Клиент' : 'Оператор'}</strong>
                    {line.speaker === 'operator' ? (
                      <StatusBadge status="info">черновик</StatusBadge>
                    ) : (
                      <StatusBadge status={line.isFinal ? 'neutral' : 'info'}>
                        {line.isFinal ? 'final' : 'partial'}
                      </StatusBadge>
                    )}
                  </header>
                  <p>{line.text}</p>
                </Card>

                {hints.length > 0 && (
                  <div className="sufler-phone__hints" data-testid={`hints-${line.turnId}`}>
                    <div className="sufler-phone__hints-title">Подсказки суфлёра</div>
                    {hints.map((hint, index) => (
                      <HintCard
                        key={`${line.turnId}-${hint.rank}`}
                        title={hintTitle(hint)}
                        relevance={`${hint.relevance_percent}%`}
                        relevancePercent={hint.relevance_percent}
                        relevanceStatus={relevanceStatusFromPercent(hint.relevance_percent)}
                        suzLink={hintSuz(hint)}
                        showFeedback
                        hintIndex={index + 1}
                        hintTotal={hints.length}
                        data-testid={`hint-${line.turnId}-${hint.rank}`}
                      >
                        {hint.text}
                      </HintCard>
                    ))}
                  </div>
                )}
                {line.speaker === 'client' && line.isFinal && hints.length === 0 && (
                  <div className="sufler-phone__hints-empty" role="status">
                    {line.hintStatus === 'loading'
                      ? (line.hintMessage || 'Подсказки загружаются…')
                      : (line.hintMessage || 'Подсказки не пришли. Повторите реплику или проверьте DeepSeek на сервере.')}
                  </div>
                )}
              </article>
            )
          })}
          {!blocks.length && (
            <Card className="sufler-phone__empty">
              {live.caption
                ? `Слышу: ${live.caption}`
                : live.recording
                  ? 'Говорите паузами или введите реплику клиента внизу — она появится в ленте.'
                  : 'Нажмите «Начать имитацию»: микрофон — клиент. Реплика клиента уходит в DeepSeek и собирает подсказки.'}
            </Card>
          )}
        </section>

        <aside className="sufler-phone__context" aria-label="Контекст">
          <header className="sufler-phone__context-header">
            <strong>Контекст</strong>
          </header>
          <ClientSummaryCard {...clientSummary} />
        </aside>
      </div>

      <footer className="sufler-phone__footer">
        <span className="sufler-phone__footer-status">
          {live.recording
            ? live.caption
              ? `Слышу: ${live.caption}`
              : live.status || 'Имитация разговора'
            : connected
              ? 'ASR активен · '
              : ''}
          {!live.recording &&
            (latencyMs != null
              ? `p95 подсказки ${Math.round(latencyMs)} мс`
              : 'p95 подсказки 1.4 с')}
        </span>
        <div className="sufler-phone__live">
          {live.recording ? (
            <>
              <label className="sufler-phone__typed">
                <input
                  value={typedLine}
                  placeholder="Реплика клиента…"
                  aria-label="Реплика клиента"
                  onChange={(event) => setTypedLine(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault()
                      submitTypedLine()
                    }
                  }}
                />
              </label>
              <span className="sufler-phone__levels" aria-hidden="true">
                <i
                  className="sufler-phone__level sufler-phone__level--mic"
                  style={{ transform: `scaleY(${Math.min(1, live.micLevel * 8)})` }}
                />
                <i
                  className="sufler-phone__level sufler-phone__level--sys"
                  style={{ transform: `scaleY(${Math.min(1, live.systemLevel * 8)})` }}
                />
              </span>
              <Button
                variant="ghost"
                onClick={live.swapSpeakers}
                title={
                  live.micSpeaker === 'client'
                    ? 'Микрофон пишет клиента'
                    : 'Микрофон пишет оператора'
                }
              >
                {live.micSpeaker === 'client' ? 'Клиент' : 'Оператор'}
              </Button>
              <Button variant="secondary" onClick={live.stop}>
                Стоп
              </Button>
            </>
          ) : (
            <Button variant="primary" onClick={startLive}>
              Начать имитацию
            </Button>
          )}
          {demoMode && !live.recording && (
            <Button
              variant="secondary"
              onClick={() =>
                pushAsr({
                  type: 'asr.final',
                  speaker: 'client',
                  text: 'Как заменить ПИН-код карты?',
                  turn_id: `demo-${Date.now()}`,
                })
              }
            >
              Демо-реплика
            </Button>
          )}
        </div>
      </footer>
    </main>
  )
}
