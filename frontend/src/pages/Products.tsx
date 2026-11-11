import { Plus, Search } from 'lucide-react'
import { useState } from 'react'
import ProductForm from '@/components/ProductForm'
import { Badge, Button, Card, EmptyState, ErrorMessage, Input, Modal, PageHeader, Spinner } from '@/components/ui'
import { useDebounced, useProducts } from '@/lib/hooks'
import type { Product } from '@/lib/types'

const pct = (fraction: string) => `${Math.round(Number(fraction) * 10000) / 100} %`

export default function ProductsPage() {
  const [search, setSearch] = useState('')
  const [showInactive, setShowInactive] = useState(false)
  const [dialog, setDialog] = useState<null | { product?: Product }>(null)
  const { data, isLoading, error } = useProducts({ activeOnly: !showInactive, search: useDebounced(search) })

  return (
    <>
      <PageHeader title="Productos" actions={<Button onClick={() => setDialog({})}><Plus className="size-4" /> Nuevo producto</Button>} />
      <div className="mb-4 grid gap-2 sm:grid-cols-2">
        <div className="relative">
          <Search className="absolute top-3.5 left-3 size-4 text-muted" />
          <Input className="pl-9" placeholder="Buscar nombre o especie…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <label className="flex min-h-11 items-center gap-2 text-sm font-medium">
          <input type="checkbox" className="size-5 accent-primary" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
          Mostrar también los inactivos
        </label>
      </div>
      <ErrorMessage error={error} />
      {isLoading ? <Spinner /> : data?.length === 0 ? <EmptyState>No hay productos.</EmptyState> : (
        <>
          {/* Desktop: table */}
          <div className="hidden overflow-hidden rounded-xl border border-border bg-card md:block">
            <table className="w-full text-left text-sm">
              <thead className="bg-primary-soft text-muted">
                <tr><th className="p-3">Nombre</th><th className="p-3">Especie</th><th className="p-3">Formato</th><th className="p-3">Unidad</th><th className="p-3">IVA</th><th className="p-3">Margen objetivo</th><th className="p-3">Estado</th></tr>
              </thead>
              <tbody>
                {data?.map((p) => (
                  <tr key={p.id} onClick={() => setDialog({ product: p })} className="cursor-pointer border-t border-border hover:bg-primary-soft">
                    <td className="p-3 font-medium">{p.name}</td>
                    <td className="p-3 italic">{p.species}</td>
                    <td className="p-3">{p.format}</td>
                    <td className="p-3">{p.base_unit}</td>
                    <td className="p-3">{pct(p.tax_rate)}</td>
                    <td className="p-3">{pct(p.target_net_margin)}</td>
                    <td className="p-3">{p.is_active ? <Badge tone="green">Activo</Badge> : <Badge>Inactivo</Badge>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Phone: cards */}
          <div className="flex flex-col gap-3 md:hidden">
            {data?.map((p) => (
              <button key={p.id} type="button" onClick={() => setDialog({ product: p })} className="text-left">
                <Card className="flex flex-col gap-1">
                  <span className="font-semibold">{p.name}</span>
                  <span className="text-sm text-muted">{[p.species, p.format, p.base_unit].filter(Boolean).join(' · ')}</span>
                  <span className="text-sm">IVA {pct(p.tax_rate)} · Margen {pct(p.target_net_margin)}</span>
                  {!p.is_active && <div><Badge>Inactivo</Badge></div>}
                </Card>
              </button>
            ))}
          </div>
        </>
      )}
      {dialog && (
        <Modal title={dialog.product ? 'Editar producto' : 'Nuevo producto'} onClose={() => setDialog(null)}>
          <ProductForm product={dialog.product} onDone={() => setDialog(null)} />
        </Modal>
      )}
    </>
  )
}
