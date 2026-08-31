/** FR-CC-06 — operator-facing empty hint when the query is outside SUZ / cc_production. */
export const NO_SUZ_HINT_MESSAGE = 'Запрос вне базы знаний / нет подсказки по СУЗ'

export function emptySuflerHintMessage(
  blocked: string | null | undefined,
  hasHints: boolean,
): string {
  if (hasHints) return ''
  if (blocked === 'no_hint_needed' || blocked === 'service_mode') return ''
  return NO_SUZ_HINT_MESSAGE
}
