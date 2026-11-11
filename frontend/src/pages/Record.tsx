import { useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Mic, Pause, Play, RotateCcw, Square, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Button, Card, ErrorMessage, Field, Input, PageHeader, Select } from '@/components/ui'
import { api, ApiError } from '@/lib/api'
import { useCompanies, useContacts } from '@/lib/hooks'
import { addPending, listPending, removePending, type PendingRecording } from '@/lib/pendingRecordings'
import { INTERACTION_TYPES, type Interaction } from '@/lib/types'
import { formatClock, fullName, nowLocalInput } from '@/lib/utils'

const MAX_SECONDS = Number(import.meta.env.VITE_MAX_RECORDING_SECONDS ?? 600)
// webm/opus on Chrome and Android, mp4/aac on iOS Safari
const MIME_CANDIDATES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus']

type Phase = 'idle' | 'recording' | 'paused' | 'review'

/** Send one recording to the API (which transcribes it); the audio is never stored on the server. */
async function uploadRecording(rec: PendingRecording): Promise<Interaction> {
  const form = new FormData()
  const ext = rec.mimeType.includes('mp4') ? 'm4a' : rec.mimeType.includes('ogg') ? 'ogg' : 'webm'
  form.append('audio', new File([rec.blob], `nota.${ext}`, { type: rec.mimeType }))
  form.append('type', rec.fields.type)
  form.append('occurred_at', rec.fields.occurred_at)
  if (rec.fields.company_id) form.append('company_id', rec.fields.company_id)
  if (rec.fields.contact_id) form.append('contact_id', rec.fields.contact_id)
  return api<Interaction>('/voice-notes', { method: 'POST', body: form })
}

/** Audio player for a Blob; the object URL is created once and released on unmount. */
function BlobAudio({ blob }: { blob: Blob }) {
  const url = useMemo(() => URL.createObjectURL(blob), [blob])
  useEffect(() => () => URL.revokeObjectURL(url), [url])
  return <audio controls src={url} className="w-full" />
}

export default function RecordPage() {
  const queryClient = useQueryClient()
  const [phase, setPhase] = useState<Phase>('idle')
  const [seconds, setSeconds] = useState(0)
  const [blob, setBlob] = useState<Blob | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [saved, setSaved] = useState<Interaction | null>(null)
  const [uploading, setUploading] = useState(false)
  const [pending, setPending] = useState<PendingRecording[]>([])
  const [retrying, setRetrying] = useState<string | null>(null)
  const [fields, setFields] = useState({ company_id: '', contact_id: '', type: 'Otro', occurred_at: nowLocalInput() })

  const recorder = useRef<MediaRecorder | null>(null)
  const stream = useRef<MediaStream | null>(null)
  const chunks = useRef<Blob[]>([])
  const timer = useRef<number | undefined>(undefined)
  const companies = useCompanies({ page_size: 100 })
  const contacts = useContacts({ company_id: fields.company_id || undefined })

  const refreshPending = useCallback(() => listPending().then(setPending).catch(() => setPending([])), [])
  useEffect(() => { refreshPending() }, [refreshPending])
  useEffect(() => () => { // leaving the page: release the microphone
    window.clearInterval(timer.current)
    stream.current?.getTracks().forEach((t) => t.stop())
  }, [])
  useEffect(() => () => { if (audioUrl) URL.revokeObjectURL(audioUrl) }, [audioUrl])

  const stop = useCallback(() => {
    if (recorder.current && recorder.current.state !== 'inactive') recorder.current.stop()
    window.clearInterval(timer.current)
  }, [])

  // Safety limit: stop automatically
  useEffect(() => { if (phase === 'recording' && seconds >= MAX_SECONDS) stop() }, [phase, seconds, stop])

  async function start() {
    setError(null)
    setSaved(null)
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setError(new Error('Este navegador no permite grabar audio (en el móvil hace falta HTTPS).'))
      return
    }
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setError(new Error('No se pudo acceder al micrófono. Revisa el permiso del navegador.'))
      return
    }
    const mimeType = MIME_CANDIDATES.find((m) => MediaRecorder.isTypeSupported(m))
    const rec = new MediaRecorder(stream.current, mimeType ? { mimeType } : undefined)
    chunks.current = []
    rec.ondataavailable = (e) => e.data.size && chunks.current.push(e.data)
    rec.onstop = () => {
      stream.current?.getTracks().forEach((t) => t.stop())
      const result = new Blob(chunks.current, { type: rec.mimeType || mimeType || 'audio/webm' })
      setBlob(result)
      setAudioUrl(URL.createObjectURL(result))
      setPhase('review')
    }
    recorder.current = rec
    rec.start(1000)
    setSeconds(0)
    setFields((f) => ({ ...f, occurred_at: nowLocalInput() }))
    timer.current = window.setInterval(() => setSeconds((s) => s + 1), 1000)
    setPhase('recording')
  }

  function togglePause() {
    const rec = recorder.current
    if (!rec) return
    if (rec.state === 'recording') {
      rec.pause(); window.clearInterval(timer.current); setPhase('paused')
    } else if (rec.state === 'paused') {
      rec.resume(); timer.current = window.setInterval(() => setSeconds((s) => s + 1), 1000); setPhase('recording')
    }
  }

  function discard() {
    setBlob(null); setAudioUrl(null); setSeconds(0); setError(null); setPhase('idle')
  }

  async function send() {
    if (!blob) return
    setUploading(true)
    setError(null)
    const rec: PendingRecording = {
      id: crypto.randomUUID(), blob, mimeType: blob.type, createdAt: new Date().toISOString(),
      fields: {
        type: fields.type, occurred_at: fields.occurred_at,
        company_id: fields.company_id || undefined, contact_id: fields.contact_id || undefined,
      },
    }
    try {
      setSaved(await uploadRecording(rec))
      queryClient.invalidateQueries()
      discard()
    } catch (e) {
      // Keep the audio in the browser so nothing is lost; it can be retried later
      await addPending({ ...rec, error: e instanceof Error ? e.message : 'Error desconocido' })
      await refreshPending()
      setError(e)
      discard()
    } finally {
      setUploading(false)
    }
  }

  async function retry(rec: PendingRecording) {
    setRetrying(rec.id)
    try {
      setSaved(await uploadRecording(rec))
      await removePending(rec.id) // only now, once the server confirmed it
      queryClient.invalidateQueries()
    } catch (e) {
      await addPending({ ...rec, error: e instanceof ApiError || e instanceof Error ? e.message : 'Error' })
    } finally {
      setRetrying(null)
      refreshPending()
    }
  }

  return (
    <>
      <PageHeader title="Grabar nota de voz" />
      <div className="mx-auto flex max-w-xl flex-col gap-4">
        {saved && (
          <Card className="flex items-start gap-3 border-primary">
            <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-primary" />
            <div className="text-sm">
              <p className="font-semibold">Nota guardada (pendiente de procesar)</p>
              <p className="mt-1 whitespace-pre-wrap text-muted">{saved.transcript}</p>
            </div>
          </Card>
        )}
        {error != null && (
          <ErrorMessage error={error instanceof ApiError && error.status === 502
            ? new Error(`${error.message}. La grabación se ha guardado en este dispositivo: puedes reintentarla abajo.`) : error} />
        )}

        <Card className="flex flex-col items-center gap-5 py-8">
          <p className="font-mono text-5xl tabular-nums" aria-live="off">{formatClock(seconds)}</p>

          {phase === 'idle' && (
            <button onClick={start} aria-label="Empezar a grabar" className="flex size-24 items-center justify-center rounded-full bg-accent text-accent-foreground shadow-lg hover:bg-accent-strong">
              <Mic className="size-10" />
            </button>
          )}
          {(phase === 'recording' || phase === 'paused') && (
            <div className="flex items-center gap-4">
              <Button variant="outline" onClick={togglePause} aria-label={phase === 'paused' ? 'Reanudar' : 'Pausar'}>
                {phase === 'paused' ? <Play className="size-5" /> : <Pause className="size-5" />}
                {phase === 'paused' ? 'Reanudar' : 'Pausar'}
              </Button>
              <Button variant="danger" onClick={stop} aria-label="Terminar grabación"><Square className="size-5" /> Terminar</Button>
            </div>
          )}
          {phase === 'recording' && <p className="flex items-center gap-2 text-sm text-danger"><span className="size-2.5 animate-pulse rounded-full bg-danger" /> Grabando…</p>}
          {phase === 'idle' && <p className="text-sm text-muted">Pulsa para grabar una nota tras una visita o llamada.</p>}

          {phase === 'review' && audioUrl && (
            <div className="flex w-full flex-col gap-4">
              <audio controls src={audioUrl} className="w-full" />
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Empresa (opcional)">
                  <Select value={fields.company_id} onChange={(e) => setFields({ ...fields, company_id: e.target.value, contact_id: '' })}>
                    <option value="">Sin asignar</option>
                    {companies.data?.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </Select>
                </Field>
                <Field label="Contacto (opcional)">
                  <Select value={fields.contact_id} disabled={!fields.company_id} onChange={(e) => setFields({ ...fields, contact_id: e.target.value })}>
                    <option value="">—</option>
                    {fields.company_id && contacts.data?.items.map((c) => <option key={c.id} value={c.id}>{fullName(c.first_name, c.last_name)}</option>)}
                  </Select>
                </Field>
                <Field label="Tipo">
                  <Select value={fields.type} onChange={(e) => setFields({ ...fields, type: e.target.value })}>
                    {INTERACTION_TYPES.map((t) => <option key={t}>{t}</option>)}
                  </Select>
                </Field>
                <Field label="Fecha y hora">
                  <Input type="datetime-local" value={fields.occurred_at} onChange={(e) => setFields({ ...fields, occurred_at: e.target.value })} />
                </Field>
              </div>
              <div className="flex gap-3">
                <Button variant="outline" onClick={discard} disabled={uploading}><Trash2 className="size-4" /> Descartar</Button>
                <Button className="flex-1" onClick={send} loading={uploading}>Transcribir y guardar</Button>
              </div>
              {uploading && <p className="text-center text-sm text-muted">Transcribiendo… puede tardar unos segundos.</p>}
            </div>
          )}
        </Card>

        {pending.length > 0 && (
          <section>
            <h2 className="mb-2 font-semibold">Grabaciones pendientes de enviar</h2>
            <div className="flex flex-col gap-3">
              {pending.map((p) => (
                <Card key={p.id} className="flex flex-col gap-2">
                  <BlobAudio blob={p.blob} />
                  {p.error && <p className="text-xs text-danger">{p.error}</p>}
                  <div className="flex gap-2">
                    <Button loading={retrying === p.id} onClick={() => retry(p)}><RotateCcw className="size-4" /> Reintentar</Button>
                    <Button variant="outline" disabled={retrying === p.id}
                      onClick={() => confirm('¿Descartar esta grabación? No se podrá recuperar.') && removePending(p.id).then(refreshPending)}>
                      <Trash2 className="size-4" /> Descartar
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          </section>
        )}
      </div>
    </>
  )
}
