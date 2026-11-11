import { Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import { useApiMutation } from '@/lib/hooks'
import { cn } from '@/lib/utils'
import { Button, ErrorMessage } from './ui'

/**
 * Deletes a record after asking for confirmation. The API only hides it (soft delete), and
 * refuses with an explanation when other records depend on it (shown under the button).
 */
export default function DeleteButton({ path, confirmText, onDone, label = 'Borrar', iconOnly = false, className }: {
  /** API path of the record, e.g. `/companies/<id>`. */
  path: string
  confirmText: string
  onDone?: () => void
  label?: string
  iconOnly?: boolean
  className?: string
}) {
  const mutation = useApiMutation(() => api<void>(path, { method: 'DELETE' }))
  const run = () => {
    if (confirm(confirmText)) mutation.mutate(undefined, { onSuccess: onDone })
  }
  if (iconOnly) {
    return (
      <>
        <button type="button" aria-label={label} onClick={run} disabled={mutation.isPending}
          className={cn('rounded-lg p-2 hover:bg-primary-soft', className)}><Trash2 className="size-4" /></button>
        <ErrorMessage error={mutation.error} />
      </>
    )
  }
  return (
    <div className="flex flex-col gap-2">
      <Button type="button" variant="danger" loading={mutation.isPending} onClick={run} className={className}>
        <Trash2 className="size-4" /> {label}
      </Button>
      <ErrorMessage error={mutation.error} />
    </div>
  )
}
