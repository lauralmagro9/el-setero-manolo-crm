import { useState, type FormEvent } from 'react'
import { Button, Card, ErrorMessage, Field, Input } from '@/components/ui'
import { supabase } from '@/lib/supabase'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<Error | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) setError(new Error('Correo o contraseña incorrectos'))
    setBusy(false)
  }

  return (
    <div className="flex min-h-dvh items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <img src="/logo.png" alt="El Setero" className="mx-auto mb-2 w-40" />
        <form onSubmit={submit} className="flex flex-col gap-4">
          <Field label="Correo electrónico">
            <Input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <Field label="Contraseña">
            <Input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          <ErrorMessage error={error} />
          <Button type="submit" loading={busy}>Entrar</Button>
        </form>
      </Card>
    </div>
  )
}
