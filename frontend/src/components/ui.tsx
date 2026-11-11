import { Loader2, X } from 'lucide-react'
import {
  forwardRef, useEffect, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode,
  type SelectHTMLAttributes, type TextareaHTMLAttributes,
} from 'react'
import { cn } from '@/lib/utils'

const field =
  'w-full rounded-lg border border-border bg-card px-3 py-2.5 text-base text-foreground placeholder:text-muted ' +
  'focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-60'

type ButtonVariant = 'primary' | 'accent' | 'outline' | 'ghost' | 'danger'
const variants: Record<ButtonVariant, string> = {
  primary: 'bg-primary text-primary-foreground hover:bg-primary-hover',
  accent: 'bg-accent text-accent-foreground hover:bg-accent-strong',
  outline: 'border border-border bg-card text-foreground hover:bg-primary-soft',
  ghost: 'text-foreground hover:bg-primary-soft',
  danger: 'bg-danger text-white hover:opacity-90',
}

export function Button({
  variant = 'primary', loading, className, children, disabled, ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; loading?: boolean }) {
  return (
    <button
      disabled={disabled || loading}
      className={cn(
        'inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-colors disabled:opacity-60',
        variants[variant], className,
      )}
      {...props}
    >
      {loading && <Loader2 className="size-4 animate-spin" />}
      {children}
    </button>
  )
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => <input ref={ref} className={cn(field, className)} {...props} />,
)
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => <textarea ref={ref} rows={3} className={cn(field, className)} {...props} />,
)
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => (
    <select ref={ref} className={cn(field, className)} {...props}>{children}</select>
  ),
)

/** A label with its control and an optional error message. */
export function Field({ label, error, children, className }: {
  label: string; error?: string; children: ReactNode; className?: string
}) {
  return (
    <label className={cn('flex flex-col gap-1.5 text-sm font-medium', className)}>
      <span>{label}</span>
      {children}
      {error && <span className="text-xs font-normal text-danger">{error}</span>}
    </label>
  )
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn('rounded-xl border border-border bg-card p-4', className)}>{children}</div>
}

type Tone = 'neutral' | 'green' | 'yellow' | 'red'
const tones: Record<Tone, string> = {
  neutral: 'bg-primary-soft text-foreground',
  green: 'bg-primary text-primary-foreground',
  yellow: 'bg-accent text-accent-foreground',
  red: 'bg-danger text-white',
}
export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={cn('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium', tones[tone])}>
      {children}
    </span>
  )
}

export function Spinner() {
  return (
    <div className="flex justify-center p-8 text-primary"><Loader2 className="size-6 animate-spin" /></div>
  )
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <p className="rounded-xl border border-dashed border-border p-8 text-center text-muted">{children}</p>
}

export function ErrorMessage({ error }: { error: unknown }) {
  if (!error) return null
  return (
    <p role="alert" className="rounded-lg border border-danger p-3 text-sm text-danger">
      {error instanceof Error ? error.message : 'Ha ocurrido un error'}
    </p>
  )
}

export function PageHeader({ title, actions }: { title: string; actions?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
      <h1 className="text-2xl font-bold">{title}</h1>
      <div className="flex flex-wrap gap-2">{actions}</div>
    </div>
  )
}

/** Dialog: a bottom sheet on phones, a centred panel on larger screens. */
export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 sm:items-center" onClick={onClose}>
      <div
        role="dialog" aria-modal="true" aria-label={title}
        className="max-h-[92dvh] w-full overflow-y-auto rounded-t-2xl bg-background p-5 sm:max-w-xl sm:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-bold">{title}</h2>
          <button onClick={onClose} aria-label="Cerrar" className="rounded-lg p-2 hover:bg-primary-soft"><X className="size-5" /></button>
        </div>
        {children}
      </div>
    </div>
  )
}
