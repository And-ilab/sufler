import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
} from 'react'
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
  type StatusBadgeStatus,
} from '../../components'
import {
  getAsrSession,
  listAsrSessions,
  seedAsrDemo,
  setTrainingCandidate,
  type AsrCatalogueStats,
  type AsrChannel,
  type AsrSessionDetail,
  type AsrSessionFilters,
  type AsrSessionSummary,
  type AsrUtterance,
  type RecognitionStatus,
} from './api/asrQa'
import './AsrQa.css'

function formatDateTime(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatDuration(sec: number): string {
  const minutes = Math.floor(sec / 60)
  const seconds = sec % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

function formatConfidence(value: number): string {
  return `${Math.round(value * 100)}%`
}

function channelLabel(channel: AsrChannel): string {
  return channel === 'telephony' ? 'Телефония' : 'Онлайн-чат'
}

function statusMeta(
  status: RecognitionStatus,
): { label: string; badge: StatusBadgeStatus } {
  if (status === 'recognized') return { label: 'Распознано', badge: 'success' }
  if (status === 'unrecognized') return { label: 'Не распознано', badge: 'danger' }
  return { label: 'Частично', badge: 'warning' }
}

function speakerLabel(speaker: AsrUtterance['speaker']): string {
  return speaker === 'operator' ? 'Оператор' : 'Клиент'
}

const EMPTY_STATS: AsrCatalogueStats = {
  total: 0,
  recognized: 0,
  unrecognized: 0,
  partial: 0,
  training_candidates: 0,
  low_confidence: 0,
}

export function AsrQaScreen() {
  const [filters, setFilters] = useState<AsrSessionFilters>({
    channel: '',
    operator: '',
    recognition_status: '',
    low_confidence_only: false,
  })
  const [draft, setDraft] = useState(filters)
  const [items, setItems] = useState<AsrSessionSummary[]>([])
  const [stats, setStats] = useState<AsrCatalogueStats>(EMPTY_STATS)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [detail, setDetail] = useState<AsrSessionDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [currentMs, setCurrentMs] = useState(0)
  const [activeUtteranceId, setActiveUtteranceId] = useState<number | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const loadCatalogue = useCallback(async (nextFilters: AsrSessionFilters) => {
    setLoading(true)
    setError('')
    try {
      let response = await listAsrSessions(nextFilters)
      const unfilteredEmpty =
        response.stats.total === 0
        && !nextFilters.channel
        && !nextFilters.operator
        && !nextFilters.recognition_status
        && !nextFilters.low_confidence_only
        && !nextFilters.date_from
        && !nextFilters.date_to
      if (unfilteredEmpty) {
        await seedAsrDemo(true)
        response = await listAsrSessions(nextFilters)
      }
      setItems(response.items)
      setStats(response.stats)
      const preferId =
        selectedId != null && response.items.some((item) => item.id === selectedId)
          ? selectedId
          : response.items[0]?.id ?? null
      setSelectedId(preferId)
      if (preferId == null) {
        setDetail(null)
      } else {
        setDetail(await getAsrSession(preferId))
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Не удалось загрузить каталог ASR',
      )
    } finally {
      setLoading(false)
    }
  }, [selectedId])

  useEffect(() => {
    void loadCatalogue(filters)
    // Initial load only; subsequent refreshes go through applyFilters / select.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const applyFilters = async (event: FormEvent) => {
    event.preventDefault()
    setFilters(draft)
    await loadCatalogue(draft)
  }

  const selectSession = async (id: number) => {
    setSelectedId(id)
    setError('')
    setBusy(true)
    setCurrentMs(0)
    setActiveUtteranceId(null)
    try {
      setDetail(await getAsrSession(id))
      if (audioRef.current) {
        audioRef.current.currentTime = 0
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Не удалось открыть карточку записи',
      )
    } finally {
      setBusy(false)
    }
  }

  const syncFromAudio = () => {
    const audio = audioRef.current
    if (!audio || !detail) return
    const ms = Math.round(audio.currentTime * 1000)
    setCurrentMs(ms)
    const active = detail.utterances.find(
      (utterance) => ms >= utterance.start_ms && ms < utterance.end_ms,
    )
    setActiveUtteranceId(active?.id ?? null)
  }

  const seekToUtterance = (utterance: AsrUtterance) => {
    const audio = audioRef.current
    if (!audio) return
    audio.currentTime = utterance.start_ms / 1000
    setCurrentMs(utterance.start_ms)
    setActiveUtteranceId(utterance.id)
    void audio.play().catch(() => undefined)
  }

  const toggleTraining = async (utterance: AsrUtterance) => {
    if (!detail) return
    setBusy(true)
    setError('')
    try {
      const result = await setTrainingCandidate(
        detail.id,
        utterance.id,
        !utterance.training_candidate,
      )
      setDetail({
        ...detail,
        has_training_candidate: result.session.has_training_candidate,
        utterances: detail.utterances.map((item) =>
          item.id === utterance.id ? result.utterance : item,
        ),
      })
      setItems((current) =>
        current.map((item) =>
          item.id === detail.id
            ? { ...item, has_training_candidate: result.session.has_training_candidate }
            : item,
        ),
      )
      setStats((current) => ({
        ...current,
        training_candidates: result.session.has_training_candidate
          ? Math.max(current.training_candidates, 1)
          : current.training_candidates,
      }))
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Не удалось сохранить учебный пример',
      )
    } finally {
      setBusy(false)
    }
  }

  const selectedMeta = useMemo(
    () => (detail ? statusMeta(detail.recognition_status) : null),
    [detail],
  )

  if (loading) {
    return <Card className="asr-qa-loading">Загрузка QA-каталога ASR…</Card>
  }

  return (
    <div className="asr-qa">
      <div className="asr-qa__stats admin-stats">
        <Card>
          <strong>{stats.total}</strong>
          <span>Все записи</span>
        </Card>
        <Card>
          <strong>{stats.recognized}</strong>
          <span>Распознано</span>
        </Card>
        <Card>
          <strong>{stats.partial + stats.unrecognized}</strong>
          <span>Проблемные</span>
        </Card>
        <Card>
          <strong>{stats.training_candidates}</strong>
          <span>Учебные примеры</span>
        </Card>
      </div>

      {error ? (
        <Card className="asr-qa__error" role="alert">
          {error}
        </Card>
      ) : null}

      <Card className="asr-qa__filters">
        <form className="asr-qa__filters-form" onSubmit={applyFilters}>
          <label>
            Канал
            <select
              value={draft.channel ?? ''}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  channel: event.target.value as AsrChannel | '',
                }))
              }
            >
              <option value="">Все</option>
              <option value="telephony">Телефония</option>
              <option value="online_chat">Онлайн-чат</option>
            </select>
          </label>
          <label>
            Оператор
            <input
              value={draft.operator ?? ''}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  operator: event.target.value,
                }))
              }
              placeholder="ФИО или ID"
            />
          </label>
          <label>
            Статус
            <select
              value={draft.recognition_status ?? ''}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  recognition_status: event.target.value as RecognitionStatus | '',
                }))
              }
            >
              <option value="">Все</option>
              <option value="recognized">Распознано</option>
              <option value="partial">Частично</option>
              <option value="unrecognized">Не распознано</option>
            </select>
          </label>
          <label className="asr-qa__checkbox">
            <input
              type="checkbox"
              checked={Boolean(draft.low_confidence_only)}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  low_confidence_only: event.target.checked,
                }))
              }
            />
            Только низкая уверенность
          </label>
          <Button type="submit" disabled={busy}>
            Применить фильтры
          </Button>
        </form>
        <p className="asr-qa__hint">
          По умолчанию каталог показывает все записи. Фильтр низкой уверенности —
          опциональный (FR-ASR-10 / комм. [55]).
        </p>
      </Card>

      <div className="asr-qa__layout">
        <Card className="asr-qa__catalog" padded={false}>
          <div className="asr-qa__section-title">Каталог записей</div>
          {items.length === 0 ? (
            <p className="asr-qa__empty">Нет записей по выбранным фильтрам.</p>
          ) : (
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Дата / время</TableHeaderCell>
                  <TableHeaderCell>Канал</TableHeaderCell>
                  <TableHeaderCell>Оператор</TableHeaderCell>
                  <TableHeaderCell>ID сессии</TableHeaderCell>
                  <TableHeaderCell>Длит.</TableHeaderCell>
                  <TableHeaderCell>Confidence</TableHeaderCell>
                  <TableHeaderCell>Статус</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.map((item) => {
                  const meta = statusMeta(item.recognition_status)
                  return (
                    <TableRow
                      key={item.id}
                      role="button"
                      tabIndex={0}
                      data-selected={item.id === selectedId ? 'true' : 'false'}
                      onClick={() => void selectSession(item.id)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          void selectSession(item.id)
                        }
                      }}
                    >
                      <TableCell>{formatDateTime(item.started_at)}</TableCell>
                      <TableCell>{channelLabel(item.channel)}</TableCell>
                      <TableCell>
                        <strong>{item.operator_name || item.operator_id}</strong>
                        <small>{item.operator_id}</small>
                      </TableCell>
                      <TableCell>{item.session_id}</TableCell>
                      <TableCell>{formatDuration(item.duration_sec)}</TableCell>
                      <TableCell>{formatConfidence(item.avg_confidence)}</TableCell>
                      <TableCell>
                        <StatusBadge status={meta.badge}>{meta.label}</StatusBadge>
                        {item.has_training_candidate ? (
                          <StatusBadge status="info">Учебный</StatusBadge>
                        ) : null}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </Card>

        <Card className="asr-qa__detail">
          {!detail || !selectedMeta ? (
            <p className="asr-qa__empty">Выберите запись в каталоге.</p>
          ) : (
            <>
              <header className="asr-qa__detail-header">
                <div>
                  <p className="app-eyebrow">Карточка записи ASR</p>
                  <h2>{detail.session_id}</h2>
                  <p className="app-muted">
                    {formatDateTime(detail.started_at)} · {channelLabel(detail.channel)} ·{' '}
                    {detail.operator_name}
                  </p>
                </div>
                <StatusBadge status={selectedMeta.badge}>
                  {selectedMeta.label}
                </StatusBadge>
              </header>

              <dl className="asr-qa__meta">
                <div>
                  <dt>Оператор</dt>
                  <dd>{detail.operator_name || detail.operator_id}</dd>
                </div>
                <div>
                  <dt>Длительность</dt>
                  <dd>{formatDuration(detail.duration_sec)}</dd>
                </div>
                <div>
                  <dt>Confidence</dt>
                  <dd>
                    avg {formatConfidence(detail.avg_confidence)} / min{' '}
                    {formatConfidence(detail.min_confidence)}
                  </dd>
                </div>
              </dl>

              {detail.channel === 'telephony' && detail.audio_url ? (
                <div className="asr-qa__player">
                  <div className="asr-qa__section-title">Аудио</div>
                  <audio
                    ref={audioRef}
                    controls
                    src={detail.audio_url}
                    onTimeUpdate={syncFromAudio}
                    onSeeked={syncFromAudio}
                    preload="metadata"
                  />
                  <p className="app-muted">
                    Текущая позиция: {(currentMs / 1000).toFixed(1)} с — подсветка
                    синхронизирована с транскриптом.
                  </p>
                </div>
              ) : (
                <div className="asr-qa__player">
                  <div className="asr-qa__section-title">Лента чата</div>
                  <p className="app-muted">
                    Для онлайн-чата аудио недоступно — используйте транскрипт ниже.
                  </p>
                </div>
              )}

              <div className="asr-qa__transcript">
                <div className="asr-qa__section-title">Транскрипт</div>
                {detail.utterances.length === 0 ? (
                  <p className="asr-qa__empty">Транскрипт отсутствует.</p>
                ) : (
                  <ul className="asr-qa__utterances">
                    {detail.utterances.map((utterance) => {
                      const active = utterance.id === activeUtteranceId
                      return (
                        <li
                          key={utterance.id}
                          className={[
                            'asr-qa__utterance',
                            utterance.low_confidence ? 'asr-qa__utterance--low' : '',
                            active ? 'asr-qa__utterance--active' : '',
                          ]
                            .filter(Boolean)
                            .join(' ')}
                        >
                          <button
                            type="button"
                            className="asr-qa__utterance-main"
                            onClick={() => seekToUtterance(utterance)}
                          >
                            <span className="asr-qa__utterance-meta">
                              <strong>{speakerLabel(utterance.speaker)}</strong>
                              <span>{formatConfidence(utterance.confidence)}</span>
                              <span>
                                {(utterance.start_ms / 1000).toFixed(1)}–
                                {(utterance.end_ms / 1000).toFixed(1)} с
                              </span>
                            </span>
                            <span className="asr-qa__utterance-text">
                              {utterance.text || '«не распознано»'}
                            </span>
                          </button>
                          <Button
                            type="button"
                            variant={utterance.training_candidate ? 'secondary' : 'ghost'}
                            disabled={busy}
                            onClick={() => void toggleTraining(utterance)}
                          >
                            {utterance.training_candidate
                              ? 'Учебный пример ✓'
                              : 'Пометить учебным'}
                          </Button>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </div>
            </>
          )}
        </Card>
      </div>
    </div>
  )
}
