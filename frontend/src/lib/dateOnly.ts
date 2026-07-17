const DATE_ONLY_PATTERN = /^(\d{4})-(\d{2})-(\d{2})/

export function dateOnlyInputValue(value?: string | null): string {
  if (!value) return ''
  const match = DATE_ONLY_PATTERN.exec(value)
  return match ? match[1] + '-' + match[2] + '-' + match[3] : ''
}

export function dateOnlyPayloadValue(value: string): string {
  return dateOnlyInputValue(value)
}

export function formatDateOnly(value?: string | null, fallback = 'No date set'): string {
  const input = dateOnlyInputValue(value)
  if (!input) return fallback
  const [yearText, monthText, dayText] = input.split('-')
  const year = Number(yearText)
  const month = Number(monthText)
  const day = Number(dayText)
  if (!year || month < 1 || month > 12 || day < 1 || day > 31) return fallback
  const monthName = new Intl.DateTimeFormat(undefined, { month: 'long' }).format(new Date(2000, month - 1, 1))
  return monthName + ' ' + day + ', ' + year
}

export function dateOnlySortKey(value?: string | null): string {
  return dateOnlyInputValue(value) || '9999-12-31'
}
