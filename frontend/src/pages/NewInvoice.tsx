import { zodResolver } from '@hookform/resolvers/zod'
import { CheckCircle2, Download, Pencil, Plus, Search, Trash2, TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import { useFieldArray, useForm, useWatch, type UseFormReturn } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { z } from 'zod'
import CompanyFields, { companyDefaults, companyShape, type CompanyValues } from '@/components/CompanyFields'
import CompanyForm from '@/components/CompanyForm'
import { Badge, Button, Card, ErrorMessage, Field, Input, Modal, PageHeader, Select, Spinner, Textarea } from '@/components/ui'
import {
  createInvoice, downloadInvoicePdf, previewInvoice, resendInvoice, useApiMutation, useCompanies,
  useInvoiceConfig, useInvoiceTotals, useProducts,
} from '@/lib/hooks'
import {
  INVOICE_TYPES, type Company, type Invoice, type InvoicePayload, type InvoiceTotals, type NewCompanyPayload,
} from '@/lib/types'
import { blankToNull, cn, todayInput } from '@/lib/utils'

const num = (v: string) => Number(v.replace(',', '.'))
const positive = (v: string) => v.trim() !== '' && num(v) > 0
const nonNegative = (v: string) => v.trim() !== '' && num(v) >= 0
const eur = (v: number | string) => new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(Number(v))

// The company rules (name, role, type, billing data) only apply when a new company is created
const newCompanySchema = z.object(companyShape(true))

const schema = z.object({
  ...companyShape(false),
  mode: z.enum(['existing', 'new']),
  company_id: z.string(),
  invoice_type: z.enum(INVOICE_TYPES),
  issue_date: z.string().min(1, 'Obligatorio'),
  operation_date: z.string().min(1, 'Obligatorio'),
  notes: z.string(),
  lines: z.array(z.object({
    product_id: z.string().min(1, 'Elige un producto'),
    description: z.string().trim().min(1, 'Obligatorio'),
    unit: z.string().trim().min(1, 'Obligatorio'),
    quantity: z.string().refine(positive, 'Mayor que 0'),
    unit_price: z.string().refine(nonNegative, 'Precio no válido'),
  })).min(1),
}).superRefine((v, ctx) => {
  if (v.mode === 'existing' && !v.company_id) ctx.addIssue({ code: 'custom', path: ['company_id'], message: 'Elige un cliente' })
  if (v.mode === 'new') {
    const result = newCompanySchema.safeParse(v)
    if (!result.success) result.error.issues.forEach((i) => ctx.addIssue({ code: 'custom', path: i.path, message: i.message }))
  }
})
type Values = z.infer<typeof schema>

const emptyLine = { product_id: '', description: '', unit: 'kg', quantity: '1', unit_price: '' }
const COMPANY_KEYS = Object.keys(companyShape(false)) as (keyof CompanyValues)[]
const hasBilling = (c: Company) => !!(c.billing_name && c.billing_address && c.tax_id)

function toPayload(v: Values): InvoicePayload {
  const company = Object.fromEntries(COMPANY_KEYS.map((k) => [k, v[k]])) as CompanyValues
  return {
    invoice_type: v.invoice_type,
    issue_date: v.issue_date,
    operation_date: v.operation_date,
    company_id: v.mode === 'existing' ? v.company_id : null,
    new_company: v.mode === 'new' ? (blankToNull(company) as unknown as NewCompanyPayload) : null,
    notes: v.notes || null,
    lines: v.lines.map((l) => ({
      product_id: l.product_id, description: l.description, unit: l.unit,
      quantity: String(num(l.quantity)), unit_price: String(num(l.unit_price)),
    })),
  }
}

/** Result of issuing an invoice: number, email status and the PDF. */
function Result({ invoice, onNew }: { invoice: Invoice; onNew: () => void }) {
  const [current, setCurrent] = useState(invoice)
  const resend = useApiMutation(() => resendInvoice(current.id))
  const [downloadError, setDownloadError] = useState<unknown>(null)
  return (
    <Card className="mx-auto flex max-w-xl flex-col gap-4">
      <div className="flex items-center gap-3">
        <CheckCircle2 className="size-8 text-primary" />
        <div>
          <p className="text-xl font-bold">Factura {current.invoice_number}</p>
          <p className="text-sm text-muted">{current.customer_name} · {eur(current.totals?.total ?? 0)}</p>
        </div>
      </div>
      {current.email_status === 'sent' && <p className="text-sm">Enviada por correo a {current.email_recipient}.</p>}
      {current.email_status === 'pending' && <p className="text-sm text-muted">El envío por correo está desactivado: la factura queda pendiente de envío.</p>}
      {current.email_status === 'failed' && (
        <p className="flex gap-2 rounded-lg border border-danger p-3 text-sm text-danger">
          <TriangleAlert className="size-5 shrink-0" /> La factura se ha guardado, pero el correo falló: {current.email_error}
        </p>
      )}
      <ErrorMessage error={resend.error ?? downloadError} />
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => downloadInvoicePdf(current).catch(setDownloadError)}><Download className="size-4" /> Descargar PDF</Button>
        {current.email_status !== 'sent' && (
          <Button variant="outline" loading={resend.isPending} onClick={() => resend.mutate(undefined, { onSuccess: setCurrent })}>Enviar por correo</Button>
        )}
        <Button variant="outline" onClick={onNew}>Nueva factura</Button>
        <Link to="/facturas"><Button variant="ghost">Ver facturas</Button></Link>
      </div>
    </Card>
  )
}

export default function NewInvoicePage() {
  const config = useInvoiceConfig()
  const products = useProducts()
  const [search, setSearch] = useState('')
  const [reviewing, setReviewing] = useState<InvoicePayload | null>(null)
  const [reviewTotals, setReviewTotals] = useState<InvoiceTotals | null>(null)
  const [issued, setIssued] = useState<Invoice | null>(null)
  const [picked, setPicked] = useState<Company | null>(null)
  const [editingBilling, setEditingBilling] = useState(false)
  const issue = useApiMutation((data: InvoicePayload) => createInvoice(data))

  const defaults = (): Values => ({
    ...companyDefaults(), customer_status: 'Cliente', mode: 'existing', company_id: '', invoice_type: 'VDA',
    issue_date: todayInput(), operation_date: todayInput(), notes: '', lines: [{ ...emptyLine }],
  })
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: defaults() })
  const { register, control, handleSubmit, setValue, reset, formState: { errors } } = form
  const { fields, append, remove } = useFieldArray({ control, name: 'lines' })
  const [mode, invoiceType, lines] = useWatch({ control, name: ['mode', 'invoice_type', 'lines'] })
  const companies = useCompanies({ search, page_size: 6 })

  // Live amounts from the server, for the lines that already have a valid quantity and price
  const valid = lines.map((l, index) => ({ index, quantity: String(num(l.quantity || '')), unit_price: String(num(l.unit_price || '')) }))
    .filter((l) => positive(lines[l.index].quantity) && nonNegative(lines[l.index].unit_price))
  const live = useInvoiceTotals(valid.map(({ quantity, unit_price }) => ({ quantity, unit_price })))
  const lineAmount = (i: number) => {
    const at = valid.findIndex((l) => l.index === i)
    return at >= 0 && live.data?.line_amounts[at] !== undefined ? eur(live.data.line_amounts[at]) : '—'
  }
  const liveTotals = valid.length > 0 ? live.data : undefined

  function chooseMode(next: 'existing' | 'new') {
    setValue('mode', next)
    if (next === 'new') { setPicked(null); setValue('company_id', '') }
  }

  function pick(c: Company) {
    setPicked(c)
    setValue('company_id', c.id, { shouldValidate: true })
  }

  async function review(v: Values) {
    const payload = toPayload(v)
    setReviewTotals(null)
    setReviewing(payload)
    setReviewTotals(await previewInvoice(payload.lines).catch(() => null))
  }

  if (issued) {
    return (
      <>
        <PageHeader title="Factura emitida" />
        <Result invoice={issued} onNew={() => { reset(defaults()); setPicked(null); setIssued(null) }} />
      </>
    )
  }

  // Name and billing data that will be printed, for the review step
  const billing = mode === 'existing' && picked
    ? { name: picked.billing_name, taxId: picked.tax_id, address: picked.billing_address }
    : { name: reviewing?.new_company?.billing_name, taxId: reviewing?.new_company?.tax_id, address: reviewing?.new_company?.billing_address }
  const pending = picked && !hasBilling(picked)

  return (
    <>
      <PageHeader title="Nueva factura" actions={<Link to="/facturas"><Button variant="ghost">Volver a facturas</Button></Link>} />
      <form onSubmit={handleSubmit(review)} className="flex flex-col gap-6">
        <Card className="flex flex-col gap-3">
          <h2 className="font-semibold">Tipo y fechas</h2>
          <div className="flex flex-wrap gap-2">
            {INVOICE_TYPES.map((t) => {
              const enabled = config.data?.enabled_types.includes(t) ?? t === 'VDA'
              return (
                <label key={t} className={cn('flex min-h-11 items-center gap-2 rounded-lg border px-4', enabled ? 'cursor-pointer border-border' : 'opacity-50',
                  invoiceType === t && 'border-primary bg-primary-soft')}>
                  <input type="radio" value={t} disabled={!enabled} className="accent-primary" {...register('invoice_type')} />
                  {t} {!enabled && <Badge>Próximamente</Badge>}
                </label>
              )
            })}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Fecha de expedición *" error={errors.issue_date?.message}><Input type="date" {...register('issue_date')} /></Field>
            <Field label="Fecha de operación *" error={errors.operation_date?.message}><Input type="date" {...register('operation_date')} /></Field>
          </div>
        </Card>

        <Card className="flex flex-col gap-4">
          <h2 className="font-semibold">1. Cliente</h2>
          <div className="flex gap-2">
            {(['existing', 'new'] as const).map((m) => (
              <button type="button" key={m} onClick={() => chooseMode(m)}
                className={cn('min-h-11 flex-1 rounded-lg border px-3 text-sm font-medium', mode === m ? 'border-primary bg-primary text-primary-foreground' : 'border-border bg-card')}>
                {m === 'existing' ? 'Empresa existente' : 'Empresa nueva'}
              </button>
            ))}
          </div>

          {mode === 'existing' && (
            <div className="flex flex-col gap-3">
              <div className="relative">
                <Search className="absolute top-3.5 left-3 size-4 text-muted" />
                <Input className="pl-9" placeholder="Buscar empresa por nombre, ciudad o NIF…" value={search} onChange={(e) => setSearch(e.target.value)} />
              </div>
              <div className="flex flex-col gap-1">
                {companies.data?.items.map((c) => (
                  <button type="button" key={c.id} onClick={() => pick(c)}
                    className={cn('flex flex-col rounded-lg border px-3 py-2 text-left', picked?.id === c.id ? 'border-primary bg-primary-soft' : 'border-border')}>
                    <span className="font-medium">{c.name}</span>
                    <span className="text-xs text-muted">{[c.billing_name && c.billing_name !== c.name ? `Fiscal: ${c.billing_name}` : null, c.tax_id, c.city].filter(Boolean).join(' · ') || 'Sin datos de facturación'}</span>
                  </button>
                ))}
                {companies.data?.items.length === 0 && <p className="text-sm text-muted">Sin resultados. Prueba con «Empresa nueva».</p>}
              </div>
              {errors.company_id && <p className="text-xs text-danger">{errors.company_id.message}</p>}
              {picked && (
                <div className="flex flex-col gap-1 rounded-lg border border-border p-3 text-sm">
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-semibold">Se facturará a</span>
                    <Button type="button" variant="ghost" className="min-h-9" onClick={() => setEditingBilling(true)}>
                      <Pencil className="size-4" /> {pending ? 'Completar datos' : 'Editar'}
                    </Button>
                  </div>
                  {pending && (
                    <p className="flex gap-2 text-danger"><TriangleAlert className="size-4 shrink-0" /> Faltan datos de facturación de esta empresa: complétalos para poder facturar.</p>
                  )}
                  <p>Nombre fiscal: <b>{picked.billing_name ?? '—'}</b></p>
                  <p>NIF/CIF: <b>{picked.tax_id ?? '—'}</b></p>
                  <p>Dirección fiscal: <b>{picked.billing_address ?? '—'}</b></p>
                </div>
              )}
            </div>
          )}

          {mode === 'new' && (
            <>
              <p className="text-sm text-muted">Se creará la empresa como cliente con estos datos. Los de facturación son obligatorios.</p>
              <CompanyFields form={form as unknown as UseFormReturn<CompanyValues>} billingRequired hideRoleAndStatus contactInRow />
            </>
          )}
        </Card>

        <Card className="flex flex-col gap-4">
          <h2 className="font-semibold">2. Datos de la venta</h2>
          {fields.map((field, i) => (
            <div key={field.id} className="flex flex-col gap-3 rounded-lg border border-border p-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Producto *" error={errors.lines?.[i]?.product_id?.message}>
                  <Select {...register(`lines.${i}.product_id`, {
                    onChange: (e) => {
                      const p = products.data?.find((x) => x.id === e.target.value)
                      if (p) {
                        setValue(`lines.${i}.unit`, p.base_unit)
                        if (!lines[i]?.description) setValue(`lines.${i}.description`, p.name, { shouldValidate: true })
                      }
                    },
                  })}>
                    <option value="" disabled>Elige un producto…</option>
                    {products.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </Select>
                </Field>
                <Field label="Descripción en la factura *" error={errors.lines?.[i]?.description?.message}><Input {...register(`lines.${i}.description`)} /></Field>
                <Field label="Cantidad *" error={errors.lines?.[i]?.quantity?.message}><Input inputMode="decimal" {...register(`lines.${i}.quantity`)} /></Field>
                <Field label="Unidad *" error={errors.lines?.[i]?.unit?.message}><Input list="units" {...register(`lines.${i}.unit`)} /></Field>
                <Field label="Precio por unidad (sin IVA) *" error={errors.lines?.[i]?.unit_price?.message}><Input inputMode="decimal" placeholder="0,00" {...register(`lines.${i}.unit_price`)} /></Field>
                <div className="flex items-end justify-between">
                  <span className="text-sm">Total sin IVA: <b>{lineAmount(i)}</b></span>
                  {fields.length > 1 && (
                    <button type="button" aria-label="Quitar línea" onClick={() => remove(i)} className="rounded-lg p-2 hover:bg-primary-soft"><Trash2 className="size-5" /></button>
                  )}
                </div>
              </div>
            </div>
          ))}
          <datalist id="units"><option value="kg" /><option value="unidad" /><option value="caja" /></datalist>
          <Button type="button" variant="outline" onClick={() => append({ ...emptyLine })}><Plus className="size-4" /> Añadir línea</Button>

          <div className="ml-auto w-full max-w-xs rounded-lg bg-primary-soft p-3 text-sm" aria-live="polite">
            <p className="flex justify-between"><span>Total sin IVA (base imponible)</span><b>{liveTotals ? eur(liveTotals.taxable_base) : '—'}</b></p>
            <p className="flex justify-between"><span>IVA ({liveTotals ? Number(liveTotals.vat_rate) * 100 : Number(config.data?.vat_rate ?? 0.1) * 100}%)</span><b>{liveTotals ? eur(liveTotals.vat_amount) : '—'}</b></p>
            <p className="mt-1 flex justify-between border-t border-border pt-1 text-base"><span>Total con IVA</span><b>{liveTotals ? eur(liveTotals.total) : '—'}</b></p>
          </div>

          <Field label="Notas (aparecen en la factura)"><Textarea {...register('notes')} /></Field>
        </Card>

        <Button type="submit" className="self-end" disabled={!!pending}>Revisar factura</Button>
      </form>

      {editingBilling && picked && (
        <Modal title={`Datos de ${picked.name}`} onClose={() => setEditingBilling(false)}>
          <CompanyForm company={picked} onDone={(updated) => { setPicked(updated); setEditingBilling(false) }} />
        </Modal>
      )}

      {reviewing && (
        <Modal title="Revisa la factura" onClose={() => setReviewing(null)}>
          <div className="flex flex-col gap-4 text-sm">
            <p><b>{reviewing.invoice_type}</b> · Expedición {reviewing.issue_date} · Operación {reviewing.operation_date}</p>
            <div>
              <p className="font-semibold">{billing.name}</p>
              <p className="text-muted">{billing.taxId} · {billing.address}</p>
              {reviewing.new_company && <p className="mt-1 text-xs text-muted">Se creará la empresa «{reviewing.new_company.name}» ({(reviewing.new_company.type ?? []).join(', ')}).</p>}
            </div>
            <table className="w-full text-left">
              <thead className="text-muted"><tr><th>Descripción</th><th className="text-right">Cant.</th><th className="text-right">Precio</th><th className="text-right">Total</th></tr></thead>
              <tbody>
                {reviewing.lines.map((l, i) => (
                  <tr key={i} className="border-t border-border">
                    <td className="py-1.5">{l.description}</td>
                    <td className="text-right">{l.quantity} {l.unit}</td>
                    <td className="text-right">{eur(l.unit_price)}</td>
                    <td className="text-right">{reviewTotals ? eur(reviewTotals.line_amounts[i]) : '…'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {reviewTotals ? (
              <div className="ml-auto w-64">
                <p className="flex justify-between"><span>Total sin IVA</span><span>{eur(reviewTotals.taxable_base)}</span></p>
                <p className="flex justify-between"><span>IVA ({Number(reviewTotals.vat_rate) * 100}%)</span><span>{eur(reviewTotals.vat_amount)}</span></p>
                <p className="flex justify-between border-t border-border pt-1 text-base font-bold"><span>Total con IVA</span><span>{eur(reviewTotals.total)}</span></p>
              </div>
            ) : <Spinner />}
            <ErrorMessage error={issue.error} />
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setReviewing(null)}>Volver a editar</Button>
              <Button loading={issue.isPending} disabled={!reviewTotals}
                onClick={() => issue.mutate(reviewing, { onSuccess: (inv) => { setReviewing(null); setIssued(inv) } })}>
                Confirmar y generar
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </>
  )
}
