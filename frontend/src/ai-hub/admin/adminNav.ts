export type AdminScreen =
  | 'audit'
  | 'llm_config_assistant'
  | 'model_params'
  | 'prompts_assistant'
  | 'capabilities'
  | 'kb_admin'
  | 'qu_admin'
  | 'data_sources'
  | 'assistant_tools'
  | 'monitoring'
  | 'llm_config_cc'
  | 'scenario_editor'
  | 'scenario_test'
  | 'scenario_bindings'
  | 'sufler_policies'
  | 'doc_types'
  | 'doc_export'
  | 'external'

export type AdminProfile = 'assistant' | 'cc'
export type DemoAdminRole = 'kb_admin' | 'cc_admin' | 'doc_admin' | 'auditor'

export interface AdminNavItem {
  id: AdminScreen
  label: string
  group: 'ОБЩЕЕ' | 'АССИСТЕНТ' | 'СУФЛЁР / КЦ' | 'ДОКУМЕНТЫ' | 'ССЫЛКИ'
  profile?: AdminProfile
  featured?: boolean
  roleCodes: readonly string[]
  demoRoles: readonly DemoAdminRole[]
}

const ALL_DEMO_ROLES: readonly DemoAdminRole[] = [
  'kb_admin',
  'cc_admin',
  'doc_admin',
  'auditor',
]
const ALL_ADMINS = [
  'software_administrator',
  'llm_knowledge_base_administrator',
  'contact_center_module_administrator',
  'ai_assistant_module_administrator',
  'document_recognition_module_administrator',
]
const ASSISTANT_ADMINS = [
  'software_administrator',
  'llm_knowledge_base_administrator',
  'ai_assistant_module_administrator',
]
const QU_ADMINS = [
  'software_administrator',
  'llm_knowledge_base_administrator',
]
const CC_ADMINS = [
  'software_administrator',
  'contact_center_module_administrator',
]
const OCR_ADMINS = [
  'software_administrator',
  'document_recognition_module_administrator',
]

export const ADMIN_NAV: readonly AdminNavItem[] = [
  { id: 'audit', label: 'Подразделения и журнал', group: 'ОБЩЕЕ', roleCodes: ALL_ADMINS, demoRoles: ALL_DEMO_ROLES },
  { id: 'llm_config_assistant', label: 'Конфигурация LLM', group: 'АССИСТЕНТ', featured: true, roleCodes: ASSISTANT_ADMINS, demoRoles: ['kb_admin', 'auditor'] },
  { id: 'model_params', label: 'Параметры модели LLM', group: 'АССИСТЕНТ', profile: 'assistant', roleCodes: ASSISTANT_ADMINS, demoRoles: ['kb_admin', 'auditor'] },
  { id: 'prompts_assistant', label: 'Промпты ассистента', group: 'АССИСТЕНТ', roleCodes: ASSISTANT_ADMINS, demoRoles: ['kb_admin', 'auditor'] },
  { id: 'capabilities', label: 'Навыки и инструменты', group: 'АССИСТЕНТ', roleCodes: ASSISTANT_ADMINS, demoRoles: ['kb_admin', 'auditor'] },
  { id: 'kb_admin', label: 'Базы знаний', group: 'АССИСТЕНТ', roleCodes: ASSISTANT_ADMINS, demoRoles: ['kb_admin', 'auditor'] },
  { id: 'qu_admin', label: 'Модуль понимания', group: 'АССИСТЕНТ', roleCodes: QU_ADMINS, demoRoles: ['kb_admin', 'auditor'] },
  { id: 'data_sources', label: 'Источники данных', group: 'АССИСТЕНТ', roleCodes: ASSISTANT_ADMINS, demoRoles: ['kb_admin', 'auditor'] },
  { id: 'assistant_tools', label: 'Инструменты ассистента', group: 'АССИСТЕНТ', roleCodes: ASSISTANT_ADMINS, demoRoles: ['kb_admin', 'auditor'] },
  { id: 'monitoring', label: 'Мониторинг ассистента', group: 'АССИСТЕНТ', roleCodes: ASSISTANT_ADMINS, demoRoles: ['kb_admin', 'auditor'] },
  { id: 'llm_config_cc', label: 'Конфигурация LLM КЦ', group: 'СУФЛЁР / КЦ', featured: true, roleCodes: CC_ADMINS, demoRoles: ['cc_admin', 'kb_admin', 'auditor'] },
  { id: 'model_params', label: 'Параметры модели (КЦ)', group: 'СУФЛЁР / КЦ', profile: 'cc', roleCodes: CC_ADMINS, demoRoles: ['cc_admin', 'kb_admin', 'auditor'] },
  { id: 'scenario_editor', label: 'Редактор сценариев', group: 'СУФЛЁР / КЦ', roleCodes: CC_ADMINS, demoRoles: ['cc_admin', 'kb_admin', 'auditor'] },
  { id: 'scenario_test', label: 'Тест сценария', group: 'СУФЛЁР / КЦ', roleCodes: CC_ADMINS, demoRoles: ['cc_admin', 'kb_admin', 'auditor'] },
  { id: 'scenario_bindings', label: 'Сценарии суфлёра', group: 'СУФЛЁР / КЦ', roleCodes: CC_ADMINS, demoRoles: ['cc_admin', 'kb_admin', 'auditor'] },
  { id: 'sufler_policies', label: 'Политики суфлёра', group: 'СУФЛЁР / КЦ', roleCodes: CC_ADMINS, demoRoles: ['cc_admin', 'kb_admin', 'auditor'] },
  { id: 'doc_types', label: 'Типы документов', group: 'ДОКУМЕНТЫ', roleCodes: OCR_ADMINS, demoRoles: ['doc_admin', 'auditor'] },
  { id: 'doc_export', label: 'Экспорт документов', group: 'ДОКУМЕНТЫ', roleCodes: OCR_ADMINS, demoRoles: ['doc_admin', 'auditor'] },
  { id: 'external', label: 'Внешние системы', group: 'ССЫЛКИ', roleCodes: ALL_ADMINS, demoRoles: ALL_DEMO_ROLES },
]

export const ADMIN_GROUPS = [...new Set(ADMIN_NAV.map((item) => item.group))]

export const ADMIN_SCREEN_IDS = [...new Set(ADMIN_NAV.map((item) => item.id))]

export function adminRoute(item: AdminNavItem): string {
  if (item.id === 'model_params' && item.profile === 'cc') {
    return '/ai-hub/admin/model_params/cc'
  }
  return `/ai-hub/admin/${item.id}`
}

export function resolveAdminRoute(pathname: string): {
  screen: AdminScreen
  profile: AdminProfile
} {
  const parts = pathname.replace(/\/+$/, '').split('/').filter(Boolean)
  const candidate = parts[2] as AdminScreen | undefined
  const screen = candidate && ADMIN_SCREEN_IDS.includes(candidate)
    ? candidate
    : 'llm_config_assistant'
  const profile = screen === 'model_params' && parts[3] === 'cc' ? 'cc' : 'assistant'
  return { screen, profile }
}

export function isAdminCenterRole(roles: readonly string[]): boolean {
  return roles.some((role) => ALL_ADMINS.includes(role))
}
