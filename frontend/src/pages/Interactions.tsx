import { Plus, Search } from 'lucide-react'
import { useState } from 'react'
import InteractionForm from '@/components/InteractionForm'
import InteractionItem from '@/components/InteractionItem'
import { Button, EmptyState, ErrorMessage, Input, Modal, PageHeader, Select, Spinner } from '@/components/ui'
import { useInteractions } from '@/lib/hooks'
import { INTERACTION_TYPES, PROCESSING_STATUSES } from '@/lib/types'

export default function InteractionsPage() {
  const [filters, setFilters] = useState({ search: '', type: '', processing_status: '', unassigned: false, page: 1 })
  const [creating, setCreating] = useState(false)
  const { data, isLoading, error } = useInteractions(filters)
  const set = (patch: Partial<typeof filters>) => setFilters((f) => ({ ...f, page: 1, ...patch }))
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <>
      <PageHeader title="Interacciones y notas" actions={<Button onClick={() => setCreating(true)}><Plus className="size-4" /> Nueva</Button>} />
      <div className="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <div className="relative">
          <Search className="absolute top-3.5 left-3 size-4 text-muted" />
          <Input className="pl-9" placeholder="Buscar texto…" value={filters.search} onChange={(e) => set({ search: e.target.value })} />
        </div>
        <Select aria-label="Tipo" value={filters.type} onChange={(e) => set({ type: e.target.value })}>
          <option value="">Todos los tipos</option>{INTERACTION_TYPES.map((t) => <option key={t}>{t}</option>)}
        </Select>
        <Select aria-label="Procesamiento" value={filters.processing_status} onChange={(e) => set({ processing_status: e.target.value })}>
          <option value="">Cualquier estado</option>{PROCESSING_STATUSES.map((s) => <option key={s}>{s}</option>)}
        </Select>
        <label className="flex min-h-11 items-center gap-2 text-sm font-medium">
          <input type="checkbox" className="size-5 accent-primary" checked={filters.unassigned} onChange={(e) => set({ unassigned: e.target.checked })} />
          Solo sin asignar
        </label>
      </div>
      <ErrorMessage error={error} />
      {isLoading ? <Spinner /> : data?.items.length === 0 ? <EmptyState>No hay interacciones.</EmptyState> : (
        <div className="flex flex-col gap-3">{data?.items.map((i) => <InteractionItem key={i.id} item={i} />)}</div>
      )}
      {data && data.total > data.page_size && (
        <div className="mt-4 flex items-center justify-end gap-2 text-sm">
          <Button variant="outline" disabled={filters.page <= 1} onClick={() => setFilters((f) => ({ ...f, page: f.page - 1 }))}>Anterior</Button>
          <span>{filters.page} / {pages}</span>
          <Button variant="outline" disabled={filters.page >= pages} onClick={() => setFilters((f) => ({ ...f, page: f.page + 1 }))}>Siguiente</Button>
        </div>
      )}
      {creating && <Modal title="Nueva interacción" onClose={() => setCreating(false)}><InteractionForm onDone={() => setCreating(false)} /></Modal>}
    </>
  )
}
