import { ArrowLeft, Mail, MapPin, Pencil, Phone, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import CompanyForm from '@/components/CompanyForm'
import DeleteButton from '@/components/DeleteButton'
import ContactForm from '@/components/ContactForm'
import InteractionForm from '@/components/InteractionForm'
import InteractionItem from '@/components/InteractionItem'
import { Badge, Button, Card, EmptyState, ErrorMessage, Modal, Spinner } from '@/components/ui'
import { deleteContact, useApiMutation, useCompany, useInteractions } from '@/lib/hooks'
import type { Contact } from '@/lib/types'
import { fullName } from '@/lib/utils'

type Dialog = null | 'company' | 'interaction' | { contact?: Contact }

export default function CompanyDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { data: company, isLoading, error } = useCompany(id)
  const interactions = useInteractions({ company_id: id })
  const [dialog, setDialog] = useState<Dialog>(null)
  const remove = useApiMutation(deleteContact)
  if (isLoading) return <Spinner />
  if (error || !company) return <ErrorMessage error={error} />
  const close = () => setDialog(null)

  return (
    <>
      <Link to="/empresas" className="mb-3 inline-flex items-center gap-1 text-sm text-muted hover:underline"><ArrowLeft className="size-4" /> Empresas</Link>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{company.name}</h1>
          <div className="mt-2 flex flex-wrap gap-2">
            {company.roles.map((r) => <Badge key={r}>{r}</Badge>)}
            {company.type.map((t) => <Badge key={t}>{t}</Badge>)}
            {company.customer_status && <Badge tone="green">{company.customer_status}</Badge>}
            {company.supplier_status && <Badge tone="yellow">Proveedor: {company.supplier_status}</Badge>}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setDialog('company')}><Pencil className="size-4" /> Editar</Button>
          <DeleteButton path={`/companies/${company.id}`} label="Borrar empresa" onDone={() => navigate('/empresas')}
            confirmText={`¿Borrar «${company.name}»? También se ocultarán sus contactos, interacciones y pedidos. Si tiene facturas, no se podrá borrar.`} />
        </div>
      </div>

      <Card className="mb-6 flex flex-col gap-2 text-sm">
        {company.phone && <a href={`tel:${company.phone}`} className="flex items-center gap-2"><Phone className="size-4" /> {company.phone}</a>}
        {company.email && <a href={`mailto:${company.email}`} className="flex items-center gap-2"><Mail className="size-4" /> {company.email}</a>}
        {(company.address || company.city) && (
          <p className="flex items-center gap-2"><MapPin className="size-4" /> {[company.address, company.city, company.region, company.country].filter(Boolean).join(', ')}</p>
        )}
        {company.tax_id && <p className="text-muted">NIF/CIF: {company.tax_id}</p>}
        {(company.billing_name || company.billing_address) && (
          <div className="rounded-lg border border-border p-3">
            <p className="mb-1 font-semibold">Datos de facturación</p>
            <p>Nombre fiscal: <b>{company.billing_name ?? '—'}</b></p>
            <p>Dirección fiscal: <b>{company.billing_address ?? '—'}</b></p>
          </div>
        )}
        {company.description && <p className="whitespace-pre-wrap">{company.description}</p>}
      </Card>

      <section className="mb-6">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Contactos</h2>
          <Button variant="outline" onClick={() => setDialog({})}><Plus className="size-4" /> Añadir</Button>
        </div>
        {company.contacts.length === 0 ? <EmptyState>Sin contactos todavía.</EmptyState> : (
          <div className="grid gap-3 sm:grid-cols-2">
            {company.contacts.map((c) => (
              <Card key={c.id} className="flex items-start justify-between gap-2">
                <div className="text-sm">
                  <p className="font-semibold">{fullName(c.first_name, c.last_name)} {c.is_primary && <Badge tone="yellow">Principal</Badge>}</p>
                  {c.position && <p className="text-muted">{c.position}</p>}
                  {c.phone && <a href={`tel:${c.phone}`} className="block">{c.phone}</a>}
                  {c.email && <a href={`mailto:${c.email}`} className="block">{c.email}</a>}
                </div>
                <div className="flex">
                  <button aria-label="Editar contacto" className="rounded-lg p-2 hover:bg-primary-soft" onClick={() => setDialog({ contact: c })}><Pencil className="size-4" /></button>
                  <button
                    aria-label="Borrar contacto" className="rounded-lg p-2 hover:bg-primary-soft"
                    onClick={() => confirm(`¿Borrar a ${c.first_name}?`) && remove.mutate(c.id)}
                  ><Trash2 className="size-4" /></button>
                </div>
              </Card>
            ))}
          </div>
        )}
        <ErrorMessage error={remove.error} />
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Historial</h2>
          <Button variant="outline" onClick={() => setDialog('interaction')}><Plus className="size-4" /> Interacción</Button>
        </div>
        {interactions.data?.items.length === 0 ? <EmptyState>Sin interacciones todavía.</EmptyState> : (
          <div className="flex flex-col gap-3">
            {interactions.data?.items.map((i) => <InteractionItem key={i.id} item={i} showCompany={false} />)}
          </div>
        )}
      </section>

      {dialog === 'company' && <Modal title="Editar empresa" onClose={close}><CompanyForm company={company} onDone={close} /></Modal>}
      {dialog === 'interaction' && <Modal title="Nueva interacción" onClose={close}><InteractionForm companyId={company.id} onDone={close} /></Modal>}
      {dialog && typeof dialog === 'object' && (
        <Modal title={dialog.contact ? 'Editar contacto' : 'Nuevo contacto'} onClose={close}>
          <ContactForm contact={dialog.contact} companyId={company.id} onDone={close} />
        </Modal>
      )}
    </>
  )
}
