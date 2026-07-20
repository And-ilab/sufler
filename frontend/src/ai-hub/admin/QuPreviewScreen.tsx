import { useState, type FormEvent } from 'react'
import { Button, Card, StatusBadge } from '../../components'
import {
  previewQuQuery,
  type QuPreviewResult,
} from './api/quPreview'

export function QuPreviewScreen() {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<QuPreviewResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!query.trim() || loading) return
    setLoading(true)
    setError('')
    try {
      setResult(await previewQuQuery(query.trim()))
    } catch (requestError) {
      setResult(null)
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Не удалось выполнить Preview',
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="qu-preview" data-testid="qu-preview-form">
      <Card className="qu-preview__query-card">
        <header>
          <div>
            <h2>Тестовый запрос</h2>
            <p>Проверьте ранжирование QU без публикации и развёртывания кода.</p>
          </div>
          <StatusBadge status="info">FR-UND-12</StatusBadge>
        </header>
        <form onSubmit={(event) => void submit(event)}>
          <label>
            <span>Запрос пользователя</span>
            <textarea
              aria-label="Запрос пользователя"
              value={query}
              rows={4}
              placeholder="Например: оформление отпуска сотруднику"
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <div className="qu-preview__actions">
            <span>Индекс: <strong>cc_production</strong></span>
            <Button type="submit" disabled={!query.trim() || loading}>
              {loading ? 'Поиск…' : 'Preview'}
            </Button>
          </div>
        </form>
      </Card>

      {error && (
        <Card className="qu-preview__error" role="alert">
          <strong>QU Preview недоступен</strong>
          <span>{error}</span>
        </Card>
      )}

      {result && (
        <Card className="qu-preview__results">
          <header>
            <div>
              <h2>Найденные документы</h2>
              <p>Результаты отсортированы по релевантности запросу.</p>
            </div>
            <StatusBadge status="neutral">
              Мин. порог {result.min_relevance_percent}%
            </StatusBadge>
          </header>
          {result.documents.length ? (
            <div className="qu-preview__table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Документ</th>
                    <th scope="col">Релевантность</th>
                    <th scope="col">Совпавший пример</th>
                  </tr>
                </thead>
                <tbody>
                  {result.documents.map((document) => (
                    <tr key={`${document.article_id}-${document.chunk_index}`}>
                      <td>
                        <span className="qu-preview__rank">{document.rank}</span>
                        {document.permalink ? (
                          <a href={document.permalink} target="_blank" rel="noreferrer">
                            {document.title}
                          </a>
                        ) : document.title}
                        <small>{document.snippet}</small>
                      </td>
                      <td>
                        <StatusBadge
                          status={document.meets_min_relevance ? 'success' : 'warning'}
                        >
                          {document.relevance_percent}%
                        </StatusBadge>
                      </td>
                      <td>{document.matched_example}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="qu-preview__empty">
              В активном индексе нет документов для этого запроса.
            </p>
          )}
        </Card>
      )}
    </div>
  )
}
