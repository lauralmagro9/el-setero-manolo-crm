import { useState } from 'react'
import {
  completeOrderDraft, discardOrderDraft, saveOrderDraft, useApiMutation, useCompanies, useContacts, useOrderDraft,
} from '@/lib/hooks'
import type { OrderDraft } from '@/lib/types'
import { fullName } from '@/lib/utils'
import ItemsEditor, { itemsAreComplete, type EditableItem } from './ItemsEditor'
import { Button, ErrorMessage, Field, Input, Select, Spinner, Textarea } from './ui'

function Form({ draft, onDone }: { draft: OrderDraft; onDone: () => void }) {
  const [company, setCompany] = useState(draft.company_id ?? '')
  const [contact, setContact] = useState(draft.contact_id ?? '')
  const [delivery, setDelivery] = useState(draft.requested_delivery_date ?? '')
  const [notes, setNotes] = useState(draft.notes ?? '')
  const [items, setItems] = useState<EditableItem[]>(
    draft.items.map((i) => ({ product_id: i.product_id ?? '', said: i.product_name, quantity: i.quantity ?? '', unit: i.unit ?? 'kg' })),
  )
  const companies = useCompanies({ page_size: 100 })
  const contacts = useContacts({ company_id: company || undefined })

  const body = () => ({
    company_id: company || null,
    contact_id: contact || null,
    requested_delivery_date: delivery || null,
    notes: notes || null,
    items: items.map((i) => ({
      product_id: i.product_id || null, product_name: i.said ?? null, quantity: i.quantity || null, unit: i.unit || null,
    })),
  })
  const save = useApiMutation(() => saveOrderDraft(draft.id, body()))
  const complete = useApiMutation(() => completeOrderDraft(draft.id, body()))
  const discard = useApiMutation(() => discardOrderDraft(draft.id))
  const ready = !!company && itemsAreComplete(items)

  return (
    <div className="flex flex-col gap-4">
      {draft.reason && <p className="rounded-lg bg-primary-soft p-3 text-sm">{draft.reason}</p>}
      {draft.transcript && (
        <blockquote className="whitespace-pre-wrap rounded-lg border-l-4 border-accent bg-primary-soft p-3 text-sm">{draft.transcript}</blockquote>
      )}
      <Field label="Empresa *">
        <Select value={company} onChange={(e) => { setCompany(e.target.value); setContact('') }}>
          <option value="">Elige una empresa…</option>
          {companies.data?.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>
      </Field>
      <Field label="Contacto">
        <Select value={contact} onChange={(e) => setContact(e.target.value)}>
          <option value="">—</option>
          {company && contacts.data?.items.map((c) => <option key={c.id} value={c.id}>{fullName(c.first_name, c.last_name)}</option>)}
        </Select>
      </Field>
      <ItemsEditor items={items} onChange={setItems} />
      <Field label="Fecha de entrega"><Input type="date" value={delivery} onChange={(e) => setDelivery(e.target.value)} /></Field>
      <Field label="Notas"><Textarea value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
      <ErrorMessage error={save.error ?? complete.error ?? discard.error} />
      {!ready && <p className="text-sm text-muted">Para crear el pedido hacen falta la empresa y, en cada producto, el producto y la cantidad.</p>}
      <div className="flex flex-wrap gap-2">
        <Button type="button" loading={complete.isPending} disabled={!ready} onClick={() => complete.mutate(undefined, { onSuccess: onDone })}>
          Marcar como completo y crear pedido
        </Button>
        <Button type="button" variant="outline" loading={save.isPending} onClick={() => save.mutate(undefined, { onSuccess: onDone })}>
          Guardar y seguir después
        </Button>
        <Button type="button" variant="ghost" loading={discard.isPending} onClick={() => discard.mutate(undefined, { onSuccess: onDone })}>
          No es un pedido
        </Button>
      </div>
    </div>
  )
}

/** Complete an order the agent could not finish: fill in what is missing and create the order. */
export default function OrderDraftForm({ draftId, onDone }: { draftId: string; onDone: () => void }) {
  const { data, isLoading, error } = useOrderDraft(draftId)
  if (isLoading) return <Spinner />
  if (error || !data) return <ErrorMessage error={error} />
  return <Form draft={data} onDone={onDone} />
}
