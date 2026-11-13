import { Bot, Pencil } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import OrderDraftForm from '@/components/OrderDraftForm'
import OrderLinkForm from '@/components/OrderLinkForm'
import { Badge, Button, Card, EmptyState, ErrorMessage, Modal, PageHeader, Select, Spinner } from '@/components/ui'
import { useOrderDrafts, useOrders } from '@/lib/hooks'
import { ORDER_STATUSES, type Order } from '@/lib/types'
import { formatDate, formatDateTime, fullName } from '@/lib/utils'

const TONE = {
  Nuevo: 'yellow', 'Acordando precio': 'yellow', 'Esperando confirmación': 'yellow',
  Confirmado: 'green', Entregado: 'green', Cancelado: 'red',
} as const

/** Customer orders (the ones the order agent creates from voice notes, and the ones edited by hand). */
export default function OrdersPage() {
  const [filters, setFilters] = useState({ status: '', page: 1 })
  const [editing, setEditing] = useState<Order | null>(null)
  const [completing, setCompleting] = useState<string | null>(null)
  const drafts = useOrderDrafts()
  const { data, isLoading, error } = useOrders(filters)
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <>
      <PageHeader title="Pedidos" />
      {!!drafts.data?.length && (
        <section className="mb-6">
          <h2 className="mb-2 font-semibold">Pedidos por completar</h2>
          <div className="flex flex-col gap-3">
            {drafts.data.map((d) => (
              <Card key={d.id} className="flex flex-col gap-2 border-accent">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-semibold">{d.company?.name ?? 'Cliente sin identificar'}</span>
                  <Badge tone="yellow">Incompleto</Badge>
                </div>
                <p className="text-sm text-muted">Falta: {d.missing.join(', ')}</p>
                <div className="flex justify-end">
                  <Button className="min-h-9" onClick={() => setCompleting(d.id)}><Pencil className="size-4" /> Completar</Button>
                </div>
              </Card>
            ))}
          </div>
        </section>
      )}
      <div className="mb-4 max-w-xs">
        <Select aria-label="Estado" value={filters.status} onChange={(e) => setFilters({ status: e.target.value, page: 1 })}>
          <option value="">Todos los estados</option>{ORDER_STATUSES.map((s) => <option key={s}>{s}</option>)}
        </Select>
      </div>
      <ErrorMessage error={error} />
      {isLoading ? <Spinner /> : data?.items.length === 0 ? <EmptyState>No hay pedidos.</EmptyState> : (
        <div className="flex flex-col gap-3">
          {data?.items.map((o) => (
            <Card key={o.id} className="flex flex-col gap-2">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <Link to={`/empresas/${o.company.id}`} className="font-semibold text-primary underline-offset-2 hover:underline">
                  {o.company.name}
                </Link>
                {o.contact && <span className="text-muted">· {fullName(o.contact.first_name, o.contact.last_name)}</span>}
                <Badge tone={TONE[o.status]}>{o.status}</Badge>
                {o.created_by_agent && <Bot className="size-4 text-primary" aria-label="Creado por el agente" />}
              </div>
              <ul className="text-sm">
                {o.items.map((i) => <li key={i.id}>{Number(i.quantity)} {i.unit} · {i.product_name}</li>)}
              </ul>
              <p className="text-sm text-muted">
                Pedido el {formatDateTime(o.requested_at)} ·{' '}
                {o.requested_delivery_date ? `entrega ${formatDate(o.requested_delivery_date)}` : 'sin fecha de entrega'}
              </p>
              {o.notes && <p className="text-sm">{o.notes}</p>}
              <div className="flex items-center justify-between">
                {o.source_interaction_id
                  ? <Link to="/interacciones" className="text-sm text-primary underline">Ver nota de voz</Link>
                  : <span />}
                <Button variant="outline" className="min-h-9" onClick={() => setEditing(o)}><Pencil className="size-4" /> Editar</Button>
              </div>
            </Card>
          ))}
        </div>
      )}
      {data && data.total > data.page_size && (
        <div className="mt-4 flex items-center justify-end gap-2 text-sm">
          <Button variant="outline" disabled={filters.page <= 1} onClick={() => setFilters((f) => ({ ...f, page: f.page - 1 }))}>Anterior</Button>
          <span>{filters.page} / {pages}</span>
          <Button variant="outline" disabled={filters.page >= pages} onClick={() => setFilters((f) => ({ ...f, page: f.page + 1 }))}>Siguiente</Button>
        </div>
      )}
      {completing && (
        <Modal title="Completar pedido" onClose={() => setCompleting(null)}>
          <OrderDraftForm draftId={completing} onDone={() => setCompleting(null)} />
        </Modal>
      )}
      {editing && (
        <Modal title="Editar pedido" onClose={() => setEditing(null)}>
          <OrderLinkForm
            interactionId={editing.source_interaction_id} companyId={editing.company_id}
            contactId={editing.contact_id} order={editing} onDone={() => setEditing(null)}
          />
        </Modal>
      )}
    </>
  )
}
