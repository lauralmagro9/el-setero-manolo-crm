import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { saveCompany, useApiMutation } from '@/lib/hooks'
import type { Company, CompanyDetail } from '@/lib/types'
import { blankToNull } from '@/lib/utils'
import CompanyFields, { companyDefaults, companyEditSchema, companyFormSchema, type CompanyValues } from './CompanyFields'
import { Button, ErrorMessage } from './ui'

/** Create (no `company`) or edit a company. Billing data is optional here and mandatory when invoicing. */
export default function CompanyForm({ company, onDone }: { company?: Company; onDone: (c: CompanyDetail) => void }) {
  const mutation = useApiMutation((data: Partial<Company>) => saveCompany(company?.id, data))
  const form = useForm<CompanyValues>({ resolver: zodResolver(company ? companyEditSchema : companyFormSchema), defaultValues: companyDefaults(company) })

  return (
    <form
      onSubmit={form.handleSubmit((v) => mutation.mutate(blankToNull(v) as Partial<Company>, { onSuccess: onDone }))}
      className="flex flex-col gap-4"
    >
      <CompanyFields form={form} />
      <ErrorMessage error={mutation.error} />
      <Button type="submit" loading={mutation.isPending}>{company ? 'Guardar cambios' : 'Crear empresa'}</Button>
    </form>
  )
}
