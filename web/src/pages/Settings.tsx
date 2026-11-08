/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ScoreHistogram } from '../components/charts'
import { Badge, Card, Notice, PageHeader, Select, Tabs } from '../components/ui'
import { api, type Dict } from '../lib/api'
import { FOCUS, when } from '../lib/format'
import { useSession } from '../lib/session'

const DIMS: [string, string, string, string][] = [
  ['performance', 'Performance', 'TPV and payment-success deterioration are direct operational signals.', 'Seasonality, and TPV measures that overlap each other.'],
  ['relationship', 'Relationship', 'Unresolved tickets and poor CSAT indicate friction.', 'Missing CSAT, and growing merchants with many resolved tickets.'],
  ['commercial', 'Commercial', 'Competitor and pricing concerns can indicate provider displacement.', 'Notes are unverified; renewal proximity is timing, not intent.'],
  ['engagement', 'Engagement', 'Low usage or contact changes may signal weakening engagement.', 'A current snapshot may not show a decline.'],
]
const ASSUMPTION: Record<string, [string, string]> = {
  net_revenue_rate: ['Net revenue rate', 'share of TPV'], false_alarm_cost_inr: ['Cost of an unnecessary outreach', 'Rs per outreach'], saved_merchant_months: ['Value of a saved merchant', 'months of net revenue at M6 TPV'],
  tpv_unit_inr: ['TPV unit', 'Rs per lakh (TPV is Rs lakh per month)'], max_outreaches: ['Outreach capacity', 'contacts per month'], churn_horizon_days: ['Churn horizon', 'days'], seasonal_industries: ['Seasonal industries', 'industry labels'],
}
const fmt = (k: string, v: any) => (Array.isArray(v) ? v.join(', ') || 'None' : k === 'net_revenue_rate' ? `${(v * 100).toFixed(2).replace(/\.?0+$/, '')}%` : typeof v === 'number' ? v.toLocaleString('en-IN') : String(v))

function rule(id: string, t: Dict): string {
  if (id === 'PB-1') return `Success rate fell ${Math.abs(t.max_success_drop_pp)}pp or more, or the note records a payment-failure concern.`
  if (id === 'PB-2') return `${t.min_unresolved}+ unresolved tickets, or CSAT of ${t.low_csat_max} or below with ${t.low_csat_min_unresolved}+ unresolved.`
  if (id === 'PB-3') return `Competitor, exploring-options or rate-card signal in the note, and renewal within ${t.max_renewal_days} days.`
  if (id === 'PB-4') return `${t.max_logins} or fewer logins and ${t.max_products} or fewer products, plus TPV down ${Math.abs(t.requires_any.max_recent_vs_early_pct)}% or an unresponsive or contact-change note.`
  if (id === 'PB-5') return `Low risk band, TPV up ${t.min_recent_vs_early_pct}% or more, stable success, at most ${t.max_unresolved} unresolved ticket, CSAT ${t.min_csat_if_present}+ if present.`
  return 'Default: seasonal dip, low-volume stable merchant, or no real risk signal.'
}

export default function Settings() {
  const { s, merchants } = useSession()
  const [tab, setTab] = useState('defaults')
  const [cfg, setCfg] = useState<Dict | null>(null)
  const [model, setModel] = useState<Dict | null>(null)
  const [cap, setCap] = useState('')
  const [focus, setFocus] = useState('revenue')
  const [saved, setSaved] = useState(false)
  const [llm, setLlm] = useState<Dict | null>(null)
  const [testing, setTesting] = useState(false)
  useEffect(() => { api.settings().then((c) => { setCfg(c); setCap(c.default_capacity ?? ''); setFocus(c.default_risk_focus ?? 'revenue') }); fetch('/api/config/model').then((r) => r.json()).then(setModel).catch(() => setModel(null)) }, [])
  const prov: Dict = Object.fromEntries((s.assumptions_provenance ?? []).map((p: Dict) => [p.key, p]))
  const over: string[] = s.assumptions_overridden ?? []
  const w: Dict = s.weights_pct ?? Object.fromEntries(DIMS.map(([k]) => [k, (s.scoring.weights[k] ?? 0) * 100]))
  const sc = model?.scoring

  return (
    <div className="space-y-5">
      <PageHeader title="Settings and governance" sub="Defaults for new analyses, the assumptions in force, how risk is scored, the playbooks used, and the AI connection." />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: 'defaults', label: 'Analysis defaults' }, { id: 'assumptions', label: 'Business assumptions' }, { id: 'model', label: 'Risk model' }, { id: 'playbooks', label: 'Playbooks' }, { id: 'ai', label: 'AI provider' }]} />

      {tab === 'defaults' && (<>
        <Card title="Defaults for new analyses" sub="Applied the next time you start an analysis. The workbook's own capacity takes precedence unless you override it.">
          <div className="flex flex-wrap items-end gap-3">
            <label className="block"><span className="label">Default outreach capacity</span><input type="number" min={1} className="input mt-1 !w-32" value={cap} onChange={(e) => setCap(e.target.value)} placeholder="Workbook value" /></label>
            <Select label="Default risk focus" value={focus} onChange={setFocus} className="w-64" options={Object.entries(FOCUS).map(([value, label]) => ({ value, label }))} />
            <button className="btn-primary" onClick={async () => { await api.saveSettings({ default_capacity: cap ? Number(cap) : null, default_risk_focus: focus }); setSaved(true); setTimeout(() => setSaved(false), 1500) }}>{saved ? 'Saved' : 'Save defaults'}</button>
          </div>
        </Card>
        <Card title="Effective configuration for this analysis">
          <dl className="grid gap-x-8 gap-y-2 text-[13px] md:grid-cols-2">
            <div><dt className="label">Workbook</dt><dd>{s.source_file}</dd></div><div><dt className="label">Analysis version</dt><dd>{s.version}</dd></div>
            <div><dt className="label">Capacity in force</dt><dd>{s.kpis.capacity} contacts</dd></div><div><dt className="label">Risk focus</dt><dd>{FOCUS[s.config.risk_focus ?? 'revenue']}</dd></div>
            <div><dt className="label">Scoring weights (P / R / E / C %)</dt><dd>{DIMS.map(([k]) => w[k]).join(' / ')}{s.scoring_overrides ? ' (set in Decision Studio)' : ''}</dd></div><div><dt className="label">Overrides</dt><dd>{(s.scoring_overrides ? 1 : 0) + over.length === 0 ? 'None' : `${s.scoring_overrides ? 'Weights. ' : ''}${over.length ? `Assumptions: ${over.map((k) => ASSUMPTION[k]?.[0] ?? k).join(', ')}` : ''}`}</dd></div>
          </dl>
        </Card>
      </>)}

      {tab === 'assumptions' && (
        <Card title="Business and revenue assumptions in force" sub="Read from the workbook for this analysis. To change one, supply it when starting a new analysis; it is then recorded as manager-supplied." pad={false}>
          <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Assumption</th><th className="th">Value in force</th><th className="th">Unit</th><th className="th">Source in workbook</th><th className="th">Override</th><th className="th">Recorded</th></tr></thead>
            <tbody>{Object.entries(s.assumptions).map(([k, v]) => { const p = prov[k]; const o = over.includes(k); return (
              <tr key={k}><td className="td font-medium">{ASSUMPTION[k]?.[0] ?? k}</td><td className="td num">{fmt(k, v)}</td><td className="td text-[12.5px] text-mute">{ASSUMPTION[k]?.[1]}</td>
                <td className="td text-[12.5px]">{p ? <><span className="font-medium">{p.workbook_item}</span><br /><span className="text-mute">{p.workbook_text}</span></> : <span className="text-mute">Read from the workbook; source text is recorded on new analyses.</span>}</td>
                <td className="td">{o ? <Badge tone="warn">Manager-supplied</Badge> : <Badge>Workbook value</Badge>}</td><td className="td text-[12.5px] text-mute">{when(s.created_at)}</td></tr>) })}</tbody></table></div>
          <p className="border-t border-line px-4 py-3 text-[12px] text-mute">Outreach cost: the workbook says 1.5 hours of CSM time valued at Rs 1,500; EDGE uses Rs 1,500 as the total per outreach (confirmed). If the figure were hourly it would be Rs 2,250.</p>
        </Card>)}

      {tab === 'model' && (<>
        <Notice tone="info" title="Design hypotheses, not learned values">No churn labels exist, so no accuracy is claimed. Weights, scales and thresholds are stated assumptions. Changing them changes the methodology, so they are tested in <Link className="font-medium underline" to={`/a/${s.id}/studio`}>Decision Studio</Link> (weight scenarios and the robustness test) rather than edited here. The baseline weights are the ones shown below.</Notice>
        <Card title="Dimension weights" sub={`Scoring version ${sc?.scoring_version ?? s.scoring.version}. The weights add up to ${DIMS.reduce((a, [k]) => a + Number(w[k]), 0)}%.`} pad={false}>
          <table className="w-full"><thead><tr><th className="th">Dimension</th><th className="th text-right">Weight</th><th className="th">Business rationale</th><th className="th">Main caveat</th></tr></thead>
            <tbody>{DIMS.map(([k, l, r, c]) => <tr key={k}><td className="td font-medium">{l}</td><td className="td num text-right">{w[k]}%</td><td className="td text-[12.5px]">{r}</td><td className="td text-[12.5px] text-mute">{c}</td></tr>)}</tbody></table>
        </Card>
        {sc && (<>
          <Card title="How a score is built and where the cut-offs are">
            <div className="space-y-2 text-[13px]">
              <p>Each dimension is scored 0 to 100. Total = {sc.aggregation.weighted_share} x weighted mean + {(1 - sc.aggregation.weighted_share).toFixed(1)} x strongest dimension + {sc.aggregation.convergence_bonus_per_extra_dim} points for each extra dimension at {sc.aggregation.convergence_threshold}+ (up to {sc.aggregation.convergence_cap}), capped at 100. One dimension alone cannot reach High, so High needs corroboration.</p>
              <p>Categories: <strong>High</strong> {sc.bands.high}+, <strong>Moderate</strong> {sc.bands.medium} to {sc.bands.high - 0.1}, <strong>Low</strong> below {sc.bands.medium}. Current result: {s.kpis.high} High, {s.kpis.medium} Moderate, {s.kpis.low} Low. These cut-offs are not calibrated; moving them changes who is flagged.</p>
              <p>A dimension must reach {sc.driver_min_score} to be named a driver.</p>
            </div>
          </Card>
          <Card title="Threshold check: where scores fall" sub="The category cut-offs are hypotheses. This shows how the scores are spread, who sits near a cut-off, and how the counts move if a cut-off shifts.">
            <div className="grid gap-5 lg:grid-cols-2">
              <ScoreHistogram ms={merchants} high={sc.bands.high} medium={sc.bands.medium} />
              <div className="space-y-4 text-[13px]">
                <div><p className="label mb-1">Counts if a cut-off moves</p>
                  <table className="w-full"><thead><tr><th className="th">High at</th><th className="th text-right">High</th><th className="th">Moderate at</th><th className="th text-right">Moderate</th></tr></thead>
                    <tbody>{[-5, 0, 5].map((d) => { const h = sc.bands.high + d; const md = sc.bands.medium + d; return (
                      <tr key={d} className={d === 0 ? 'font-medium' : ''}><td className="td num">{h}{d === 0 ? ' (current)' : ''}</td><td className="td num text-right">{merchants.filter((m) => m.risk_score >= h).length}</td>
                        <td className="td num">{md}{d === 0 ? ' (current)' : ''}</td><td className="td num text-right">{merchants.filter((m) => m.risk_score >= md && m.risk_score < sc.bands.high).length}</td></tr>) })}</tbody></table>
                  <p className="mt-1 text-[12px] text-mute">The two cut-offs are shifted separately, so read each side on its own.</p></div>
                <div><p className="label mb-1">Merchants within 3 points of a cut-off</p>
                  {(() => { const near = merchants.filter((m) => Math.abs(m.risk_score - sc.bands.high) <= 3 || Math.abs(m.risk_score - sc.bands.medium) <= 3).sort((a, b) => b.risk_score - a.risk_score)
                    return near.length ? <ul className="space-y-0.5">{near.map((m) => <li key={m.id}><Link className="font-medium hover:text-brand-dark" to={`/a/${s.id}/merchant/${m.id}`}>{m.name}</Link> <span className="num text-mute">{m.risk_score.toFixed(1)} · {m.risk_label}</span></li>)}</ul> : <p className="text-mute">None.</p> })()}</div>
              </div>
            </div>
          </Card>
          <Card title="Contextual adjustments (always shown in the explanation when they apply)" pad={false}>
            <table className="w-full"><tbody>{[
              ['Seasonal industry with a dip and rebound', `TPV component x ${sc.seasonal.multiplier}. A dip of ${sc.seasonal.dip_min_pct}% or more in M4 or M5 followed by a ${sc.seasonal.rebound_min_pct}% rebound in M6 is not escalated on volume alone.`],
              ['Small, stable merchant', `Low-usage score x ${sc.engagement.natural_low_touch.multiplier} when TPV change is ${sc.engagement.natural_low_touch.min_tpv_change_pct}% or better and no note signal exists.`],
              ['Busy but growing merchant', `Service score x ${sc.service.growth_damping.multiplier} with at most ${sc.service.growth_damping.max_unresolved} unresolved ticket and TPV up ${sc.service.growth_damping.min_growth_pct}%+. Resolved tickets are never penalised.`],
              ['Missing CSAT or note', 'Contributes no risk points. Lowers evidence completeness and confidence only.'],
              ['Renewal proximity', 'Counted only alongside a commercial signal. Renewal alone is timing, not intent.'],
            ].map(([a, b]) => <tr key={a}><td className="td w-72 font-medium">{a}</td><td className="td text-[12.5px]">{b}</td></tr>)}</tbody></table>
          </Card>
          <Card title="Critical review triggers" sub="These flag a merchant for human review. They add no score and reserve no outreach slot." pad={false}>
            <table className="w-full"><tbody>{[
              ['Severe performance', `TPV down ${Math.abs(sc.critical_triggers.severe_performance.max_recent_vs_early_pct)}% or more and success down ${Math.abs(sc.critical_triggers.severe_performance.max_success_drop_pp)}pp or more`],
              ['Competitor near renewal', `Explicit competitor comparison and renewal within ${sc.critical_triggers.competitor_near_renewal.max_renewal_days} days`],
              ['Service breakdown', `${sc.critical_triggers.service_breakdown.min_unresolved}+ unresolved tickets and CSAT of ${sc.critical_triggers.service_breakdown.max_csat} or below`],
              ['Silent decline', `${sc.critical_triggers.silent_decline.max_logins} or fewer logins, ${sc.critical_triggers.silent_decline.min_consecutive_declines}+ consecutive TPV declines and TPV down ${Math.abs(sc.critical_triggers.silent_decline.max_recent_vs_early_pct)}% or more`],
            ].map(([a, b]) => <tr key={a}><td className="td w-72 font-medium">{a}</td><td className="td text-[12.5px]">{b}</td></tr>)}</tbody></table>
          </Card>
          <Card title="Limitations">
            <ul className="list-disc space-y-1 pl-4 text-[13px]"><li>No outcome data, so weights cannot be learned or checked for accuracy.</li><li>Engagement and support fields are snapshots; success rate has two period averages only.</li><li>Notes are unverified free text.</li><li>Industry groups are small (about 5 to 12 merchants).</li></ul>
            <details className="mt-3"><summary className="cursor-pointer text-[12.5px] font-medium text-brand-dark">Technical details</summary>
              <p className="mt-1 text-[12px] text-mute">Configuration files: {model.config_files.map((f: string) => <code key={f} className="mr-2">{f}</code>)}. Feature scales: TPV {sc.tpv.zero_at_pct}% to {sc.tpv.full_at_pct}%, success {sc.success.zero_at_pp}pp to {sc.success.full_at_pp}pp, performance blend {sc.performance.max_share}.</p></details>
          </Card>
        </>)}
      </>)}

      {tab === 'playbooks' && (
        <Card title="Playbooks from the workbook" sub="The six playbooks come from the P2_Playbooks sheet, word for word. EDGE decides when each applies using the rules in the last column; it never adds a playbook or a commitment." pad={false}>
          <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Playbook</th><th className="th">What happens (permitted commitments)</th><th className="th">When it applies (workbook)</th><th className="th">Rule EDGE uses</th><th className="th">Outreach capacity</th><th className="th">Owner</th></tr></thead>
            <tbody>{s.playbooks.map((p: Dict) => (
              <tr key={p.playbook_id}><td className="td align-top font-medium">{p.playbook_id}<br />{p.name}</td><td className="td align-top text-[12.5px]">{p.what_happens}</td><td className="td align-top text-[12.5px]">{p.when_it_applies}</td>
                <td className="td align-top text-[12.5px] text-mute">{model ? rule(p.playbook_id, model.playbook_triggers[p.playbook_id] ?? {}) : '…'}</td>
                <td className="td align-top">{model?.eligible_playbooks.includes(p.playbook_id) ? <Badge tone="brand">Uses a slot</Badge> : <Badge>No outreach</Badge>}</td><td className="td align-top text-[12.5px] text-mute">Not specified in the workbook</td></tr>))}</tbody></table></div>
          <p className="border-t border-line px-4 py-3 text-[12px] text-mute">Required checks before contact are listed per merchant under Merchant Intelligence ("Verify before contacting"). Tie-break order when several apply: {model?.tie_break_order.join(', ') ?? '…'}.</p>
        </Card>)}

      {tab === 'ai' && (
        <Card title="AI provider">
          <div className="space-y-3 text-[13px]">
            <p>Provider: Anthropic Claude · Model: <span className="font-medium">{cfg?.model}</span> · API key: {cfg?.llm_available ? <Badge tone="ok">Configured on the server</Badge> : <Badge tone="warn">Not set</Badge>}</p>
            <p className="text-mute">The key is read from the server environment and is never shown or sent to the browser. Set <code>ANTHROPIC_API_KEY</code> and <code>CLAUDE_MODEL</code> in the server's environment (for a local run, the project's <code>.env</code> file) and restart.</p>
            <div className="flex items-center gap-3"><button className="btn-secondary" disabled={testing || !cfg?.llm_available} onClick={async () => { setTesting(true); setLlm(await api.testLlm()); setTesting(false) }}>{testing ? 'Testing…' : 'Test connection'}</button>
              {llm && <span className={llm.ok ? 'text-ok' : 'text-bad'}>{llm.message}</span>}</div>
            <Notice tone="info">Without a key everything except open-ended Ask EDGE questions and Claude-written drafts still works. Reports & History shows exactly where AI was and was not used.</Notice>
          </div>
        </Card>)}
    </div>
  )
}
