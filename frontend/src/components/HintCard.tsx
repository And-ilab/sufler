import { forwardRef, useId, useState, type ButtonHTMLAttributes } from 'react'
import { StatusBadge } from './StatusBadge'
import './components.css'

export interface HintCardProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'title' | 'onChange'> {
  title: string
  relevance?: string
  defaultExpanded?: boolean
  expanded?: boolean
  onExpandedChange?: (expanded: boolean) => void
}

export const HintCard = forwardRef<HTMLButtonElement, HintCardProps>(
  (
    {
      title,
      relevance = 'Высокая релевантность',
      children,
      defaultExpanded = false,
      expanded,
      onExpandedChange,
      className = '',
      onClick,
      ...props
    },
    ref,
  ) => {
    const [internalExpanded, setInternalExpanded] = useState(defaultExpanded)
    const contentId = useId()
    const isExpanded = expanded ?? internalExpanded

    const toggle = () => {
      const next = !isExpanded
      if (expanded === undefined) setInternalExpanded(next)
      onExpandedChange?.(next)
    }

    return (
      <button
        ref={ref}
        type="button"
        aria-expanded={isExpanded}
        aria-controls={contentId}
        className={`ui-hint ${className}`.trim()}
        onClick={(event) => {
          toggle()
          onClick?.(event)
        }}
        {...props}
      >
        <span className="ui-hint__header">
          <strong className="ui-hint__title">{title}</strong>
          <StatusBadge status="info">{relevance}</StatusBadge>
        </span>
        <span
          id={contentId}
          className={`ui-hint__content ${isExpanded ? '' : 'ui-hint__content--compact'}`.trim()}
        >
          {children}
        </span>
      </button>
    )
  },
)

HintCard.displayName = 'HintCard'
