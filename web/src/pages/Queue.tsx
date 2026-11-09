/* eslint-disable @typescript-eslint/no-explicit-any */
import clsx from 'clsx'
import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { RowActions } from '../components/RowActions'
import { Badge, BandBadge, Card, Empty, Identity, Notice, PageHeader, Select, Tip } from '../components/ui'
import { api, type Dict } from '../lib/api'
import { DRIVER_SHORT, FOCUS, PRIORITY, STATUS, inr, isNum, num, pct, pp } from '../lib/format'
import { useSession, type M } from '../lib/session'

const urgency = (d: number) => (d <= 30 ? ['Renews in ' + d + ' days', 'bad'] : d <= 60 ? ['Renews in ' + d + ' days', 'warn'] : d <= 90 ? ['Renews in ' + d + ' days', 'neutral'] : ['No near-term renewal', 'neutral']) as [string, 'bad' | 'warn' | 'neutral']
const DECISIONS = ['Escalate to manager', 'Review next cycle', 'Request extra capacity', 'Monitor, no outreach']
const plusDays = (n: number) => new Date(Date.now() + n * 864e5).toISOString().slice(0, 10)
const mix = (ms: M[], key: (m: M) => string) => Object.entries(ms.reduce((a: Record<string, number>, m) => { const k = key(m); a[k] = (a[k] ?? 0) + 1; return a }, {})).map(([k, v]) => `${k} ${v}`).join(', ') || 'none'

function ValueBar({ v, max }: { v: number; max: number }) {
  return <div className="flex items-center gap-2"><div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100"><div className="h-full bg-brand" style={{ width: `${Math.max(4, (v / max) * 100)}%` }} /></div><span className="num text-[12px]">{inr(v)}</span></div>
}

function Md({ t }: { t: string }) {
  return <>{t.split('\n').map((line, i) => <p key={i} className={line ? 'mt-1' : ''}>{line.split(/(\*\*[^*]+\*\*)/g).map((p, j) => (p.startsWith('**') ? <strong key={j}>{p.slice(2, -2)}</strong> : <span key={j}>{p}</span>))}</p>)}</>
}

export default function Queue() {
  const { sid, s, merchants, status, st, patch, byId } = useSession()
  const [sp] = useSearchParams()
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const [why, setWhy] = useState<string | null>(null)
  const [capRes, setCapRes] = useState<Dict | null>(null)
  const [capBusy, setCapBusy] = useState<number | null>(null)
  const cap = s.kpis.capacity
  const scn = s.scenario
  const sel = useMemo(() => merchants.filter((m) => m.selected).sort((x, y) => x.rank - y.rank), [merchants])
  const outside = useMemo(() => merchants.filter((m) => m.eligible && !m.selected && m.rank).sort((x, y) => x.rank - y.rank), [merchants])
  const excluded = useMemo(() => merchants.filter((m) => !m.eligible && m.risk_band !== 'low').sort((x, y) => y.risk_score - x.risk_score), [merchants])
  const urgent = useMemo(() => merchants.filter((m) => m.immediate && !m.selected).sort((x, y) => y.risk_score - x.risk_score), [merchants])
  const urgentSel = merchants.filter((m) => m.immediate && m.selected).length
  const maxV = Math.max(...merchants.map((m) => m.annual_value), 1)
  const cutoff = sel[sel.length - 1]
  const overlap = sel.filter((m) => m.baseline_selected).length
  const scenarioActive = JSON.stringify({ p: scn.priorities, f: scn.risk_focus, s: scn.segments, r: scn.renewal_window, c: scn.capacity, i: scn.include_ids, e: scn.exclude_ids }) !== JSON.stringify({ p: s.baseline_scenario.priorities, f: s.baseline_scenario.risk_focus, s: s.baseline_scenario.segments, r: s.baseline_scenario.renewal_window, c: s.baseline_scenario.capacity, i: s.baseline_scenario.include_ids, e: s.baseline_scenario.exclude_ids })
  const urlCmp = (sp.get('compare') ?? '').split(',').filter(Boolean).map((id) => byId[id]).filter(Boolean) as M[]
  const cmp = a && b ? ([byId[a], byId[b]].filter(Boolean) as M[]) : urlCmp
  const priorities: string[] = scn.priorities ?? []
  const pool = [...sel, ...outside]
  const decisions: Dict = st.capacity_decisions ?? {}

  const whyOutside = (m: M) => {
    const gap = cutoff ? `Priority index ${inr(m.priority_value)} against ${inr(cutoff.priority_value)} for the last shortlisted merchant (${cutoff.name}).` : ''
    const rule = priorities.length ? `The shortlist favours merchants matching the selected priorities (${priorities.map((p) => PRIORITY[p]).join('; ')}), then ${FOCUS[scn.risk_focus].toLowerCase()}.` : `Ordered by ${FOCUS[scn.risk_focus].toLowerCase()}, then the priority index.`
    return `Ranked #${m.rank}, ${m.rank - cap} place(s) outside the ${cap} slots. ${rule} ${gap}`
  }
  const whyNot = (m: M) => (m.eligible && m.rank ? whyOutside(m) : m.selection_reason || 'Not eligible for outreach under the current rules.')

  async function explain() {
    const A = byId[a], B = byId[b]
    if (!A || !B) return
    const [hi, lo] = A.rank && B.rank && A.rank > B.rank ? [B, A] : [A, B]
    const r = await api.ask(sid, `Why is ${hi.name} ranked above ${lo.name}?`, {}, [])
    setWhy(r.answer)
  }
  async function impact(n: number) {
    setCapBusy(n)
    try {
      const spec = { capacity: n, priorities: scn.priorities, risk_focus: scn.risk_focus, segments: scn.segments, prefer_segments: scn.prefer_segments ?? [], exclude_industries: scn.exclude_industries, renewal_window: scn.renewal_window, include_ids: scn.include_ids ?? [], exclude_ids: scn.exclude_ids ?? [], exclude_reasons: scn.exclude_reasons ?? {} }
      setCapRes({ n, ...(await api.scenario(sid, spec, 'current')) })
    } finally { setCapBusy(null) }
  }
  const setDecision = (m: M, v: Dict) => patch({ capacity_decisions: { [m.id]: { next_review: plusDays(14), ...(decisions[m.id] ?? {}), ...v, at: new Date().toISOString() } } })

  return (
    <div className="space-y-5">
      <PageHeader title="Priority Queue" sub="Who to contact first, and why." />
      <Notice tone="info" title="Risk score and priority rank are different things">
        Risk score (0-100) assesses how concerning the merchant's signals are. Priority rank orders who to consider first under the {cap}-contact limit, using the configured priorities ({priorities.length ? priorities.map((p) => PRIORITY[p]).join(', ') : 'none selected'}), the risk focus ({FOCUS[scn.risk_focus]}) and the priority index (a ranking aid in rupee units, not an expected saving).
      </Notice>

      <Card title={`Outreach capacity: ${sel.length} of ${cap} slots used`} sub="The team can contact this many merchants this month. Everyone else needs a decision, shown below.">
        <div className="flex flex-wrap gap-1.5" role="img" aria-label={`${sel.length} of ${cap} slots used`}>{Array.from({ length: Math.max(cap, sel.length) }).map((_, i) => (
          <span key={i} className={clsx('flex h-8 w-8 items-center justify-center rounded-md border text-[11px] font-semibold', i < sel.length ? 'border-brand bg-brand text-white' : 'border-dashed border-line text-mute')}>{i < sel.length ? i + 1 : ''}</span>))}</div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <div className="rounded-md border border-brand/30 bg-brand-soft p-3"><p className="label">Selected</p><p className="num text-[24px] font-semibold text-navy">{sel.length}</p><p className="text-[12px] text-mute">On the shortlist for outreach</p></div>
          <div className="rounded-md border border-line p-3"><p className="label">Not selected</p><p className="num text-[24px] font-semibold text-navy">{outside.length}</p><p className="text-[12px] text-mute">Eligible but outside the {cap}; the reason is listed under each name below</p></div>
          <div className={clsx('rounded-md border p-3', urgent.length ? 'border-amber-300 bg-amber-50' : 'border-line')}><p className="label">Need management attention</p><p className="num text-[24px] font-semibold text-navy">{urgent.length}</p><p className="text-[12px] text-mute">Urgent review flag but no slot. Each needs a decision</p></div>
        </div>
      </Card>

      <Card>
        <div className="flex flex-wrap items-center gap-x-8 gap-y-2">
          <div><p className="label">Selected</p><p className="num text-[24px] font-semibold">{sel.length} <span className="text-[14px] font-normal text-mute">of {cap}</span></p></div>
          <div><p className="label">Remaining capacity</p><p className="num text-[24px] font-semibold">{Math.max(cap - sel.length, 0)}</p></div>
          <div><p className="label">Eligible, just outside</p><p className="num text-[24px] font-semibold">{outside.length}</p></div>
          <div><p className="label">Not eligible (moderate/high)</p><p className="num text-[24px] font-semibold">{excluded.length}</p></div>
          <div><p className="label flex items-center gap-1">Run-rate represented <Tip text="Sum of the annual net-revenue run-rate proxy of the shortlisted merchants. Exposure, not a forecast of savings." /></p><p className="num text-[24px] font-semibold">{inr(s.commercial.shortlist_annual_inr)}</p></div>
          {scenarioActive && <div><p className="label">Overlap with baseline list</p><p className="num text-[24px] font-semibold">{overlap} <span className="text-[14px] font-normal text-mute">of {s.baseline_scenario.capacity}</span></p></div>}
        </div>
        <div className="mt-3 grid gap-x-8 gap-y-1 border-t border-line pt-3 text-[12.5px] text-mute md:grid-cols-2">
          <p><span className="font-medium text-ink">Driver mix. </span>{mix(sel, (m) => (m.primary_dimension ? DRIVER_SHORT[m.primary_dimension] : 'None'))}</p>
          <p><span className="font-medium text-ink">Segment mix. </span>{mix(sel, (m) => (m.segment === 'Mid' ? 'Mid-market' : m.segment))}</p>
        </div>
        {sel.length < cap && <p className="mt-3 text-[12.5px] text-mute">Fewer than {cap} merchants are eligible under the current rules, so capacity is not filled. Eligible means playbook PB-1 to PB-4, moderate or high band, and a positive priority index.</p>}
      </Card>

      <Card title={`Urgent review versus selected for outreach (${urgent.length} urgent, not selected)`} sub="Immediate review means a critical trigger fired. It is not the same as being selected for outreach, which is limited by capacity.">
        <p className="text-[13px]">{urgentSel + urgent.length} merchants meet a critical review trigger. {urgentSel} are on the shortlist; {urgent.length} are not. Each one below needs a decision so it does not go unseen.</p>
        {urgent.length === 0 ? <p className="mt-2 text-[13px] text-ok">Every urgent merchant is on the shortlist.</p> : (
          <div className="mt-3 divide-y divide-line">{urgent.map((m) => { const d = decisions[m.id]; return (
            <div key={m.id} className="grid gap-3 py-3 text-[13px] first:pt-0 lg:grid-cols-[1fr_auto]">
              <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><Link to={`/a/${sid}/merchant/${m.id}`} className="font-medium hover:text-brand">{m.name}</Link><BandBadge band={m.risk_band} label={m.risk_label} /><Badge tone="bad">{m.critical_triggers[0]?.split(':')[0].replace(/_/g, ' ')}</Badge>{!d?.decision && <Badge tone="warn">Decision needed</Badge>}</div>
                <p className="mt-0.5 text-[12.5px] text-mute"><span className="font-medium text-ink">Why not selected. </span>{whyNot(m)}</p></div>
              <div className="flex flex-wrap items-end gap-2">
                <Select label="Capacity decision" value={d?.decision ?? ''} onChange={(v) => setDecision(m, { decision: v })} options={[{ value: '', label: 'Choose…' }, ...DECISIONS.map((x) => ({ value: x, label: x }))]} className="w-52" />
                <label className="block"><span className="label">Next review</span><input type="date" className="input mt-1 !w-40" value={d?.next_review ?? plusDays(14)} onChange={(e) => setDecision(m, { next_review: e.target.value })} aria-label={`Next review date for ${m.name}`} /></label>
              </div></div>) })}</div>)}
      </Card>

      <Card title="Compare two merchants" sub="Why does one rank above the other?">
        <div className="flex flex-wrap items-end gap-3">
          <Select label="Merchant A" value={a} onChange={(v) => { setA(v); setWhy(null) }} options={[{ value: '', label: 'Choose…' }, ...pool.map((m) => ({ value: m.id, label: `#${m.rank} ${m.name}` }))]} className="w-64" />
          <Select label="Merchant B" value={b} onChange={(v) => { setB(v); setWhy(null) }} options={[{ value: '', label: 'Choose…' }, ...pool.map((m) => ({ value: m.id, label: `#${m.rank} ${m.name}` }))]} className="w-64" />
          <button className="btn-secondary" disabled={!a || !b || a === b} onClick={explain}>Explain the ranking</button>
        </div>
        {why && <div className="mt-3 rounded-md bg-bg p-3 text-[13px]"><Md t={why} /></div>}
      </Card>

      {cmp.length > 1 && (
        <Card title="Comparison" sub="Side by side." action={<Link className="btn-ghost" to={`/a/${sid}/queue`} onClick={() => { setA(''); setB('') }}>Close</Link>}>
          <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Measure</th>{cmp.map((m) => <th key={m.id} className="th"><Link className="text-brand" to={`/a/${sid}/merchant/${m.id}`}>{m.name}</Link></th>)}</tr></thead>
            <tbody>{([['Priority rank', (m: M) => (m.rank ? `#${m.rank}` : 'Not ranked')], ['Risk', (m: M) => `${m.risk_label} (${Math.round(m.risk_score)})`], ['Priority index', (m: M) => (m.eligible ? inr(m.priority_value) : 'Not eligible')],
              ['Risk weight / urgency', (m: M) => `${num(m.risk_weight, 2)} / ${num(m.urgency_multiplier, 2)}`], ['Primary driver', (m: M) => m.assessment.primary_risk_driver],
              ['TPV change', (m: M) => pct(m.tpv_change_pct, 0, true)], ['Success change', (m: M) => pp(m.success_drop_pp)], ['Unresolved tickets', (m: M) => num(m.unresolved)], ['CSAT', (m: M) => (isNum(m.csat) ? m.csat : 'Not available')],
              ['Renewal', (m: M) => `${num(m.renewal_days)} days`], ['Annual run-rate proxy', (m: M) => inr(m.annual_value)], ['Evidence completeness', (m: M) => `${m.completeness}%`], ['Playbook', (m: M) => m.assessment.primary_playbook_id + ' ' + m.assessment.primary_playbook_name]] as [string, (m: M) => any][]).map(([l, f]) => (
              <tr key={l}><td className="td label">{l}</td>{cmp.map((m) => <td key={m.id} className="td">{f(m)}</td>)}</tr>))}</tbody></table></div>
        </Card>
      )}

      <Card title={`Shortlist (${sel.length})`} pad={false}
        action={<span className="flex items-center gap-1.5 text-[12px] text-mute">Capacity if it were <button className="btn-secondary !px-2 !py-0.5" onClick={() => impact(10)} disabled={capBusy !== null}>10</button><button className="btn-secondary !px-2 !py-0.5" onClick={() => impact(20)} disabled={capBusy !== null}>20</button></span>}>
        {capRes && (
          <div className="border-b border-line px-5 py-3 text-[13px]"><div className="flex items-start justify-between gap-3"><div><p className="font-medium">If capacity were {capRes.n}</p><p className="mt-0.5">{capRes.result.summary}</p>
            <p className="mt-0.5 text-[12.5px] text-mute">Moves in: {capRes.result.moved_in.map((x: Dict) => x.business_name).join(', ') || 'none'}. Moves out: {capRes.result.moved_out.map((x: Dict) => x.business_name).join(', ') || 'none'}. Preview only; nothing is changed. Use Decision Studio to apply a different capacity.</p></div>
            <button className="btn-ghost" onClick={() => setCapRes(null)}>Close</button></div></div>)}
        {sel.length === 0 ? <div className="p-5"><Empty title="Nobody is shortlisted">No merchant is eligible for outreach under the current rules and filters.</Empty></div> : (
          <div className="overflow-x-auto"><table className="w-full">
            <thead><tr><th className="th">Rank</th><th className="th">Merchant</th><th className="th">Risk</th><th className="th">Main driver</th><th className="th">Run-rate proxy</th><th className="th">Priority index</th><th className="th">Renewal</th><th className="th min-w-[260px]">Reason for priority</th><th className="th">Playbook</th><th className="th">Evidence</th><th className="th">Outreach status</th><th className="th w-8" /></tr></thead>
            <tbody>{sel.map((m) => { const [u, tone] = urgency(m.renewal_days); const cur = status(m.id); return (
              <tr key={m.id} className="hover:bg-brand-soft/30">
                <td className="td num font-semibold">#{m.rank}</td>
                <td className="td"><Link to={`/a/${sid}/merchant/${m.id}`} className="flex items-center gap-2 font-medium hover:text-brand"><Identity name={m.name} logo={m.logo_url} size={24} />{m.name}</Link><span className="text-[11.5px] text-mute">{m.id} · {m.segment === 'Mid' ? 'Mid-market' : m.segment}</span></td>
                <td className="td"><BandBadge band={m.risk_band} label={m.risk_label} /><span className="num ml-1.5 text-[12px] text-mute">{Math.round(m.risk_score)}</span>{m.immediate && <Badge tone="bad" className="ml-1">Immediate</Badge>}</td>
                <td className="td">{m.primary_dimension ? DRIVER_SHORT[m.primary_dimension] : '–'}</td>
                <td className="td"><ValueBar v={m.annual_value} max={maxV} /></td>
                <td className="td num text-[12.5px]" title={`Risk weight ${num(m.risk_weight, 2)} x exposure ${inr(m.annual_value)}, less outreach cost, x renewal urgency ${num(m.urgency_multiplier, 2)}`}>{inr(m.priority_value)}</td>
                <td className="td"><Badge tone={tone}>{u}</Badge></td>
                <td className="td text-[12.5px] leading-snug">{m.why_priority}{(m.selection_reason || '').includes('manual') ? ' Added manually.' : ''}</td>
                <td className="td text-[12.5px]">{m.assessment.primary_playbook_id} {m.assessment.primary_playbook_name}</td>
                <td className="td text-[12.5px]">{m.completeness < 100 ? <span title={`Missing: ${m.missing_fields.join(', ')}`}>{m.completeness}% <span className="text-mute">incomplete</span></span> : '100%'}</td>
                <td className="td"><Badge tone={cur === 'not_contacted' ? 'neutral' : cur === 'follow_up_due' ? 'bad' : 'brand'}>{STATUS[cur]}</Badge></td>
                <td className="td"><RowActions m={m} compare={[a, b].filter(Boolean)} setCompare={(v) => { setA(v[v.length - 2] ?? ''); setB(v[v.length - 1] ?? '') }} /></td>
              </tr>) })}</tbody></table></div>)}
      </Card>

      <Card title={`Just outside the shortlist (${outside.length})`} sub="Eligible merchants that did not fit in the capacity, with the reason.">
        {outside.length === 0 ? <p className="text-[13px] text-mute">Every eligible merchant is on the shortlist.</p> : (
          <div className="divide-y divide-line">{outside.slice(0, 8).map((m) => (
            <div key={m.id} className="flex flex-wrap items-start justify-between gap-3 py-2.5 first:pt-0">
              <div className="min-w-0 flex-1"><Link to={`/a/${sid}/merchant/${m.id}`} className="font-medium hover:text-brand">{m.name}</Link> <BandBadge band={m.risk_band} label={m.risk_label} /><p className="mt-0.5 text-[12.5px] text-mute">{whyOutside(m)}</p></div>
              <RowActions m={m} /></div>))}</div>)}
        <p className="mt-3 text-[12.5px] text-mute">To see what changes if a different merchant is prioritised, use <Link className="text-brand hover:underline" to={`/a/${sid}/studio`}>Decision Studio</Link>.</p>
      </Card>

      <Card title={`Not selected for churn outreach (${excluded.length})`} sub="Moderate or high risk, but outside the eligibility rules. Review these manually.">
        {excluded.length === 0 ? <p className="text-[13px] text-mute">None.</p> : <ul className="space-y-1.5 text-[13px]">{excluded.slice(0, 10).map((m) => <li key={m.id}><Link to={`/a/${sid}/merchant/${m.id}`} className="font-medium hover:text-brand">{m.name}</Link> · {m.risk_label} · {m.selection_reason}</li>)}</ul>}
      </Card>
      {Object.keys(st.exclusions ?? {}).length > 0 && <Notice tone="warn" title="Manager exclusions recorded">{Object.entries(st.exclusions).map(([id, r]) => `${merchants.find((m) => m.id === id)?.name ?? id}: ${r}`).join('; ')}. Apply them in Decision Studio to change the shortlist.</Notice>}
    </div>
  )
}
