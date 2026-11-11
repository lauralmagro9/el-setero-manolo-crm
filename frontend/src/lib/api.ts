import { supabase } from './supabase'

/** Error returned by the API; `status` is the HTTP code (502 = transcription failed). */
export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** Turn FastAPI's `detail` (text or validation list) into one readable message. */
function readDetail(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((d) => `${(d.loc ?? []).slice(1).join('.')}: ${d.msg}`).join('; ')
  }
  return fallback
}

/** Call the API with the current Supabase token; throws ApiError on non-2xx answers. */
export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { data } = await supabase.auth.getSession()
  const headers = new Headers(init.headers)
  if (data.session) headers.set('Authorization', `Bearer ${data.session.access_token}`)
  let body = init.body
  if (init.json !== undefined) {
    headers.set('Content-Type', 'application/json')
    body = JSON.stringify(init.json)
  }
  let response: Response
  try {
    response = await fetch(`/api${path}`, { ...init, headers, body })
  } catch {
    throw new ApiError(0, 'No hay conexión con el servidor')
  }
  if (response.status === 401) await supabase.auth.signOut()
  if (!response.ok) {
    const parsed = await response.json().catch(() => null)
    throw new ApiError(response.status, readDetail(parsed, response.statusText))
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T)
}

/** GET a binary file (e.g. a PDF) with the current token. */
export async function apiBlob(path: string): Promise<Blob> {
  const { data } = await supabase.auth.getSession()
  const headers = new Headers()
  if (data.session) headers.set('Authorization', `Bearer ${data.session.access_token}`)
  const response = await fetch(`/api${path}`, { headers }).catch(() => {
    throw new ApiError(0, 'No hay conexión con el servidor')
  })
  if (!response.ok) throw new ApiError(response.status, response.statusText)
  return response.blob()
}

/** Build a query string, skipping empty values. */
export function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '' && v !== false) q.set(k, String(v))
  }
  const text = q.toString()
  return text ? `?${text}` : ''
}
