/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Badge, Card, Notice, PageHeader, Tabs, Tip } from '../components/ui'
import { DRIVER, inr, num, pct } from '../lib/format'
import { useSession } from '../lib/session'

export default function Insights() {
  const { sid, s } = useSession()
  const nav = useNavigate()
  const [tab, setTab] = useState('drivers')
  const [meth, setMeth] = useState(false)
  const c = s.commercial
  const maxH = Math.max(...s.heatmap.map((h: any) => h.count), 1)

  return (
    <div className="space-y-5">
      <PageHeader title="Business Insights" sub="Patterns across the portfolio, beyond individual outreach. These are leads to investigate, not proven causes." />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: 'drivers', label: 'Risk drivers' }, { id: 'segments', label: 'Segments' }, { id: 'commercial', label: 'Commercial exposure' }, { id: 'ops', label: 'Operational recommendations' }]} />

      {tab === 'drivers' && (
        <div className="space-y-4">
          {s.drivers.map((d: any) => (
            <Card key={d.key}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div><h3 className="h-sec">{d.name}</h3><p className="mt-0.5 text-[12.5px] text-mute">{d.merchants} merchants · {d.share_of_portfolio_pct}% of portfolio · {inr(d.annual_value_inr)} run-rate</p></div>
                <button className="btn-secondary" disabled={!d.merchants} onClick={() => nav(`/a/${sid}/portfolio?driver=${d.key}`)}>View {d.merchants} merchants</button>
              </div>
              <div className="mt-3 grid gap-4 md:grid-cols-2">
                <div><p className="label mb-1">Common supporting signals</p>{d.signals.length ? <ul className="list-disc space-y-0.5 pl-4 text-[13px]">{d.signals.map((x: string) => <li key={x}>{x}</li>)}</ul> : <p className="text-[13px] text-mute">No merchants in this group.</p>}</div>
                <div><p className="label mb-1">Recommended business response</p><p className="text-[13px]">{d.response}</p></div>
              </div>
            </Card>))}
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
          <Card title="Where each segment's risk comes from" sub="Moderate and high-risk merchants by segment and primary driver. Darker means more merchants.">
            <div className="grid gap-1" style={{ gridTemplateColumns: `120px repeat(${Object.keys(DRIVER).length}, 1fr)` }}>
              <div />{Object.values(DRIVER).map((d) => <div key={d} className="px-1 pb-1 text-center text-[11.5px] font-medium text-mute">{d}</div>)}
              {['Small', 'Mid', 'Enterprise'].map((sg) => (<>
                <div key={sg} className="flex items-center text-[13px] font-medium">{sg === 'Mid' ? 'Mid-market' : sg}</div>
                {Object.keys(DRIVER).map((d) => { const n = s.heatmap.find((h: any) => h.segment === sg && h.driver === d)?.count ?? 0
                  return <button key={sg + d} onClick={() => nav(`/a/${sid}/portfolio?segment=${sg}&driver=${d}`)} className="num rounded py-3 text-center text-[15px] font-semibold hover:ring-2 hover:ring-brand"
                    style={{ background: `rgba(49,91,255,${0.06 + (n / maxH) * 0.7})`, color: n / maxH > 0.55 ? '#fff' : '#182B49' }} aria-label={`${sg} ${DRIVER[d]}: ${n}`}>{n}</button> })}
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
          <Card title="How these are calculated" action={<button className="btn-ghost" onClick={() => setMeth(!meth)}>{meth ? 'Hide' : 'Show'}</button>}>
            {meth ? <ul className="list-disc space-y-1 pl-4 text-[13px]">{c.methodology.map((x: string) => <li key={x}>{x}</li>)}<li>Cost of an outreach that proves unnecessary: {inr(c.false_alarm_cost_inr)} (workbook), used only in the priority value.</li></ul> : <p className="text-[13px] text-mute">Every figure uses the net-revenue rate, unit, horizon and capacity stated in the workbook's assumptions sheet.</p>}
          </Card>
        </div>)}

      {tab === 'ops' && (
        <div className="space-y-4">
          {s.operational.length === 0 ? <Notice tone="info">No cross-portfolio pattern met the thresholds for a recommendation.</Notice> : s.operational.map((o: any) => (
            <Card key={o.title}><div className="flex items-start justify-between gap-3"><h3 className="h-sec">{o.title}</h3><Badge tone="brand">{o.count} merchants</Badge></div>
              <p className="mt-2 text-[13px]"><span className="font-medium">Observed. </span>{o.evidence}</p><p className="mt-1.5 text-[13px]"><span className="font-medium">Suggested investigation. </span>{o.suggestion}</p></Card>))}
          <p className="text-[12px] text-mute">These patterns are associations in a six-month snapshot. They may point to a product, service or commercial issue but do not prove one.</p>
        </div>)}
    </div>
  )
}
