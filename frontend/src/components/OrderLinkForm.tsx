import { useState } from 'react'
import { saveInteraction, saveOrder, useApiMutation, useCompanies, useContacts } from '@/lib/hooks'
import { ORDER_STATUSES, type Order, type OrderStatus } from '@/lib/types'
import { fullName } from '@/lib/utils'
import ItemsEditor, { itemsAreComplete, type EditableItem } from './ItemsEditor'
import { Button, ErrorMessage, Field, Input, Select, Textarea } from './ui'

interface Props {
  /** The voice note the data comes from; its company and contact are kept in step with the order. */
  interactionId?: string | null
  /** Company and contact currently linked (to the order when there is one, else to the note). */
  companyId: string | null
  contactId: string | null
  order?: Order | null
  onDone: () => void
}

/** Edit what a processed note was linked to: company, contact and, if there is an order, its date, status and notes. */
export default function OrderLinkForm({ interactionId, companyId, contactId, order, onDone }: Props) {
  const [company, setCompany] = useState(companyId ?? '')
  const [contact, setContact] = useState(contactId ?? '')
  const [delivery, setDelivery] = useState(order?.requested_delivery_date ?? '')
  const [status, setStatus] = useState<OrderStatus>(order?.status ?? 'Nuevo')
  const [notes, setNotes] = useState(order?.notes ?? '')
  const [items, setItems] = useState<EditableItem[]>(
    (order?.items ?? []).map((i) => ({ id: i.id, product_id: i.product_id, quantity: String(Number(i.quantity)), unit: i.unit })),
  )
  const companies = useCompanies({ page_size: 100 })
  const contacts = useContacts({ company_id: company || undefined })

  const mutation = useApiMutation(async () => {
    const link = { company_id: company, contact_id: contact || null }
    if (order) {
      await saveOrder(order.id, {
        ...link, requested_delivery_date: delivery || null, status, notes: notes || null,
        items: items.map((i) => ({ id: i.id, product_id: i.product_id, quantity: i.quantity, unit: i.unit || null })),
      })
    }
    if (interactionId) await saveInteraction(interactionId, link)
  })

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); mutation.mutate(undefined, { onSuccess: onDone }) }}
      className="flex flex-col gap-4"
    >
      <Field label="Empresa *">
        <Select value={company} onChange={(e) => { setCompany(e.target.value); setContact('') }} required>
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
      {order && (
        <>
          <ItemsEditor items={items} onChange={setItems} />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Fecha de entrega"><Input type="date" value={delivery} onChange={(e) => setDelivery(e.target.value)} /></Field>
            <Field label="Estado">
              <Select value={status} onChange={(e) => setStatus(e.target.value as OrderStatus)}>
                {ORDER_STATUSES.map((s) => <option key={s}>{s}</option>)}
              </Select>
            </Field>
          </div>
          <Field label="Notas"><Textarea value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
        </>
      )}
      <ErrorMessage error={mutation.error} />
      <Button type="submit" loading={mutation.isPending} disabled={!company || (!!order && !itemsAreComplete(items))}>Guardar cambios</Button>
    </form>
  )
}
