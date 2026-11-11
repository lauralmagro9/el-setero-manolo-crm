import { zodResolver } from '@hookform/resolvers/zod'
import { useForm, useWatch } from 'react-hook-form'
import { z } from 'zod'
import { saveInteraction, useApiMutation, useCompanies, useContacts } from '@/lib/hooks'
import { DIRECTIONS, INTERACTION_TYPES } from '@/lib/types'
import { blankToNull, fullName, nowLocalInput } from '@/lib/utils'
import { Button, ErrorMessage, Field, Select, Textarea, Input } from './ui'

const schema = z.object({
  company_id: z.string().min(1, 'Elige una empresa'),
  contact_id: z.string(),
  occurred_at: z.string().min(1, 'Obligatorio'),
  type: z.enum(INTERACTION_TYPES),
  direction: z.string(),
  summary: z.string().trim().min(1, 'Obligatorio'),
  notes: z.string(),
})
type Values = z.infer<typeof schema>

/** Register an interaction by hand. `companyId` fixes the company (used from a company page). */
export default function InteractionForm({ companyId, onDone }: { companyId?: string; onDone: () => void }) {
  const companies = useCompanies({ page_size: 100 })
  const mutation = useApiMutation((data: Record<string, unknown>) => saveInteraction(undefined, data))
  const { register, handleSubmit, control, formState: { errors } } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { company_id: companyId ?? '', contact_id: '', occurred_at: nowLocalInput(), type: 'Llamada', direction: '', summary: '', notes: '' },
  })
  const selected = useWatch({ control, name: 'company_id' })
  const contacts = useContacts({ company_id: selected || undefined })

  return (
    <form onSubmit={handleSubmit((v) => mutation.mutate(blankToNull(v), { onSuccess: onDone }))} className="flex flex-col gap-4">
      <Field label="Empresa *" error={errors.company_id?.message}>
        <Select {...register('company_id')} disabled={!!companyId}>
          <option value="">Elige una empresa…</option>
          {companies.data?.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Contacto">
          <Select {...register('contact_id')}>
            <option value="">—</option>
            {selected && contacts.data?.items.map((c) => <option key={c.id} value={c.id}>{fullName(c.first_name, c.last_name)}</option>)}
          </Select>
        </Field>
        <Field label="Fecha y hora *" error={errors.occurred_at?.message}><Input type="datetime-local" {...register('occurred_at')} /></Field>
        <Field label="Tipo"><Select {...register('type')}>{INTERACTION_TYPES.map((t) => <option key={t}>{t}</option>)}</Select></Field>
        <Field label="Dirección">
          <Select {...register('direction')}><option value="">—</option>{DIRECTIONS.map((d) => <option key={d}>{d}</option>)}</Select>
        </Field>
      </div>
      <Field label="Resumen *" error={errors.summary?.message}><Textarea {...register('summary')} /></Field>
      <Field label="Notas"><Textarea {...register('notes')} /></Field>
      <ErrorMessage error={mutation.error} />
      <Button type="submit" loading={mutation.isPending}>Guardar interacción</Button>
    </form>
  )
}
