/* eslint-disable @typescript-eslint/no-explicit-any */
import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { RowActions } from '../components/RowActions'
import { Badge, BandBadge, Card, Empty, Identity, Notice, PageHeader, Tip } from '../components/ui'
import { DRIVER_SHORT, FOCUS, PRIORITY, STATUS, inr, isNum, num, pct, pp } from '../lib/format'
import { useSession, type M } from '../lib/session'

const urgency = (d: number) => (d <= 30 ? ['Renews in ' + d + ' days', 'bad'] : d <= 60 ? ['Renews in ' + d + ' days', 'warn'] : d <= 90 ? ['Renews in ' + d + ' days', 'neutral'] : ['No near-term renewal', 'neutral']) as [string, 'bad' | 'warn' | 'neutral']

function ValueBar({ v, max }: { v: number; max: number }) {
  return <div className="flex items-center gap-2"><div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100"><div className="h-full bg-brand" style={{ width: `${Math.max(4, (v / max) * 100)}%` }} /></div><span className="num text-[12px]">{inr(v)}</span></div>
}

export default function Queue() {
  const { sid, s, merchants, status, st } = useSession()
  const [sp] = useSearchParams()
  const cap = s.kpis.capacity
  const scn = s.scenario
  const sel = useMemo(() => merchants.filter((m) => m.selected).sort((a, b) => a.rank - b.rank), [merchants])
  const outside = useMemo(() => merchants.filter((m) => m.eligible && !m.selected && m.rank).sort((a, b) => a.rank - b.rank), [merchants])
  const excluded = useMemo(() => merchants.filter((m) => !m.eligible && m.risk_band !== 'low').sort((a, b) => b.risk_score - a.risk_score), [merchants])
  const maxV = Math.max(...merchants.map((m) => m.annual_value), 1)
  const cutoff = sel[sel.length - 1]
  const cmp = (sp.get('compare') ?? '').split(',').filter((x) => x && x.length).map((id) => merchants.find((m) => m.id === id)).filter(Boolean) as M[]
  const priorities: string[] = scn.priorities ?? []

  const whyOutside = (m: M) => {
    const gap = cutoff ? `Priority value ${inr(m.priority_value)} against ${inr(cutoff.priority_value)} for the last shortlisted merchant (${cutoff.name}).` : ''
    const rule = priorities.length ? `The shortlist favours merchants matching the selected priorities (${priorities.map((p) => PRIORITY[p]).join('; ')}), then ${FOCUS[scn.risk_focus].toLowerCase()}.` : `Ordered by ${FOCUS[scn.risk_focus].toLowerCase()}, then risk-weighted run-rate revenue.`
    return `Ranked #${m.rank}, ${m.rank - cap} place(s) outside the ${cap} slots. ${rule} ${gap}`
  }

  return (
    <div className="space-y-5">
      <PageHeader title="Priority Queue" sub="Who to contact first, and why." />
      <Notice tone="info" title="Risk score and priority rank are different things">
        Risk score (0-100) assesses how concerning the merchant's signals are. Priority rank orders who to consider first under the {cap}-contact limit, using the configured priorities ({priorities.length ? priorities.map((p) => PRIORITY[p]).join(', ') : 'none selected'}), the risk focus ({FOCUS[scn.risk_focus]}) and risk-weighted run-rate revenue.
      </Notice>

      <Card>
        <div className="flex flex-wrap items-center gap-x-8 gap-y-2">
          <div><p className="label">Selected</p><p className="num text-[24px] font-semibold">{sel.length} <span className="text-[14px] font-normal text-mute">of {cap}</span></p></div>
          <div><p className="label">Remaining capacity</p><p className="num text-[24px] font-semibold">{Math.max(cap - sel.length, 0)}</p></div>
          <div><p className="label">Just outside</p><p className="num text-[24px] font-semibold">{outside.length}</p></div>
          <div><p className="label">Not eligible (moderate/high)</p><p className="num text-[24px] font-semibold">{excluded.length}</p></div>
          <div><p className="label flex items-center gap-1">Run-rate represented <Tip text="Sum of annual run-rate net revenue of the shortlisted merchants. Exposure, not a forecast of savings." /></p><p className="num text-[24px] font-semibold">{inr(s.commercial.shortlist_annual_inr)}</p></div>
        </div>
        {sel.length < cap && <p className="mt-3 text-[12.5px] text-mute">Fewer than {cap} merchants are eligible under the current rules, so capacity is not filled. Eligible means playbook PB-1 to PB-4, moderate or high band, and positive risk-weighted value.</p>}
      </Card>

      {cmp.length > 1 && (
        <Card title="Comparison" sub="Selected merchants side by side." action={<Link className="btn-ghost" to={`/a/${sid}/queue`}>Close</Link>}>
          <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Measure</th>{cmp.map((m) => <th key={m.id} className="th"><Link className="text-brand" to={`/a/${sid}/merchant/${m.id}`}>{m.name}</Link></th>)}</tr></thead>
            <tbody>{([['Priority rank', (m: M) => (m.rank ? `#${m.rank}` : 'Not ranked')], ['Risk', (m: M) => `${m.risk_label} (${Math.round(m.risk_score)})`], ['Primary driver', (m: M) => m.assessment.primary_risk_driver],
              ['TPV change', (m: M) => pct(m.tpv_change_pct, 0, true)], ['Success change', (m: M) => pp(m.success_drop_pp)], ['Unresolved tickets', (m: M) => num(m.unresolved)], ['CSAT', (m: M) => (isNum(m.csat) ? m.csat : 'Not available')],
              ['Renewal', (m: M) => `${num(m.renewal_days)} days`], ['Annual run-rate', (m: M) => inr(m.annual_value)], ['Playbook', (m: M) => m.assessment.primary_playbook_id + ' ' + m.assessment.primary_playbook_name]] as [string, (m: M) => any][]).map(([l, f]) => (
              <tr key={l}><td className="td label">{l}</td>{cmp.map((m) => <td key={m.id} className="td">{f(m)}</td>)}</tr>))}</tbody></table></div>
        </Card>
      )}

      <Card title={`Shortlist (${sel.length})`} pad={false}>
        {sel.length === 0 ? <div className="p-5"><Empty title="Nobody is shortlisted">No merchant is eligible for outreach under the current rules and filters.</Empty></div> : (
          <div className="overflow-x-auto"><table className="w-full">
            <thead><tr><th className="th">Rank</th><th className="th">Merchant</th><th className="th">Risk</th><th className="th">Main driver</th><th className="th">Business value</th><th className="th">Renewal</th><th className="th min-w-[280px]">Reason for priority</th><th className="th">Playbook</th><th className="th">Outreach status</th><th className="th w-8" /></tr></thead>
            <tbody>{sel.map((m) => { const [u, tone] = urgency(m.renewal_days); return (
              <tr key={m.id} className="hover:bg-brand-soft/30">
                <td className="td num font-semibold">#{m.rank}</td>
                <td className="td"><Link to={`/a/${sid}/merchant/${m.id}`} className="flex items-center gap-2 font-medium hover:text-brand"><Identity name={m.name} logo={m.logo_url} size={24} />{m.name}</Link><span className="text-[11.5px] text-mute">{m.id} · {m.segment === 'Mid' ? 'Mid-market' : m.segment}</span></td>
                <td className="td"><BandBadge band={m.risk_band} label={m.risk_label} /><span className="num ml-1.5 text-[12px] text-mute">{Math.round(m.risk_score)}</span>{m.immediate && <Badge tone="bad" className="ml-1">Immediate</Badge>}</td>
                <td className="td">{m.primary_dimension ? DRIVER_SHORT[m.primary_dimension] : '–'}</td>
                <td className="td"><ValueBar v={m.annual_value} max={maxV} /></td>
                <td className="td"><Badge tone={tone}>{u}</Badge></td>
                <td className="td text-[12.5px] leading-snug">{m.why_priority}{(m.selection_reason || '').includes('manual') ? ' Added manually.' : ''}</td>
                <td className="td text-[12.5px]">{m.assessment.primary_playbook_id} {m.assessment.primary_playbook_name}</td>
                <td className="td"><Badge tone={status(m.id) === 'not_contacted' ? 'neutral' : 'brand'}>{STATUS[status(m.id)]}</Badge></td>
                <td className="td"><RowActions m={m} /></td>
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
