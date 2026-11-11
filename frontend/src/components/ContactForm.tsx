import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { saveContact, useApiMutation, useCompanies } from '@/lib/hooks'
import type { Contact } from '@/lib/types'
import { blankToNull } from '@/lib/utils'
import DeleteButton from './DeleteButton'
import { Button, ErrorMessage, Field, Input, Select, Textarea } from './ui'

const schema = z.object({
  company_id: z.string().min(1, 'Elige una empresa'),
  first_name: z.string().trim().min(1, 'Obligatorio'),
  last_name: z.string(), position: z.string(), phone: z.string(),
  email: z.string().refine((v) => !v || z.email().safeParse(v).success, 'Correo no válido'),
  is_primary: z.boolean(), summary: z.string(),
})
type Values = z.infer<typeof schema>

/** Create or edit a contact. `companyId` pre-selects (and fixes) the company. */
export default function ContactForm({ contact, companyId, onDone }: {
  contact?: Contact; companyId?: string; onDone: () => void
}) {
  const companies = useCompanies({ page_size: 100 })
  const mutation = useApiMutation((data: Partial<Contact>) => saveContact(contact?.id, data))
  const { register, handleSubmit, formState: { errors } } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      company_id: contact?.company_id ?? companyId ?? '', first_name: contact?.first_name ?? '',
      last_name: contact?.last_name ?? '', position: contact?.position ?? '', phone: contact?.phone ?? '',
      email: contact?.email ?? '', is_primary: contact?.is_primary ?? false, summary: contact?.summary ?? '',
    },
  })

  return (
    <form onSubmit={handleSubmit((v) => mutation.mutate(blankToNull(v) as Partial<Contact>, { onSuccess: onDone }))} className="flex flex-col gap-4">
      <Field label="Empresa *" error={errors.company_id?.message}>
        <Select {...register('company_id')} disabled={!!companyId}>
          <option value="">Elige una empresa…</option>
          {companies.data?.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Nombre *" error={errors.first_name?.message}><Input {...register('first_name')} /></Field>
        <Field label="Apellidos"><Input {...register('last_name')} /></Field>
        <Field label="Cargo"><Input {...register('position')} /></Field>
        <Field label="Teléfono (WhatsApp)"><Input type="tel" placeholder="+34600000000" {...register('phone')} /></Field>
        <Field label="Correo" error={errors.email?.message}><Input type="email" {...register('email')} /></Field>
      </div>
      <label className="flex items-center gap-2 text-sm font-medium">
        <input type="checkbox" className="size-5 accent-primary" {...register('is_primary')} /> Contacto principal
      </label>
      <Field label="Notas"><Textarea {...register('summary')} /></Field>
      <ErrorMessage error={mutation.error} />
      <Button type="submit" loading={mutation.isPending}>{contact ? 'Guardar cambios' : 'Crear contacto'}</Button>
      {contact && (
        <DeleteButton path={`/contacts/${contact.id}`} label="Borrar contacto" onDone={onDone}
          confirmText={`¿Borrar a ${contact.first_name}? Sus interacciones se conservan, sin contacto.`} />
      )}
    </form>
  )
}
