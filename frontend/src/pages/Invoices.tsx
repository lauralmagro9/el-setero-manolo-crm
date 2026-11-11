import { Download, Plus, Search } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import DeleteButton from '@/components/DeleteButton'
import { Badge, Button, Card, EmptyState, ErrorMessage, Input, PageHeader, Select, Spinner } from '@/components/ui'
import { downloadInvoicePdf, resendInvoice, useApiMutation, useInvoices } from '@/lib/hooks'
import type { EmailStatus, Invoice } from '@/lib/types'
import { formatDate } from '@/lib/utils'

const eur = (v: string | number) => new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(Number(v))
const emailLabel: Record<EmailStatus, string> = { pending: 'Pendiente de envío', sent: 'Enviada', failed: 'Error de envío' }
const emailTone = { pending: 'yellow', sent: 'green', failed: 'red' } as const

function Row({ invoice }: { invoice: Invoice }) {
  const resend = useApiMutation(() => resendInvoice(invoice.id))
  const [error, setError] = useState<unknown>(null)
  return (
    <Card className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-semibold">{invoice.invoice_number}</span>
        <span className="font-semibold">{eur(invoice.totals?.total ?? 0)}</span>
      </div>
      <p className="text-sm">{invoice.customer_name} <span className="text-muted">· {invoice.issue_date && formatDate(invoice.issue_date)}</span></p>
      <div className="flex flex-wrap items-center gap-2">
        <Badge>{invoice.invoice_type}</Badge>
        <Badge tone={emailTone[invoice.email_status]}>{emailLabel[invoice.email_status]}</Badge>
        <span className="flex-1" />
        {invoice.email_status !== 'sent' && (
          <Button variant="outline" className="min-h-9" loading={resend.isPending} onClick={() => resend.mutate(undefined)}>Enviar</Button>
        )}
        <Button variant="outline" className="min-h-9" onClick={() => downloadInvoicePdf(invoice).catch(setError)}><Download className="size-4" /> PDF</Button>
        <DeleteButton iconOnly path={`/invoices/${invoice.id}`} label="Borrar factura"
          confirmText={`¿Borrar la factura ${invoice.invoice_number}? Dejará de verse en la aplicación y su número no se reutilizará.`} />
      </div>
      {invoice.email_error && <p className="text-xs text-danger">{invoice.email_error}</p>}
      <ErrorMessage error={resend.error ?? error} />
    </Card>
  )
}

export default function InvoicesPage() {
  const [filters, setFilters] = useState({ search: '', email_status: '', page: 1 })
  const { data, isLoading, error } = useInvoices(filters)
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <>
      <PageHeader title="Facturas" actions={<Link to="/facturas/nueva"><Button><Plus className="size-4" /> Nueva factura</Button></Link>} />
      <div className="mb-4 grid gap-2 sm:grid-cols-2">
        <div className="relative">
          <Search className="absolute top-3.5 left-3 size-4 text-muted" />
          <Input className="pl-9" placeholder="Buscar número o cliente…" value={filters.search}
            onChange={(e) => setFilters({ ...filters, search: e.target.value, page: 1 })} />
        </div>
        <Select aria-label="Estado del envío" value={filters.email_status} onChange={(e) => setFilters({ ...filters, email_status: e.target.value, page: 1 })}>
          <option value="">Cualquier estado de envío</option>
          <option value="pending">Pendiente de envío</option>
          <option value="sent">Enviada</option>
          <option value="failed">Error de envío</option>
        </Select>
      </div>
      <ErrorMessage error={error} />
      {isLoading ? <Spinner /> : data?.items.length === 0 ? <EmptyState>Todavía no hay facturas.</EmptyState> : (
        <div className="flex flex-col gap-3">{data?.items.map((i) => <Row key={i.id} invoice={i} />)}</div>
      )}
      {data && data.total > data.page_size && (
        <div className="mt-4 flex items-center justify-end gap-2 text-sm">
          <Button variant="outline" disabled={filters.page <= 1} onClick={() => setFilters({ ...filters, page: filters.page - 1 })}>Anterior</Button>
          <span>{filters.page} / {pages}</span>
          <Button variant="outline" disabled={filters.page >= pages} onClick={() => setFilters({ ...filters, page: filters.page + 1 })}>Siguiente</Button>
        </div>
      )}
    </>
  )
}
