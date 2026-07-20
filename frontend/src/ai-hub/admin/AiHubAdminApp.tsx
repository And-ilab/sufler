import {
  useCallback,
  useMemo,
  useRef,
  useState,
  type MouseEvent,
} from 'react'
import { Button, Card, StatusBadge } from '../../components'
import {
  ModelParamsScreen,
  type ModelParamsScreenHandle,
} from './ModelParamsScreen'
import { QuPreviewScreen } from './QuPreviewScreen'
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
    subtitle: 'Scope подразделений, роли и единый журнал изменений настроек.',
    status: 'Аудит включён',
    cards: [['Подразделения', '12', 'Активные scope'], ['Изменения', '28', 'За последние 7 дней'], ['Ожидают проверки', '3', 'Запросы доступа']],
  },
  llm_config_assistant: {
    title: 'Конфигурация LLM',
    subtitle: 'Профиль assistant_bank, fallback-модель и контроль доступности.',
    status: 'approved_dev',
    cards: [['Основная модель', 'stub-assistant-bank', 'ModelRegistry'], ['Fallback', 'Включён', 'OpenAI-compatible'], ['Health', '99.9%', 'Последние 24 часа']],
  },
  model_params: {
    title: 'Параметры модели LLM',
    subtitle: 'Preset генерации, лимиты ответа и параметры семантики.',
    status: 'Черновик',
    cards: [['Temperature', '0.20', 'Диапазон 0–1'], ['Max tokens', '1024', 'Контекст 8k'], ['Top P', '0.90', 'Профиль модели']],
  },
  prompts_assistant: {
    title: 'Промпты ассистента',
    subtitle: 'Библиотека System, Task и Scope промптов с версиями.',
    status: '24 опубликовано',
    cards: [['System', '6', 'Базовые инструкции'], ['Task', '12', 'Рабочие сценарии'], ['Scope', '8', 'Подразделения']],
  },
  capabilities: {
    title: 'Навыки и инструменты',
    subtitle: 'Каталог навыков ассистента и разрешённых операций.',
    status: '18 навыков',
    cards: [['KB lookup', 'Включён', 'Поиск по БЗ'], ['Calculator', 'Включён', 'Локальное выполнение'], ['HR helper', 'Черновик', 'Требует review']],
  },
  kb_admin: {
    title: 'Базы знаний',
    subtitle: 'Источники, индексация и scope корпоративных знаний.',
    status: 'Индекс актуален',
    cards: [['Документы', '1 240', 'В основном индексе'], ['Последний reindex', '2 мин', 'FR-UND-08'], ['Ошибки', '0', 'За 24 часа']],
  },
  qu_admin: {
    title: 'Модуль понимания',
    subtitle: 'Preview семантического поиска, релевантности и совпавших примеров QU.',
    status: 'Hybrid QU',
    cards: [['Intent', '46', 'Активные классы'], ['Match rate', '94%', 'RU / EN'], ['Порог', '0.72', 'Калибровка']],
  },
  data_sources: {
    title: 'Источники данных',
    subtitle: 'Подключения к СУЗ, файловым каталогам и внутренним API.',
    status: '5 подключено',
    cards: [['СУЗ', 'Online', 'Webhook работает'], ['Файловый каталог', 'Online', 'Синхронизация 5 мин'], ['HR API', 'Review', 'Тестовый контур']],
  },
  assistant_tools: {
    title: 'Инструменты ассистента',
    subtitle: 'RPA, шаблоны документов и безопасные SQL-инструменты.',
    status: 'IB review',
    cards: [['RPA', '7', 'Зарегистрировано'], ['Шаблоны', '14', 'Активные формы'], ['SQL', '3', 'Read-only запросы']],
  },
  monitoring: {
    title: 'Мониторинг ассистента',
    subtitle: 'Качество ответов, полезность, ошибки и галлюцинации.',
    status: 'Данные за 24 ч',
    cards: [['Полезность', '87%', 'Оценки пользователей'], ['Ошибочные ответы', '1.8%', 'Ручная разметка'], ['Галлюцинации', '2.1%', 'Цель ≤3%']],
  },
  llm_config_cc: {
    title: 'Конфигурация LLM КЦ',
    subtitle: 'Профиль sufler_cc для подсказок операторам контакт-центра.',
    status: 'approved_dev',
    cards: [['Основная модель', 'stub-sufler-cc', 'ModelRegistry'], ['Ответ', '≤500 симв.', 'FR-LLM-07'], ['Latency', '1–2 с', 'Целевой KPI']],
  },
  scenario_editor: {
    title: 'Редактор сценариев',
    subtitle: 'Реестр, карта переходов, промпты и публикация сценариев КЦ.',
    status: '52 сценария',
    cards: [['Опубликовано', '47', 'Production scope'], ['Черновики', '5', 'Ожидают review'], ['Покрытие', '94%', 'CC-SCR']],
  },
  scenario_test: {
    title: 'Тест сценария',
    subtitle: 'Sandbox прохождения веток и формирование отчёта 4.5.2.8.',
    status: 'Sandbox',
    cards: [['Ветки', '12 / 12', 'Пройдено'], ['Среднее время', '1.4 с', 'Ответ узла'], ['Ошибки', '0', 'Последний прогон']],
  },
  scenario_bindings: {
    title: 'Сценарии суфлёра',
    subtitle: 'Привязка сценариев к отделам, каналам и skill-группам.',
    status: '38 привязок',
    cards: [['Телефония', '18', 'Активные'], ['Онлайн-чат', '14', 'Активные'], ['Внутренний КЦ', '6', 'Тестовые']],
  },
  sufler_policies: {
    title: 'Политики суфлёра',
    subtitle: 'Релевантность, автоответы и ограничения подсказок.',
    status: 'Политика v4',
    cards: [['Порог контекста', '0.62', 'ModelRegistry'], ['Детерминированный ответ', '0.84', 'ModelRegistry'], ['Max hints', '3', 'На один запрос']],
  },
  doc_types: {
    title: 'Типы документов',
    subtitle: 'Шаблоны полей, правила OCR и валидация документов.',
    status: '8 типов',
    cards: [['Кредитная заявка', '24 поля', 'Активна'], ['Паспорт', '12 полей', 'Активен'], ['Справка о доходах', '16 полей', 'Черновик']],
  },
  doc_export: {
    title: 'Экспорт документов',
    subtitle: 'Маршруты выгрузки validated JSON и статусы интеграций.',
    status: 'Очередь пуста',
    cards: [['JSON API', 'Online', 'Основной канал'], ['Архив', 'Online', 'Air-gapped storage'], ['Ошибки', '0', 'За 24 часа']],
  },
  external: {
    title: 'Внешние системы',
    subtitle: 'Статус Bitrix24, Online Chat, Oktell и других интеграций.',
    status: '3 online',
    cards: [['Bitrix24', 'Online', 'CRM adapter'], ['Online Chat', 'Online', 'Webhook'], ['Oktell', 'Mock', 'WebSocket / MRCP risk']],
  },
}

const DEMO_ROLE_LABELS: Record<DemoAdminRole, string> = {
  kb_admin: 'Админ БЗ',
  cc_admin: 'Админ сценариев / КЦ',
  doc_admin: 'Админ OCR',
  auditor: 'Аудитор (read)',
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
  const profileBadge = screen === 'model_params'
    ? profile === 'cc' ? 'sufler_cc' : 'assistant_bank'
    : undefined

  const navigate = (event: MouseEvent<HTMLAnchorElement>, item: AdminNavItem) => {
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
                      {demoRoleSwitcher && !demoReadable && <small>(read)</small>}
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
                    <p>Stub-контент подготовлен для следующей профильной UI-задачи.</p>
                  </div>
                  <StatusBadge status="info">{screen}</StatusBadge>
                </header>
                <div className="admin-form-grid">
                  <label>
                    <span>Название конфигурации</span>
                    <input defaultValue={copy.title} disabled={!canEdit} />
                  </label>
                  <label>
                    <span>Scope</span>
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

        {screen !== 'qu_admin' && (
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
