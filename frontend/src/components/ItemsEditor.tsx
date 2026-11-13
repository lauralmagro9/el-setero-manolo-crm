import { Plus, Trash2 } from 'lucide-react'
import { useProducts } from '@/lib/hooks'
import { Button, Input, Select } from './ui'

/** A line being edited: `id` is the existing order line (absent for new ones), `said` what the customer called the product. */
export interface EditableItem {
  id?: string
  product_id: string
  said?: string | null
  quantity: string
  unit: string
}

/** True when every line has a product and a positive quantity (and there is at least one). */
export function itemsAreComplete(items: EditableItem[]): boolean {
  return items.length > 0 && items.every((i) => i.product_id && Number(i.quantity) > 0)
}

/** Edit the products and quantities of an order or a draft: change the product, the quantity, add or remove lines. */
export default function ItemsEditor({ items, onChange }: { items: EditableItem[]; onChange: (items: EditableItem[]) => void }) {
  const products = useProducts({ activeOnly: true })
  const set = (index: number, patch: Partial<EditableItem>) =>
    onChange(items.map((item, i) => (i === index ? { ...item, ...patch } : item)))
  const pick = (index: number, productId: string) =>
    set(index, { product_id: productId, unit: products.data?.find((p) => p.id === productId)?.base_unit ?? items[index].unit })

  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="mb-1 text-sm font-medium">Productos</legend>
      {items.map((item, index) => (
        <div key={item.id ?? index} className="flex flex-col gap-1 rounded-lg border border-border p-2">
          {item.said && !item.product_id && <p className="text-xs text-muted">Dijo: «{item.said}»</p>}
          <div className="grid grid-cols-[1fr_5rem_4rem_auto] items-center gap-2">
            <Select aria-label="Producto" value={item.product_id} onChange={(e) => pick(index, e.target.value)}>
              <option value="">Elige un producto…</option>
              {products.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </Select>
            <Input
              aria-label="Cantidad" type="number" min="0" step="0.001" inputMode="decimal" placeholder="Cant."
              value={item.quantity} onChange={(e) => set(index, { quantity: e.target.value })}
            />
            <Input aria-label="Unidad" value={item.unit} onChange={(e) => set(index, { unit: e.target.value })} />
            <button
              type="button" aria-label="Quitar producto" onClick={() => onChange(items.filter((_, i) => i !== index))}
              className="rounded-lg p-2 hover:bg-primary-soft"
            >
              <Trash2 className="size-4" />
            </button>
          </div>
        </div>
      ))}
      <Button type="button" variant="outline" className="self-start" onClick={() => onChange([...items, { product_id: '', quantity: '', unit: 'kg' }])}>
        <Plus className="size-4" /> Añadir producto
      </Button>
    </fieldset>
  )
}
