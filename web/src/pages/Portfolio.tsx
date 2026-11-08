/* eslint-disable @typescript-eslint/no-explicit-any */
import { ArrowDown, ArrowUp, Columns3, Download, Search } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Badge, BandBadge, Card, Empty, Identity, MultiPick, PageHeader, Select } from '../components/ui'
import { api } from '../lib/api'
import { DRIVER_SHORT, STATUS, STATUS_FLOW, inr, isNum, lakh, num, pct, pp } from '../lib/format'
import { useSession, type M } from '../lib/session'
import { RowActions } from '../components/RowActions'

interface Col { id: string; label: string; get: (m: M) => any; render?: (m: M) => React.ReactNode; num?: boolean; def: boolean }

export function useCols(status: (id: string) => string): Col[] {
  return useMemo(() => [
    { id: 'rank', label: 'Priority', get: (m) => m.rank ?? 9999, render: (m) => (m.rank ? <span className="num font-semibold">#{m.rank}</span> : <span className="text-mute">–</span>), num: true, def: true },
    { id: 'id', label: 'Merchant ID', get: (m) => m.id, def: true },
    { id: 'name', label: 'Merchant', get: (m) => m.name, render: (m) => <span className="flex items-center gap-2"><Identity name={m.name} logo={m.logo_url} size={24} /><span className="font-medium">{m.name}</span></span>, def: true },
    { id: 'segment', label: 'Segment', get: (m) => m.segment, render: (m) => (m.segment === 'Mid' ? 'Mid-market' : m.segment), def: true },
    { id: 'industry', label: 'Industry', get: (m) => m.industry, def: false },
    { id: 'tpv', label: 'M6 TPV', get: (m) => m.tpv_m6, render: (m) => lakh(m.tpv_m6), num: true, def: true },
    { id: 'tpvchg', label: 'TPV change', get: (m) => m.tpv_change_pct, render: (m) => <span className={isNum(m.tpv_change_pct) && m.tpv_change_pct <= -10 ? 'text-bad' : ''}>{pct(m.tpv_change_pct, 0, true)}</span>, num: true, def: true },
    { id: 'succ', label: 'Success rate', get: (m) => m.success_recent, render: (m) => pct(m.success_recent, 1), num: true, def: true },
    { id: 'succchg', label: 'Success change', get: (m) => m.success_drop_pp, render: (m) => <span className={isNum(m.success_drop_pp) && m.success_drop_pp <= -2 ? 'text-bad' : ''}>{pp(m.success_drop_pp)}</span>, num: true, def: false },
    { id: 'csat', label: 'CSAT', get: (m) => m.csat, render: (m) => (isNum(m.csat) ? m.csat : <span className="text-mute">Not available</span>), num: true, def: true },
    { id: 'unres', label: 'Unresolved', get: (m) => m.unresolved, render: (m) => `${num(m.unresolved)} / ${num(m.tickets)}`, num: true, def: true },
    { id: 'logins', label: 'Logins (30d)', get: (m) => m.logins, render: (m) => num(m.logins), num: true, def: false },
    { id: 'products', label: 'Products', get: (m) => m.products, render: (m) => num(m.products), num: true, def: false },
    { id: 'renewal', label: 'Renewal in', get: (m) => m.renewal_days, render: (m) => <span className={m.renewal_days <= 30 ? 'font-medium text-bad' : m.renewal_days <= 60 ? 'text-warn' : ''}>{num(m.renewal_days)} d</span>, num: true, def: true },
    { id: 'score', label: 'Risk score', get: (m) => m.risk_score, render: (m) => <span className="num font-semibold">{Math.round(m.risk_score)}</span>, num: true, def: true },
    { id: 'band', label: 'Risk category', get: (m) => m.risk_score, render: (m) => <span className="flex items-center gap-1.5"><BandBadge band={m.risk_band} label={m.risk_label} />{m.immediate && <Badge tone="bad">Immediate review</Badge>}</span>, def: true },
    { id: 'driver', label: 'Primary driver', get: (m) => m.primary_dimension ?? '', render: (m) => (m.primary_dimension ? DRIVER_SHORT[m.primary_dimension] : <span className="text-mute">None</span>), def: true },
    { id: 'value', label: 'Annual revenue value', get: (m) => m.annual_value, render: (m) => inr(m.annual_value), num: true, def: false },
    { id: 'prio', label: 'Priority index', get: (m) => (m.eligible ? m.priority_value : -1), render: (m) => (m.eligible ? <span title="Ranking aid in rupee units. Not an expected saving.">{inr(m.priority_value)}</span> : <span className="text-mute">Not eligible</span>), num: true, def: false },
    { id: 'secondary', label: 'Secondary drivers', get: (m) => (m.secondary_dimensions ?? []).join(','), render: (m) => ((m.secondary_dimensions ?? []).length ? m.secondary_dimensions.map((d: string) => DRIVER_SHORT[d]).join(', ') : <span className="text-mute">None</span>), def: false },
    { id: 'complete', label: 'Evidence completeness', get: (m) => m.completeness, render: (m) => <span title={m.missing_fields?.length ? `Missing: ${m.missing_fields.join(', ')}` : 'No fields missing'}>{m.completeness}%{m.completeness < 100 ? ' ' : ''}{m.completeness < 100 && <span className="text-mute">(incomplete)</span>}</span>, num: true, def: false },
    { id: 'playbook', label: 'Recommended action', get: (m) => m.assessment.primary_playbook_id, render: (m) => <span title={m.assessment.playbook_rationale}>{m.assessment.primary_playbook_id} {m.assessment.primary_playbook_name}</span>, def: false },
    { id: 'status', label: 'Review status', get: (m) => status(m.id), render: (m) => <Badge tone={status(m.id) === 'not_contacted' ? 'neutral' : 'brand'}>{STATUS[status(m.id)]}</Badge>, def: false },
  ] as Col[], [status])
}

const SORTS: Record<string, { label: string; col: string; dir: 1 | -1 }> = {
  rank: { label: 'Priority rank', col: 'rank', dir: 1 }, risk: { label: 'Highest risk', col: 'score', dir: -1 }, tpv: { label: 'Highest TPV', col: 'tpv', dir: -1 },
  value: { label: 'Highest annual revenue value', col: 'value', dir: -1 }, renewal: { label: 'Nearest renewal', col: 'renewal', dir: 1 },
  success: { label: 'Lowest payment success rate', col: 'succ', dir: 1 }, decline: { label: 'Largest TPV deterioration', col: 'tpvchg', dir: 1 }, csat: { label: 'Lowest CSAT', col: 'csat', dir: 1 },
}

export default function Portfolio() {
  const { sid, s, merchants, st, patch, status } = useSession()
  const nav = useNavigate()
  const [sp, setSp] = useSearchParams()
  const cols = useCols(status)
  const [vis, setVis] = useState<string[]>(() => { try { return JSON.parse(localStorage.getItem('edge.cols') || 'null') ?? cols.filter((c) => c.def).map((c) => c.id) } catch { return cols.filter((c) => c.def).map((c) => c.id) } })
  useEffect(() => { try { localStorage.setItem('edge.cols', JSON.stringify(vis)) } catch { /* ignore */ } }, [vis])
  const [colMenu, setColMenu] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const [sortBy, setSortBy] = useState<{ col: string; dir: 1 | -1 }>({ col: 'rank', dir: 1 })
  const [q, setQ] = useState('')
  const [compare, setCompare] = useState<string[]>([])

  const f = (k: string) => sp.get(k)?.split(',').filter(Boolean) ?? []
  const setF = (k: string, v: string[]) => { const n = new URLSearchParams(sp); if (v.length) n.set(k, v.join(',')); else n.delete(k); setSp(n, { replace: true }) }
  const flag = (k: string) => sp.get(k) === '1'
  const setFlag = (k: string, on: boolean) => { const n = new URLSearchParams(sp); if (on) n.set(k, '1'); else n.delete(k); setSp(n, { replace: true }) }
  const renewal = Number(sp.get('renewal') || 0)

  const rows = useMemo(() => {
    const t = q.trim().toLowerCase()
    const risk = f('risk'), seg = f('segment'), drv = f('driver'), stat = f('status'), prod = f('products'), eng = f('engagement'), val = f('value')
    const q75 = [...merchants].map((m) => m.annual_value).sort((a, b) => a - b)[Math.floor(merchants.length * 0.75)]
    let r = merchants.filter((m) =>
      (!t || m.name.toLowerCase().includes(t) || m.id.toLowerCase().includes(t) || m.industry.toLowerCase().includes(t)) &&
      (!risk.length || risk.includes(m.risk_band)) && (!seg.length || seg.includes(m.segment)) && (!drv.length || drv.includes(m.primary_dimension ?? 'none')) &&
      (!stat.length || stat.includes(status(m.id))) && (!renewal || m.renewal_days <= renewal) &&
      (!flag('tpvdrop') || m.tpv_change_pct <= -10) && (!flag('succdrop') || m.success_drop_pp <= -2) && (!flag('lowcsat') || (isNum(m.csat) && m.csat <= 2)) &&
      (!flag('unresolved') || m.unresolved >= 1) && (!flag('immediate') || m.immediate) && (!flag('shortlist') || m.selected) &&
      (!prod.length || prod.includes(m.products <= 2 ? 'low' : m.products <= 4 ? 'mid' : 'high')) &&
      (!eng.length || eng.includes(m.logins <= 5 ? 'low' : m.logins <= 15 ? 'mid' : 'high')) &&
      (!val.length || val.includes(m.annual_value >= q75 ? 'top' : 'rest')))
    const c = cols.find((x) => x.id === sortBy.col) ?? cols[0]
    r = [...r].sort((a, b) => {
      const x = c.get(a), y = c.get(b)
      const xn = x == null || (typeof x === 'number' && !isFinite(x)), yn = y == null || (typeof y === 'number' && !isFinite(y))
      if (xn || yn) return xn === yn ? 0 : xn ? 1 : -1
      return (typeof x === 'string' ? x.localeCompare(y) : x - y) * sortBy.dir
    })
    return r
  }, [merchants, sp, q, sortBy, cols, status])

  const active = [...sp.keys()].length
  const shown = cols.filter((c) => vis.includes(c.id))
  const reset = () => { setSp({}, { replace: true }); setQ('') }
  const opt = (arr: [string, string][]) => arr.map(([value, label]) => ({ value, label }))

  return (
    <div className="space-y-4">
      <PageHeader title="Merchant Portfolio" sub={`${rows.length} of ${merchants.length} merchants shown. Select a row to open the full merchant profile.`}
        actions={<a className="btn-secondary" href={api.exportUrl(sid, 'risk_register', 'csv')}><Download size={14} /> Export risk register</a>} />
      <Card pad={false}>
        <div className="flex flex-wrap items-center gap-2 border-b border-line p-3">
          <div className="relative w-64"><Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-mute" /><input className="input !pl-8" placeholder="Search name, ID or industry" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search merchants" /></div>
          <MultiPick label="Risk" options={['high', 'medium', 'low']} value={f('risk')} onChange={(v) => setF('risk', v)} />
          <MultiPick label="Segment" options={['Small', 'Mid', 'Enterprise']} value={f('segment')} onChange={(v) => setF('segment', v)} />
          <MultiPick label="Driver" options={['performance', 'relationship', 'commercial', 'engagement', 'none']} value={f('driver')} onChange={(v) => setF('driver', v)} />
          <MultiPick label="Products" options={['low', 'mid', 'high']} value={f('products')} onChange={(v) => setF('products', v)} />
          <MultiPick label="Engagement" options={['low', 'mid', 'high']} value={f('engagement')} onChange={(v) => setF('engagement', v)} />
          <MultiPick label="Value" options={['top', 'rest']} value={f('value')} onChange={(v) => setF('value', v)} />
          <MultiPick label="Review status" options={['not_contacted', ...STATUS_FLOW]} value={f('status')} onChange={(v) => setF('status', v)} />
          <Select value={String(renewal || '')} onChange={(v) => { const n = new URLSearchParams(sp); v ? n.set('renewal', v) : n.delete('renewal'); setSp(n, { replace: true }) }} className="w-40"
            options={opt([['', 'Any renewal'], ['30', 'Renews in 30 days'], ['60', 'Renews in 60 days'], ['90', 'Renews in 90 days']])} />
          <div className="relative ml-auto" ref={menuRef}>
            <button className="btn-secondary" onClick={() => setColMenu(!colMenu)}><Columns3 size={14} /> Columns</button>
            {colMenu && <div className="absolute right-0 top-full z-40 mt-1 max-h-80 w-52 overflow-auto rounded-md border border-line bg-white p-1.5 shadow-pop scroll-thin">
              {cols.map((c) => <label key={c.id} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-[13px] hover:bg-bg"><input type="checkbox" className="accent-brand" checked={vis.includes(c.id)} onChange={() => setVis(vis.includes(c.id) ? vis.filter((x) => x !== c.id) : [...vis, c.id])} />{c.label}</label>)}</div>}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-line bg-bg px-3 py-2 text-[12.5px]">
          <span className="label">Quick filters</span>
          {([['tpvdrop', 'TPV down 10%+'], ['succdrop', 'Success down 2pp+'], ['lowcsat', 'CSAT 2 or below'], ['unresolved', 'Has unresolved tickets'], ['immediate', 'Immediate review'], ['shortlist', 'On shortlist']] as const).map(([k, l]) => (
            <label key={k} className="flex items-center gap-1.5"><input type="checkbox" className="accent-brand" checked={flag(k)} onChange={(e) => setFlag(k, e.target.checked)} />{l}</label>))}
          <span className="ml-auto flex items-center gap-2"><span className="label">Sort</span>
            <Select value={Object.entries(SORTS).find(([, v]) => v.col === sortBy.col && v.dir === sortBy.dir)?.[0] ?? 'custom'} onChange={(v) => v !== 'custom' && setSortBy({ col: SORTS[v].col, dir: SORTS[v].dir })}
              options={[...Object.entries(SORTS).map(([value, v]) => ({ value, label: v.label })), { value: 'custom', label: 'Custom (column header)' }]} className="w-56" /></span>
          {(active > 0 || q) && <button className="btn-ghost !py-0.5" onClick={reset}>Clear filters</button>}
        </div>
        {rows.length === 0 ? <div className="p-6"><Empty title="No merchants match these filters" action={<button className="btn-primary" onClick={reset}>Reset filters</button>}>Try removing a filter or searching for a different name.</Empty></div> : (
          <div className="max-h-[68vh] overflow-auto scroll-thin">
            <table className="w-full border-collapse">
              <thead className="sticky top-0 z-10"><tr>
                {shown.map((c) => (
                  <th key={c.id} className={`th cursor-pointer select-none ${c.num ? 'text-right' : ''}`} onClick={() => setSortBy({ col: c.id, dir: sortBy.col === c.id ? ((sortBy.dir * -1) as 1 | -1) : c.num ? -1 : 1 })} aria-sort={sortBy.col === c.id ? (sortBy.dir === 1 ? 'ascending' : 'descending') : 'none'}>
                    <span className="inline-flex items-center gap-1">{c.label}{sortBy.col === c.id && (sortBy.dir === 1 ? <ArrowUp size={11} /> : <ArrowDown size={11} />)}</span></th>))}
                <th className="th w-10" />
              </tr></thead>
              <tbody>
                {rows.map((m) => (
                  <tr key={m.id} className="group cursor-pointer hover:bg-brand-soft/40" onClick={() => nav(`/a/${sid}/merchant/${m.id}`)}>
                    {shown.map((c) => <td key={c.id} className={`td ${c.num ? 'num text-right' : ''}`}>{c.render ? c.render(m) : String(c.get(m) ?? '')}</td>)}
                    <td className="td" onClick={(e) => e.stopPropagation()}><RowActions m={m} compare={compare} setCompare={setCompare} /></td>
                  </tr>))}
              </tbody>
            </table>
          </div>)}
        {compare.length > 0 && <div className="flex items-center justify-between border-t border-line bg-brand-soft/50 px-3 py-2 text-[13px]"><span>{compare.length} merchant(s) selected to compare</span>
          <span className="flex gap-2"><button className="btn-ghost" onClick={() => setCompare([])}>Clear</button><button className="btn-primary" disabled={compare.length < 2} onClick={() => nav(`/a/${sid}/queue?compare=${compare.join(',')}`)}>Compare</button></span></div>}
      </Card>
    </div>
  )
}
