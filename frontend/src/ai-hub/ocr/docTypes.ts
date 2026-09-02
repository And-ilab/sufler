export const OPERATOR_DOC_TYPES = ['passport', 'account_statement', 'loan_agreement'] as const

export type OperatorDocType = (typeof OPERATOR_DOC_TYPES)[number]

export const ML_DOC_TYPE = 'ml'

export const OPERATOR_DOC_TITLES: Record<OperatorDocType, string> = {
  passport: 'Паспорт',
  account_statement: 'Банковская выписка',
  loan_agreement: 'Договор',
}

export function isOperatorDocType(value: string): value is OperatorDocType {
  return (OPERATOR_DOC_TYPES as readonly string[]).includes(value)
}

export function isMlDocType(value: string): boolean {
  return value === ML_DOC_TYPE || value === 'auto'
}

export function operatorDocTitle(docType: string): string {
  if (isMlDocType(docType)) return 'ML распознавание'
  if (isOperatorDocType(docType)) return OPERATOR_DOC_TITLES[docType]
  return ''
}
