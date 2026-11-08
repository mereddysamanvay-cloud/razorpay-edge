/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Badge, Card, Notice, PageHeader, Tabs, Tip } from '../components/ui'
import { api, type Dict } from '../lib/api'
import { DRIVER, inr, num, pct } from '../lib/format'
import { useSession } from '../lib/session'

const STRENGTH: Record<string, 'ok' | 'warn' | 'neutral'> = { Strong: 'ok', Moderate: 'warn', Limited: 'neutral' }
const frac = (x: Dict) => `${x.n} of ${x.of}${x.pct === null ? '' : ` (${x.pct}%)`}`

export default function Insights() {
  const { sid, s } = useSession()
  const nav = useNavigate()
  const [tab, setTab] = useState('drivers')
  const [meth, setMeth] = useState(false)
  const [x, setX] = useState<Dict | null>(null)
  useEffect(() => { api.insights(sid).then(setX).catch(() => setX(null)) }, [sid])
  const c = s.commercial
  const maxH = Math.max(...s.heatmap.map((h: any) => h.count), 1)

  return (
    <div className="space-y-5">
      <PageHeader title="Business Insights" sub="Patterns across the portfolio, beyond individual outreach. These are leads to investigate, not proven causes." />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: 'drivers', label: 'Risk drivers' }, { id: 'segments', label: 'Segments' }, { id: 'commercial', label: 'Commercial exposure' }, { id: 'ops', label: 'Operational recommendations' }]} />

      {tab === 'drivers' && (
        <div className="space-y-4">
          {x && (
            <Card title="Merchant count versus revenue exposure" sub={`Share of the ${x.flagged_total} moderate and high-risk merchants, beside the share of their ${inr(x.flagged_exposure_inr)} annual run-rate exposure. The two rankings can differ.`}>
              <div className="space-y-3">{x.comparison.map((r: Dict) => (
                <div key={r.key} className="grid items-center gap-2 text-[13px] md:grid-cols-[220px_1fr]">
                  <span className="font-medium">{r.driver}</span>
                  <div className="space-y-1">
                    <div className="flex items-center gap-2"><span className="w-20 text-[11.5px] text-mute">Merchants</span><div className="h-2.5 flex-1 rounded bg-slate-100"><div className="h-full rounded bg-brand" style={{ width: `${r.merchants_pct ?? 0}%` }} /></div><span className="num w-28 text-right">{r.merchants} ({r.merchants_pct ?? 0}%)</span></div>
                    <div className="flex items-center gap-2"><span className="w-20 text-[11.5px] text-mute">Exposure</span><div className="h-2.5 flex-1 rounded bg-slate-100"><div className="h-full rounded bg-navy" style={{ width: `${r.exposure_pct ?? 0}%` }} /></div><span className="num w-28 text-right">{inr(r.exposure_inr)} ({r.exposure_pct ?? 0}%)</span></div>
                  </div></div>))}</div>
              <p className="mt-3 text-[12.5px] text-mute">{x.same_leader ? `${x.leader_by_count} leads on both count and exposure.` : `${x.leader_by_count} has the most merchants; ${x.leader_by_exposure} carries the most exposure.`} Exposure is annual run-rate of the grouped merchants, not revenue lost or expected savings.</p>
            </Card>)}
          {s.drivers.map((d: any) => { const e = x?.drivers.find((y: Dict) => y.key === d.key); return (
            <Card key={d.key}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div><h3 className="h-sec">{d.name} {e && <Badge tone={STRENGTH[e.evidence_strength]} className="ml-1">Independent evidence: {e.evidence_strength}</Badge>}</h3>
                  <p className="mt-0.5 text-[12.5px] text-mute">{d.merchants} merchants{e ? ` (${e.share_of_flagged_pct ?? 0}% of those flagged)` : ''} · {inr(d.annual_value_inr)} run-rate exposure{e ? ` (${e.share_of_exposure_pct ?? 0}% of exposure)` : ''}</p></div>
                <button className="btn-secondary" disabled={!d.merchants} onClick={() => nav(`/a/${sid}/portfolio?driver=${d.key}`)}>View {d.merchants} merchants</button>
              </div>
              {e ? (
                <div className="mt-3 grid gap-4 md:grid-cols-3">
                  <div><p className="label mb-1">How merchants were grouped</p><p className="text-[13px]">{e.selection_rule}</p><p className="mt-1 text-[12px] text-mute">{e.caveat}</p></div>
                  <div><p className="label mb-1">Independent corroborating evidence</p><ul className="list-disc space-y-1 pl-4 text-[13px]">{e.corroboration.map((c: Dict) => <li key={c.text}>{c.text}: <span className="num font-medium">{frac(c)}</span></li>)}</ul></div>
                  <div><p className="label mb-1">Counter-evidence</p><ul className="list-disc space-y-1 pl-4 text-[13px]">{e.counter_evidence.map((c: Dict) => <li key={c.text}>{c.text}: <span className="num font-medium">{frac(c)}</span></li>)}</ul></div>
                </div>) : (
                <div className="mt-3"><p className="label mb-1">Common supporting signals</p>{d.signals.length ? <ul className="list-disc space-y-0.5 pl-4 text-[13px]">{d.signals.map((y: string) => <li key={y}>{y}</li>)}</ul> : <p className="text-[13px] text-mute">No merchants in this group.</p>}</div>)}
              <div className="mt-3 border-t border-line pt-3"><p className="label mb-1">Recommended business response</p><p className="text-[13px]">{d.response}</p></div>
            </Card>) })}
        </div>)}

      {tab === 'segments' && (
        <div className="space-y-4">
          <Card title="Segment comparison" pad={false}>
            <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Measure</th>{s.segments.map((x: any) => <th key={x.segment} className="th text-right">{x.segment === 'Mid' ? 'Mid-market' : x.segment}</th>)}</tr></thead>
              <tbody>{([
                ['Merchants', (x: any) => x.merchants], ['High risk', (x: any) => x.high], ['Moderate risk', (x: any) => x.medium], ['Low risk', (x: any) => x.low],
                ['Share at moderate or high risk', (x: any) => pct(((x.high + x.medium) / x.merchants) * 100, 0)],
                ['M6 TPV (Rs lakh)', (x: any) => num(x.tpv_m6_lakh, 1)], ['Average TPV per merchant (Rs lakh)', (x: any) => num(x.avg_tpv_m6_lakh, 1)],
                ['Median TPV change, M4-M6 vs M1-M3', (x: any) => pct(x.median_tpv_change_pct, 0, true)], ['Average payment success rate', (x: any) => pct(x.avg_success_pct, 1)],
                ['Average CSAT (where available)', (x: any) => `${num(x.avg_csat, 1)} (${x.csat_known} of ${x.merchants} known)`], ['Average tickets, 90 days', (x: any) => num(x.avg_tickets_90d, 1)],
                ['Average unresolved tickets', (x: any) => num(x.avg_unresolved, 1)], ['Average products used', (x: any) => num(x.avg_products, 1)], ['Average logins, 30 days', (x: any) => num(x.avg_logins, 1)],
                ['Renewals within 60 days', (x: any) => x.renewals_60], ['Revenue exposed (moderate + high)', (x: any) => inr(x.exposed_inr)],
              ] as [string, (x: any) => any][]).map(([l, f]) => <tr key={l}><td className="td">{l}</td>{s.segments.map((x: any) => <td key={x.segment} className="td num text-right">{f(x)}</td>)}</tr>)}</tbody></table></div>
          </Card>
          {x && (
            <Card title="Segment rates with denominators" sub="Each rate states what it is a share of. Segment sizes differ, so compare shares rather than counts." pad={false}>
              <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Measure</th>{x.segments.map((g: Dict) => <th key={g.segment} className="th text-right">{g.segment === 'Mid' ? 'Mid-market' : g.segment} ({g.merchants})</th>)}</tr></thead>
                <tbody>{([
                  ['High risk (of segment)', (g: Dict) => frac(g.bands.high)], ['Moderate risk (of segment)', (g: Dict) => frac(g.bands.medium)], ['Moderate or high (of segment)', (g: Dict) => frac(g.flagged_rate)],
                  ['Share of portfolio M6 TPV', (g: Dict) => `${g.tpv_share_pct}%`], ['Annual run-rate exposure', (g: Dict) => `${inr(g.exposure_inr)} (${g.exposure_share_pct ?? 0}% of exposure)`],
                  ['Primary drivers (flagged)', (g: Dict) => Object.entries(g.drivers).filter(([, v]) => (v as number) > 0).map(([k, v]) => `${DRIVER[k]} ${v}`).join(', ') || 'None'],
                  ['Evidence incomplete', (g: Dict) => frac(g.missing.incomplete)], ['CSAT missing', (g: Dict) => frac(g.missing.csat)], ['No account-manager note', (g: Dict) => frac(g.missing.note)],
                ] as [string, (g: Dict) => string][]).map(([l, f]) => <tr key={l}><td className="td">{l}</td>{x.segments.map((g: Dict) => <td key={g.segment} className="td num text-right text-[12.5px]">{f(g)}</td>)}</tr>)}</tbody></table></div>
            </Card>)}
          <Card title="Where each segment's risk comes from" sub="Moderate and high-risk merchants by segment and primary driver. Darker means more merchants.">
            <div className="grid gap-1" style={{ gridTemplateColumns: `120px repeat(${Object.keys(DRIVER).length}, 1fr)` }}>
              <div />{Object.values(DRIVER).map((d) => <div key={d} className="px-1 pb-1 text-center text-[11.5px] font-medium text-mute">{d}</div>)}
              {['Small', 'Mid', 'Enterprise'].map((sg) => (<>
                <div key={sg} className="flex items-center text-[13px] font-medium">{sg === 'Mid' ? 'Mid-market' : sg}</div>
                {Object.keys(DRIVER).map((d) => { const n = s.heatmap.find((h: any) => h.segment === sg && h.driver === d)?.count ?? 0
                  return <button key={sg + d} onClick={() => nav(`/a/${sid}/portfolio?segment=${sg}&driver=${d}`)} className="num rounded py-3 text-center text-[15px] font-semibold hover:ring-2 hover:ring-brand"
                    style={{ background: `rgba(53,92,255,${0.06 + (n / maxH) * 0.7})`, color: n / maxH > 0.55 ? '#fff' : '#10213E' }} aria-label={`${sg} ${DRIVER[d]}: ${n}`}>{n}</button> })}
              </>))}
            </div>
            <p className="mt-3 text-[12px] text-mute">Segments differ in size; compare shares in the table above before drawing conclusions. Industry groups hold roughly 5 to 12 merchants each, too few for reliable industry comparisons.</p>
          </Card>
        </div>)}

      {tab === 'commercial' && (
        <div className="space-y-4">
          <div className="grid gap-3 md:grid-cols-3">
            {[['Merchant TPV (M6, monthly)', c.monthly_tpv_inr, 'Total latest-month transaction value processed for these merchants.'],
              ['Estimated Razorpay revenue (monthly)', c.monthly_net_revenue_inr, `M6 TPV x ${(c.net_revenue_rate * 100).toFixed(2).replace(/\.?0+$/, '')}% net revenue assumption from the workbook.`],
              ['Revenue run-rate (annual)', c.annual_run_rate_inr, `Monthly net revenue x ${c.months} months.`],
              ['Revenue potentially exposed', c.exposed_annual_inr, 'Run-rate of moderate and high-risk merchants. Exposure, not loss.'],
              ['Risk-weighted exposure', c.risk_weighted_exposed_inr, 'Exposure weighted by risk score x confidence (hypothesis weights, not probabilities).'],
              ['Represented by current shortlist', c.shortlist_annual_inr, 'Run-rate of the merchants currently selected for outreach.']].map(([l, v, t]) => (
              <div key={l as string} className="card p-4"><p className="label flex items-center gap-1">{l}<Tip text={t as string} /></p><p className="num mt-1.5 text-[24px] font-semibold">{inr(v as number)}</p></div>))}
            <div className="card p-4"><p className="label flex items-center gap-1">Revenue actually lost<Tip text="The workbook contains no churn outcomes, so lost revenue cannot be measured." /></p><p className="mt-1.5 text-[24px] font-semibold text-mute">Not available</p></div>
          </div>
          {x && (
            <div className="grid gap-4 lg:grid-cols-2">
              <Card title="Where the exposure sits, by segment" pad={false}>
                <table className="w-full"><thead><tr><th className="th">Segment</th><th className="th text-right">Exposure</th><th className="th text-right">Share</th></tr></thead>
                  <tbody>{x.commercial.segment_concentration.map((r: Dict) => <tr key={r.segment}><td className="td">{r.segment === 'Mid' ? 'Mid-market' : r.segment}</td><td className="td num text-right">{inr(r.exposure_inr)}</td><td className="td num text-right">{r.share_pct ?? 0}%</td></tr>)}</tbody></table>
              </Card>
              <Card title="Exposure by renewal window" pad={false}>
                <table className="w-full"><thead><tr><th className="th">Renewal</th><th className="th text-right">Merchants</th><th className="th text-right">Flagged</th><th className="th text-right">Exposure</th></tr></thead>
                  <tbody>{x.commercial.renewal_windows.map((r: Dict) => <tr key={r.window}><td className="td">{r.window}</td><td className="td num text-right">{r.merchants}</td><td className="td num text-right">{r.flagged} of {r.merchants}</td><td className="td num text-right">{inr(r.exposure_inr)}</td></tr>)}</tbody></table>
              </Card>
              <Card title="Commercial evidence" className="lg:col-span-2">
                <p className="text-[13px]"><span className="num font-semibold">{x.commercial.commercial_evidence.merchants_with_signal}</span> merchants have a pricing, rate-card or competitor signal in their account-manager note, carrying {inr(x.commercial.commercial_evidence.exposure_inr)} of run-rate; {x.commercial.commercial_evidence.renewing_60} renew within 60 days.</p>
                <p className="mt-1 text-[12.5px] text-mute">{x.commercial.commercial_evidence.status} Renewal proximity shows timing, not intent to leave.</p>
              </Card>
            </div>)}
          <Card title="How these are calculated" action={<button className="btn-ghost" onClick={() => setMeth(!meth)}>{meth ? 'Hide' : 'Show'}</button>}>
            {meth ? <ul className="list-disc space-y-1 pl-4 text-[13px]">{c.methodology.map((x: string) => <li key={x}>{x}</li>)}<li>Cost of an outreach that proves unnecessary: {inr(c.false_alarm_cost_inr)} (workbook), used only in the priority index, a ranking aid and not an expected saving.</li></ul> : <p className="text-[13px] text-mute">Every figure uses the net-revenue rate, unit, horizon and capacity stated in the workbook's assumptions sheet.</p>}
          </Card>
        </div>)}

      {tab === 'ops' && x && x.operational.length > 0 && (
        <div className="space-y-4">
          <Notice tone="info" title="How these leads are ordered">{x.operational_order}</Notice>
          <Card pad={false}>
            <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">#</th><th className="th">Lead</th><th className="th text-right">Merchants</th><th className="th text-right">Exposure</th><th className="th">Evidence</th><th className="th text-right">Renewing in 60 days</th><th className="th">Effort</th><th className="th">Scope</th></tr></thead>
              <tbody>{x.operational.map((o: Dict, i: number) => (
                <tr key={o.title}><td className="td num text-mute">{o.informational ? '–' : i + 1}</td><td className="td font-medium">{o.title}</td><td className="td num text-right">{o.merchants}</td><td className="td num text-right">{o.informational ? 'Not at risk' : inr(o.exposure_inr)}</td>
                  <td className="td"><Badge tone={STRENGTH[o.evidence_strength]}>{o.evidence_strength}</Badge></td><td className="td num text-right">{o.urgent_renewals_60}</td><td className="td text-[12.5px]">{o.effort}</td><td className="td text-[12.5px]">{o.scope}</td></tr>))}</tbody></table></div>
          </Card>
          {x.operational.map((o: Dict) => (
            <Card key={o.title}><div className="flex items-start justify-between gap-3"><h3 className="h-sec">{o.title}</h3><Badge tone="brand">{o.merchants} merchants</Badge></div>
              <p className="mt-2 text-[13px]"><span className="font-medium">Observed. </span>{o.evidence}</p><p className="mt-1.5 text-[13px]"><span className="font-medium">Suggested investigation. </span>{o.suggestion}</p>
              <p className="mt-1.5 text-[12px] text-mute">Segments: {o.segments.map((g: string) => (g === 'Mid' ? 'Mid-market' : g)).join(', ')}. No amount recoverable by acting on this lead is claimed.</p></Card>))}
          <p className="text-[12px] text-mute">These patterns are associations in a six-month snapshot. They may point to a product, service or commercial issue but do not prove one.</p>
        </div>)}
      {tab === 'ops' && !(x && x.operational.length > 0) && (
        <div className="space-y-4">
          {s.operational.length === 0 ? <Notice tone="info">No cross-portfolio pattern met the thresholds for a recommendation.</Notice> : s.operational.map((o: any) => (
            <Card key={o.title}><div className="flex items-start justify-between gap-3"><h3 className="h-sec">{o.title}</h3><Badge tone="brand">{o.count} merchants</Badge></div>
              <p className="mt-2 text-[13px]"><span className="font-medium">Observed. </span>{o.evidence}</p><p className="mt-1.5 text-[13px]"><span className="font-medium">Suggested investigation. </span>{o.suggestion}</p></Card>))}
          <p className="text-[12px] text-mute">These patterns are associations in a six-month snapshot. They may point to a product, service or commercial issue but do not prove one.</p>
        </div>)}
    </div>
  )
}
