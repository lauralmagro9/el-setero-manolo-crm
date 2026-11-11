import { Plus, Search } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import ContactForm from '@/components/ContactForm'
import { Badge, Button, Card, EmptyState, ErrorMessage, Input, Modal, PageHeader, Spinner } from '@/components/ui'
import { useContacts } from '@/lib/hooks'
import type { Contact } from '@/lib/types'
import { fullName } from '@/lib/utils'

export default function ContactsPage() {
  const [search, setSearch] = useState('')
  const [dialog, setDialog] = useState<null | { contact?: Contact }>(null)
  const { data, isLoading, error } = useContacts({ search })

  return (
    <>
      <PageHeader title="Contactos" actions={<Button onClick={() => setDialog({})}><Plus className="size-4" /> Nuevo contacto</Button>} />
      <div className="relative mb-4">
        <Search className="absolute top-3.5 left-3 size-4 text-muted" />
        <Input className="pl-9" placeholder="Buscar nombre, teléfono, correo…" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>
      <ErrorMessage error={error} />
      {isLoading ? <Spinner /> : data?.items.length === 0 ? <EmptyState>No hay contactos.</EmptyState> : (
        <div className="grid gap-3 md:grid-cols-2">
          {data?.items.map((c) => (
            <Card key={c.id} className="flex items-start justify-between gap-2">
              <div className="text-sm">
                <p className="font-semibold">{fullName(c.first_name, c.last_name)} {c.is_primary && <Badge tone="yellow">Principal</Badge>}</p>
                <Link to={`/empresas/${c.company.id}`} className="text-primary hover:underline">{c.company.name}</Link>
                {c.position && <p className="text-muted">{c.position}</p>}
                {c.phone && <a href={`tel:${c.phone}`} className="block">{c.phone}</a>}
                {c.email && <a href={`mailto:${c.email}`} className="block">{c.email}</a>}
              </div>
              <Button variant="outline" onClick={() => setDialog({ contact: c })}>Editar</Button>
            </Card>
          ))}
        </div>
      )}
      {dialog && (
        <Modal title={dialog.contact ? 'Editar contacto' : 'Nuevo contacto'} onClose={() => setDialog(null)}>
          <ContactForm contact={dialog.contact} onDone={() => setDialog(null)} />
        </Modal>
      )}
    </>
  )
}
