import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useMemo,
  useState,
} from 'react'
import { Card, StatusBadge } from '../../components'
import {
  loadModelParams,
  ModelParamsApiError,
  saveModelParams,
  type ModelParamsData,
  type ModelParamsPayload,
  type ModelParamsProfile,
} from './api/modelRegistry'
import type { AdminProfile } from './adminNav'

export interface ModelParamsScreenHandle {
  save: () => Promise<boolean>
  reset: () => void
}

interface ModelParamsScreenProps {
  profile: AdminProfile
  canEdit: boolean
  initialData?: ModelParamsData
  onStateChange: (state: {
    dirty: boolean
    valid: boolean
    saving: boolean
    message: string
  }) => void
}

type FieldErrors = Record<string, string>

function apiProfile(profile: AdminProfile): ModelParamsProfile {
  return profile === 'cc' ? 'sufler_cc' : 'assistant_bank'
}

function editablePayload(data: ModelParamsData): ModelParamsPayload {
  return {
    generation: { ...data.generation },
    rag: { ...data.rag },
  }
}

function validate(
  form: ModelParamsPayload,
  data: ModelParamsData,
): FieldErrors {
  const errors: FieldErrors = {}
  const temperature = data.constraints.temperature
  if (
    form.generation.temperature < temperature.min
    || form.generation.temperature > temperature.max
  ) {
    errors.temperature = `Допустимо: ${temperature.min}–${temperature.max}`
  }
  if (form.generation.top_p <= 0 || form.generation.top_p > 1) {
    errors.top_p = 'Значение должно быть больше 0 и не больше 1'
  }
  if (
    form.generation.max_tokens < 1
    || form.generation.max_tokens > data.constraints.max_tokens.max
  ) {
    errors.max_tokens = `Допустимо: 1–${data.constraints.max_tokens.max}`
  }
  if (
    form.generation.response_chars_max < 1
    || form.generation.response_chars_max > 500
  ) {
    errors.response_chars_max = 'Максимум 500 символов'
  }
  if (form.rag.chunk_size_tokens <= 0) {
    errors.chunk_size_tokens = 'Размер chunk должен быть положительным'
  }
  if (
    form.rag.chunk_overlap_tokens < 0
    || form.rag.chunk_overlap_tokens >= form.rag.chunk_size_tokens
  ) {
    errors.chunk_overlap_tokens = 'Overlap должен быть меньше размера chunk'
  }
  for (const [field, value] of [
    ['context_inclusion', form.rag.context_inclusion],
    ['deterministic_answer', form.rag.deterministic_answer],
  ] as const) {
    if (value < 0 || value > 1) {
      errors[field] = 'Порог должен быть от 0 до 1'
    }
  }
  if (form.rag.context_inclusion > form.rag.deterministic_answer) {
    errors.deterministic_answer = 'Не может быть ниже порога включения'
  }
  return errors
}

export const ModelParamsScreen = forwardRef<
  ModelParamsScreenHandle,
  ModelParamsScreenProps
>(({ profile, canEdit, initialData, onStateChange }, ref) => {
  const selectedProfile = apiProfile(profile)
  const [data, setData] = useState<ModelParamsData | null>(null)
  const [form, setForm] = useState<ModelParamsPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [serverErrors, setServerErrors] = useState<FieldErrors>({})
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (initialData && initialData.profile === selectedProfile) {
      setData(initialData)
      setForm(editablePayload(initialData))
      setLoading(false)
      setLoadError('')
      return
    }
    let active = true
    setLoading(true)
    setLoadError('')
    void loadModelParams(selectedProfile)
      .then((loaded) => {
        if (!active) return
        setData(loaded)
        setForm(editablePayload(loaded))
        setMessage('')
      })
      .catch((error: unknown) => {
        if (!active) return
        setLoadError(
          error instanceof Error ? error.message : 'Не удалось загрузить настройки',
        )
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [initialData, selectedProfile])

  const clientErrors = useMemo(
    () => form && data ? validate(form, data) : {},
    [data, form],
  )
  const errors = { ...serverErrors, ...clientErrors }
  const dirty = Boolean(
    data && form && JSON.stringify(form) !== JSON.stringify(editablePayload(data)),
  )
  const valid = Boolean(form && data && Object.keys(errors).length === 0)

  useEffect(() => {
    onStateChange({ dirty, valid, saving, message })
  }, [dirty, message, onStateChange, saving, valid])

  const save = async (): Promise<boolean> => {
    if (!form || !data || !canEdit || !valid) return false
    setSaving(true)
    setServerErrors({})
    setMessage('')
    try {
      const saved = await saveModelParams(selectedProfile, form)
      setData(saved)
      setForm(editablePayload(saved))
      setMessage(`Сохранено · revision ${saved.revision}`)
      return true
    } catch (error) {
      if (error instanceof ModelParamsApiError) {
        setServerErrors(
          Object.fromEntries(
            Object.entries(error.details).map(([field, values]) => [
              field.replace('_threshold', ''),
              values.join(' '),
            ]),
          ),
        )
        setMessage('Исправьте ошибки формы')
      } else {
        setMessage('Не удалось сохранить настройки')
      }
      return false
    } finally {
      setSaving(false)
    }
  }

  const reset = () => {
    if (!data) return
    setForm(editablePayload(data))
    setServerErrors({})
    setMessage('')
  }

  useImperativeHandle(ref, () => ({ save, reset }))

  if (loading) {
    return <Card className="model-params-loading" aria-busy="true">Загрузка ModelRegistry…</Card>
  }
  if (loadError || !data || !form) {
    return (
      <Card className="model-params-error" role="alert">
        <strong>ModelRegistry недоступен</strong>
        <span>{loadError || 'Пустой ответ API'}</span>
      </Card>
    )
  }

  const setGeneration = (
    field: keyof ModelParamsPayload['generation'],
    value: number,
  ) => {
    setServerErrors({})
    setForm((current) => current && ({
      ...current,
      generation: { ...current.generation, [field]: value },
    }))
  }
  const setRag = (
    field: keyof ModelParamsPayload['rag'],
    value: number,
  ) => {
    setServerErrors({})
    setForm((current) => current && ({
      ...current,
      rag: { ...current.rag, [field]: value },
    }))
  }

  return (
    <div className="model-params" data-testid="model-params-form">
      <section className="model-params__summary">
        <Card>
          <span>Dev model</span>
          <strong>{data.read_only.dev_model ?? 'Не назначена'}</strong>
          <small>Slot: {data.slot}</small>
        </Card>
        <Card>
          <span>Статус</span>
          <StatusBadge status="success">{data.read_only.status}</StatusBadge>
          <small>Revision {data.revision}</small>
        </Card>
        <Card>
          <span>Production candidate</span>
          <strong>{data.read_only.prod_candidate ?? 'Не утверждён'}</strong>
          <small>Только после human SIGNOFF</small>
        </Card>
      </section>

      <Card className="model-params__section">
        <header>
          <div>
            <h2>Генерация ответа</h2>
            <p>Параметры профиля {data.profile}; изменения сохраняются в БД.</p>
          </div>
          <StatusBadge status="info">{data.profile}</StatusBadge>
        </header>
        <div className="model-params__fields">
          <label className="model-params__slider">
            <span>Temperature <output>{form.generation.temperature.toFixed(2)}</output></span>
            <input
              aria-label="Temperature"
              type="range"
              min={data.constraints.temperature.min}
              max={data.constraints.temperature.max}
              step={data.constraints.temperature.step}
              value={form.generation.temperature}
              disabled={!canEdit}
              onChange={(event) => setGeneration('temperature', Number(event.target.value))}
            />
            {errors.temperature && <small role="alert">{errors.temperature}</small>}
          </label>
          <label className="model-params__slider">
            <span>Top P <output>{form.generation.top_p.toFixed(2)}</output></span>
            <input
              aria-label="Top P"
              type="range"
              min={data.constraints.top_p.min}
              max={data.constraints.top_p.max}
              step={data.constraints.top_p.step}
              value={form.generation.top_p}
              disabled={!canEdit}
              onChange={(event) => setGeneration('top_p', Number(event.target.value))}
            />
            {errors.top_p && <small role="alert">{errors.top_p}</small>}
          </label>
          <NumberField label="Max tokens" value={form.generation.max_tokens} error={errors.max_tokens} disabled={!canEdit} onChange={(value) => setGeneration('max_tokens', value)} />
          <NumberField label="Максимум символов ответа" value={form.generation.response_chars_max} error={errors.response_chars_max} disabled={!canEdit} onChange={(value) => setGeneration('response_chars_max', value)} />
        </div>
      </Card>

      <Card className="model-params__section">
        <header>
          <div>
            <h2>Chunking и retrieval</h2>
            <p>Калибровка фрагментов и порогов включения контекста.</p>
          </div>
          <StatusBadge status="warning">kb_cc_production</StatusBadge>
        </header>
        <div className="model-params__fields">
          <NumberField label="Chunk size, tokens" value={form.rag.chunk_size_tokens} error={errors.chunk_size_tokens} disabled={!canEdit} onChange={(value) => setRag('chunk_size_tokens', value)} />
          <NumberField label="Chunk overlap, tokens" value={form.rag.chunk_overlap_tokens} error={errors.chunk_overlap_tokens} disabled={!canEdit} onChange={(value) => setRag('chunk_overlap_tokens', value)} />
          <NumberField label="Context inclusion" value={form.rag.context_inclusion} error={errors.context_inclusion} disabled={!canEdit} step={0.01} onChange={(value) => setRag('context_inclusion', value)} />
          <NumberField label="Deterministic answer" value={form.rag.deterministic_answer} error={errors.deterministic_answer} disabled={!canEdit} step={0.01} onChange={(value) => setRag('deterministic_answer', value)} />
        </div>
      </Card>
    </div>
  )
})

ModelParamsScreen.displayName = 'ModelParamsScreen'

function NumberField({
  label,
  value,
  error,
  disabled,
  step = 1,
  onChange,
}: {
  label: string
  value: number
  error?: string
  disabled: boolean
  step?: number
  onChange: (value: number) => void
}) {
  return (
    <label className={error ? 'model-params__field model-params__field--error' : 'model-params__field'}>
      <span>{label}</span>
      <input
        type="number"
        value={value}
        step={step}
        disabled={disabled}
        aria-invalid={Boolean(error)}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      {error && <small role="alert">{error}</small>}
    </label>
  )
}
