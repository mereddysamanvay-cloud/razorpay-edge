/* eslint-disable @typescript-eslint/no-explicit-any */
import clsx from 'clsx'
import { ArrowDown, Check, ChevronRight, HelpCircle } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge, Card, Notice, PageHeader, Tabs } from '../components/ui'
import { api, type Dict } from '../lib/api'
import { DRIVER, inr } from '../lib/format'
import { useSession } from '../lib/session'

const DIM_LABEL: Record<string, string> = { performance: 'Performance', relationship: 'Relationship', engagement: 'Engagement', commercial: 'Commercial' }
const Formula = ({ children }: { children: React.ReactNode }) => <div className="overflow-x-auto rounded-md bg-bg px-3 py-2 font-mono text-[13px] leading-relaxed text-navy">{children}</div>

/* ------------------------------------------------------------------ 1. flow */
function Flow({ d, go }: { d: Dict; go: (t: string) => void }) {
  const [open, setOpen] = useState<string>(d.architecture[0].id)
  const st = d.architecture.find((a: Dict) => a.id === open)
  const Q: [string, string, string][] = [['What does EDGE analyse?', 'data', 'Data and features'], ['How is raw data turned into signals?', 'data', 'Data and features'], ['How is risk calculated?', 'math', 'The mathematics'],
    ['How are merchants prioritised?', 'math', 'The mathematics'], ['How is the playbook chosen?', 'tree', 'Decision tree']]
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2" aria-label="The five questions this page answers">{Q.map(([q, t]) => <button key={q} className="btn-secondary !py-1 text-[12.5px]" onClick={() => go(t)}>{q}</button>)}</div>
      <div className="grid items-start gap-5 lg:grid-cols-[320px_1fr]">
        <ol className="space-y-0" aria-label="EDGE decision pipeline">{d.architecture.map((a: Dict, i: number) => (
          <li key={a.id}>
            <button onClick={() => setOpen(a.id)} aria-current={open === a.id} className={clsx('flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors', open === a.id ? 'border-brand bg-brand-soft' : 'border-line bg-white hover:border-brand/50')}>
              <span className={clsx('num flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11.5px] font-semibold', open === a.id ? 'bg-brand text-white' : 'bg-slate-100 text-mute')}>{i + 1}</span>
              <span className="text-[13px] font-semibold leading-tight text-navy">{a.title}</span>
              <ChevronRight size={14} className="ml-auto shrink-0 text-mute" aria-hidden />
            </button>
            {i < d.architecture.length - 1 && <div className="flex justify-center py-0.5 text-mute" aria-hidden><ArrowDown size={14} /></div>}
          </li>))}</ol>
        <Card title={st.title} sub="Select any stage on the left. This is generated from the live configuration.">
          <dl className="space-y-3 text-[13px]">
            <div><dt className="label">What happens</dt><dd className="mt-0.5">{st.what}</dd></div>
            <div><dt className="label">Data fields used</dt><dd className="mt-1 flex flex-wrap gap-1.5">{st.fields.map((f: string) => <Badge key={f}>{f}</Badge>)}</dd></div>
            <div><dt className="label">Calculation or rule applied</dt><dd className="mt-1"><Formula>{st.rule}</Formula></dd></div>
            <div><dt className="label">Why this step is needed</dt><dd className="mt-0.5">{st.why}</dd></div>
            <div><dt className="label">Output passed on</dt><dd className="mt-0.5 font-medium text-navy">{st.output}</dd></div>
          </dl>
        </Card>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ 2. data and features */
function Data({ d }: { d: Dict }) {
  const v = d.validation
  return (
    <div className="space-y-5">
      <Card title="Checks before any analysis" sub="Every upload goes through these. Problems are shown to you, never hidden.">
        <table className="w-full"><tbody>{v.checks.map((c: Dict) => <tr key={c.check}><td className="td w-72 align-top font-medium">{c.check}</td><td className="td text-[12.5px]">{c.action}</td></tr>)}</tbody></table>
      </Card>
      <Card title="Missing is unknown, not negative" sub="Why missing information never raises a merchant's risk score.">
        <div className="grid gap-3 md:grid-cols-3">{v.unknown_examples.map((e: Dict) => (
          <div key={e.claim} className="rounded-md border border-line p-3"><p className="text-[13.5px] font-semibold text-navy">{e.claim}</p><p className="mt-1 text-[12.5px] text-mute">{e.detail}</p></div>))}</div>
        <p className="mt-3 text-[12.5px] text-mute">{v.confidence_rule}</p>
      </Card>
      <div className="space-y-3">
        <h2 className="h-sec">Four dimensions, built from source fields</h2>
        {d.features.map((dim: Dict) => (
          <details key={dim.dimension} className="card" open={dim.dimension === 'performance'}>
            <summary className="cursor-pointer px-4 py-3 text-[14px] font-semibold text-navy">{dim.name} <span className="ml-2 text-[12px] font-normal text-mute">weight {d.weights[dim.dimension] * 100}%</span></summary>
            <div className="overflow-x-auto border-t border-line"><table className="w-full"><thead><tr><th className="th">Feature</th><th className="th">Source field</th><th className="th">Calculation</th><th className="th">Effect on risk</th><th className="th">Limitation</th></tr></thead>
              <tbody>{dim.features.map((f: Dict) => <tr key={f.feature}><td className="td align-top font-medium">{f.feature}</td><td className="td align-top text-[12px] text-mute">{f.source}</td><td className="td align-top text-[12.5px]">{f.calc}</td><td className="td align-top text-[12.5px]">{f.direction}</td><td className="td align-top text-[12.5px] text-mute">{f.limit}</td></tr>)}</tbody></table></div>
          </details>))}
        <Notice tone="info" title="Two limits of the source data">The workbook gives only two payment success-rate averages (M1-M3 and M4-M6), so no monthly success-rate trend is shown or inferred. Logins and products used are current snapshots, so no adoption or engagement trend over time is claimed.</Notice>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ 3. mathematics */
function Maths({ d }: { d: Dict }) {
  const w = d.worked.score
  const p = d.worked.priority
  const r = d.worked.revenue
  const pct = (x: number) => Math.round(x * 100)
  return (
    <div className="space-y-5">
      <Card title="The weights in force" sub={`Read from the scoring configuration (version ${d.generated_from.scoring_version}). They are manager-designed heuristic weights, not statistically trained coefficients.`}>
        <div className="flex h-9 overflow-hidden rounded-md border border-line" role="img" aria-label="Dimension weights">{Object.entries(d.weights).map(([k, v]: [string, any], i) => (
          <div key={k} className={clsx('flex items-center justify-center text-[12px] font-semibold text-white', ['bg-brand', 'bg-navy', 'bg-slate-500', 'bg-brand-dark'][i % 4])} style={{ width: `${pct(v)}%` }}>{pct(v)}%</div>))}</div>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px]">{Object.entries(d.weights).map(([k, v]: [string, any], i) => <span key={k} className="flex items-center gap-1.5"><span className={clsx('h-2.5 w-2.5 rounded-sm', ['bg-brand', 'bg-navy', 'bg-slate-500', 'bg-brand-dark'][i % 4])} aria-hidden />{DIM_LABEL[k]} {pct(v)}%</span>)}</div>
        <p className="mt-2 text-[12.5px] text-mute">Total {pct(d.weights_sum)}%. A weighted additive model: each dimension's contribution is visible, can be challenged, and can be tested in Decision Studio.</p>
      </Card>

      <Card title="The Mathematics Behind EDGE" sub="Every formula below is the one the engine runs. Open a step for the plain-language reading.">
        <div className="space-y-2">{d.equations.map((e: Dict, i: number) => (
          <details key={e.key} className="rounded-md border border-line" open={i < 3}>
            <summary className="flex cursor-pointer flex-wrap items-center gap-2 px-3 py-2.5 text-[13.5px] font-semibold text-navy">{e.title}<Badge className="ml-auto">{e.kind}</Badge></summary>
            <div className="space-y-2 border-t border-line px-3 py-3"><Formula>{e.formula}</Formula><p className="text-[13px]">{e.plain}</p></div>
          </details>))}</div>
      </Card>

      {w && (
        <Card title={`Worked example: ${w.merchant.name} (${w.merchant.id})`} sub="Real values from this analysis. Open the merchant to see the same numbers in its score breakdown.">
          <div className="overflow-x-auto"><table className="w-full max-w-2xl"><thead><tr><th className="th">Dimension</th><th className="th text-right">Score S</th><th className="th text-right">Weight w</th><th className="th text-right">S × w</th></tr></thead>
            <tbody>{Object.keys(d.weights).map((k) => <tr key={k}><td className="td">{DIM_LABEL[k]}</td><td className="td num text-right">{w.dims[k].toFixed(1)}</td><td className="td num text-right">{d.weights[k]}</td><td className="td num text-right">{w.weighted_points[k].toFixed(2)}</td></tr>)}
              <tr><td className="td font-medium" colSpan={3}>Weighted mean (WM)</td><td className="td num text-right font-medium">{w.weighted_mean.toFixed(2)}</td></tr></tbody></table></div>
          <Formula>Score = {w.share} × {w.weighted_mean.toFixed(2)} + {(1 - w.share).toFixed(1)} × {w.strongest.toFixed(2)} + bonus {w.bonus} = {(w.share * w.weighted_mean + (1 - w.share) * w.strongest + w.bonus).toFixed(1)}  →  {w.band}</Formula>
          <p className="mt-2 text-[12.5px] text-mute">The strongest-dimension term keeps one severe signal from being diluted by healthy dimensions. It is a fixed {Math.round((1 - w.share) * 100)}% share of the formula, not a cap, and the convergence bonus is separate (maximum {d.aggregation.convergence_cap}). Both are heuristics and have not been statistically validated.</p>
        </Card>)}

      <Card title="Risk bands" sub="Rule-based categories. They are not probabilities of churn.">
        <div className="relative h-10 overflow-hidden rounded-md border border-line text-[12px] font-semibold" role="img" aria-label="Risk band scale">
          <div className="absolute inset-y-0 left-0 flex items-center justify-center bg-emerald-50 text-ok" style={{ width: `${d.bands.medium}%` }}>LOW RISK  0 to {d.bands.medium - 0.1}</div>
          <div className="absolute inset-y-0 flex items-center justify-center bg-amber-50 text-warn" style={{ left: `${d.bands.medium}%`, width: `${d.bands.high - d.bands.medium}%` }}>MODERATE  {d.bands.medium} to {d.bands.high - 0.1}</div>
          <div className="absolute inset-y-0 right-0 flex items-center justify-center bg-red-50 text-bad" style={{ left: `${d.bands.high}%` }}>HIGH  {d.bands.high}+</div>
        </div>
        <p className="mt-2 text-[12.5px] text-mute">EDGE never shows a "% probability of churn". That would need a model trained and calibrated on verified outcomes, which do not exist in this data.</p>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        {r && (
          <Card title="Revenue exposure" sub={`Worked example: ${r.merchant.name}`} className="min-w-0">
            <Formula>Run-rate = {r.m6_tpv_lakh} lakh × {r.rate} × {r.months} = Rs {r.annual_lakh} lakh a year</Formula>
            <div className="overflow-x-auto"><table className="mt-3 w-full text-[13px]"><tbody>{[['Current TPV', 'The latest month processed (M6), Rs lakh'], ['Annual net-revenue run-rate', 'M6 TPV × net revenue rate × 12. A size measure'], ['Revenue exposure', 'Run-rate of Moderate and High merchants: revenue at stake'],
              ['Revenue actually lost', 'Not available. The workbook has no churn outcomes'], ['Revenue potentially retained', 'Not estimated. The 12-month saved-merchant value is a valuation assumption, not an observed or guaranteed result']].map(([a, b]) => <tr key={a}><td className="td w-44 font-medium">{a}</td><td className="td text-[12.5px]">{b}</td></tr>)}</tbody></table></div>
          </Card>)}
        {p && (
          <Card title="Risk is not priority" sub="Who is riskiest is a different question from who to contact first." className="min-w-0">
            <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Merchant</th><th className="th text-right">Risk</th><th className="th text-right">Run-rate</th><th className="th text-right">Index</th><th className="th text-right">Rank</th></tr></thead>
              <tbody>{[p.higher_priority, p.higher_risk].map((m: Dict) => <tr key={m.id}><td className="td"><span className="font-medium">{m.name}</span><br /><span className="text-[11.5px] text-mute">{m.segment} · {m.band}</span></td><td className="td num text-right">{m.score}</td><td className="td num text-right">{inr(m.annual_inr)}</td><td className="td num text-right">{inr(m.index)}</td><td className="td num text-right">#{m.rank ?? '–'}</td></tr>)}</tbody></table></div>
            <Formula>Index = (w_r × run-rate − (1 − w_r) × Rs {p.cost}) × urgency</Formula>
            <p className="mt-2 text-[12.5px] text-mute">{p.higher_priority.name} ({p.higher_priority.band.toLowerCase()}, {p.higher_priority.segment}) ranks above {p.higher_risk.name} ({p.higher_risk.band.toLowerCase()}, {p.higher_risk.segment}) because its run-rate is far larger and its renewal is closer. The index is a ranking aid in rupees. It is not an expected-value forecast: w_r is not a probability.</p>
          </Card>)}
      </div>

      <Card title="Mathematical methods glossary" sub="Only methods the code actually uses." pad={false}>
        <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Method</th><th className="th">What it means</th><th className="th">Where EDGE uses it</th><th className="th">Why it suits this problem</th><th className="th">Limitation</th></tr></thead>
          <tbody>{d.glossary.map((g: Dict) => <tr key={g.method}><td className="td align-top font-medium">{g.method}</td><td className="td align-top text-[12.5px]">{g.meaning}</td><td className="td align-top text-[12.5px]">{g.where}</td><td className="td align-top text-[12.5px]">{g.why}</td><td className="td align-top text-[12.5px] text-mute">{g.limit}</td></tr>)}</tbody></table></div>
        <p className="border-t border-line px-4 py-3 text-[12px] text-mute">Not used anywhere in EDGE: {d.not_used.join(', ').toLowerCase()}.</p>
      </Card>
    </div>
  )
}

/* ------------------------------------------------------------------ 4. decision tree */
function Node({ n, sel, onPick }: { n: Dict; sel: string; onPick: (id: string) => void }) {
  const kind = n.type
  return (
    <button onClick={() => onPick(n.id)} aria-pressed={sel === n.id}
      className={clsx('w-full rounded-lg border px-3 py-2 text-left text-[12.5px] leading-snug transition-colors', sel === n.id ? 'border-brand bg-brand-soft ring-2 ring-brand/20' : 'bg-white hover:border-brand/50', kind === 'outcome' ? 'border-emerald-300' : kind === 'start' ? 'border-navy' : 'border-line')}>
      <span className="flex items-start gap-1.5">{kind === 'decision' && <HelpCircle size={14} className="mt-0.5 shrink-0 text-brand" aria-hidden />}{kind === 'outcome' && <Check size={14} className="mt-0.5 shrink-0 text-ok" aria-hidden />}<span className="font-semibold text-navy">{n.title}</span></span>
    </button>
  )
}
const Down = ({ label }: { label?: string }) => <div className="flex flex-col items-center py-1 text-mute" aria-hidden><ArrowDown size={14} />{label && <span className="text-[10.5px] font-medium">{label}</span>}</div>

function Tree({ d }: { d: Dict }) {
  const { sid } = useSession()
  const [sel, setSel] = useState('n0')
  const detail = useRef<HTMLDivElement>(null)
  const pick = (id: string) => { setSel(id); setTimeout(() => detail.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 60) }
  const by: Dict = Object.fromEntries(d.tree.map((n: Dict) => [n.id, n]))
  const n = by[sel]
  const P = (id: string) => <Node n={by[id]} sel={sel} onPick={pick} />
  return (
    <div className="space-y-5">
      <Notice tone="info" title="How EDGE Decides What to Do">This is the real playbook-selection logic, drawn from the engine's rules, not a fixed top-to-bottom order. Several playbooks can trigger at once; the one that fits the strongest evidence wins. Select any step to see its condition, the threshold, a real merchant and the result.</Notice>
      <div className="space-y-5">
        <Card title="Decision path" sub="Select any box. The details open directly below.">
          <div className="space-y-0">
            {P('n0')}<Down />{P('n1')}<Down />{P('n2')}
            <div className="grid gap-3 pt-1 md:grid-cols-2">
              <div className="rounded-lg border border-dashed border-line p-2"><p className="mb-1 text-center text-[11px] font-semibold text-ok">YES: Low band</p>{P('n3')}<div className="grid grid-cols-2 gap-2 pt-1"><div><Down label="Yes" />{P('o5')}</div><div><Down label="No" />{P('o6')}</div></div></div>
              <div className="rounded-lg border border-dashed border-line p-2"><p className="mb-1 text-center text-[11px] font-semibold text-bad">NO: Moderate or High</p>{P('n4')}<div className="grid grid-cols-2 gap-2 pt-1"><div><Down label="One or more fire" />{P('n5')}<Down />{P('o1')}<Down />{P('n6')}<div className="grid grid-cols-2 gap-2 pt-1"><div><Down label="Yes" />{P('o7')}</div><div><Down label="No" />{P('o8')}</div></div></div><div><Down label="None fire" /><div className="text-[11px] text-mute">→ PB-6 Monitor only</div></div></div></div>
            </div>
          </div>
        </Card>
        <div ref={detail} className="scroll-mt-2">
          <Card title={n.title} sub={n.type === 'decision' ? 'Decision step' : n.type === 'outcome' ? 'Result' : 'Starting point'}>
            <dl className="grid gap-x-8 gap-y-3 text-[13px] md:grid-cols-2">
              {n.question && <div><dt className="label">Question</dt><dd className="mt-0.5">{n.question}</dd></div>}
              <div className="md:col-span-2"><dt className="label">Condition and thresholds</dt><dd className="mt-1"><Formula>{n.condition}</Formula></dd></div>
              {n.yes_label && <div><dt className="label">If yes</dt><dd className="mt-0.5">{n.yes_label}</dd></div>}
              {n.no_label && <div><dt className="label">If no</dt><dd className="mt-0.5">{n.no_label}</dd></div>}
              {n.result && <div><dt className="label">Result</dt><dd className="mt-0.5 font-semibold text-navy">{n.result}</dd></div>}
              <div><dt className="label">Why</dt><dd className="mt-0.5 text-mute">{n.reason}</dd></div>
              {n.data && <div><dt className="label">Data used</dt><dd className="mt-0.5 text-[12px] text-mute">{n.data}</dd></div>}
              <div className="md:col-span-2"><dt className="label">Example from this analysis</dt>
                <dd className="mt-0.5">{n.example ? <span><Link className="font-medium text-brand-dark hover:underline" to={`/a/${sid}/merchant/${n.example.id}`}>{n.example.name}</Link> <span className="text-mute">({n.example.id}, {n.example.segment}, {n.example.risk.toLowerCase()}, score {n.example.score}) → {n.example.playbook}</span>{n.example.why && <span className="mt-0.5 block text-[12px] text-mute">{n.example.why}</span>}</span> : <span className="text-mute">No merchant in this workbook reaches this step.</span>}</dd></div>
            </dl>
          </Card>
        </div>
      </div>
      <Card title="Why six playbooks exist" sub="Each addresses a different kind of business concern. The text is the workbook's; EDGE adds nothing." pad={false}>
        <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Playbook</th><th className="th">Concern it addresses</th><th className="th">What happens (workbook)</th><th className="th">Rule EDGE uses</th><th className="th">Slot</th></tr></thead>
          <tbody>{d.playbooks.map((p: Dict) => <tr key={p.id}><td className="td align-top font-medium">{p.id}<br />{p.name}</td><td className="td align-top text-[12.5px]">{p.concern}</td><td className="td align-top text-[12.5px]">{p.what_happens}</td><td className="td align-top text-[12.5px] text-mute">{p.rule}</td><td className="td align-top">{p.uses_slot ? <Badge tone="brand">Uses a slot</Badge> : <Badge>No outreach</Badge>}</td></tr>)}</tbody></table></div>
      </Card>
    </div>
  )
}

/* ------------------------------------------------------------------ 5. robustness */
function Robust({ d }: { d: Dict }) {
  const { sid, byId } = useSession()
  const [x, setX] = useState<Dict | null>(null)
  const [loaded, setLoaded] = useState(false)
  useEffect(() => { api.stability(sid).then((r) => setX(r.ready ? r : null)).catch(() => setX(null)).finally(() => setLoaded(true)) }, [sid])
  const name = (id: string) => byId[id]?.name ?? id
  return (
    <div className="space-y-5">
      <Notice tone="info" title="Why the weights can be changed">{d.sensitivity_note}</Notice>
      {!loaded ? <p className="text-[13px] text-mute">Loading…</p> : !x ? (
        <Card title="No robustness test yet" sub="Re-scoring all merchants under 305 reproducible configurations takes about 30 seconds."><Link className="btn-primary" to={`/a/${sid}/studio?tab=robust`}>Run it in Decision Studio</Link></Card>
      ) : (<>
        <Card title="Scenarios against the baseline" sub="The shortlist under each weight set. Test scenarios, not recommended weights." pad={false}>
          <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Scenario</th><th className="th">Weights P/R/E/C %</th><th className="th min-w-[170px]">Top-15 overlap</th><th className="th">Entering</th><th className="th">Leaving</th><th className="th text-right">Avg rank movement</th><th className="th text-right">Largest move</th><th className="th" /></tr></thead>
            <tbody>{x.scenarios.map((s: Dict) => (
              <tr key={s.scenario}><td className="td font-medium">{s.scenario}</td><td className="td num text-[12.5px]">{Object.values(s.weights).join('/')}</td>
                <td className="td"><span className="flex items-center gap-2"><span className="h-2 w-24 rounded bg-slate-100"><span className="block h-full rounded bg-brand" style={{ width: `${(s.overlap_with_baseline / Math.max(s.top_n.length, 1)) * 100}%` }} /></span><span className="num text-[12.5px]">{s.overlap_with_baseline} of {s.top_n.length}</span></span></td>
                <td className="td text-[12.5px]">{s.moved_in.map(name).join(', ') || 'None'}</td><td className="td text-[12.5px]">{s.moved_out.map(name).join(', ') || 'None'}</td>
                <td className="td num text-right">{s.avg_rank_movement ?? '–'}</td><td className="td num text-right">{s.max_rank_movement ?? '–'}</td>
                <td className="td">{s.scenario !== 'Baseline' && <Link className="btn-secondary !py-0.5 text-[12px]" to={`/a/${sid}/studio?preset=${encodeURIComponent(s.scenario)}`}>Open in Decision Studio</Link>}</td></tr>))}</tbody></table></div>
        </Card>
        <div className="grid gap-5 md:grid-cols-3">
          <Card title="Stable priorities" sub={`In the shortlist in ${Math.round(x.robust_at * 100)}%+ of ${x.configurations} configurations`}><ul className="space-y-0.5 text-[13px]">{x.merchants.filter((m: Dict) => m.classification === 'Robust priority').map((m: Dict) => <li key={m.merchant_id}>{m.name} <span className="num text-mute">{Math.round(m.selection_frequency * 100)}%</span></li>)}</ul></Card>
          <Card title="Sensitive to assumptions" sub="In the shortlist only for some weight sets"><ul className="space-y-0.5 text-[13px]">{x.merchants.filter((m: Dict) => m.classification === 'Weight-sensitive').map((m: Dict) => <li key={m.merchant_id}>{m.name} <span className="num text-mute">{Math.round(m.selection_frequency * 100)}%</span></li>)}</ul></Card>
          <Card title="Reading this" sub="Ranking robustness, not accuracy"><p className="text-[12.5px] text-mute">Stability is partly a property of the value-weighted selection rule: only {x.counts['Robust priority'] + x.counts['Weight-sensitive']} merchants ever reach the shortlist. A stable list means the decision does not depend on the weights; it does not mean the weights are right.</p>
            <Link className="mt-2 inline-block text-[12.5px] font-medium text-brand-dark hover:underline" to={`/a/${sid}/studio?tab=robust`}>Full results and exports</Link></Card>
        </div>
      </>)}
    </div>
  )
}

/* ------------------------------------------------------------------ 6. human */
function Human({ d }: { d: Dict }) {
  const h = d.human
  return (
    <div className="space-y-5">
      <Card title="Where human judgement sits">
        <ol className="grid gap-2 md:grid-cols-3 lg:grid-cols-6">{h.steps.map((s: string, i: number) => (
          <li key={s} className="rounded-md border border-line p-3 text-[12.5px]"><span className="num mb-1 flex h-5 w-5 items-center justify-center rounded-full bg-brand text-[11px] font-semibold text-white">{i + 1}</span>{s}</li>))}</ol>
      </Card>
      <Notice tone="warn" title="What EDGE is, and is not">{h.statement}</Notice>
      <Card title="Context that prevents false alarms" sub="These patterns look risky in the raw numbers but are normal. The counts are from this analysis.">
        <div className="grid gap-3 md:grid-cols-3">{h.context_factors.map((c: Dict) => (
          <div key={c.name} className="rounded-md border border-line p-3"><p className="text-[13.5px] font-semibold text-navy">{c.name}</p><p className="num mt-0.5 text-[20px] font-semibold">{c.count}</p><p className="mt-1 text-[12.5px] text-mute">{c.detail}</p></div>))}</div>
      </Card>
    </div>
  )
}

const TABS = [{ id: 'flow', label: 'How EDGE works' }, { id: 'data', label: 'Data and features' }, { id: 'math', label: 'The mathematics' }, { id: 'tree', label: 'Decision tree' }, { id: 'robust', label: 'Robustness' }, { id: 'human', label: 'Human validation' }]

export default function DecisionIntelligence() {
  const { sid } = useSession()
  const [d, setD] = useState<Dict | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [tab, setTab] = useState('flow')
  useEffect(() => { api.intelligence(sid).then(setD).catch((e) => setErr(e.message)) }, [sid])
  if (err) return <Notice tone="bad">{err}</Notice>
  if (!d) return <p className="text-[13px] text-mute">Loading…</p>
  return (
    <div className="space-y-5">
      <PageHeader title="Decision Intelligence" sub="Understand how EDGE interprets merchant signals, calculates risk and recommends action." />
      <p className="-mt-3 text-[12px] text-mute">Generated from scoring version {d.generated_from.scoring_version}{d.generated_from.analysis ? ` and the analysis "${d.generated_from.analysis}"` : ''}. A rule-based decision-support method; there is no machine-learning model and no churn probability. Dimension names: {Object.values(DRIVER).join(', ')}.</p>
      <Tabs value={tab} onChange={setTab} tabs={TABS} />
      {tab === 'flow' && <Flow d={d} go={setTab} />}
      {tab === 'data' && <Data d={d} />}
      {tab === 'math' && <Maths d={d} />}
      {tab === 'tree' && <Tree d={d} />}
      {tab === 'robust' && <Robust d={d} />}
      {tab === 'human' && <Human d={d} />}
    </div>
  )
}
