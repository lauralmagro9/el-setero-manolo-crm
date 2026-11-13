import { Bell, Check, Pencil } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  markAlertRead, markAllAlertsRead, processPendingNotes, useAlerts, useApiMutation, useInteraction, useOrder,
} from '@/lib/hooks'
import { ALERT_TYPE_LABELS, type Alert } from '@/lib/types'
import { formatDate } from '@/lib/utils'
import OrderDraftForm from './OrderDraftForm'
import OrderLinkForm from './OrderLinkForm'
import { Badge, Button, Card, ErrorMessage, Modal, Spinner } from './ui'

const TONE = { info: 'neutral', aviso: 'yellow', critico: 'red' } as const

/** Where an alert leads: the note to review or the company suggested first. */
function alertLink(alert: Alert): string | null {
  if (alert.order_id) return '/pedidos'
  if (alert.interaction_id) return '/interacciones'
  if (alert.company_id) return `/empresas/${alert.company_id}`
  return null
}

/** Dialog to correct what a processed note was linked to (company, contact and, if any, its order). */
function EditLinkDialog({ alert, onClose }: { alert: Alert; onClose: () => void }) {
  const interaction = useInteraction(alert.interaction_id)
  const order = useOrder(alert.order_id)
  const loading = interaction.isLoading || order.isLoading
  const error = interaction.error ?? order.error
  return (
    <Modal title="Editar vinculación de la nota" onClose={onClose}>
      <p className="mb-4 text-sm text-muted">{alert.message}</p>
      <ErrorMessage error={error} />
      {loading ? <Spinner /> : (
        <OrderLinkForm
          interactionId={alert.interaction_id}
          companyId={order.data?.company_id ?? interaction.data?.company_id ?? null}
          contactId={order.data ? order.data.contact_id : interaction.data?.contact_id ?? null}
          order={order.data} onDone={onClose}
        />
      )}
    </Modal>
  )
}

/** Dialog to complete the order the agent found in a note but could not create by itself. */
function CompleteDraftDialog({ draftId, onClose }: { draftId: string; onClose: () => void }) {
  return (
    <Modal title="Completar pedido" onClose={onClose}>
      <OrderDraftForm draftId={draftId} onDone={onClose} />
    </Modal>
  )
}

/** Unread alerts raised by the agents, with "mark as read" and a retry for pending voice notes. */
export default function AlertList() {
  const { data } = useAlerts(true)
  const read = useApiMutation(markAlertRead)
  const readAll = useApiMutation(markAllAlertsRead)
  const retry = useApiMutation(processPendingNotes)
  const [editing, setEditing] = useState<Alert | null>(null)
  const [completing, setCompleting] = useState<string | null>(null)
  const alerts = data?.items ?? []

  return (
    <Card className="mb-6">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 font-semibold"><Bell className="size-5 text-accent-strong" /> Alertas</h2>
        <div className="flex gap-2">
          <Button type="button" variant="outline" loading={retry.isPending} onClick={() => retry.mutate(undefined)}>
            Procesar notas pendientes
          </Button>
          {alerts.length > 0 && (
            <Button type="button" variant="outline" loading={readAll.isPending} onClick={() => readAll.mutate(undefined)}>
              Marcar todas como leídas
            </Button>
          )}
        </div>
      </div>
      <ErrorMessage error={retry.error} />
      {retry.data && (
        <p className="mb-2 text-sm text-muted">
          Procesadas: {retry.data.processed} · pedidos creados: {retry.data.orders_created} · por revisar: {retry.data.needs_review} · errores: {retry.data.errors}
        </p>
      )}
      {alerts.length === 0 ? <p className="text-sm text-muted">No hay alertas sin leer.</p> : (
        <ul className="flex flex-col gap-3">
          {alerts.map((a) => {
            const link = alertLink(a)
            return (
              <li key={a.id} className="flex flex-wrap items-start justify-between gap-2 text-sm">
                <div className="min-w-0 flex-1">
                  <p className="mb-1 flex flex-wrap items-center gap-2">
                    <Badge tone={TONE[a.severity]}>{ALERT_TYPE_LABELS[a.type]}</Badge>
                    <span className="text-xs text-muted">{formatDate(a.created_at)}</span>
                  </p>
                  <p>{a.message}</p>
                  <span className="flex flex-wrap gap-3">
                    {link && <Link to={link} className="text-primary underline">Ver</Link>}
                    {a.type === 'pedido_incompleto' && a.data?.draft_id && (
                      <button onClick={() => setCompleting(a.data!.draft_id!)} className="inline-flex items-center gap-1 font-semibold text-primary underline">
                        <Pencil className="size-3.5" /> Completar pedido
                      </button>
                    )}
                    {a.type === 'nota_procesada' && a.interaction_id && (
                      <button onClick={() => setEditing(a)} className="inline-flex items-center gap-1 text-primary underline">
                        <Pencil className="size-3.5" /> Editar
                      </button>
                    )}
                  </span>
                </div>
                <button
                  onClick={() => read.mutate(a.id)} aria-label="Marcar como leída"
                  className="rounded-lg p-2 hover:bg-primary-soft"
                >
                  <Check className="size-5" />
                </button>
              </li>
            )
          })}
        </ul>
      )}
      {completing && <CompleteDraftDialog draftId={completing} onClose={() => setCompleting(null)} />}
      {editing && <EditLinkDialog alert={editing} onClose={() => setEditing(null)} />}
    </Card>
  )
}
