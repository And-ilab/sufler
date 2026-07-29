import { useState } from 'react'
import { StatusBadge } from '../components'
import type { QueueItem, QueueSection } from './sessions'

export interface QueuePanelProps {
  sections: QueueSection[]
  selectedId: string
  onSelect: (item: QueueItem) => void
}

export function QueuePanel({ sections, selectedId, onSelect }: QueuePanelProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(
      sections.map((section) => [section.id, section.defaultExpanded]),
    ),
  )

  const toggle = (sectionId: string) => {
    setExpanded((current) => ({
      ...current,
      [sectionId]: !current[sectionId],
    }))
  }

  return (
    <aside className="chat-arm__queue" aria-label="Очереди диалогов" data-testid="queue-panel">
      {sections.map((section) => {
        const isOpen = expanded[section.id] ?? section.defaultExpanded
        return (
          <section
            key={section.id}
            className="chat-arm__queue-section"
            data-testid={`queue-section-${section.id}`}
          >
            <button
              type="button"
              className="chat-arm__section-title chat-arm__section-title--toggle"
              aria-expanded={isOpen}
              onClick={() => toggle(section.id)}
            >
              <span>{section.title}</span>
              <span className="chat-arm__section-count">{section.items.length}</span>
            </button>
            {isOpen ? (
              <ul className="chat-arm__queue-list">
                {section.items.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      className={`chat-arm__queue-item ${
                        item.id === selectedId ? 'chat-arm__queue-item--active' : ''
                      }`}
                      onClick={() => onSelect(item)}
                      data-testid={`queue-${item.id}`}
                    >
                      <span className="chat-arm__queue-item-head">
                        <strong>{item.name}</strong>
                        <span>{item.wait}</span>
                      </span>
                      <span className="app-muted">{item.channel}</span>
                      <span className="chat-arm__queue-preview">{item.preview}</span>
                      <span className="chat-arm__queue-badges">
                        {item.urgent ? (
                          <StatusBadge status="danger">срочно</StatusBadge>
                        ) : null}
                        {item.result === 'offline' ? (
                          <StatusBadge status="warning">офлайн</StatusBadge>
                        ) : null}
                        {item.result === 'lost' ? (
                          <StatusBadge status="neutral">потерянный</StatusBadge>
                        ) : null}
                        {item.active ? (
                          <StatusBadge status="success">активный</StatusBadge>
                        ) : null}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </section>
        )
      })}
    </aside>
  )
}
