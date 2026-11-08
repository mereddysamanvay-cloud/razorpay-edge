import clsx from 'clsx'
import {
  BarChart3, ClipboardCheck, FileText, Gauge, History, ListOrdered, Menu, MessageSquareText, Search, Settings as SettingsIcon, SlidersHorizontal, UserSearch, Users, X,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useSession } from '../lib/session'
import { when } from '../lib/format'
import { AskPanel } from './AskPanel'
import { DESCRIPTOR, Logo, TAGLINE } from './Logo'
import { Identity } from './ui'

const NAV = [
  { to: 'overview', label: 'Overview', icon: Gauge },
  { to: 'portfolio', label: 'Merchant Portfolio', icon: Users },
  { to: 'queue', label: 'Priority Queue', icon: ListOrdered },
  { to: 'merchant', label: 'Merchant Intelligence', icon: UserSearch },
  { to: 'studio', label: 'Decision Studio', icon: SlidersHorizontal },
  { to: 'actions', label: 'Action Centre', icon: ClipboardCheck },
  { to: 'insights', label: 'Business Insights', icon: BarChart3 },
  { to: 'reports', label: 'Reports & History', icon: History },
  { to: 'settings', label: 'Settings', icon: SettingsIcon },
]

export function Shell() {
  const { sid, s, merchants } = useSession()
  const [open, setOpen] = useState(false)
  const [ask, setAsk] = useState(false)
  const [q, setQ] = useState('')
  const nav = useNavigate()
  const loc = useLocation()
  const mid = loc.pathname.match(/\/merchant\/([^/]+)/)?.[1]
  const hits = useMemo(() => {
    const t = q.trim().toLowerCase()
    return t ? merchants.filter((m) => m.name.toLowerCase().includes(t) || m.id.toLowerCase().includes(t)).slice(0, 6) : []
  }, [q, merchants])

  const links = (
    <nav className="mt-4 flex flex-col gap-0.5 px-2" aria-label="Main">
      {NAV.map(({ to, label, icon: Icon }) => (
        <NavLink key={to} to={`/a/${sid}/${to}`} onClick={() => setOpen(false)}
          className={({ isActive }) => clsx('flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] font-medium transition-colors',
            isActive ? 'bg-brand-soft text-brand' : 'text-slate-600 hover:bg-bg hover:text-ink')}>
          <Icon size={16} strokeWidth={1.9} /> {label}
        </NavLink>
      ))}
    </nav>
  )

  return (
    <div className="flex h-full">
      <aside className="hidden w-[232px] shrink-0 flex-col border-r border-line bg-white lg:flex">
        <div className="border-b border-line px-4 pb-3 pt-4">
          <Logo height={34} showMissing={false} />
          <p className="mt-2 text-[11.5px] font-medium leading-tight text-navy">{DESCRIPTOR}</p>
          <p className="mt-0.5 text-[11px] leading-tight text-mute">{TAGLINE}</p>
        </div>
        {links}
        <div className="mt-auto border-t border-line px-4 py-3 text-[11.5px] leading-snug text-mute">
          <p className="truncate font-medium text-ink" title={s.name}>{s.name}</p>
          <p>{s.merchant_count} merchants</p>
          <p>{when(s.created_at)}</p>
        </div>
      </aside>

      {open && (
        <div className="fixed inset-0 z-50 lg:hidden" onClick={() => setOpen(false)}>
          <div className="absolute inset-0 bg-navy/40" />
          <aside className="relative h-full w-64 bg-white shadow-pop" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between border-b border-line px-4 py-4">
              <div><Logo height={30} showMissing={false} /><p className="mt-1.5 text-[11px] text-mute">{DESCRIPTOR}</p></div>
              <button className="btn-ghost !p-1" onClick={() => setOpen(false)} aria-label="Close menu"><X size={16} /></button>
            </div>
            {links}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 shrink-0 items-center gap-3 border-b border-line bg-white px-4">
          <button className="btn-ghost !p-1.5 lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu"><Menu size={18} /></button>
          <div className="relative w-full max-w-sm">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-mute" />
            <input className="input !pl-8" placeholder="Find a merchant by name or ID" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Find a merchant" />
            {hits.length > 0 && (
              <ul className="absolute left-0 top-full z-40 mt-1 w-full rounded-md border border-line bg-white p-1 shadow-pop">
                {hits.map((m) => (
                  <li key={m.id}>
                    <button className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-[13px] hover:bg-bg" onClick={() => { nav(`/a/${sid}/merchant/${m.id}`); setQ('') }}>
                      <Identity name={m.name} logo={m.logo_url} size={22} /><span className="font-medium">{m.name}</span><span className="text-mute">{m.id}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="ml-auto flex items-center gap-2">
            <button className="btn-secondary" onClick={() => nav('/new')}><FileText size={14} /> New analysis</button>
            <button className="btn-primary" onClick={() => setAsk(true)}><MessageSquareText size={14} /> Ask EDGE</button>
          </div>
        </header>
        <main className="min-h-0 flex-1 overflow-auto scroll-thin"><div className="mx-auto w-full max-w-[1320px] px-5 py-5 lg:px-7"><Outlet /></div></main>
      </div>
      <AskPanel open={ask} onClose={() => setAsk(false)} merchantId={mid} />
    </div>
  )
}
