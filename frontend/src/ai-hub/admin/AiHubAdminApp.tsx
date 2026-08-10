import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent,
} from 'react'
import { ensureDevSession } from '../../auth/ensureDevSession'
import { Button, Card, StatusBadge } from '../../components'
import {
  ModelParamsScreen,
  type ModelParamsScreenHandle,
} from './ModelParamsScreen'
import { QuPreviewScreen } from './QuPreviewScreen'
import { KbAdminScreen } from './KbAdminScreen'
import { PromptsAssistantScreen } from './PromptsAssistantScreen'
import { CapabilitiesScreen } from './CapabilitiesScreen'
import type { ModelParamsData } from './api/modelRegistry'
import {
  ADMIN_GROUPS,
  ADMIN_NAV,
  adminRoute,
  resolveAdminRoute,
  type AdminNavItem,
  type AdminProfile,
  type AdminScreen,
  type DemoAdminRole,
} from './adminNav'
import './AiHubAdmin.css'

interface AiHubAdminAppProps {
  roles: readonly string[]
  initialScreen?: AdminScreen
  initialProfile?: AdminProfile
  initialModelParams?: ModelParamsData
  demoRoleSwitcher?: boolean
}

interface ScreenCopy {
  title: string
  subtitle: string
  status: string
  cards: readonly [string, string, string][]
}

const SCREEN_COPY: Record<AdminScreen, ScreenCopy> = {
  audit: {
    title: 'Подразделения и журнал',
    subtitle: 'Область подразделений, роли и единый журнал изменений настроек.',
    status: 'Аудит включён',
    cards: [['Подразделения', '12', 'Активные области'], ['Изменения', '28', 'За последние 7 дней'], ['Ожидают проверки', '3', 'Запросы доступа']],
  },
  llm_config_assistant: {
    title: 'Конфигурация LLM',
    subtitle: 'Профиль ассистента банка, резервная модель и контроль доступности.',
    status: 'Утверждено (тест)',
    cards: [
      ['Основная модель', 'stub-assistant-bank', 'Реестр моделей'],
      ['Резервная модель', 'Включён', 'Совместимо с OpenAI'],
      ['Доступность', '99.9%', 'Последние 24 часа'],
    ],
  },
  model_params: {
    title: 'Параметры модели LLM',
    subtitle: 'Пресет генерации, лимиты ответа и параметры семантики.',
    status: 'Черновик',
    cards: [['Температура', '0.20', 'Диапазон 0–1'], ['Макс. токенов', '1024', 'Контекст 8k'], ['Top P', '0.90', 'Профиль модели']],
  },
  prompts_assistant: {
    title: 'Промпты ассистента',
    subtitle: 'Библиотека системных, рабочих и областных промптов профиля ассистента.',
    status: 'Редактирование',
    cards: [['Промпты', 'assistant_*', 'Отдельно от КЦ'], ['Студия', '3 колонки', 'Библиотека · Редактор · Просмотр'], ['Публикация', 'черновик → vN', 'Журнал «Общее»']],
  },
  capabilities: {
    title: 'Навыки и инструменты',
    subtitle: 'Реестр навыков: поиск по БЗ, RPA, SQL, перевод — переключатели и ссылки.',
    status: 'Черновой реестр',
    cards: [['Навыки', '8', 'Карточки'], ['Базы знаний', 'assistant_*', 'Изоляция'], ['Политики', 'III.6.5', 'SQL только чтение']],
  },
  kb_admin: {
    title: 'Базы знаний КЦ',
    subtitle: 'Создание БЗ, загрузка pdf/docx, переиндексация и статус индекса.',
    status: 'Индекс актуален',
    cards: [['Документы', '1 240', 'В основном индексе'], ['Последняя переиндексация', '2 мин', 'FR-UND-08'], ['Ошибки', '0', 'За 24 часа']],
  },
  qu_admin: {
    title: 'Модуль понимания',
    subtitle: 'Предпросмотр семантического поиска, релевантности и совпавших примеров.',
    status: 'Гибридный режим',
    cards: [['Намерения', '46', 'Активные классы'], ['Точность совпадений', '94%', 'RU / EN'], ['Порог', '0.72', 'Калибровка']],
  },
  data_sources: {
    title: 'Источники данных',
    subtitle: 'Подключения к СУЗ, файловым каталогам и внутренним API.',
    status: '5 подключено',
    cards: [['СУЗ', 'В сети', 'Webhook работает'], ['Файловый каталог', 'В сети', 'Синхронизация 5 мин'], ['HR API', 'На проверке', 'Тестовый контур']],
  },
  assistant_tools: {
    title: 'Инструменты ассистента',
    subtitle: 'RPA, шаблоны документов и безопасные SQL-инструменты.',
    status: 'На проверке ИБ',
    cards: [['RPA', '7', 'Зарегистрировано'], ['Шаблоны', '14', 'Активные формы'], ['SQL', '3', 'Запросы только на чтение']],
  },
  monitoring: {
    title: 'Мониторинг ассистента',
    subtitle: 'Качество ответов, полезность, ошибки и галлюцинации.',
    status: 'Данные за 24 ч',
    cards: [['Полезность', '87%', 'Оценки пользователей'], ['Ошибочные ответы', '1.8%', 'Ручная разметка'], ['Галлюцинации', '2.1%', 'Цель ≤3%']],
  },
  llm_config_cc: {
    title: 'Конфигурация LLM КЦ',
    subtitle: 'Профиль суфлёра КЦ для подсказок операторам контакт-центра.',
    status: 'Утверждено (тест)',
    cards: [
      ['Основная модель', 'stub-sufler-cc', 'Реестр моделей'],
      ['Ответ', '≤500 симв.', 'Лимит ответа'],
      ['Задержка', '1–2 с', 'Целевой показатель'],
    ],
  },
  scenario_editor: {
    title: 'Редактор сценариев',
    subtitle: 'Реестр, карта переходов, промпты и публикация сценариев КЦ.',
    status: '52 сценария',
    cards: [['Опубликовано', '47', 'Рабочий контур'], ['Черновики', '5', 'Ожидают проверки'], ['Покрытие', '94%', 'Сценарии КЦ']],
  },
  scenario_test: {
    title: 'Тест сценария',
    subtitle: 'Песочница прохождения веток и формирование отчёта.',
    status: 'Песочница',
    cards: [['Ветки', '12 / 12', 'Пройдено'], ['Среднее время', '1.4 с', 'Ответ узла'], ['Ошибки', '0', 'Последний прогон']],
  },
  scenario_bindings: {
    title: 'Сценарии суфлёра',
    subtitle: 'Привязка сценариев к отделам, каналам и группам навыков.',
    status: '38 привязок',
    cards: [['Телефония', '18', 'Активные'], ['Онлайн-чат', '14', 'Активные'], ['Внутренний КЦ', '6', 'Тестовые']],
  },
  sufler_policies: {
    title: 'Политики суфлёра',
    subtitle: 'Релевантность, автоответы и ограничения подсказок.',
    status: 'Политика v4',
    cards: [['Порог контекста', '0.62', 'Реестр моделей'], ['Детерминированный ответ', '0.84', 'Реестр моделей'], ['Макс. подсказок', '3', 'На один запрос']],
  },
  doc_types: {
    title: 'Типы документов',
    subtitle: 'Шаблоны полей, правила OCR и валидация документов.',
    status: '8 типов',
    cards: [['Кредитная заявка', '24 поля', 'Активна'], ['Паспорт', '12 полей', 'Активен'], ['Справка о доходах', '16 полей', 'Черновик']],
  },
  doc_export: {
    title: 'Экспорт документов',
    subtitle: 'Маршруты выгрузки проверенного JSON и статусы интеграций.',
    status: 'Очередь пуста',
    cards: [['JSON API', 'В сети', 'Основной канал'], ['Архив', 'В сети', 'Изолированное хранилище'], ['Ошибки', '0', 'За 24 часа']],
  },
  external: {
    title: 'Внешние системы',
    subtitle: 'Статус Bitrix24, онлайн-чата, Oktell и других интеграций.',
    status: '3 в сети',
    cards: [['Bitrix24', 'В сети', 'Адаптер CRM'], ['Онлайн-чат', 'В сети', 'Webhook'], ['Oktell', 'Имитация', 'WebSocket / MRCP']],
  },
  asr_qa: {
    title: 'QA записей ASR',
    subtitle: 'Каталог записей, аудиоплеер и синхронный транскрипт для аналитика КЦ.',
    status: 'Контроль качества ASR',
    cards: [['Каталог', 'Все записи', 'Хранение 1 год'], ['Фильтры', 'Опционально', 'Низкая уверенность'], ['Учебные', 'Кандидаты', 'Дообучение ASR']],
  },
  cc_reports: {
    title: 'Отчётность КЦ',
    subtitle: 'Таблицы, фильтры периода, экспорт CSV/XLSX и графики ASR.',
    status: 'Отчёты КЦ',
    cards: [['Аналитика', 'Черновой ETL', 'Статистика ASR'], ['Экспорт', 'CSV / XLSX', 'UTF-8'], ['Графики', 'Качество ASR', 'Распознавание']],
  },
}

const DEMO_ROLE_LABELS: Record<DemoAdminRole, string> = {
  kb_admin: 'Админ БЗ',
  cc_admin: 'Админ сценариев / КЦ',
  doc_admin: 'Админ OCR',
  auditor: 'Аудитор (чтение)',
}

function demoCanEdit(role: DemoAdminRole, item?: AdminNavItem): boolean {
  if (!item || role === 'auditor') return false
  if (item.group === 'АССИСТЕНТ') return role === 'kb_admin'
  if (item.group === 'СУФЛЁР / КЦ') return role === 'cc_admin'
  if (item.group === 'ДОКУМЕНТЫ') return role === 'doc_admin'
  return item.demoRoles.includes(role)
}

function hasRole(roles: readonly string[], item: AdminNavItem): boolean {
  return item.roleCodes.some((role) => roles.includes(role))
}

export function AiHubAdminApp({
  roles,
  initialScreen,
  initialProfile,
  initialModelParams,
  demoRoleSwitcher = false,
}: AiHubAdminAppProps) {
  const resolved = resolveAdminRoute(window.location.pathname)
  const [screen, setScreen] = useState(initialScreen ?? resolved.screen)
  const [profile, setProfile] = useState(initialProfile ?? resolved.profile)
  const [demoRole, setDemoRole] = useState<DemoAdminRole>('kb_admin')
  const [saved, setSaved] = useState(false)
  const modelParamsRef = useRef<ModelParamsScreenHandle>(null)
  const [modelFormState, setModelFormState] = useState({
    dirty: false,
    valid: false,
    saving: false,
    message: '',
  })
  const handleModelFormState = useCallback(
    (state: typeof modelFormState) => setModelFormState(state),
    [],
  )

  useEffect(() => {
    // Do not resetDevSessionCache here — KbAdminScreen / other screens also
    // call ensureDevSession on mount; clearing inFlight races and can hang login.
    void ensureDevSession()
  }, [])

  const visibleNav = useMemo(
    () => demoRoleSwitcher ? ADMIN_NAV : ADMIN_NAV.filter((item) => hasRole(roles, item)),
    [demoRoleSwitcher, roles],
  )
  const activeItem = ADMIN_NAV.find(
    (item) => item.id === screen && (item.profile === undefined || item.profile === profile),
  )
  const canEdit = demoRoleSwitcher
    ? demoCanEdit(demoRole, activeItem)
    : Boolean(activeItem && hasRole(roles, activeItem))
  const copy = SCREEN_COPY[screen]
  const screenBadge = activeItem?.label ?? copy.title
  const profileBadge = screen === 'model_params'
    ? profile === 'cc' ? 'Профиль суфлёра КЦ' : 'Профиль ассистента'
    : undefined

  const navigate = (event: MouseEvent<HTMLAnchorElement>, item: AdminNavItem) => {
    if (item.id === 'asr_qa' || item.id === 'cc_reports') {
      window.location.assign(adminRoute(item))
      return
    }
    event.preventDefault()
    setScreen(item.id)
    setProfile(item.profile ?? (item.id === 'llm_config_cc' ? 'cc' : 'assistant'))
    setSaved(false)
    setModelFormState({ dirty: false, valid: false, saving: false, message: '' })
    window.history.pushState({}, '', adminRoute(item))
  }

  return (
    <div className="admin-center" data-testid="admin-shell">
      <aside className="admin-sidebar" data-testid="admin-sidebar">
        <a className="admin-sidebar__brand" href="/ai-hub/admin">
          <img src="/assets/belarusbank-logo.png" alt="Беларусбанк" />
          <span><strong>AI Hub</strong><small>Центр настроек</small></span>
        </a>
        <nav aria-label="Настройки AI Hub">
          {ADMIN_GROUPS.map((group) => {
            const items = visibleNav.filter((item) => item.group === group)
            if (!items.length) return null
            return (
              <section key={group} className="admin-sidebar__group">
                <h2>{group}</h2>
                {items.map((item) => {
                  const active = item.id === screen
                    && (item.profile === undefined || item.profile === profile)
                  const demoReadable = item.demoRoles.includes(demoRole)
                  return (
                    <a
                      key={`${item.id}-${item.profile ?? 'default'}`}
                      href={adminRoute(item)}
                      aria-current={active ? 'page' : undefined}
                      onClick={(event) => navigate(event, item)}
                    >
                      <span>{item.featured ? '★ ' : ''}{item.label}</span>
                      {demoRoleSwitcher && !demoReadable && <small>(чтение)</small>}
                    </a>
                  )
                })}
              </section>
            )
          })}
        </nav>
      </aside>

      <div className="admin-workspace">
        <header className="admin-topbar">
          <div>
            <strong>Центр настроек AI Hub</strong>
            <span>Управление конфигурацией платформы</span>
          </div>
          {demoRoleSwitcher && (
            <label className="admin-role-switcher">
              <span>Демо роль</span>
              <select
                value={demoRole}
                onChange={(event) => setDemoRole(event.target.value as DemoAdminRole)}
              >
                {Object.entries(DEMO_ROLE_LABELS).map(([value, label]) => (
                  <option value={value} key={value}>{label}</option>
                ))}
              </select>
            </label>
          )}
          {!demoRoleSwitcher && <StatusBadge status="success">RBAC активен</StatusBadge>}
        </header>

        <main className="admin-main" data-screen-id={screen}>
          <div className="admin-breadcrumbs" aria-label="Хлебные крошки">
            <a href="/ai-hub/admin">Центр настроек</a><span>/</span><span>{copy.title}</span>
          </div>
          <header className="admin-page-header">
            <div>
              <div className="admin-page-header__title">
                <h1>{copy.title}</h1>
                {profileBadge && <StatusBadge status="info">{profileBadge}</StatusBadge>}
              </div>
              <p>{copy.subtitle}</p>
            </div>
            <StatusBadge status={canEdit ? 'success' : 'neutral'}>
              {canEdit ? copy.status : 'Только просмотр'}
            </StatusBadge>
          </header>

          {!canEdit && (
            <div className="admin-readonly" role="status">
              Текущая роль может просматривать экран, но не изменять настройки.
            </div>
          )}

          {screen === 'model_params' ? (
            <ModelParamsScreen
              ref={modelParamsRef}
              profile={profile}
              canEdit={canEdit}
              initialData={initialModelParams}
              onStateChange={handleModelFormState}
            />
          ) : screen === 'qu_admin' ? (
            <QuPreviewScreen />
          ) : screen === 'kb_admin' ? (
            <KbAdminScreen canEdit={canEdit} />
          ) : screen === 'prompts_assistant' ? (
            <PromptsAssistantScreen canEdit={canEdit} />
          ) : screen === 'capabilities' ? (
            <CapabilitiesScreen canEdit={canEdit} />
          ) : (
            <>
              <section className="admin-stats" aria-label={`Сводка экрана ${copy.title}`}>
                {copy.cards.map(([label, value, note]) => (
                  <Card key={label}>
                    <span>{label}</span>
                    <strong>{value}</strong>
                    <small>{note}</small>
                  </Card>
                ))}
              </section>

              <Card className="admin-settings-card">
                <header>
                  <div>
                    <h2>Настройки экрана</h2>
                    <p>Черновой контент подготовлен для следующей профильной UI-задачи.</p>
                  </div>
                  <StatusBadge status="info">{screenBadge}</StatusBadge>
                </header>
                <div className="admin-form-grid">
                  <label>
                    <span>Название конфигурации</span>
                    <input defaultValue={copy.title} disabled={!canEdit} />
                  </label>
                  <label>
                    <span>Область</span>
                    <select defaultValue="bank" disabled={!canEdit}>
                      <option value="bank">Весь банк</option>
                      <option value="cc">Контакт-центр</option>
                      <option value="department">Подразделение</option>
                    </select>
                  </label>
                  <label className="admin-form-grid__wide">
                    <span>Описание</span>
                    <textarea defaultValue={copy.subtitle} rows={4} disabled={!canEdit} />
                  </label>
                </div>
              </Card>
            </>
          )}
        </main>

        {screen !== 'qu_admin' && screen !== 'kb_admin' && screen !== 'prompts_assistant' && screen !== 'capabilities' && (
        <footer className="admin-save-footer" data-testid="admin-save-footer">
          <span>
            {screen === 'model_params'
              ? modelFormState.message || (modelFormState.dirty ? 'Есть несохранённые изменения' : 'Настройки синхронизированы')
              : saved ? 'Изменения сохранены' : 'Есть несохранённые изменения'}
          </span>
          <div>
            <Button
              variant="ghost"
              disabled={!canEdit || (screen === 'model_params' && !modelFormState.dirty)}
              onClick={() => screen === 'model_params' ? modelParamsRef.current?.reset() : setSaved(false)}
            >
              Сбросить
            </Button>
            <Button
              disabled={
                !canEdit
                || (
                  screen === 'model_params'
                  && (
                    !modelFormState.dirty
                    || !modelFormState.valid
                    || modelFormState.saving
                  )
                )
              }
              onClick={() => {
                if (screen === 'model_params') {
                  void modelParamsRef.current?.save()
                } else {
                  setSaved(true)
                }
              }}
            >
              {modelFormState.saving && screen === 'model_params' ? 'Сохранение…' : 'Сохранить'}
            </Button>
          </div>
        </footer>
        )}
      </div>
    </div>
  )
}
