import { Mic } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { saveInteraction, useApiMutation, useCompanies } from '@/lib/hooks'
import type { Interaction } from '@/lib/types'
import { formatDateTime, fullName } from '@/lib/utils'
import DeleteButton from './DeleteButton'
import { Badge, Button, Card, ErrorMessage, Select } from './ui'

const statusTone = { pendiente: 'yellow', procesando: 'yellow', procesada: 'green', error: 'red' } as const

/** One interaction: header, summary/transcript and, for unassigned notes, a company picker. */
export default function InteractionItem({ item, showCompany = true }: { item: Interaction; showCompany?: boolean }) {
  const [companyId, setCompanyId] = useState('')
  const companies = useCompanies({ page_size: 100 })
  const assign = useApiMutation(() => saveInteraction(item.id, { company_id: companyId }))
  const isVoice = item.source === 'nota_de_voz'

  return (
    <Card className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {isVoice && <Mic className="size-4 text-primary" aria-label="Nota de voz" />}
        <span className="font-semibold">{item.type}</span>
        <span className="text-muted">{formatDateTime(item.occurred_at)}</span>
        <Badge tone={statusTone[item.processing_status]}>{item.processing_status}</Badge>
      </div>
      {showCompany && item.company && (
        <Link to={`/empresas/${item.company.id}`} className="font-medium text-primary underline-offset-2 hover:underline">
          {item.company.name}
          {item.contact && ` · ${fullName(item.contact.first_name, item.contact.last_name)}`}
        </Link>
      )}
      {item.summary && <p>{item.summary}</p>}
      {item.transcript && (
        <blockquote className="whitespace-pre-wrap rounded-lg border-l-4 border-accent bg-primary-soft p-3 text-sm">{item.transcript}</blockquote>
      )}
      {item.notes && <p className="text-sm text-muted">{item.notes}</p>}
      {!item.company_id && (
        <div className="flex flex-wrap gap-2 pt-1">
          <Badge tone="yellow">Sin asignar</Badge>
          <Select className="min-w-0 flex-1 py-1.5 text-sm" value={companyId} onChange={(e) => setCompanyId(e.target.value)} aria-label="Asignar empresa">
            <option value="">Asignar a empresa…</option>
            {companies.data?.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
          <Button className="min-h-9" disabled={!companyId} loading={assign.isPending} onClick={() => assign.mutate(undefined)}>Asignar</Button>
          <ErrorMessage error={assign.error} />
        </div>
      )}
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted">{item.created_by && `Por ${item.created_by}`}</p>
        <DeleteButton iconOnly path={`/interactions/${item.id}`} label="Borrar interacción"
          confirmText="¿Borrar esta interacción? Dejará de verse en la aplicación." />
      </div>
    </Card>
  )
}
