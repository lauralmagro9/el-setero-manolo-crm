import { AlertTriangle, Mic, PackageMinus } from 'lucide-react'
import { Link } from 'react-router-dom'
import InteractionItem from '@/components/InteractionItem'
import { Badge, Card, EmptyState, ErrorMessage, PageHeader, Spinner } from '@/components/ui'
import { useDashboard } from '@/lib/hooks'
import type { LotAlert } from '@/lib/types'
import { formatDate } from '@/lib/utils'

function Kpi({ label, value, to }: { label: string; value: number; to?: string }) {
  const body = (
    <Card className="h-full">
      <p className="text-3xl font-bold text-primary">{value}</p>
      <p className="text-sm text-muted">{label}</p>
    </Card>
  )
  return to ? <Link to={to}>{body}</Link> : body
}

function LotList({ title, icon, lots, empty }: { title: string; icon: React.ReactNode; lots: LotAlert[]; empty: string }) {
  return (
    <Card>
      <h2 className="mb-2 flex items-center gap-2 font-semibold">{icon}{title}</h2>
      {lots.length === 0 ? <p className="text-sm text-muted">{empty}</p> : (
        <ul className="flex flex-col gap-2">
          {lots.map((l) => (
            <li key={l.lot_id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span><b>{l.product_name}</b> · {l.lot_code}</span>
              <span className="flex gap-2">
                <Badge>{Number(l.available_quantity)} kg</Badge>
                {l.expiry_date && <Badge tone="yellow">Caduca {formatDate(l.expiry_date)}</Badge>}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

export default function DashboardPage() {
  const { data, isLoading, error } = useDashboard()
  if (isLoading) return <Spinner />
  if (error || !data) return <ErrorMessage error={error} />
  const pipeline = data.customers_by_status

  return (
    <>
      <PageHeader title="Inicio" />
      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label={`Interacciones (${data.short_window_days} días)`} value={data.interactions_short_window} to="/interacciones" />
        <Kpi label={`Interacciones (${data.long_window_days} días)`} value={data.interactions_long_window} to="/interacciones" />
        <Kpi label="Notas pendientes de procesar" value={data.pending_interactions} to="/interacciones" />
        <Kpi label="Notas de voz sin asignar" value={data.unassigned_voice_notes} to="/interacciones" />
      </div>

      <Card className="mb-6">
        <h2 className="mb-3 font-semibold">Clientes por estado</h2>
        <div className="flex flex-wrap gap-2">
          {pipeline.map((p) => (
            <Link key={p.customer_status} to={`/empresas?customer_status=${encodeURIComponent(p.customer_status)}`}>
              <Badge tone={p.count ? 'green' : 'neutral'}>{p.customer_status}: {p.count}</Badge>
            </Link>
          ))}
        </div>
      </Card>

      <div className="mb-6 grid gap-3 md:grid-cols-2">
        <LotList title="Lotes a punto de caducar" icon={<AlertTriangle className="size-5 text-accent-strong" />} lots={data.expiring_lots} empty="Nada caduca pronto." />
        <LotList title="Poco stock" icon={<PackageMinus className="size-5 text-accent-strong" />} lots={data.low_stock_lots} empty="Todo el stock está bien." />
      </div>

      <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold"><Mic className="size-5" /> Actividad reciente</h2>
      {data.recent_interactions.length === 0 ? (
        <EmptyState>Aún no hay actividad. Graba tu primera nota de voz con el botón amarillo.</EmptyState>
      ) : (
        <div className="flex flex-col gap-3">
          {data.recent_interactions.map((i) => <InteractionItem key={i.id} item={i} />)}
        </div>
      )}
    </>
  )
}
