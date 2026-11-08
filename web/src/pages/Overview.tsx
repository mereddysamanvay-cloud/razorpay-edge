/* eslint-disable @typescript-eslint/no-explicit-any */
import { RefreshCw, Upload } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { RenewalBars, RiskDonut, RiskValueScatter, SegmentStack, TpvConcentration } from '../components/charts'
import { Badge, BandBadge, Card, Notice, PageHeader, Stat } from '../components/ui'
import { api } from '../lib/api'
import { inr, when } from '../lib/format'
import { waitForJob } from '../lib/poll'
import { useSession } from '../lib/session'

export default function Overview() {
  const { sid, s, merchants } = useSession()
  const nav = useNavigate()
  const k = s.kpis
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [more, setMore] = useState(false)
  const [detail, setDetail] = useState(false)
  const go = (q: string) => nav(`/a/${sid}/portfolio?${q}`)
  const flagged = k.high + k.medium
  const drivers: any[] = useMemo(() => [...s.drivers].sort((a, b) => b.annual_value_inr - a.annual_value_inr), [s.drivers])
  const maxCount = Math.max(...drivers.map((d) => d.merchants), 1)
  const maxExp = Math.max(...drivers.map((d) => d.annual_value_inr), 1)
  const topExp = drivers[0]
  const topCount = [...s.drivers].sort((a, b) => b.merchants - a.merchants)[0]
  const urgent = useMemo(() => merchants.filter((m) => m.immediate).sort((a, b) => Number(a.selected) - Number(b.selected) || b.risk_score - a.risk_score), [merchants])
  const urgentOut = urgent.filter((m) => !m.selected).length

  async function refresh() {
    setBusy(true); setErr(null)
    try {
      const { job_id } = await api.analyse({
        upload_id: s.upload_id, name: s.name, mapping: s.mapping, merchant_sheet: s.sheets.merchants, playbook_sheet: s.sheets.playbooks, assumption_sheet: s.sheets.assumptions,
        config: s.config, assumption_overrides: s.assumptions, use_reference_playbooks: (s.sheets.reference_used ?? []).length > 0,
      })
      const j = await waitForJob(job_id)
      nav(`/a/${j.session_id}/overview`)
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <div className="space-y-5">
      <PageHeader title={s.name}
        sub={<><span className="font-medium text-ink">{s.source_file}</span> · analysed {when(s.created_at)} · {s.merchant_count} merchants · {s.period}</>}
        actions={<>
          <button className="btn-secondary" onClick={() => nav('/new')}><Upload size={14} /> Upload new workbook</button>
          <button className="btn-secondary" onClick={refresh} disabled={busy || !s.upload_id}><RefreshCw size={14} className={busy ? 'animate-spin' : ''} /> Refresh analysis</button>
        </>} />
      {err && <Notice tone="bad" title="Refresh failed">{err}</Notice>}

      <Card title="Summary and recommendation">
        <p className="text-[14.5px] leading-relaxed">
          {flagged} of {k.total} merchants show material risk evidence ({k.high} high, {k.medium} moderate); {k.immediate} meet a critical review trigger, and {urgentOut} of those are not on the shortlist.
          {' '}{k.selected} of {k.capacity} outreach slots are used. {topExp && topExp.merchants > 0 ? <>The largest exposure is <strong>{topExp.name.toLowerCase()}</strong> at {inr(topExp.annual_value_inr)}{topCount && topCount.key !== topExp.key ? `, while ${topCount.name.toLowerCase()} has the most merchants (${topCount.merchants})` : ''}.</> : null}
          {k.renewals_30_at_risk > 0 && <> {k.renewals_30_at_risk} flagged merchant(s) renew within 30 days.</>}
        </p>
        <p className="mt-2 text-[13px] text-mute">Suggested next step: review the {urgentOut > 0 ? `${urgentOut} urgent merchant(s) outside the shortlist in the ` : ''}<Link className="text-brand-dark underline" to={`/a/${sid}/queue`}>Priority Queue</Link>, then work the shortlist in the <Link className="text-brand-dark underline" to={`/a/${sid}/actions`}>Action Centre</Link>. Scores are heuristics, not churn probabilities; exposure is annual run-rate, not revenue lost.</p>
        <button className="mt-3 text-[12.5px] font-medium text-brand-dark hover:underline" onClick={() => setDetail(!detail)} aria-expanded={detail}>{detail ? 'Hide detail' : 'Show detail'}</button>
        {detail && <div className="mt-2 space-y-2 border-t border-line pt-3 text-[13.5px] leading-relaxed">{s.narrative.map((p: string, i: number) => <p key={i}>{p}</p>)}</div>}
      </Card>

      <section aria-label="Key figures" className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Merchants monitored" value={k.total} sub="In this analysis" tip="Valid merchant records in this analysis." onClick={() => go('')} />
        <Stat label="Material risk" tone="bad" value={flagged} sub={`${k.high} high · ${k.medium} moderate`} tip="High is a score of 50 or more; moderate is 28 to 49. A heuristic from four dimensions, not a churn probability." onClick={() => go('risk=high,medium')} />
        <Stat label="Immediate attention" value={k.immediate} sub="Meets a critical review trigger" tip="Severe performance fall, competitor mention close to renewal, many unresolved tickets with low CSAT, or near-zero logins after a steep decline. A review flag; the score is unchanged." onClick={() => go('immediate=1')} />
        <Stat label="Outreach slots" value={`${k.selected} / ${k.capacity}`} sub={`${k.remaining_capacity} remaining`} tip="Contacts the team can make this month (workbook assumption or your override)." onClick={() => nav(`/a/${sid}/queue`)} />
        <Stat label="Revenue exposure" value={inr(k.exposure_annual_inr)} sub="Annual run-rate, moderate + high" tip="M6 TPV x net revenue rate x 12 for merchants in the moderate or high band. Exposure, not revenue lost and not expected savings." onClick={() => nav(`/a/${sid}/insights`)} />
        <Stat label="Upcoming renewals" value={k.renewals_60} sub={`${k.renewals_30} within 30 days · ${k.renewals_30_at_risk} flagged`} tip="Contracts due within 60 days, regardless of risk." onClick={() => go('renewal=60')} />
        <Stat label="Evidence complete" value={`${k.total - k.data_incomplete} of ${k.total}`} sub={`${k.data_incomplete} missing CSAT or a note`} tip="Missing CSAT or notes are treated as unknown, not as poor. They lower completeness and add no risk." onClick={() => go('')} />
        <Stat label="Low risk" tone="ok" value={k.low} sub={`${k.seasonal_protected} seasonal dips not escalated`} tip="No material risk signal, or a signal explained by seasonality or naturally low volume." onClick={() => go('risk=low')} />
      </section>

      <div className="grid gap-5 lg:grid-cols-3">
        <Card title="Risk distribution" sub="Merchants by risk category (count)"><RiskDonut ms={merchants} onPick={(b) => go(`risk=${b}`)} /></Card>
        <Card title="Primary risk drivers" sub="Moderate and high-risk merchants: count beside annual run-rate exposure" className="lg:col-span-2">
          <div className="space-y-3">{drivers.map((d) => (
            <button key={d.key} className="grid w-full items-center gap-1 text-left text-[13px] hover:bg-bg md:grid-cols-[190px_1fr]" onClick={() => go(`driver=${d.key}`)}>
              <span className="font-medium">{d.name}</span>
              <span className="space-y-1">
                <span className="flex items-center gap-2"><span className="w-16 text-[11px] text-mute">Merchants</span><span className="h-2.5 flex-1 rounded bg-slate-100"><span className="block h-full rounded bg-brand" style={{ width: `${(d.merchants / maxCount) * 100}%` }} /></span><span className="num w-10 text-right">{d.merchants}</span></span>
                <span className="flex items-center gap-2"><span className="w-16 text-[11px] text-mute">Exposure</span><span className="h-2.5 flex-1 rounded bg-slate-100"><span className="block h-full rounded bg-navy" style={{ width: `${(d.annual_value_inr / maxExp) * 100}%` }} /></span><span className="num w-20 text-right">{inr(d.annual_value_inr)}</span></span>
              </span>
            </button>))}</div>
          <p className="mt-3 text-[11.5px] text-mute">Select a driver to list its merchants. The count and exposure rankings can differ; exposure is not revenue lost.</p>
        </Card>
        <Card title="Renewal timeline" sub="Merchants by days to contract renewal (count)" className="lg:col-span-2"><RenewalBars ms={merchants} onPick={(w) => go(`renewal=${Math.min(Number(w), 180)}`)} /></Card>
        <Card title="Needs attention now" sub={`${urgent.length} merchants meet a critical review trigger`}>
          {urgent.length === 0 ? <p className="text-[13px] text-mute">No merchant meets a critical review trigger.</p> : (
            <ul className="divide-y divide-line">{urgent.slice(0, 6).map((m) => (
              <li key={m.id} className="flex items-center justify-between gap-2 py-2 text-[13px] first:pt-0 last:pb-0">
                <span className="min-w-0"><Link to={`/a/${sid}/merchant/${m.id}`} className="block truncate font-medium hover:text-brand-dark">{m.name}</Link><span className="text-[11.5px] text-mute">{m.id} · {Math.round(m.renewal_days)} days to renewal</span></span>
                <span className="flex shrink-0 items-center gap-1"><BandBadge band={m.risk_band} label={m.risk_label} />{!m.selected && <Badge tone="warn">Not shortlisted</Badge>}</span></li>))}</ul>)}
          {urgent.length > 6 && <Link className="mt-3 inline-block text-[12.5px] font-medium text-brand-dark hover:underline" to={`/a/${sid}/portfolio?immediate=1`}>See all {urgent.length}</Link>}
        </Card>
      </div>

      <button className="btn-secondary" onClick={() => setMore(!more)} aria-expanded={more}>{more ? 'Hide' : 'Show'} more portfolio charts</button>
      {more && (
        <div className="grid gap-5 lg:grid-cols-2">
          <Card title="Merchant segments" sub="Merchants per segment by risk category (count)"><SegmentStack ms={merchants} /></Card>
          <Card title="TPV concentration by segment" sub="Share of M6 TPV (Rs lakh per month)"><TpvConcentration ms={merchants} /></Card>
          <Card title="Risk versus business value" sub="Each dot is a merchant: risk score against annual run-rate"><RiskValueScatter ms={merchants} onPick={(id) => nav(`/a/${sid}/merchant/${id}`)} /></Card>
        </div>)}
    </div>
  )
}
