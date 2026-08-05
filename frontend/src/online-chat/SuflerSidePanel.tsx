import { Button, Card, HintCard, StatusBadge } from '../components'
import { relevanceStatusFromPercent } from '../components/hintRelevance'
import type { SuflerHint } from '../sufler/api/suggest'

export interface SuflerSidePanelProps {
  hints: SuflerHint[]
  loading?: boolean
  error?: string
  latencyMs?: number | null
  clientPreview?: string
  onInsert?: (text: string) => void
  disabled?: boolean
}

function hintTitle(hint: SuflerHint): string {
  return hint.citations[0]?.title || `Подсказка ${hint.rank}`
}

function hintSuz(hint: SuflerHint) {
  const citation = hint.citations[0]
  if (!citation?.permalink) return null
  return { title: citation.title, href: citation.permalink }
}

export function SuflerSidePanel({
  hints,
  loading = false,
  error = '',
  latencyMs = null,
  clientPreview = '',
  onInsert,
  disabled = false,
}: SuflerSidePanelProps) {
  return (
    <aside className="chat-arm__sufler" data-testid="sufler-side-panel" aria-label="Суфлёр">
      <header className="chat-arm__sufler-header">
        <h2>Суфлёр</h2>
        <StatusBadge status={loading ? 'info' : 'success'}>
          {loading ? 'запрос…' : 'активен'}
        </StatusBadge>
      </header>

      {clientPreview ? (
        <Card className="chat-arm__client-preview" padded>
          <p className="app-eyebrow">Сообщение клиента</p>
          <p>{clientPreview}</p>
        </Card>
      ) : null}

      {error ? (
        <Card className="chat-arm__error" role="alert">
          {error}
        </Card>
      ) : null}

      <div className="chat-arm__hints" data-testid="sufler-hints">
        {hints.length === 0 && !loading ? (
          <p className="app-muted">Подсказки появятся после сообщения клиента.</p>
        ) : null}
        {hints.map((hint, index) => (
          <HintCard
            key={hint.rank}
            title={hintTitle(hint)}
            relevance={`${hint.relevance_percent}%`}
            relevancePercent={hint.relevance_percent}
            relevanceStatus={relevanceStatusFromPercent(hint.relevance_percent)}
            suzLink={hintSuz(hint)}
            showFeedback
            hintIndex={index + 1}
            hintTotal={hints.length}
            onInsert={
              disabled || !onInsert
                ? undefined
                : () => onInsert(hint.text)
            }
            data-testid={`chat-hint-${hint.rank}`}
          >
            {hint.text}
          </HintCard>
        ))}
      </div>

      <footer className="chat-arm__sufler-footer">
        <span>
          {latencyMs != null
            ? `orchestrator · ${Math.round(latencyMs)} мс`
            : 'тот же suggest API, что телефония'}
        </span>
        {onInsert && hints[0] && !disabled ? (
          <Button
            variant="ghost"
            onClick={() => onInsert(hints[0].text)}
            data-testid="sufler-insert-top"
          >
            Вставить топ-1
          </Button>
        ) : null}
      </footer>
    </aside>
  )
}
