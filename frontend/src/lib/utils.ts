/** Join CSS class names, ignoring falsy values. */
export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(' ')
}

/** "12 nov 2026, 10:30" in Spanish. The API sends naive local timestamps. */
export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('es-ES', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat('es-ES', { dateStyle: 'medium' }).format(new Date(value))
}

/** Current local time as the value of an <input type="datetime-local">. */
export function nowLocalInput(): string {
  const d = new Date()
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 16)
}

/** "Marta Ruiz" from a first and an optional last name. */
export function fullName(first: string, last: string | null): string {
  return [first, last].filter(Boolean).join(' ')
}

/** "02:35" from a number of seconds. */
export function formatClock(seconds: number): string {
  const m = Math.floor(seconds / 60)
  return `${String(m).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`
}

/** Empty strings become null so the API stores them as missing values. */
export function blankToNull<T extends Record<string, unknown>>(data: T): T {
  return Object.fromEntries(
    Object.entries(data).map(([k, v]) => [k, v === '' ? null : v]),
  ) as T
}

/** Today as the value of an <input type="date"> (local time). */
export function todayInput(): string {
  return nowLocalInput().slice(0, 10)
}
