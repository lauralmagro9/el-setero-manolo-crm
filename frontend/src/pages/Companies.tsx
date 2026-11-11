import { Plus, Search } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import CompanyForm from '@/components/CompanyForm'
import { Badge, Button, Card, EmptyState, ErrorMessage, Input, Modal, PageHeader, Select, Spinner } from '@/components/ui'
import { useCompanies } from '@/lib/hooks'
import { COMPANY_TYPES, CUSTOMER_STATUSES, ROLES, type Company } from '@/lib/types'

export default function CompaniesPage() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const [creating, setCreating] = useState(false)
  const filters = {
    search: params.get('search') ?? '', role: params.get('role') ?? '', type: params.get('type') ?? '',
    customer_status: params.get('customer_status') ?? '', page: Number(params.get('page') ?? 1),
  }
  const { data, isLoading, error } = useCompanies({ ...filters, page_size: 20 })

  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value); else next.delete(key)
    if (key !== 'page') next.delete('page')
    setParams(next, { replace: true })
  }
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <>
      <PageHeader title="Empresas" actions={<Button onClick={() => setCreating(true)}><Plus className="size-4" /> Nueva empresa</Button>} />
      <div className="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <div className="relative sm:col-span-2 lg:col-span-1">
          <Search className="absolute top-3.5 left-3 size-4 text-muted" />
          <Input className="pl-9" placeholder="Buscar nombre, ciudad, CIF…" value={filters.search} onChange={(e) => set('search', e.target.value)} />
        </div>
        <Select value={filters.role} onChange={(e) => set('role', e.target.value)} aria-label="Rol">
          <option value="">Todos los roles</option>{ROLES.map((r) => <option key={r}>{r}</option>)}
        </Select>
        <Select value={filters.type} onChange={(e) => set('type', e.target.value)} aria-label="Tipo">
          <option value="">Todos los tipos</option>{COMPANY_TYPES.map((t) => <option key={t}>{t}</option>)}
        </Select>
        <Select value={filters.customer_status} onChange={(e) => set('customer_status', e.target.value)} aria-label="Estado">
          <option value="">Todos los estados</option>{CUSTOMER_STATUSES.map((s) => <option key={s}>{s}</option>)}
        </Select>
      </div>

      <ErrorMessage error={error} />
      {isLoading ? <Spinner /> : data && data.items.length === 0 ? (
        <EmptyState>No hay empresas con estos filtros.</EmptyState>
      ) : data && (
        <>
          {/* Desktop: table */}
          <div className="hidden overflow-hidden rounded-xl border border-border bg-card md:block">
            <table className="w-full text-left text-sm">
              <thead className="bg-primary-soft text-muted">
                <tr><th className="p-3">Nombre</th><th className="p-3">Tipo</th><th className="p-3">Estado</th><th className="p-3">Ciudad</th><th className="p-3">Teléfono</th></tr>
              </thead>
              <tbody>
                {data.items.map((c: Company) => (
                  <tr key={c.id} onClick={() => navigate(`/empresas/${c.id}`)} className="cursor-pointer border-t border-border hover:bg-primary-soft">
                    <td className="p-3 font-medium">{c.name}</td>
                    <td className="p-3 capitalize">{c.type.join(', ')}</td>
                    <td className="p-3">{c.customer_status && <Badge tone="green">{c.customer_status}</Badge>}</td>
                    <td className="p-3">{c.city}</td>
                    <td className="p-3">{c.phone}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Phone: cards */}
          <div className="flex flex-col gap-3 md:hidden">
            {data.items.map((c: Company) => (
              <Link key={c.id} to={`/empresas/${c.id}`}>
                <Card className="flex flex-col gap-1">
                  <span className="font-semibold">{c.name}</span>
                  <span className="text-sm capitalize text-muted">{c.type.join(', ')}{c.city && ` · ${c.city}`}</span>
                  {c.customer_status && <div><Badge tone="green">{c.customer_status}</Badge></div>}
                </Card>
              </Link>
            ))}
          </div>
          <div className="mt-4 flex items-center justify-between text-sm">
            <span className="text-muted">{data.total} empresas</span>
            <div className="flex items-center gap-2">
              <Button variant="outline" disabled={filters.page <= 1} onClick={() => set('page', String(filters.page - 1))}>Anterior</Button>
              <span>{filters.page} / {pages}</span>
              <Button variant="outline" disabled={filters.page >= pages} onClick={() => set('page', String(filters.page + 1))}>Siguiente</Button>
            </div>
          </div>
        </>
      )}

      {creating && (
        <Modal title="Nueva empresa" onClose={() => setCreating(false)}>
          <CompanyForm onDone={(c) => navigate(`/empresas/${c.id}`)} />
        </Modal>
      )}
    </>
  )
}
