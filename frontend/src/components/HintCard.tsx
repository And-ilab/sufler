import {
  forwardRef,
  useId,
  useState,
  type HTMLAttributes,
  type KeyboardEvent,
  type ReactNode,
} from 'react'
import { StatusBadge, type StatusBadgeStatus } from './StatusBadge'
import {
  HINT_FEEDBACK_OPTIONS,
  parseRelevancePercent,
  relevanceStatusFromPercent,
  relevanceTierFromPercent,
  type HintFeedbackChoice,
  type RelevanceTier,
} from './hintRelevance'
import './components.css'

export type { HintFeedbackChoice, RelevanceTier }
export { HINT_FEEDBACK_OPTIONS, parseRelevancePercent, relevanceTierFromPercent }

export interface HintSuzLink {
  title: string
  href: string
}

export interface HintCardProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title' | 'onChange'> {
  title: string
  relevance?: string
  relevancePercent?: number
  relevanceStatus?: StatusBadgeStatus
  suzLink?: HintSuzLink | null
  defaultExpanded?: boolean
  expanded?: boolean
  onExpandedChange?: (expanded: boolean) => void
  onInsert?: () => void
  insertLabel?: string
  /** §4.3.1.9 — show ОС buttons when expanded (telephony / online-chat). */
  showFeedback?: boolean
  feedbackValue?: HintFeedbackChoice | null
  onFeedback?: (choice: HintFeedbackChoice) => void
  hintIndex?: number
  hintTotal?: number
  children?: ReactNode
}

export const HintCard = forwardRef<HTMLDivElement, HintCardProps>(
  (
    {
      title,
      relevance = 'Высокая релевантность',
      relevancePercent,
      relevanceStatus,
      suzLink = null,
      children,
      defaultExpanded = false,
      expanded,
      onExpandedChange,
      onInsert,
      insertLabel = 'Вставить в ответ',
      showFeedback = false,
      feedbackValue,
      onFeedback,
      hintIndex,
      hintTotal,
      className = '',
      onClick,
      onMouseEnter,
      onMouseLeave,
      onFocus,
      onBlur,
      onKeyDown,
      ...props
    },
    ref,
  ) => {
    const [internalExpanded, setInternalExpanded] = useState(defaultExpanded)
    const [hoverExpanded, setHoverExpanded] = useState(false)
    const [localFeedback, setLocalFeedback] = useState<HintFeedbackChoice | null>(null)
    const contentId = useId()
    const isExpanded = expanded ?? (internalExpanded || hoverExpanded)
    const feedbackControlled = feedbackValue !== undefined
    const selectedFeedback = feedbackControlled ? feedbackValue : localFeedback

    const percent = relevancePercent ?? parseRelevancePercent(relevance)
    const tier = percent == null ? null : relevanceTierFromPercent(percent)
    const badgeStatus =
      relevanceStatus
      ?? (percent == null ? 'info' : relevanceStatusFromPercent(percent))

    const setExpanded = (next: boolean) => {
      if (expanded === undefined) setInternalExpanded(next)
      onExpandedChange?.(next)
    }

    const toggle = () => setExpanded(!isExpanded)

    const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault()
        toggle()
      }
      onKeyDown?.(event)
    }

    const selectFeedback = (choice: HintFeedbackChoice) => {
      const next = selectedFeedback === choice ? null : choice
      if (!feedbackControlled) setLocalFeedback(next)
      if (next) onFeedback?.(next)
    }

    const indexLabel =
      hintIndex != null && hintTotal != null
        ? `Подсказка ${hintIndex} из ${hintTotal}`
        : null

    return (
      <div
        ref={ref}
        role="button"
        tabIndex={0}
        aria-expanded={isExpanded}
        aria-controls={contentId}
        className={[
          'ui-hint',
          tier ? `ui-hint--relevance-${tier}` : '',
          className,
        ]
          .filter(Boolean)
          .join(' ')}
        onMouseEnter={(event) => {
          setHoverExpanded(true)
          onMouseEnter?.(event)
        }}
        onMouseLeave={(event) => {
          setHoverExpanded(false)
          onMouseLeave?.(event)
        }}
        onFocus={(event) => {
          setHoverExpanded(true)
          onFocus?.(event)
        }}
        onBlur={(event) => {
          const next = event.relatedTarget as Node | null
          if (!next || !event.currentTarget.contains(next)) {
            setHoverExpanded(false)
          }
          onBlur?.(event)
        }}
        onClick={(event) => {
          toggle()
          onClick?.(event)
        }}
        onKeyDown={handleKeyDown}
        {...props}
      >
        <span className="ui-hint__header">
          <span className="ui-hint__titles">
            <strong className="ui-hint__title">{title}</strong>
            {indexLabel ? <small className="ui-hint__index">{indexLabel}</small> : null}
          </span>
          <StatusBadge status={badgeStatus}>{relevance}</StatusBadge>
        </span>
        <span
          id={contentId}
          className={`ui-hint__content ${isExpanded ? '' : 'ui-hint__content--compact'}`.trim()}
        >
          {children}
        </span>
        {isExpanded && suzLink?.href ? (
          <a
            className="ui-hint__suz"
            href={suzLink.href}
            target="_blank"
            rel="noreferrer"
            onClick={(event) => event.stopPropagation()}
            onMouseDown={(event) => event.stopPropagation()}
          >
            {suzLink.title} ↗
          </a>
        ) : null}
        {isExpanded && showFeedback ? (
          <div
            className="ui-hint__feedback"
            role="group"
            aria-label="Обратная связь по подсказке"
            onClick={(event) => event.stopPropagation()}
            onMouseDown={(event) => event.stopPropagation()}
          >
            {HINT_FEEDBACK_OPTIONS.map((option) => {
              const active = selectedFeedback === option.id
              return (
                <button
                  key={option.id}
                  type="button"
                  className={[
                    'ui-hint__feedback-btn',
                    `ui-hint__feedback-btn--${option.id}`,
                    active ? 'is-active' : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                  aria-pressed={active}
                  title={option.label}
                  data-testid={`hint-feedback-${option.id}`}
                  onClick={(event) => {
                    event.preventDefault()
                    event.stopPropagation()
                    selectFeedback(option.id)
                  }}
                >
                  {option.label}
                  {active ? ' ✓' : ''}
                </button>
              )
            })}
          </div>
        ) : null}
        {isExpanded && onInsert ? (
          <button
            type="button"
            className="ui-hint__insert"
            onMouseDown={(event) => {
              event.preventDefault()
              event.stopPropagation()
            }}
            onClick={(event) => {
              event.preventDefault()
              event.stopPropagation()
              onInsert()
            }}
          >
            {insertLabel}
          </button>
        ) : null}
      </div>
    )
  },
)

HintCard.displayName = 'HintCard'
