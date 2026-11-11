import { Building2, ContactRound, FileText, Package, KanbanSquare, LayoutDashboard, LogOut, MessageSquare, Mic, Moon, Sun } from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '@/lib/auth'
import { supabase } from '@/lib/supabase'
import { cn } from '@/lib/utils'

const NAV: { to: string; label: string; icon: typeof FileText; end?: boolean }[] = [
  { to: '/', label: 'Inicio', icon: LayoutDashboard, end: true },
  { to: '/empresas', label: 'Empresas', icon: Building2 },
  { to: '/pipeline', label: 'Pipeline', icon: KanbanSquare },
  { to: '/contactos', label: 'Contactos', icon: ContactRound },
  { to: '/interacciones', label: 'Notas', icon: MessageSquare },
  { to: '/facturas', label: 'Facturas', icon: FileText, end: true },
  { to: '/productos', label: 'Productos', icon: Package },
]

function ThemeToggle() {
  const [dark, setDark] = useState(document.documentElement.classList.contains('dark'))
  const toggle = () => {
    const next = !dark
    document.documentElement.classList.toggle('dark', next)
    try { localStorage.setItem('theme', next ? 'dark' : 'light') } catch { /* private mode */ }
    setDark(next)
  }
  return (
    <button onClick={toggle} aria-label="Cambiar tema" className="rounded-lg p-2 hover:bg-primary-soft">
      {dark ? <Sun className="size-5" /> : <Moon className="size-5" />}
    </button>
  )
}

/** Shell of every logged-in screen: sidebar (desktop), bottom bar (phone) and the "Grabar" button. */
export default function Layout() {
  const { session } = useAuth()
  const navigate = useNavigate()
  const recording = useLocation().pathname === '/grabar'

  return (
    <div className="flex min-h-dvh">
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-r border-border bg-card p-4 md:flex">
        <img src="/logo.png" alt="El Setero" className="mx-auto mb-4 w-32" />
        <button
          onClick={() => navigate('/grabar')}
          className="mb-4 flex items-center justify-center gap-2 rounded-lg bg-accent py-3 font-semibold text-accent-foreground hover:bg-accent-strong"
        >
          <Mic className="size-5" /> Grabar nota
        </button>
        <nav className="flex flex-1 flex-col gap-1">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to} to={to} end={end}
              className={({ isActive }) =>
                cn('flex items-center gap-3 rounded-lg px-3 py-2.5 font-medium hover:bg-primary-soft',
                  isActive && 'bg-primary text-primary-foreground hover:bg-primary')}
            >
              <Icon className="size-5" /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="flex items-center justify-between border-t border-border pt-3">
          <span className="truncate text-xs text-muted" title={session?.user.email}>{session?.user.email}</span>
          <div className="flex">
            <ThemeToggle />
            <button onClick={() => supabase.auth.signOut()} aria-label="Cerrar sesión" className="rounded-lg p-2 hover:bg-primary-soft">
              <LogOut className="size-5" />
            </button>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-border bg-card px-4 py-2 md:hidden">
          <img src="/logo.png" alt="El Setero" className="h-10" />
          <div className="flex">
            <ThemeToggle />
            <button onClick={() => supabase.auth.signOut()} aria-label="Cerrar sesión" className="rounded-lg p-2 hover:bg-primary-soft">
              <LogOut className="size-5" />
            </button>
          </div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 p-4 pb-28 md:p-8 md:pb-8">
          <Outlet />
        </main>
      </div>

      {!recording && (
        <button
          onClick={() => navigate('/grabar')}
          aria-label="Grabar nota de voz"
          className="fixed right-4 bottom-20 z-40 flex size-14 items-center justify-center rounded-full bg-accent text-accent-foreground shadow-lg hover:bg-accent-strong md:hidden"
        >
          <Mic className="size-6" />
        </button>
      )}

      <nav className="fixed inset-x-0 bottom-0 z-30 flex overflow-x-auto border-t border-border bg-card pb-[env(safe-area-inset-bottom)] md:hidden">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to} to={to} end={end}
            className={({ isActive }) =>
              cn('flex min-w-[4.5rem] flex-1 shrink-0 flex-col items-center gap-0.5 py-2 text-[11px] font-medium', isActive ? 'text-primary' : 'text-muted')}
          >
            <Icon className="size-5" /> {label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
