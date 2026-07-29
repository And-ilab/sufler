import { useMemo } from 'react'
import { Button, Card, HintCard, StatusBadge, type StatusBadgeStatus } from '../components'
import {
  useSuflerTranscript,
  type TranscriptLine,
} from './hooks/useSuflerTranscript'
import type { SuflerHint } from './api/suggest'
import './SuflerPhoneApp.css'

export interface SuflerPhoneAppProps {
  roles?: readonly string[]
  callId?: string
  demoMode?: boolean
  demoLines?: TranscriptLine[]
  operatorName?: string
}

function relevanceStatus(percent: number): StatusBadgeStatus {
  if (percent >= 90) return 'success'
  if (percent >= 80) return 'info'
  if (percent >= 70) return 'warning'
  return 'neutral'
}

function hintTitle(hint: SuflerHint): string {
  return hint.citations[0]?.title || `Подсказка ${hint.rank}`
}

function hintSuz(hint: SuflerHint) {
  const citation = hint.citations[0]
  if (!citation?.permalink) return null
  return { title: citation.title, href: citation.permalink }
}

const DEFAULT_DEMO: TranscriptLine[] = [
  {
    id: 't1-client',
    speaker: 'client',
    text: 'Подскажите, как оформить банковскую карту и какой нужен паспорт?',
    isFinal: true,
    turnId: 't1',
    hints: [
      {
        rank: 1,
        text: 'Для оформления карты потребуется паспорт. Заявку можно подать в отделении или через интернет-банкинг.',
        relevance_score: 0.96,
        relevance_percent: 96,
        citations: [
          {
            article_id: 101,
            chunk_index: 0,
            title: 'Оформление банковской карты',
            permalink: 'https://suz.local/articles/101',
          },
        ],
      },
      {
        rank: 2,
        text: 'Уточните тип карты: дебетовая или кредитная — от этого зависят документы и срок выпуска.',
        relevance_score: 0.88,
        relevance_percent: 88,
        citations: [
          {
            article_id: 102,
            chunk_index: 0,
            title: 'Типы карт',
            permalink: 'https://suz.local/articles/102',
          },
        ],
      },
      {
        rank: 3,
        text: 'Срок выпуска зависит от продукта и региона обслуживания.',
        relevance_score: 0.81,
        relevance_percent: 81,
        citations: [
          {
            article_id: 103,
            chunk_index: 0,
            title: 'Сроки выпуска карт',
            permalink: 'https://suz.local/articles/103',
          },
        ],
      },
    ],
  },
  {
    id: 't1-operator',
    speaker: 'operator',
    text: 'Для оформления карты нужен паспорт. Могу подсказать по отделению или онлайн-заявке.',
    isFinal: true,
    turnId: 't1-op',
  },
]

export function SuflerPhoneApp({
  callId = 'live',
  demoMode = false,
  demoLines = DEFAULT_DEMO,
  operatorName = 'Оператор КЦ',
}: SuflerPhoneAppProps) {
  const { lines, connected, error, latencyMs, pushAsr } = useSuflerTranscript({
    callId,
    demoMode,
    demoLines,
  })

  const blocks = useMemo(() => lines, [lines])

  return (
    <main className="sufler-phone" data-testid="sufler-phone-app">
      <header className="sufler-phone__header">
        <div>
          <p className="sufler-phone__eyebrow">Суфлёр · активный звонок</p>
          <h1>Телефония</h1>
        </div>
        <div className="sufler-phone__meta">
          <StatusBadge status={connected ? 'success' : 'warning'}>
            {connected ? 'ASR активен' : 'ASR офлайн'}
          </StatusBadge>
          <StatusBadge status="info">Консультация</StatusBadge>
          <span>{operatorName}</span>
        </div>
      </header>

      {error && (
        <Card className="sufler-phone__error" role="alert">
          {error}
        </Card>
      )}

      <section className="sufler-phone__dialogue" aria-label="Диалог звонка">
        {blocks.map((line) => (
          <article
            key={line.id}
            className={`sufler-phone__turn sufler-phone__turn--${line.speaker}`}
            data-testid={`turn-${line.turnId}-${line.speaker}`}
          >
            <Card className="sufler-phone__bubble">
              <header>
                <strong>{line.speaker === 'client' ? 'Клиент' : 'Оператор'}</strong>
                <StatusBadge status={line.isFinal ? 'neutral' : 'info'}>
                  {line.isFinal ? 'final' : 'partial'}
                </StatusBadge>
              </header>
              <p>{line.text}</p>
            </Card>

            {line.speaker === 'client' && line.hints && line.hints.length > 0 && (
              <div className="sufler-phone__hints" data-testid={`hints-${line.turnId}`}>
                <div className="sufler-phone__hints-title">Подсказки суфлёра</div>
                {line.hints.slice(0, 5).map((hint) => (
                  <HintCard
                    key={`${line.turnId}-${hint.rank}`}
                    title={hintTitle(hint)}
                    relevance={`${hint.relevance_percent}%`}
                    relevanceStatus={relevanceStatus(hint.relevance_percent)}
                    suzLink={hintSuz(hint)}
                    data-testid={`hint-${line.turnId}-${hint.rank}`}
                  >
                    {hint.text}
                  </HintCard>
                ))}
              </div>
            )}
          </article>
        ))}
        {!blocks.length && (
          <Card className="sufler-phone__empty">
            Ожидание реплик клиента. Транскрипт появится по WebSocket.
          </Card>
        )}
      </section>

      <footer className="sufler-phone__footer">
        <span>
          {latencyMs != null
            ? `p95 подсказки ~ ${Math.round(latencyMs)} мс`
            : 'Ожидание подсказок orchestrator'}
        </span>
        {demoMode && (
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
      </footer>
    </main>
  )
}
