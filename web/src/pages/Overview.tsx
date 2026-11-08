/* eslint-disable @typescript-eslint/no-explicit-any */
import { RefreshCw, Upload } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { DriverBars, RenewalBars, RiskDonut, RiskValueScatter, SegmentStack, TpvConcentration } from '../components/charts'
import { Ticker } from '../components/Ticker'
import { Card, Notice, PageHeader, Stat } from '../components/ui'
import { api } from '../lib/api'
import { inr, when } from '../lib/format'
import { useSession } from '../lib/session'

export default function Overview() {
  const { sid, s, merchants } = useSession()
  const nav = useNavigate()
  const k = s.kpis
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const go = (q: string) => nav(`/a/${sid}/portfolio?${q}`)

  async function refresh() {
    setBusy(true); setErr(null)
    try {
      const { job_id } = await api.analyse({
        upload_id: s.upload_id, name: s.name, mapping: s.mapping, merchant_sheet: s.sheets.merchants, playbook_sheet: s.sheets.playbooks, assumption_sheet: s.sheets.assumptions,
        config: s.config, assumption_overrides: s.assumptions, use_reference_playbooks: (s.sheets.reference_used ?? []).length > 0,
      })
      for (let i = 0; i < 240; i++) {
        await new Promise((r) => setTimeout(r, 500))
        const j = await api.job(job_id)
        if (j.status === 'done') { nav(`/a/${j.session_id}/overview`); return }
        if (j.status === 'error') throw new Error(j.error)
      }
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

      <section aria-label="Key figures" className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Merchants monitored" value={k.total} sub={`${k.data_incomplete} with incomplete data`} tip="Valid merchant records in this analysis. Incomplete means CSAT or an account note is missing; missing is treated as unknown, not as poor." onClick={() => go('')} />
        <Stat label="High risk" tone="bad" value={k.high} sub="Risk score 50 or more" tip="Heuristic score from four dimensions: performance, service, engagement, commercial. A hypothesis, not a churn probability." onClick={() => go('risk=high')} />
        <Stat label="Moderate risk" tone="warn" value={k.medium} sub="Risk score 28 to 49" tip="Band thresholds are design hypotheses chosen after inspecting the score gap in the data." onClick={() => go('risk=medium')} />
        <Stat label="Low risk" tone="ok" value={k.low} sub={`${k.seasonal_protected} seasonal dips not escalated`} tip="No material risk signal, or a signal explained by seasonality or naturally low volume." onClick={() => go('risk=low')} />
        <Stat label="Immediate attention" value={k.immediate} sub="Meets a critical review trigger" tip="Severe performance fall, competitor mention close to renewal, many unresolved tickets with low CSAT, or near-zero logins after a steep decline. Flags for review; the score is unchanged." onClick={() => go('immediate=1')} />
        <Stat label="Outreach capacity" value={`${k.selected} / ${k.capacity}`} sub={`${k.remaining_capacity} slot(s) remaining`} tip="Contacts the team can make this month (workbook assumption or your override). Shortlisted merchants fill these slots." onClick={() => nav(`/a/${sid}/queue`)} />
        <Stat label="Revenue exposure" value={inr(k.exposure_annual_inr)} sub="Run-rate of moderate + high risk" tip="Annual run-rate net revenue of merchants in the moderate or high band: M6 TPV x net revenue rate x 12. This is revenue at stake, not revenue lost." onClick={() => nav(`/a/${sid}/insights`)} />
        <Stat label="Upcoming renewals" value={k.renewals_60} sub={`${k.renewals_30} within 30 days · ${k.renewals_30_at_risk} of those at risk`} tip="Contracts due within 60 days, regardless of risk." onClick={() => go('renewal=60')} />
      </section>

      <Card title="Portfolio summary" sub="Written from this workbook's numbers.">
        <div className="space-y-2 text-[14px] leading-relaxed">{s.narrative.map((p: string, i: number) => <p key={i}>{p}</p>)}</div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Risk distribution" sub="Select a segment of the chart to filter the portfolio."><RiskDonut ms={merchants} onPick={(b) => go(`risk=${b}`)} /></Card>
        <Card title="Risk drivers"><DriverBars drivers={s.drivers} onPick={(d) => go(`driver=${d}`)} /></Card>
        <Card title="Merchant segments"><SegmentStack ms={merchants} /></Card>
        <Card title="TPV concentration by segment"><TpvConcentration ms={merchants} /></Card>
        <Card title="Renewal timeline"><RenewalBars ms={merchants} onPick={(w) => go(`renewal=${Math.min(Number(w), 180)}`)} /></Card>
        <Card title="Risk versus business value"><RiskValueScatter ms={merchants} onPick={(id) => nav(`/a/${sid}/merchant/${id}`)} /></Card>
      </div>

      <Ticker label="Merchants in this analysis" items={merchants.map((m) => ({ id: m.id, name: m.name, sub: `${m.segment} · ${m.industry}`, logo: m.logo_url }))} onPick={(id) => nav(`/a/${sid}/merchant/${id}`)} />
    </div>
  )
}
