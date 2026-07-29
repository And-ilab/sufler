import {
  forwardRef,
  useId,
  useState,
  type HTMLAttributes,
  type KeyboardEvent,
  type ReactNode,
} from 'react'
import { StatusBadge, type StatusBadgeStatus } from './StatusBadge'
import './components.css'

export interface HintSuzLink {
  title: string
  href: string
}

export interface HintCardProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title' | 'onChange'> {
  title: string
  relevance?: string
  relevanceStatus?: StatusBadgeStatus
  suzLink?: HintSuzLink | null
  defaultExpanded?: boolean
  expanded?: boolean
  onExpandedChange?: (expanded: boolean) => void
  onInsert?: () => void
  insertLabel?: string
  children?: ReactNode
}

export const HintCard = forwardRef<HTMLDivElement, HintCardProps>(
  (
    {
      title,
      relevance = 'Высокая релевантность',
      relevanceStatus = 'info',
      suzLink = null,
      children,
      defaultExpanded = false,
      expanded,
      onExpandedChange,
      onInsert,
      insertLabel = 'Вставить в ответ',
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
    const contentId = useId()
    const isExpanded = expanded ?? (internalExpanded || hoverExpanded)

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

    return (
      <div
        ref={ref}
        role="button"
        tabIndex={0}
        aria-expanded={isExpanded}
        aria-controls={contentId}
        className={`ui-hint ${className}`.trim()}
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
          <strong className="ui-hint__title">{title}</strong>
          <StatusBadge status={relevanceStatus}>{relevance}</StatusBadge>
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
