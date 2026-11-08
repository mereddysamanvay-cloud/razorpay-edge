/* eslint-disable @typescript-eslint/no-explicit-any */
import clsx from 'clsx'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useMemo } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { TpvLine } from '../components/charts'
import { DraftWorkflow } from '../components/DraftWorkflow'
import { Badge, BandBadge, Card, Empty, Identity, Meter, Notice, Tip } from '../components/ui'
import { DRIVER, STATUS, inr, isNum, lakh, num, pct, pp } from '../lib/format'
import { useSession, type M } from '../lib/session'

type Level = 'ok' | 'watch' | 'concern' | 'unknown'
const LV: Record<Level, { l: string; c: string }> = {
  ok: { l: 'Healthy', c: 'bg-ok-fill' }, watch: { l: 'Watch', c: 'bg-warn-fill' }, concern: { l: 'Concern', c: 'bg-bad' }, unknown: { l: 'Data not available', c: 'bg-slate-300' },
}

function health(m: M) {
  const lvl = (c: boolean, w: boolean): Level => (c ? 'concern' : w ? 'watch' : 'ok')
  return [
    { k: 'Transaction performance', v: pct(m.tpv_change_pct, 0, true), d: 'avg TPV M4-M6 vs M1-M3', lv: lvl(m.tpv_change_pct <= -20, m.tpv_change_pct <= -10), tip: 'Compares the average of the last three months with the first three. A lone dip that rebounds counts for little.' },
    { k: 'Payment performance', v: pp(m.success_drop_pp), d: `${pct(m.success_early, 1)} to ${pct(m.success_recent, 1)}`, lv: lvl(m.success_drop_pp <= -5, m.success_drop_pp <= -2), tip: 'Only two period averages exist in the workbook (M1-M3 and M4-M6); no monthly series is shown.' },
    { k: 'Support experience', v: `${num(m.unresolved)} open`, d: `of ${num(m.tickets)} tickets in 90 days`, lv: lvl(m.unresolved >= 3, m.unresolved >= 1), tip: 'Resolved tickets are not penalised. A high count with everything resolved and a growing merchant is not a warning sign.' },
    { k: 'Customer satisfaction', v: isNum(m.csat) ? `${m.csat} / 5` : 'Not available', d: isNum(m.csat) ? 'last survey' : 'no survey response', lv: !isNum(m.csat) ? 'unknown' : lvl(m.csat <= 2, m.csat === 3), tip: 'A missing survey is unknown, not unhappy.' },
    { k: 'Engagement', v: `${num(m.logins)} logins`, d: `${num(m.products)} product(s) used`, lv: lvl(m.dims.engagement >= 40, m.dims.engagement >= 25), tip: 'A snapshot of the last 30 days. Change over time cannot be claimed from this data.' },
    { k: 'Commercial & renewal', v: `${num(m.renewal_days)} days`, d: m.note_signals.some((s: string) => ['competitor_explicit', 'exploring_options', 'rate_card_request', 'pricing_objection'].includes(s)) ? 'commercial signal in note' : 'to renewal', lv: lvl(m.dims.commercial >= 40, m.dims.commercial >= 25), tip: 'Renewal proximity alone adds no risk; it raises the stakes of a commercial signal.' },
  ]
}

const SIGNAL_DIM = (f: string) => (/tpv|success/.test(f) ? 'performance' : /ticket|csat/.test(f) ? 'relationship' : /login|product/.test(f) ? 'engagement' : 'commercial')
const SEV = (v: number) => (v >= 50 ? ['High', 'bad'] : v >= 25 ? ['Medium', 'warn'] : ['Low', 'neutral']) as ['High' | 'Medium' | 'Low', 'bad' | 'warn' | 'neutral']
const NEXT: Record<string, string[]> = {
  'PB-1': ['Get the success-rate breakdown by method and bank from Payments Ops', 'Book a joint call with the merchant and Payments Ops', 'Commit only to the 3-day fix-plan window stated in the playbook'],
  'PB-2': ['Take ownership of every open ticket and name a single point of contact', 'Confirm a closure date per ticket', 'Arrange a senior callback within 48 hours'],
  'PB-3': ['Review rate card, volume tiers and renewal terms before the renewal date', 'Confirm with the Account Manager what was actually said about competitors or pricing', 'Prepare options internally; make no commercial commitment in the first message'],
  'PB-4': ['Re-confirm the right contact person', 'Invite the merchant to a short workshop on unused products and reports', 'Involve the executive sponsor where the segment warrants it'],
  'PB-5': ['Hold a positive check-in', 'Offer relevant new products or higher-limit plans'],
  'PB-6': ['No outreach this month', 'Keep on the watchlist and re-check next month'],
}

const PERIOD = (f: string) => (/tpv/.test(f) ? 'M1 to M6 (latest M6)' : /success/.test(f) ? 'Two averages: M1-M3 and M4-M6' : /ticket/.test(f) ? 'Last 90 days' : /csat/.test(f) ? 'Most recent survey' : /login/.test(f) ? 'Last 30 days (snapshot)' : /product/.test(f) ? 'Current snapshot' : /renewal|days_to/.test(f) ? 'Days to contract renewal' : /note/.test(f) ? 'Account-manager note (undated)' : 'As supplied')
const NOTE_LABEL: Record<string, string> = { competitor_explicit: 'Competitor mentioned', exploring_options: 'Exploring other options', rate_card_request: 'Rate-card request', pricing_objection: 'Pricing objection',
  service_complaint: 'Service complaint', service_escalation: 'Service escalation', unresponsive: 'Unresponsive to check-ins', decision_maker_change: 'Contact or decision-maker change', performance_complaint: 'Payment failure concern',
  resolved_minor: 'Minor issue resolved', seasonal_claim: 'Seasonal explanation given', positive_growth: 'Positive growth', expansion_interest: 'Expansion interest', low_touch: 'Low-touch merchant', no_concerns: 'No concerns raised' }
const DIM4 = ['performance', 'relationship', 'engagement', 'commercial'] as const

export default function Merchant360() {
  const { mid } = useParams()
  const { sid, s, merchants, byId, status } = useSession()
  const nav = useNavigate()
  const m = mid ? byId[mid] : undefined
  const order = useMemo(() => [...merchants].sort((a, b) => (a.rank ?? 9999) - (b.rank ?? 9999) || a.risk_rank - b.risk_rank), [merchants])
  if (!m) return <Empty title="Merchant not found" action={<Link className="btn-primary" to={`/a/${sid}/portfolio`}>Back to portfolio</Link>}>This merchant is not part of the current analysis.</Empty>
  const i = order.findIndex((x) => x.id === m.id)
  const a = m.assessment
  const pb = s.playbooks.find((p: any) => p.playbook_id === a.primary_playbook_id)
  const sec = s.playbooks.find((p: any) => p.playbook_id === a.secondary_playbook_id)
  const rows = health(m)

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between text-[13px]">
        <Link to={`/a/${sid}/portfolio`} className="text-brand hover:underline">Merchant Portfolio</Link>
        <div className="flex items-center gap-1"><button className="btn-ghost !p-1.5" disabled={i <= 0} onClick={() => nav(`/a/${sid}/merchant/${order[i - 1].id}`)} aria-label="Previous merchant"><ChevronLeft size={16} /></button>
          <span className="text-mute">{i + 1} of {order.length} by priority</span>
          <button className="btn-ghost !p-1.5" disabled={i >= order.length - 1} onClick={() => nav(`/a/${sid}/merchant/${order[i + 1].id}`)} aria-label="Next merchant"><ChevronRight size={16} /></button></div>
      </div>

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <Identity name={m.name} logo={m.logo_url} size={48} />
            <div>
              <h1 className="h-page">{m.name}</h1>
              <p className="mt-0.5 text-[13px] text-mute">{m.id} · {m.segment === 'Mid' ? 'Mid-market' : m.segment} · {m.industry}{m.city ? ` · ${m.city}` : ''}{m.account_manager ? ` · AM: ${m.account_manager}` : ''}</p>
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                <BandBadge band={m.risk_band} label={m.risk_label} />
                {m.immediate && <Badge tone="bad">Immediate review</Badge>}
                {m.completeness < 100 && <Badge>Data incomplete</Badge>}
                <Badge tone="brand">Human review required</Badge>
                {m.selected && <Badge tone="brand">On shortlist</Badge>}
              </div>
            </div>
          </div>
          <dl className="grid grid-cols-4 gap-x-6 gap-y-1 text-right">
            <div><dt className="label flex items-center justify-end gap-1">Risk score <Tip text="0-100 heuristic built from four dimensions. It is not a probability of churn." /></dt><dd className="num text-[24px] font-semibold">{Math.round(m.risk_score)}</dd></div>
            <div><dt className="label flex items-center justify-end gap-1">Priority <Tip text="Order in which to consider outreach under the capacity limit. Different from risk score: it also reflects value and the selected priorities." /></dt><dd className="num text-[24px] font-semibold">{m.rank ? `#${m.rank}` : '–'}</dd></div>
            <div><dt className="label">Renewal</dt><dd className={clsx('num text-[24px] font-semibold', m.renewal_days <= 30 && 'text-bad')}>{num(m.renewal_days)}<span className="text-[13px] font-normal text-mute"> d</span></dd></div>
            <div><dt className="label">Run-rate / yr</dt><dd className="num text-[24px] font-semibold">{inr(m.annual_value)}</dd></div>
          </dl>
        </div>
        <p className="mt-4 rounded-md bg-bg px-3 py-2 text-[13.5px] leading-relaxed"><span className="font-medium">Summary. </span>{a.plain_language_reason}</p>
        <p className="mt-2 text-[12.5px] text-mute"><span className="font-medium text-ink">Annual net-revenue run-rate proxy: </span>M6 TPV Rs {num(m.tpv_m6, 1)} lakh x {((s.assumptions.net_revenue_rate ?? 0) * 100).toFixed(2).replace(/\.?0+$/, '')}% net revenue x 12 months = {inr(m.annual_value)}. An exposure proxy: not revenue lost and not expected savings. No churn outcome exists in the data.</p>
      </Card>

      <Card title="Merchant health" sub="Six separate dimensions. The single score is a summary, not the whole story.">
        <div className="grid gap-3 md:grid-cols-3">
          {rows.map((r) => (
            <div key={r.k} className="rounded-md border border-line p-3">
              <div className="flex items-center justify-between"><span className="flex items-center gap-1 text-[12.5px] font-medium">{r.k}<Tip text={r.tip} /></span>
                <span className="flex items-center gap-1.5 text-[11.5px] text-mute"><span className={clsx('h-2 w-2 rounded-full', LV[r.lv].c)} />{LV[r.lv].l}</span></div>
              <p className="num mt-1.5 text-[20px] font-semibold leading-none">{r.v}</p><p className="mt-1 text-[12px] text-mute">{r.d}</p>
            </div>))}
        </div>
        <div className="mt-4 grid gap-x-6 gap-y-1 md:grid-cols-4">
          {(['performance', 'relationship', 'engagement', 'commercial'] as const).map((d) => (
            <div key={d}><p className="label mb-1">{DRIVER[d]}</p><Meter value={m.dims[d]} label="Dimension score 0-100" /></div>))}
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Transaction performance" sub="Observed monthly TPV (Rs lakh)">
          <TpvLine m={m} />
          <dl className="mt-3 grid grid-cols-3 gap-3 text-[13px]">
            <div><dt className="label">M1 to M6</dt><dd className="num font-semibold">{pct(m.tpv_change_m1_m6_pct, 0, true)}</dd></div>
            <div><dt className="label">M6 vs M5</dt><dd className="num font-semibold">{pct(m.m6_vs_m5_pct, 0, true)}</dd></div>
            <div><dt className="label">Consecutive declines</dt><dd className="num font-semibold">{num(m.consecutive_declines)}</dd></div>
          </dl>
          <p className="mt-3 text-[12.5px] leading-snug text-mute"><span className="font-medium text-ink">Interpretation. </span>
            {m.seasonal_adjusted ? 'The industry is seasonal and the pattern is a dip followed by a rebound, so the volume signal was discounted.' : m.tpv_trend === 'deteriorating' ? 'Volume is lower in the recent three months. This is a signal to investigate, not proof that the merchant is leaving.' : m.tpv_trend === 'improving' ? 'Volume is growing.' : 'Volume is broadly stable.'}
            {isNum(m.peer?.vs_segment_pp) && ` Against the ${m.segment} median change (${pct(m.peer.segment_median_change, 0, true)}), this merchant is ${pp(m.peer.vs_segment_pp)}. Peer context is shown for information and not scored.`}</p>
        </Card>
        <Card title="Payment performance, support and engagement">
          <div className="space-y-4 text-[13px]">
            <div><p className="label mb-1">Payment success rate</p>
              <div className="flex items-end gap-6"><div><p className="text-[11.5px] text-mute">M1-M3 average</p><p className="num text-[22px] font-semibold">{pct(m.success_early, 1)}</p></div>
                <div><p className="text-[11.5px] text-mute">M4-M6 average</p><p className="num text-[22px] font-semibold">{pct(m.success_recent, 1)}</p></div>
                <div><p className="text-[11.5px] text-mute">Change</p><p className={clsx('num text-[22px] font-semibold', m.success_drop_pp <= -2 && 'text-bad')}>{pp(m.success_drop_pp)}</p></div></div>
              <p className="mt-1 text-[12px] text-mute">Two period aggregates only. No monthly success rate is available or inferred.</p></div>
            <div className="border-t border-line pt-3"><p className="label mb-1">Support and satisfaction</p>
              <p><span className="num font-semibold">{num(m.tickets - m.unresolved)}</span> resolved · <span className={clsx('num font-semibold', m.unresolved >= 3 && 'text-bad')}>{num(m.unresolved)}</span> unresolved · CSAT {isNum(m.csat) ? `${m.csat}/5` : <span className="text-mute">not available (unknown, not negative)</span>}</p>
              {m.tickets >= 5 && m.unresolved === 0 && m.tpv_change_pct >= 5 && <p className="mt-1 text-[12px] text-mute">High ticket volume with all tickets resolved and growing TPV is not treated as dissatisfaction.</p>}</div>
            <div className="border-t border-line pt-3"><p className="label mb-1">Engagement and adoption</p>
              <p><span className="num font-semibold">{num(m.logins)}</span> logins in 30 days · <span className="num font-semibold">{num(m.products)}</span> product(s) used</p>
              <p className="mt-1 text-[12px] text-mute">Current snapshot. Historical adoption is not in the workbook, so no change is claimed.</p></div>
            <div className="border-t border-line pt-3"><p className="label mb-1">Renewal and commercial context</p>
              <p>Renewal in <span className="num font-semibold">{num(m.renewal_days)}</span> days. {m.note_signals.length ? `Signals in note: ${m.note_signals.map((x: string) => x.replace(/_/g, ' ')).join(', ')}.` : 'No commercial signal recorded.'}</p></div>
          </div>
        </Card>
      </div>

      <Card title="Account manager note" sub="Free text from the source workbook. Treated as untrusted data.">
        {m.note ? <blockquote className="border-l-2 border-brand/40 pl-3 text-[13.5px] italic text-ink">{m.note}</blockquote> : <p className="text-[13px] text-mute">No note recorded. Ask the Account Manager for context.</p>}
        {m.note_injection_suspect && <div className="mt-3"><Notice tone="warn" title="Instruction-like text detected">This note contains wording that reads like an instruction. It was ignored by the analysis and should be reviewed.</Notice></div>}
      </Card>

      <Card title="Evidence, separated by type" sub="What was observed, what was extracted from the note, what we infer, and what we recommend. Each is labelled so a fact is never confused with an opinion.">
        <div className="grid gap-5 lg:grid-cols-2">
          <div><p className="label mb-1.5">1. Observed facts <Badge tone="ok">Observed</Badge></p>
            {a.supporting_evidence.filter((e: any) => !/note/.test(e.source_field)).length === 0 ? <p className="text-[13px] text-mute">No observed metric crosses a reporting threshold.</p> : (
              <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Fact</th><th className="th">Source and period</th><th className="th">Severity</th></tr></thead>
                <tbody>{a.supporting_evidence.filter((e: any) => !/note/.test(e.source_field)).map((e: any, k: number) => { const [sv, tone] = SEV(m.dims[SIGNAL_DIM(e.source_field)]); return (
                  <tr key={k}><td className="td align-top">{e.observed_value}</td><td className="td align-top text-[12.5px] text-mute">{e.source_field}<br />{PERIOD(e.source_field)}</td><td className="td align-top"><Badge tone={tone}>{sv}</Badge></td></tr>) })}</tbody></table></div>)}
          </div>
          <div><p className="label mb-1.5">2. Extracted from the account-manager note <Badge tone="warn">Unverified</Badge></p>
            {m.note ? (<><p className="text-[13px] italic">"{m.note}"</p>
              <p className="mt-1.5 text-[13px]">{m.note_signals.length ? m.note_signals.map((x: string) => NOTE_LABEL[x] ?? x.replace(/_/g, ' ')).join('; ') : 'No signal extracted.'}</p>
              <p className="mt-1 text-[12px] text-mute">Signals come from fixed keyword rules on free text. The note has not been verified with the account manager.</p></>) : <p className="text-[13px] text-mute">No note recorded, so nothing is extracted. This lowers evidence completeness; it does not add risk.</p>}
          </div>
          <div><p className="label mb-1.5">3. Interpretation <Badge>Inference</Badge></p>
            <ul className="list-disc space-y-1 pl-4 text-[13px]">{[...new Set(a.supporting_evidence.map((e: any) => e.interpretation))].slice(0, 5).map((x: any, k: number) => <li key={k}>{x}</li>)}{a.supporting_evidence.length === 0 && <li>{a.plain_language_reason}</li>}</ul>
            <p className="mt-1 text-[12px] text-mute">These are readings of the data, not proven causes.</p></div>
          <div><p className="label mb-1.5">4. Recommendation <Badge tone="brand">Playbook</Badge></p>
            <p className="text-[13px] font-medium">{a.primary_playbook_id} · {a.primary_playbook_name}</p><p className="mt-0.5 text-[13px]">{a.playbook_rationale}</p></div>
        </div>
        <div className="mt-4 rounded-md bg-bg px-3 py-2 text-[12.5px]"><span className="font-medium">Limitations. </span>{m.missing_fields.length ? `Missing and treated as unknown: ${m.missing_fields.join(', ')}. ` : 'No fields are missing. '}Usage fields are current snapshots; success rate has two period averages only; run-rate is an assumption-based proxy.</div>
      </Card>

      <Card title="Why is this merchant flagged?" sub="Every concern, the data behind it, how serious it is, and what limits our confidence.">
        {a.supporting_evidence.length === 0 ? <p className="text-[13.5px] text-mute">{a.plain_language_reason}</p> : (
          <div className="overflow-x-auto"><table className="w-full">
            <thead><tr><th className="th">Risk signal</th><th className="th">Supporting data</th><th className="th">Business interpretation</th><th className="th">Severity</th><th className="th">Confidence and limits</th></tr></thead>
            <tbody>{a.supporting_evidence.map((e: any, k: number) => {
              const dim = SIGNAL_DIM(e.source_field); const [sv, tone] = SEV(m.dims[dim])
              const lim = /login|product/.test(e.source_field) ? 'Snapshot only; no history' : /csat/.test(e.source_field) ? 'Single survey' : /note/.test(e.source_field) ? 'Unverified free text' : m.completeness < 100 ? 'Some fields missing' : 'Complete source data'
              return <tr key={k}><td className="td align-top font-medium">{DRIVER[dim]}</td><td className="td align-top">{e.observed_value}<span className="mt-0.5 block text-[11.5px] text-mute">{e.source_field}</span></td><td className="td align-top">{e.interpretation}</td>
                <td className="td align-top"><Badge tone={tone}>{sv}</Badge></td><td className="td align-top text-mute">{lim}</td></tr>
            })}</tbody></table></div>)}
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          {([['Mitigating signals', a.mitigating_signals], ['Contradictory signals', a.contradictory_signals], ['Alternative explanations', a.alternative_explanations]] as const).map(([t, l]) => (
            <div key={t}><p className="label mb-1.5">{t}</p>{l.length ? <ul className="list-disc space-y-1 pl-4 text-[13px]">{l.map((x: string, k: number) => <li key={k}>{x}</li>)}</ul> : <p className="text-[13px] text-mute">None identified.</p>}</div>))}
        </div>
        {m.critical_triggers.length > 0 && <div className="mt-4"><Notice tone="bad" title="Critical review triggers">{m.critical_triggers.join('; ')}</Notice></div>}
        {a.llm_used && <p className="mt-3 text-[12px] text-mute">Interpretation text refined by Claude and checked against safety rules. Scores and ranks are deterministic.</p>}
        <p className="mt-4 rounded-md bg-bg px-3 py-2 text-[13px]"><span className="font-medium">If we do not intervene. </span>{inr(m.annual_value)} of annual run-rate revenue stays exposed{m.renewal_days <= 90 ? `, with renewal in ${num(m.renewal_days)} days` : ''}. {a.primary_risk_driver !== 'No material risk signal' ? `The ${a.primary_risk_driver.toLowerCase()} remains unaddressed.` : ''} The data cannot forecast what the merchant will do.</p>
      </Card>

      {m.score_parts && (() => {
        const sp = m.score_parts
        const w: any = s.weights_pct ?? Object.fromEntries(DIM4.map((d) => [d, (s.scoring.weights[d] ?? 0) * 100]))
        const ok = Math.abs(Math.min(100, sp.uncapped_total) - m.risk_score) < 0.06
        return (
          <Card title="How the score is built" sub="Every point is traceable. The total reconciles with the dimension scores.">
            <details open>
              <summary className="cursor-pointer text-[13px] font-semibold text-navy">Dimension breakdown and formula</summary>
              <div className="overflow-x-auto"><table className="mt-2 w-full max-w-2xl"><thead><tr><th className="th">Dimension</th><th className="th text-right">Score (0-100)</th><th className="th text-right">Weight</th><th className="th text-right">Weighted points</th></tr></thead>
                <tbody>{DIM4.map((d) => <tr key={d}><td className="td">{DRIVER[d]}</td><td className="td num text-right">{m.dims[d].toFixed(1)}</td><td className="td num text-right">{w[d]}%</td><td className="td num text-right">{sp.weighted_points[d].toFixed(2)}</td></tr>)}
                  <tr><td className="td font-medium" colSpan={3}>Weighted mean</td><td className="td num text-right font-medium">{sp.weighted_mean.toFixed(2)}</td></tr></tbody></table></div>
              <p className="mt-3 text-[13px]">Total = {sp.weighted_share} x weighted mean ({sp.weighted_mean.toFixed(2)}) + {(1 - sp.weighted_share).toFixed(1)} x strongest dimension ({sp.strongest_dimension.toFixed(1)}) + convergence bonus ({sp.convergence_bonus}) = <span className="num font-semibold">{sp.uncapped_total.toFixed(1)}</span>{sp.uncapped_total > 100 ? ', capped at 100' : ''}. Shown score: <span className="num font-semibold">{m.risk_score.toFixed(1)}</span> {ok ? <Badge tone="ok">Reconciles</Badge> : <Badge tone="bad">Does not reconcile</Badge>}</p>
              <p className="mt-1 text-[12px] text-mute">Weights and thresholds are design hypotheses, not learned values. Configuration: {s.version}. Contextual adjustments (seasonal, low-touch, growth) appear in the feature table below when they apply.</p>
            </details>
            <details className="mt-3">
              <summary className="cursor-pointer text-[13px] font-semibold text-navy">Feature-level contributions ({a.score_contributions.length})</summary>
              <div className="overflow-x-auto"><table className="mt-2 w-full"><thead><tr><th className="th">Dimension</th><th className="th">Feature</th><th className="th text-right">Value</th><th className="th text-right">Points</th><th className="th">How it was derived</th></tr></thead>
                <tbody>{a.score_contributions.map((c: any, k: number) => <tr key={k}><td className="td">{DRIVER[c.dimension] ?? c.dimension}</td><td className="td">{c.feature}</td><td className="td num text-right">{c.value === null || c.value === undefined ? 'Not available' : String(c.value)}</td><td className="td num text-right">{c.points}</td><td className="td text-[12.5px] text-mute">{c.why}</td></tr>)}</tbody></table></div>
            </details>
          </Card>)
      })()}

      <Card title="Recommended intervention" action={<Badge tone="brand">{STATUS[status(m.id)]}</Badge>}>
        <div className="grid gap-5 lg:grid-cols-2">
          <div>
            <p className="label">Playbook</p>
            <p className="mt-1 text-[15px] font-semibold">{a.primary_playbook_id} · {a.primary_playbook_name}</p>
            {pb && <p className="mt-1 text-[13px] text-mute">{pb.what_happens}</p>}
            <p className="mt-3 text-[13px]"><span className="font-medium">Why selected. </span>{a.playbook_rationale}</p>
            {sec && <p className="mt-2 text-[12.5px] text-mute">Secondary: {sec.playbook_id} {sec.name}. Coordinate as one CSM interaction with internal specialists.</p>}
            <p className="label mt-4">Suggested next steps (from playbook)</p>
            <ul className="mt-1 list-disc space-y-1 pl-4 text-[13px]">{(NEXT[a.primary_playbook_id] ?? []).map((x) => <li key={x}>{x}</li>)}</ul>
            <p className="label mt-4">Verify before contacting</p>
            {a.additional_checks_for_csm.length ? <ul className="mt-1 list-disc space-y-1 pl-4 text-[13px]">{a.additional_checks_for_csm.map((x: string, k: number) => <li key={k}>{x}</li>)}</ul> : <p className="mt-1 text-[13px] text-mute">No additional checks beyond the standard review.</p>}
            {a.llm_notes?.length > 0 && <div className="mt-3 space-y-1">{a.llm_notes.map((n: string, k: number) => <p key={k} className="text-[12px] text-mute">{n}</p>)}</div>}
          </div>
          <div>
            <DraftWorkflow m={m} key={m.id} />
          </div>
        </div>
      </Card>
    </div>
  )
}
