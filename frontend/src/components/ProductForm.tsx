import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { saveProduct, useApiMutation } from '@/lib/hooks'
import { PRODUCT_FORMATS, type Product } from '@/lib/types'
import { blankToNull } from '@/lib/utils'
import DeleteButton from './DeleteButton'
import { Button, ErrorMessage, Field, Input, Select, Textarea } from './ui'

const percent = (v: string) => v.trim() !== '' && Number(v.replace(',', '.')) >= 0 && Number(v.replace(',', '.')) < 100

const schema = z.object({
  name: z.string().trim().min(1, 'Obligatorio'),
  species: z.string(),
  format: z.enum(PRODUCT_FORMATS),
  description: z.string(),
  base_unit: z.string().trim().min(1, 'Obligatorio'),
  tax_percent: z.string().refine(percent, 'Entre 0 y 99,99'),
  margin_percent: z.string().refine(percent, 'Entre 0 y 99,99'),
  is_active: z.boolean(),
})
type Values = z.infer<typeof schema>

/** Fractions (0.10) are shown as percentages (10) and converted back on save. */
const toPercent = (fraction: string) => String(Math.round(Number(fraction) * 10000) / 100)
const toFraction = (percentText: string) => String(Math.round(Number(percentText.replace(',', '.')) * 100) / 10000)

/** Create (no `product`) or edit a product. */
export default function ProductForm({ product, onDone }: { product?: Product; onDone: () => void }) {
  const mutation = useApiMutation((data: Partial<Product>) => saveProduct(product?.id, data))
  const { register, handleSubmit, formState: { errors } } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: product?.name ?? '', species: product?.species ?? '', format: product?.format ?? 'Fresco',
      description: product?.description ?? '', base_unit: product?.base_unit ?? 'kg',
      tax_percent: product ? toPercent(product.tax_rate) : '10',
      margin_percent: product ? toPercent(product.target_net_margin) : '',
      is_active: product?.is_active ?? true,
    },
  })

  function submit(v: Values) {
    const { tax_percent, margin_percent, ...rest } = v
    mutation.mutate(
      { ...blankToNull(rest), tax_rate: toFraction(tax_percent), target_net_margin: toFraction(margin_percent) } as Partial<Product>,
      { onSuccess: onDone },
    )
  }

  return (
    <form onSubmit={handleSubmit(submit)} className="flex flex-col gap-4">
      <Field label="Nombre *" error={errors.name?.message}><Input {...register('name')} /></Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Especie"><Input placeholder="Boletus edulis" {...register('species')} /></Field>
        <Field label="Formato *">
          <Select {...register('format')}>{PRODUCT_FORMATS.map((f) => <option key={f}>{f}</option>)}</Select>
        </Field>
        <Field label="Unidad base *" error={errors.base_unit?.message}><Input {...register('base_unit')} /></Field>
        <Field label="IVA (%) *" error={errors.tax_percent?.message}><Input inputMode="decimal" {...register('tax_percent')} /></Field>
        <Field label="Margen neto objetivo (%) *" error={errors.margin_percent?.message}><Input inputMode="decimal" placeholder="30" {...register('margin_percent')} /></Field>
      </div>
      <Field label="Descripción"><Textarea {...register('description')} /></Field>
      <label className="flex items-center gap-2 text-sm font-medium">
        <input type="checkbox" className="size-5 accent-primary" {...register('is_active')} /> Activo (aparece al facturar)
      </label>
      <ErrorMessage error={mutation.error} />
      <Button type="submit" loading={mutation.isPending}>{product ? 'Guardar cambios' : 'Crear producto'}</Button>
      {product && (
        <DeleteButton path={`/products/${product.id}`} label="Borrar producto" onDone={onDone}
          confirmText={`¿Borrar «${product.name}»? Si ya se usa en lotes o pedidos no se podrá borrar: en ese caso desactívalo.`} />
      )}
    </form>
  )
}
