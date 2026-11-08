import clsx from 'clsx'
import {
  BarChart3, ChevronsLeft, ChevronsRight, ClipboardCheck, FileText, Gauge, History, ListOrdered, Menu, MessageSquareText, Search, Settings as SettingsIcon, SlidersHorizontal, UserSearch, Users, X,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useSession } from '../lib/session'
import { when } from '../lib/format'
import { AskPanel } from './AskPanel'
import { DESCRIPTOR, Logo, TAGLINE } from './Logo'
import { Identity } from './ui'

const GROUPS = [
  { title: 'Understand', items: [
    { to: 'overview', label: 'Overview', icon: Gauge }, { to: 'portfolio', label: 'Merchant Portfolio', icon: Users },
    { to: 'merchant', label: 'Merchant Intelligence', icon: UserSearch }, { to: 'insights', label: 'Business Insights', icon: BarChart3 }] },
  { title: 'Decide and act', items: [
    { to: 'queue', label: 'Priority Queue', icon: ListOrdered }, { to: 'studio', label: 'Decision Studio', icon: SlidersHorizontal }, { to: 'actions', label: 'Action Centre', icon: ClipboardCheck }] },
  { title: 'Govern', items: [{ to: 'reports', label: 'Reports & History', icon: History }, { to: 'settings', label: 'Settings', icon: SettingsIcon }] },
]

const read = (k: string) => { try { return localStorage.getItem(k) } catch { return null } }

export function Shell() {
  const { sid, s, merchants } = useSession()
  const [open, setOpen] = useState(false)
  const [ask, setAsk] = useState(false)
  const [q, setQ] = useState('')
  const [slim, setSlim] = useState(() => read('edge_nav_slim') === '1')
  const nav = useNavigate()
  const loc = useLocation()
  const mid = loc.pathname.match(/\/merchant\/([^/]+)/)?.[1]
  const hits = useMemo(() => {
    const t = q.trim().toLowerCase()
    return t ? merchants.filter((m) => m.name.toLowerCase().includes(t) || m.id.toLowerCase().includes(t)).slice(0, 6) : []
  }, [q, merchants])
  useEffect(() => { try { localStorage.setItem('edge_nav_slim', slim ? '1' : '0') } catch { /* ignore */ } }, [slim])
  useEffect(() => {
    if (!open) return
    const h = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [open])

  const links = (compact: boolean) => (
    <nav className="mt-3 flex flex-col px-2" aria-label="Main">
      {GROUPS.map((g) => (
        <div key={g.title} className="mb-2">
          {compact ? <div className="mx-2 my-1.5 border-t border-line" /> : <p className="px-2.5 pb-1 pt-2 text-[10.5px] font-semibold uppercase tracking-wider text-mute">{g.title}</p>}
          <div className="flex flex-col gap-0.5">
            {g.items.map(({ to, label, icon: Icon }) => (
              <NavLink key={to} to={`/a/${sid}/${to}`} onClick={() => setOpen(false)} title={compact ? label : undefined} aria-label={compact ? label : undefined}
                className={({ isActive }) => clsx('flex items-center rounded-md py-2 text-[13px] font-medium transition-colors', compact ? 'justify-center px-2' : 'gap-2.5 px-2.5',
                  isActive ? 'bg-brand-soft text-brand-dark' : 'text-slate-700 hover:bg-bg hover:text-ink')}>
                <Icon size={16} strokeWidth={1.9} aria-hidden /> {!compact && label}
              </NavLink>
            ))}
          </div>
        </div>
      ))}
    </nav>
  )

  return (
    <div className="flex h-full">
      <a href="#main" className="skip-link">Skip to main content</a>
      <aside className={clsx('hidden shrink-0 flex-col border-r border-line bg-white transition-[width] lg:flex', slim ? 'w-[64px]' : 'w-[240px]')}>
        {!slim && (
          <div className="border-b border-line px-4 pb-3 pt-4">
            <Logo height={30} showMissing={false} />
            <p className="mt-2 text-[11.5px] font-medium leading-tight text-navy">{DESCRIPTOR}</p>
            <p className="mt-0.5 text-[11px] leading-tight text-mute">{TAGLINE}</p>
          </div>
        )}
        {links(slim)}
        <div className="mt-auto border-t border-line">
          {!slim && (
            <div className="px-4 py-3 text-[11.5px] leading-snug text-mute">
              <p className="truncate font-medium text-ink" title={s.name}>{s.name}</p>
              <p>{s.merchant_count} merchants</p>
              <p>{when(s.created_at)}</p>
            </div>
          )}
          <button className="btn-ghost m-2 !px-2" onClick={() => setSlim(!slim)} aria-label={slim ? 'Expand navigation' : 'Collapse navigation'} aria-pressed={slim}>
            {slim ? <ChevronsRight size={16} /> : <><ChevronsLeft size={16} /> Collapse</>}
          </button>
        </div>
      </aside>

      {open && (
        <div className="fixed inset-0 z-50 lg:hidden" onClick={() => setOpen(false)} role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-navy/40" />
          <aside className="relative h-full w-72 max-w-[85vw] overflow-auto bg-white shadow-pop" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between border-b border-line px-4 py-4">
              <div><Logo height={30} showMissing={false} /><p className="mt-1.5 text-[11px] text-mute">{DESCRIPTOR}</p></div>
              <button className="btn-ghost !p-1" onClick={() => setOpen(false)} aria-label="Close menu"><X size={16} /></button>
            </div>
            {links(false)}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 shrink-0 items-center gap-2 border-b border-line bg-white px-3 sm:gap-3 sm:px-4">
          <button className="btn-ghost !p-1.5 lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu"><Menu size={18} /></button>
          {slim && <div className="hidden lg:block"><Logo height={24} showMissing={false} /></div>}
          <div className="relative w-full max-w-sm min-w-0">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-mute" aria-hidden />
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
          <div className="ml-auto flex shrink-0 items-center gap-2">
            <button className="btn-secondary" onClick={() => nav('/new')} aria-label="New analysis"><FileText size={14} /> <span className="hidden sm:inline">New analysis</span></button>
            <button className="btn-primary" onClick={() => setAsk(true)} aria-label="Ask EDGE"><MessageSquareText size={14} /> <span className="hidden sm:inline">Ask EDGE</span></button>
          </div>
        </header>
        <main id="main" tabIndex={-1} className="min-h-0 flex-1 overflow-auto scroll-thin focus:outline-none"><div className="mx-auto w-full max-w-[1320px] px-4 py-5 sm:px-5 lg:px-7"><Outlet /></div></main>
      </div>
      <AskPanel open={ask} onClose={() => setAsk(false)} merchantId={mid} />
    </div>
  )
}
