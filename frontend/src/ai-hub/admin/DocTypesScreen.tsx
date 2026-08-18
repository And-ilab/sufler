import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Button, Card, StatusBadge } from '../../components'
import {
  listOcrTemplates,
  saveOcrTemplate,
  updateOcrTemplate,
  uploadTemplateSample,
  type OcrTemplate,
} from './api/ocrAdmin'
import './DocTypesScreen.css'

interface DocTypesScreenProps {
  canEdit?: boolean
}

const EMPTY_FORM = {
  doc_type: 'passport',
  title: 'Удостоверение личности / паспорт',
  description: '',
  required_fields: 'full_name, series, number, issue_date',
  confidence_min: '0.6',
  sample_prompt: '',
  field_schema_json: JSON.stringify(
    {
      full_name: { type: 'string', min_length: 3, max_length: 200 },
      series: { type: 'string', pattern: '^[A-ZА-Я]{2}$' },
      number: { type: 'string', pattern: '^\\d{7}$' },
      issue_date: { type: 'date', formats: ['%d.%m.%Y', '%Y-%m-%d'] },
    },
    null,
    2,
  ),
}

export function DocTypesScreen({ canEdit = true }: DocTypesScreenProps) {
  const [items, setItems] = useState<OcrTemplate[]>([])
  const [selected, setSelected] = useState<string>('passport')
  const [form, setForm] = useState(EMPTY_FORM)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [sampleFile, setSampleFile] = useState<File | null>(null)

  const reload = useCallback(async () => {
    setError('')
    try {
      const next = await listOcrTemplates()
      setItems(next)
      if (next.length && !next.some((item) => item.doc_type === selected)) {
        setSelected(next[0].doc_type)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось загрузить шаблоны')
    }
  }, [selected])

  useEffect(() => {
    void reload()
  }, [reload])

  useEffect(() => {
    const current = items.find((item) => item.doc_type === selected)
    if (!current) return
    setForm({
      doc_type: current.doc_type,
      title: current.title,
      description: current.description || '',
      required_fields: (current.required_fields || []).join(', '),
      confidence_min: String(current.confidence_min ?? 0.6),
      sample_prompt: current.sample_prompt || '',
      field_schema_json: JSON.stringify(current.field_schema || {}, null, 2),
    })
  }, [items, selected])

  const active = items.find((item) => item.doc_type === selected)

  const onSave = async (event: FormEvent, publish = false) => {
    event.preventDefault()
    if (!canEdit) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      let fieldSchema: Record<string, unknown> = {}
      try {
        fieldSchema = JSON.parse(form.field_schema_json) as Record<string, unknown>
      } catch {
        throw new Error('field_schema должен быть валидным JSON')
      }
      const payload = {
        doc_type: form.doc_type.trim(),
        title: form.title.trim(),
        description: form.description,
        required_fields: form.required_fields
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
        confidence_min: Number(form.confidence_min),
        sample_prompt: form.sample_prompt,
        field_schema: fieldSchema,
        publish,
        bump_version: publish,
      }
      const saved = items.some((item) => item.doc_type === payload.doc_type)
        ? await updateOcrTemplate(payload.doc_type, payload)
        : await saveOcrTemplate(payload)
      setMessage(
        publish
          ? `Шаблон ${saved.doc_type} опубликован (v${saved.template_version})`
          : `Шаблон ${saved.doc_type} сохранён`,
      )
      setSelected(saved.doc_type)
      await reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка сохранения')
    } finally {
      setBusy(false)
    }
  }

  const onUploadSample = async () => {
    if (!canEdit || !sampleFile || !selected) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const result = await uploadTemplateSample(selected, sampleFile)
      setMessage(
        `Образец «${sampleFile.name}» загружен`
          + (result.recognition ? ' и прогнан через OCR' : ''),
      )
      setSampleFile(null)
      await reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка загрузки образца')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="doc-types" data-testid="doc-types-screen">
      <section className="doc-types__list" aria-label="Типы документов">
        {items.map((item) => (
          <button
            type="button"
            key={item.doc_type}
            className={item.doc_type === selected ? 'is-active' : undefined}
            onClick={() => setSelected(item.doc_type)}
            data-testid={`doc-type-${item.doc_type}`}
          >
            <strong>{item.title}</strong>
            <span>{item.doc_type}</span>
            <StatusBadge status={item.status === 'published' ? 'success' : 'neutral'}>
              v{item.template_version} · {item.status}
            </StatusBadge>
          </button>
        ))}
      </section>

      <Card className="doc-types__editor">
        <header>
          <div>
            <h2>Шаблон OCR</h2>
            <p>
              Админ задаёт поля, порог confidence и обучающие образцы.
              Публикация создаёт новую версию шаблона.
            </p>
          </div>
          {active ? (
            <StatusBadge status="info">
              образцов: {active.sample_count ?? active.samples?.length ?? 0}
            </StatusBadge>
          ) : null}
        </header>

        <form className="doc-types__form" onSubmit={(event) => void onSave(event, false)}>
          <label>
            <span>Код типа</span>
            <input
              value={form.doc_type}
              disabled={!canEdit || busy}
              onChange={(event) => setForm((prev) => ({ ...prev, doc_type: event.target.value }))}
              data-testid="doc-type-code"
            />
          </label>
          <label>
            <span>Название</span>
            <input
              value={form.title}
              disabled={!canEdit || busy}
              onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
            />
          </label>
          <label>
            <span>Обязательные поля (через запятую)</span>
            <input
              value={form.required_fields}
              disabled={!canEdit || busy}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, required_fields: event.target.value }))
              }
            />
          </label>
          <label>
            <span>Порог confidence</span>
            <input
              type="number"
              min={0}
              max={1}
              step={0.01}
              value={form.confidence_min}
              disabled={!canEdit || busy}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, confidence_min: event.target.value }))
              }
            />
          </label>
          <label className="doc-types__wide">
            <span>Описание</span>
            <textarea
              rows={2}
              value={form.description}
              disabled={!canEdit || busy}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, description: event.target.value }))
              }
            />
          </label>
          <label className="doc-types__wide">
            <span>Пример OCR-текста (обучение)</span>
            <textarea
              rows={4}
              value={form.sample_prompt}
              disabled={!canEdit || busy}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, sample_prompt: event.target.value }))
              }
              placeholder={'ПАСПОРТ\nФамилия: ИВАНОВ\nИмя: ИВАН\nСерия: MP\nНомер: 4123456\nДата выдачи: 12.03.2019'}
            />
          </label>
          <label className="doc-types__wide">
            <span>JSON schema полей</span>
            <textarea
              rows={10}
              value={form.field_schema_json}
              disabled={!canEdit || busy}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, field_schema_json: event.target.value }))
              }
              data-testid="doc-type-schema"
            />
          </label>

          <div className="doc-types__actions">
            <Button type="submit" disabled={!canEdit || busy}>
              Сохранить черновик
            </Button>
            <Button
              type="button"
              disabled={!canEdit || busy}
              onClick={(event) => void onSave(event as unknown as FormEvent, true)}
              data-testid="doc-type-publish"
            >
              Опубликовать версию
            </Button>
          </div>
        </form>

        <section className="doc-types__train" aria-label="Обучение на образце">
          <h3>Обучение на образце</h3>
          <p>Загрузите скан/фото — система прогонит OCR и сохранит поля как эталон шаблона.</p>
          <div className="doc-types__train-row">
            <input
              type="file"
              accept=".pdf,.jpg,.jpeg,.png,.tiff,.tif,.txt"
              disabled={!canEdit || busy}
              onChange={(event) => setSampleFile(event.target.files?.[0] || null)}
              data-testid="doc-type-sample-input"
            />
            <Button
              type="button"
              disabled={!canEdit || busy || !sampleFile}
              onClick={() => void onUploadSample()}
            >
              Загрузить образец
            </Button>
          </div>
          {active?.samples?.length ? (
            <ul className="doc-types__samples">
              {active.samples.map((sample) => (
                <li key={sample.id}>
                  <strong>{sample.filename}</strong>
                  <span>{Object.keys(sample.expected_fields || {}).join(', ') || 'без полей'}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </section>

        {error ? <p className="doc-types__error" role="alert">{error}</p> : null}
        {message ? <p className="doc-types__ok" role="status">{message}</p> : null}
      </Card>
    </div>
  )
}
