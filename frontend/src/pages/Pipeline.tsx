import { DndContext, PointerSensor, TouchSensor, useDraggable, useDroppable, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core'
import { useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Card, ErrorMessage, PageHeader, Spinner } from '@/components/ui'
import { moveCompany, usePipelineCompanies } from '@/lib/hooks'
import { CUSTOMER_STATUSES, type Company, type CustomerStatus, type Page } from '@/lib/types'
import { cn } from '@/lib/utils'

function CompanyCard({ company }: { company: Company }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id: company.id })
  return (
    <div
      ref={setNodeRef} {...listeners} {...attributes}
      style={{ transform: transform ? `translate(${transform.x}px, ${transform.y}px)` : undefined, touchAction: 'none' }}
      className={cn('cursor-grab', isDragging && 'z-10 opacity-80')}
    >
      <Card className="p-3">
        <Link to={`/empresas/${company.id}`} className="font-medium hover:underline" onPointerDown={(e) => e.stopPropagation()}>
          {company.name}
        </Link>
        {company.city && <p className="text-xs text-muted">{company.city}</p>}
      </Card>
    </div>
  )
}

function Column({ status, companies }: { status: CustomerStatus; companies: Company[] }) {
  const { setNodeRef, isOver } = useDroppable({ id: status })
  return (
    <section
      ref={setNodeRef}
      className={cn('flex w-64 shrink-0 flex-col gap-2 rounded-xl border border-border p-2', isOver ? 'bg-primary-soft' : 'bg-background')}
    >
      <h2 className="flex items-center justify-between px-1 text-sm font-semibold">
        {status} <span className="rounded-full bg-accent px-2 text-xs text-accent-foreground">{companies.length}</span>
      </h2>
      {companies.map((c) => <CompanyCard key={c.id} company={c} />)}
    </section>
  )
}

/** Kanban of customers by status; drag a card to another column to change its status. */
export default function PipelinePage() {
  const queryClient = useQueryClient()
  const { data, isLoading, error } = usePipelineCompanies()
  // A short press scrolls the page on touch screens; a long press starts the drag
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 8 } }),
  )
  const key = ['companies', 'pipeline']

  async function onDragEnd(event: DragEndEvent) {
    const status = event.over?.id as CustomerStatus | undefined
    const id = String(event.active.id)
    const previous = queryClient.getQueryData<Page<Company>>(key)
    if (!status || !previous || previous.items.find((c) => c.id === id)?.customer_status === status) return
    // Optimistic update; undone if the API refuses
    queryClient.setQueryData<Page<Company>>(key, {
      ...previous, items: previous.items.map((c) => (c.id === id ? { ...c, customer_status: status } : c)),
    })
    try {
      await moveCompany(id, status)
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    } catch {
      queryClient.setQueryData(key, previous)
    }
  }

  if (isLoading) return <Spinner />
  return (
    <>
      <PageHeader title="Pipeline de clientes" />
      <ErrorMessage error={error} />
      <p className="mb-3 text-sm text-muted">Arrastra una empresa a otra columna para cambiar su estado (en el móvil, mantén pulsado).</p>
      <DndContext sensors={sensors} onDragEnd={onDragEnd}>
        <div className="-mx-4 flex gap-3 overflow-x-auto px-4 pb-4 md:mx-0 md:px-0">
          {CUSTOMER_STATUSES.map((s) => (
            <Column key={s} status={s} companies={data?.items.filter((c) => c.customer_status === s) ?? []} />
          ))}
        </div>
      </DndContext>
    </>
  )
}
