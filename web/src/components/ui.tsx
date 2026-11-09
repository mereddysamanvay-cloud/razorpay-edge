/* eslint-disable @typescript-eslint/no-explicit-any */
import clsx from 'clsx'
import { AlertTriangle, ChevronDown, Info, X } from 'lucide-react'
import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { hueFor, initials } from '../lib/format'

export function Tip({ text, children }: { text: string; children?: ReactNode }) {
  const [open, setOpen] = useState(false)
  const id = useId()
  return (
    <span className="relative inline-flex items-center" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button type="button" aria-describedby={open ? id : undefined} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}
        className="inline-flex text-slate-400 hover:text-brand focus-visible:text-brand" aria-label="More information">
        {children ?? <Info size={13} />}
      </button>
      {open && (
        <span id={id} role="tooltip" className="absolute left-1/2 top-full z-50 mt-1.5 w-64 -translate-x-1/2 rounded-md bg-navy px-3 py-2 text-left text-[12px] font-normal normal-case leading-snug tracking-normal text-white shadow-pop">
          {text}
        </span>
      )}
    </span>
  )
}

export function Badge({ tone = 'neutral', children, className }: { tone?: 'neutral' | 'ok' | 'warn' | 'bad' | 'brand'; children: ReactNode; className?: string }) {
  const t = {
    neutral: 'bg-slate-100 text-slate-600', ok: 'bg-emerald-50 text-emerald-700', warn: 'bg-amber-50 text-amber-700',
    bad: 'bg-red-50 text-red-700', brand: 'bg-brand-soft text-brand-dark',
  }[tone]
  return <span className={clsx('inline-flex items-center gap-1 whitespace-nowrap rounded px-1.5 py-0.5 text-[11.5px] font-medium', t, className)}>{children}</span>
}

export const bandTone = (b: string) => (b === 'high' ? 'bad' : b === 'medium' ? 'warn' : 'ok') as 'bad' | 'warn' | 'ok'
export const BandBadge = ({ band, label }: { band: string; label: string }) => <Badge tone={bandTone(band)}>{label}</Badge>

export function Card({ title, sub, action, children, className, pad = true }: { title?: ReactNode; sub?: ReactNode; action?: ReactNode; children: ReactNode; className?: string; pad?: boolean }) {
  return (
    <section className={clsx('card', className)}>
      {(title || action) && (
        <header className="flex flex-wrap items-start justify-between gap-3 px-4 pt-3.5">
          <div>
            {title && <h3 className="h-sec">{title}</h3>}
            {sub && <p className="mt-0.5 text-[12px] leading-snug text-mute">{sub}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={clsx(pad ? 'p-4' : 'max-w-full overflow-x-auto', title && pad && 'pt-3')}>{children}</div>
    </section>
  )
}

export function PageHeader({ title, sub, actions }: { title: string; sub?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="h-page">{title}</h1>
        {sub && <p className="mt-1 max-w-3xl text-[13px] text-mute">{sub}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-line bg-white px-6 py-12 text-center">
      <p className="text-[14px] font-medium text-ink">{title}</p>
      {children && <p className="mt-1 max-w-md text-[13px] text-mute">{children}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function Notice({ tone = 'info', title, children }: { tone?: 'info' | 'warn' | 'bad' | 'ok'; title?: string; children?: ReactNode }) {
  const c = { info: 'border-brand/25 bg-brand-soft/60 text-navy', warn: 'border-amber-300/60 bg-amber-50 text-amber-900', bad: 'border-red-300/60 bg-red-50 text-red-800', ok: 'border-emerald-300/60 bg-emerald-50 text-emerald-900' }[tone]
  return (
    <div className={clsx('flex gap-2.5 rounded-md border px-3 py-2.5 text-[13px] leading-snug', c)} role={tone === 'bad' ? 'alert' : undefined}>
      <AlertTriangle size={15} className="mt-0.5 shrink-0" />
      <div>{title && <p className="font-semibold">{title}</p>}{children && <div className={title ? 'mt-0.5' : ''}>{children}</div>}</div>
    </div>
  )
}

export function Modal({ open, onClose, title, children, footer, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  useEffect(() => {
    if (!open) return
    const h = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-navy/40 p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-label={title} className={clsx('card max-h-[88vh] w-full overflow-hidden shadow-pop', wide ? 'max-w-3xl' : 'max-w-lg')}>
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <h2 className="h-sec">{title}</h2>
          <button className="btn-ghost !p-1" onClick={onClose} aria-label="Close"><X size={16} /></button>
        </div>
        <div className="max-h-[66vh] overflow-auto p-4 text-[13px]">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-line bg-bg px-4 py-3">{footer}</div>}
      </div>
    </div>
  )
}

export function Segmented<T extends string>({ value, onChange, options }: { value: T; onChange: (v: T) => void; options: { value: T; label: string }[] }) {
  return (
    <div className="inline-flex rounded-md border border-line bg-white p-0.5" role="tablist">
      {options.map((o) => (
        <button key={o.value} role="tab" aria-selected={value === o.value} onClick={() => onChange(o.value)}
          className={clsx('rounded px-2.5 py-1 text-[12.5px] font-medium transition-colors', value === o.value ? 'bg-brand text-white' : 'text-mute hover:text-ink')}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Tabs({ tabs, value, onChange }: { tabs: { id: string; label: string }[]; value: string; onChange: (v: string) => void }) {
  return (
    <div className="flex gap-5 overflow-x-auto whitespace-nowrap border-b border-line scroll-thin" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={clsx('-mb-px border-b-2 pb-2 text-[13px] font-medium', value === t.id ? 'border-brand text-brand' : 'border-transparent text-mute hover:text-ink')}>
          {t.label}
        </button>
      ))}
    </div>
  )
}

export function Select({ value, onChange, options, label, className }: { value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; label?: string; className?: string }) {
  return (
    <label className={clsx('block', className)}>
      {label && <span className="label mb-1 block">{label}</span>}
      <span className="relative block">
        <select value={value} onChange={(e) => onChange(e.target.value)} className="input appearance-none pr-7">
          {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <ChevronDown size={14} className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-mute" />
      </span>
    </label>
  )
}

export function MultiPick({ label, options, value, onChange }: { label: string; options: string[]; value: string[]; onChange: (v: string[]) => void }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  return (
    <div className="relative" ref={ref}>
      <button className={clsx('btn-secondary !py-1', value.length && '!border-brand !text-brand')} onClick={() => setOpen(!open)} aria-expanded={open}>
        {label}{value.length ? ` (${value.length})` : ''} <ChevronDown size={13} />
      </button>
      {open && (
        <div className="absolute left-0 top-full z-40 mt-1 max-h-72 w-56 overflow-auto rounded-md border border-line bg-white p-1.5 shadow-pop scroll-thin">
          {options.map((o) => (
            <label key={o} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-[13px] hover:bg-bg">
              <input type="checkbox" checked={value.includes(o)} onChange={() => onChange(value.includes(o) ? value.filter((x) => x !== o) : [...value, o])} className="accent-brand" />
              {o}
            </label>
          ))}
          {value.length > 0 && <button className="btn-ghost mt-1 w-full !py-1" onClick={() => onChange([])}>Clear</button>}
        </div>
      )}
    </div>
  )
}

export function Identity({ name, logo, size = 28 }: { name: string; logo?: string | null; size?: number }) {
  const h = hueFor(name)
  if (logo) return <img src={logo} alt="" style={{ width: size, height: size }} className="rounded object-contain" />
  return (
    <span aria-hidden style={{ width: size, height: size, background: `hsl(${h} 45% 94%)`, color: `hsl(${h} 45% 32%)`, fontSize: size * 0.4 }}
      className="inline-flex shrink-0 items-center justify-center rounded font-semibold">
      {initials(name)}
    </span>
  )
}

export function Meter({ value, tone, label }: { value: number; tone?: string; label?: string }) {
  const c = tone ?? (value >= 50 ? 'bg-bad' : value >= 25 ? 'bg-warn-fill' : 'bg-ok-fill')
  return (
    <div className="flex items-center gap-2" title={label}>
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-100" role="meter" aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={100}>
        <div className={clsx('h-full rounded-full', c)} style={{ width: `${Math.min(100, Math.max(2, value))}%` }} />
      </div>
      <span className="num w-7 text-right text-[12px] text-ink">{Math.round(value)}</span>
    </div>
  )
}

export function Stat({ label, value, sub, tip, onClick, tone }: { label: string; value: ReactNode; sub?: ReactNode; tip?: string; onClick?: () => void; tone?: 'bad' | 'warn' | 'ok' }) {
  const Tag: any = onClick ? 'button' : 'div'
  return (
    <Tag onClick={onClick} className={clsx('card p-3.5 text-left', onClick && 'transition-shadow hover:shadow-pop focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand')}>
      <div className="flex items-center gap-1.5"><span className="label">{label}</span>{tip && <Tip text={tip} />}</div>
      <div className={clsx('num mt-1.5 text-[26px] font-semibold leading-none', tone === 'bad' && 'text-bad', tone === 'warn' && 'text-warn', tone === 'ok' && 'text-ok')}>{value}</div>
      {sub && <div className="mt-1.5 text-[12px] leading-snug text-mute">{sub}</div>}
    </Tag>
  )
}
