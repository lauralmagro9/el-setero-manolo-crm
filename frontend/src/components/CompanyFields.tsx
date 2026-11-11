import { useEffect, useRef, useState } from 'react'
import { Controller, useWatch, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'
import { parseAddress } from '@/lib/hooks'
import { COMPANY_TYPES, CUSTOMER_STATUSES, ROLES, SUPPLIER_STATUSES, type Company } from '@/lib/types'
import { cn } from '@/lib/utils'
import { Field, Input, Select, Textarea } from './ui'

/** Rules for the company fields. With `strict`, roles, type and the fiscal data are mandatory. */
export function companyShape(strict: boolean) {
  const required = (message: string) => (strict ? z.string().trim().min(1, message) : z.string())
  return {
    name: strict ? z.string().trim().min(1, 'Obligatorio') : z.string(),
    tax_id: required('Obligatorio'), website: z.string(), phone: z.string(),
    email: z.string().refine((v) => !v || z.email().safeParse(v).success, 'Correo no válido'),
    address: required('Obligatorio: calle, número y ciudad'), city: z.string(), region: z.string(), country: z.string(),
    roles: strict ? z.array(z.enum(ROLES)).min(1, 'Elige al menos un rol') : z.array(z.enum(ROLES)),
    type: strict ? z.array(z.enum(COMPANY_TYPES)).min(1, 'Elige al menos un tipo') : z.array(z.enum(COMPANY_TYPES)),
    customer_status: z.string(), supplier_status: z.string(), description: z.string(),
    billing_name: required('Obligatorio'), billing_address: required('Obligatorio'),
  }
}

/** Strict rules for a company that is saved on its own (the fiscal data stays optional there). */
export const companyFormSchema = z.object({
  ...companyShape(true),
  tax_id: z.string(), billing_name: z.string(), billing_address: z.string(),
})
/** Editing an old company that has no address yet must not be blocked: the address is only mandatory on creation. */
export const companyEditSchema = companyFormSchema.extend({ address: z.string() })
export type CompanyValues = z.infer<typeof companyFormSchema>

export function companyDefaults(company?: Company): CompanyValues {
  return {
    name: company?.name ?? '', tax_id: company?.tax_id ?? '', website: company?.website ?? '',
    phone: company?.phone ?? '', email: company?.email ?? '', address: company?.address ?? '',
    city: company?.city ?? '', region: company?.region ?? '', country: company?.country ?? '',
    roles: company?.roles ?? ['Cliente'], type: company?.type ?? [],
    customer_status: company?.customer_status ?? '', supplier_status: company?.supplier_status ?? '',
    description: company?.description ?? '',
    billing_name: company?.billing_name ?? '', billing_address: company?.billing_address ?? '',
  }
}

/** Toggle buttons for a multiple choice. */
function Chips<T extends string>({ options, value, onChange }: {
  options: readonly T[]; value: T[]; onChange: (v: T[]) => void
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => {
        const on = value.includes(o)
        return (
          <button
            type="button" key={o} aria-pressed={on}
            onClick={() => onChange(on ? value.filter((x) => x !== o) : [...value, o])}
            className={cn('min-h-9 rounded-full border px-3 text-sm capitalize',
              on ? 'border-primary bg-primary text-primary-foreground' : 'border-border bg-card')}
          >
            {o}
          </button>
        )
      })}
    </div>
  )
}

const ADDRESS_FIELDS = ['city', 'region', 'country'] as const

/**
 * Keeps the derived fields in sync while the user types the address:
 * - the billing address copies the address until the user writes a different one;
 * - city, province and country are looked up when leaving the address field, and only replace
 *   fields that are empty or were filled by a previous lookup (never what the user typed).
 */
function useAddressSync(form: UseFormReturn<CompanyValues>) {
  const { control, getValues, setValue } = form
  const address = useWatch({ control, name: 'address' })
  const billingOwn = useRef(!!getValues('billing_address') && getValues('billing_address') !== getValues('address'))
  const autoFilled = useRef(new Set<string>())
  const lastLookup = useRef(getValues('address').trim())
  const [looking, setLooking] = useState(false)

  useEffect(() => {
    if (!billingOwn.current) setValue('billing_address', address, { shouldValidate: !!address })
  }, [address, setValue])

  /** The user is writing the billing address: stop copying, unless they empty it or repeat the address. */
  const onBillingChange = (value: string) => {
    billingOwn.current = value !== '' && value !== getValues('address')
    if (!billingOwn.current) setValue('billing_address', getValues('address'))
  }
  /** The user typed in a derived field: a later lookup must not overwrite it. */
  const onManual = (field: string) => autoFilled.current.delete(field)

  async function lookup() {
    const query = getValues('address').trim()
    if (query.length < 4 || query === lastLookup.current) return
    lastLookup.current = query
    setLooking(true)
    try {
      const found = await parseAddress(query)
      for (const field of ADDRESS_FIELDS) {
        const value = found[field]
        if (value && (!getValues(field) || autoFilled.current.has(field))) {
          setValue(field, value, { shouldDirty: true })
          autoFilled.current.add(field)
        }
      }
    } catch {
      // The lookup is only a convenience: the fields can be typed by hand
    } finally {
      setLooking(false)
    }
  }
  return { looking, lookup, onBillingChange, onManual }
}

/** The inputs of a company (including its fiscal data), bound to a parent react-hook-form. */
export default function CompanyFields({ form, billingRequired = false, hideRoleAndStatus = false, contactInRow = false }: {
  form: UseFormReturn<CompanyValues>
  billingRequired?: boolean
  /** Put phone, email and website on a single row (for wide containers, e.g. the invoice form). */
  contactInRow?: boolean
  /** Hidden when the company is created from an invoice: it is always created as a customer. */
  hideRoleAndStatus?: boolean
}) {
  const { register, control, formState: { errors } } = form
  const { looking, lookup, onBillingChange, onManual } = useAddressSync(form)
  const star = billingRequired ? ' *' : ''
  return (
    <div className="flex flex-col gap-4">
      <Field label="Nombre comercial *" error={errors.name?.message}><Input {...register('name')} /></Field>
      {!hideRoleAndStatus && (
        <Field label="Rol *" error={errors.roles?.message}>
          <Controller control={control} name="roles" render={({ field }) => <Chips options={ROLES} value={field.value} onChange={field.onChange} />} />
        </Field>
      )}
      <Field label="Tipo de negocio *" error={errors.type?.message}>
        <Controller control={control} name="type" render={({ field }) => <Chips options={COMPANY_TYPES} value={field.value} onChange={field.onChange} />} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        {!hideRoleAndStatus && (
          <>
            <Field label="Estado como cliente">
              <Select {...register('customer_status')}>
                <option value="">—</option>
                {CUSTOMER_STATUSES.map((s) => <option key={s}>{s}</option>)}
              </Select>
            </Field>
            <Field label="Estado como proveedor">
              <Select {...register('supplier_status')}>
                <option value="">—</option>
                {SUPPLIER_STATUSES.map((s) => <option key={s}>{s}</option>)}
              </Select>
            </Field>
          </>
        )}
      </div>
      {/* Phone, email and website share one row when there is room (invoice flow) */}
      <div className={cn('grid gap-4', contactInRow ? 'sm:grid-cols-3' : 'sm:grid-cols-2')}>
        <Field label="Teléfono"><Input type="tel" {...register('phone')} /></Field>
        <Field label="Correo" error={errors.email?.message}><Input type="email" {...register('email')} /></Field>
        <Field label="Web"><Input {...register('website')} /></Field>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={looking ? 'Dirección * (buscando ciudad, provincia y país…)' : 'Dirección *'} error={errors.address?.message} className="sm:col-span-2">
          <Input placeholder="Calle, número, ciudad" {...register('address', { onBlur: lookup })} />
          <span className="text-xs font-normal text-muted">Incluye la ciudad: con ella se detectan la provincia y el país.</span>
        </Field>
        <Field label="Ciudad"><Input {...register('city', { onChange: () => onManual('city') })} /></Field>
        <Field label="Provincia"><Input {...register('region', { onChange: () => onManual('region') })} /></Field>
        <Field label="País"><Input {...register('country', { onChange: () => onManual('country') })} /></Field>
      </div>
      <Field label="Descripción"><Textarea {...register('description')} /></Field>

      <fieldset className="flex flex-col gap-3 rounded-lg border border-border p-3">
        <legend className="px-1 text-sm font-semibold">Datos fiscales</legend>
        <p className="text-xs text-muted">Es lo que aparece en las facturas (p. ej. el nombre del dueño si es un autónomo). La dirección fiscal es la de la empresa salvo que la cambies.</p>
        <Field label={`Nombre fiscal${star}`} error={errors.billing_name?.message}><Input {...register('billing_name')} /></Field>
        <Field label={`NIF / CIF fiscal${star}`} error={errors.tax_id?.message}><Input {...register('tax_id')} /></Field>
        <Field label={`Dirección fiscal${star}`} error={errors.billing_address?.message}>
          <Input {...register('billing_address', { onChange: (e) => onBillingChange(e.target.value) })} />
        </Field>
      </fieldset>
    </div>
  )
}
