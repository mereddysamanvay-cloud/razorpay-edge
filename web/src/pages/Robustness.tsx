/* eslint-disable @typescript-eslint/no-explicit-any */
import { Download, Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge, Card, Notice, Select } from '../components/ui'
import { api, type Dict } from '../lib/api'
import { inr, pct } from '../lib/format'
import { waitForJob } from '../lib/poll'
import { useSession } from '../lib/session'

const CLS_TONE: Record<string, 'ok' | 'warn' | 'neutral'> = { 'Robust priority': 'ok', 'Weight-sensitive': 'warn', 'Low priority': 'neutral' }
const W = (w: Dict) => `${w.performance}/${w.relationship}/${w.engagement}/${w.commercial}`

export default function Robustness() {
  const { sid } = useSession()
  const [d, setD] = useState<Dict | null>(null)
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState(0)
  const [err, setErr] = useState<string | null>(null)
  const [filter, setFilter] = useState('all')
  const [loaded, setLoaded] = useState(false)
  const load = () => api.stability(sid).then((x) => setD(x.ready ? x : null)).catch((e) => setErr(e.message)).finally(() => setLoaded(true))
  useEffect(() => { load() }, [sid]) // eslint-disable-line react-hooks/exhaustive-deps

  async function run() {
    setBusy(true); setErr(null); setProgress(0.02)
    try { const { job_id } = await api.runStability(sid, 300); await waitForJob(job_id, (j) => setProgress(j.progress ?? 0)); await load() }
    catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  const rows: Dict[] = (d?.merchants ?? []).filter((r: Dict) => (filter === 'all' ? r.times_selected > 0 || r.baseline_selected : r.classification === filter))
  const runLabel = busy ? <><Loader2 size={14} className="animate-spin" /> Testing {Math.round(progress * 100)}%</> : null
  return (
    <div className="space-y-5">
      <Notice tone="info" title="What this measures">How stable the shortlist is when the design hypotheses change: dimension weights between {d?.weight_bounds_pct?.[0] ?? 10}% and {d?.weight_bounds_pct?.[1] ?? 50}% and the feature scales. It is ranking robustness, not prediction accuracy; no churn labels exist.</Notice>
      {err && <Notice tone="bad">{err}</Notice>}
      {!loaded ? <p className="text-[13px] text-mute">Loading…</p> : !d ? (
        <Card title="Run the robustness test" sub="Re-scores all merchants under the five test scenarios and 300 reproducible configurations (fixed seed). Takes about 30 seconds.">
          <button className="btn-primary" onClick={run} disabled={busy}>{runLabel ?? 'Run robustness test'}</button>
        </Card>
      ) : (<>
        <div className="grid gap-3 md:grid-cols-4">
          {[['Configurations tested', d.configurations, `${d.grid_size} sampled + 5 test scenarios, seed ${d.seed}`], ['Robust priority', d.counts['Robust priority'], `in the shortlist in ${pct(d.robust_at * 100, 0)} or more of configurations`],
            ['Weight-sensitive', d.counts['Weight-sensitive'], 'in the shortlist for some configurations only'], ['Low priority', d.counts['Low priority'], `${pct(d.low_at * 100, 0)} or fewer, and not in the baseline shortlist`]].map(([l, v, sub]) => (
            <div key={l as string} className="card p-4"><p className="label">{l}</p><p className="num mt-1.5 text-[26px] font-semibold">{v}</p><p className="mt-1 text-[12px] text-mute">{sub}</p></div>))}
        </div>

        <Card title="Test scenarios against the baseline" sub="Same workbook, different weights. These are test scenarios, not recommended final weights. Weights are Performance / Relationship / Engagement / Commercial, in percent." pad={false}
          action={<div className="flex gap-2"><a className="btn-secondary" href={api.exportUrl(sid, 'weight_scenarios', 'csv')}><Download size={13} /> Scenarios CSV</a><a className="btn-secondary" href={api.exportUrl(sid, 'overlap', 'csv')}><Download size={13} /> Overlap CSV</a></div>}>
          <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Scenario</th><th className="th">Weights %</th><th className="th text-right">High</th><th className="th text-right">Moderate</th><th className="th text-right">Overlap with baseline</th><th className="th">Moved in</th><th className="th">Moved out</th><th className="th text-right">Run-rate represented</th><th className="th text-right">Seasonal</th><th className="th text-right">Incomplete evidence</th></tr></thead>
            <tbody>{d.scenarios.map((x: Dict) => (
              <tr key={x.scenario}><td className="td font-medium">{x.scenario}</td><td className="td num">{W(x.weights)}</td><td className="td num text-right">{x.high}</td><td className="td num text-right">{x.medium}</td>
                <td className="td num text-right">{x.overlap_with_baseline} of {x.top_n.length}</td><td className="td text-[12.5px]">{x.moved_in.join(', ') || 'None'}</td><td className="td text-[12.5px]">{x.moved_out.join(', ') || 'None'}</td>
                <td className="td num text-right">{inr(x.run_rate_inr)}</td><td className="td num text-right">{x.seasonal_selected}</td><td className="td num text-right">{x.incomplete_selected}</td></tr>))}</tbody></table></div>
        </Card>

        <Card title="Shortlist overlap between scenarios" sub="Merchants shared by each pair of top lists.">
          <table className="w-full max-w-2xl"><thead><tr><th className="th" />{Object.keys(d.overlap_matrix).map((k) => <th key={k} className="th text-right">{k}</th>)}</tr></thead>
            <tbody>{Object.entries(d.overlap_matrix).map(([a, row]: [string, any]) => <tr key={a}><td className="td font-medium">{a}</td>{Object.keys(row).map((b) => <td key={b} className="td num text-right">{row[b]}</td>)}</tr>)}</tbody></table>
        </Card>

        <Card title="Merchant stability" sub="How often each merchant makes the shortlist across all configurations, and how far its rank moves." pad={false}
          action={<div className="flex items-center gap-2"><Select value={filter} onChange={setFilter} className="w-48" options={[{ value: 'all', label: 'Ever shortlisted' }, { value: 'Robust priority', label: 'Robust priority' }, { value: 'Weight-sensitive', label: 'Weight-sensitive' }, { value: 'Low priority', label: 'Low priority' }]} />
            <a className="btn-secondary" href={api.exportUrl(sid, 'stability', 'csv')}><Download size={13} /> CSV</a></div>}>
          <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Merchant</th><th className="th">Classification</th><th className="th text-right">In shortlist</th><th className="th text-right">Average rank</th><th className="th text-right">Best to worst</th><th className="th text-right">Score range</th><th className="th">Categories seen</th><th className="th">Moved materially by</th></tr></thead>
            <tbody>{rows.map((r: Dict) => (
              <tr key={r.merchant_id}><td className="td"><Link to={`/a/${sid}/merchant/${r.merchant_id}`} className="font-medium hover:text-brand">{r.name}</Link><span className="ml-1.5 text-[12px] text-mute">{r.merchant_id}</span></td>
                <td className="td"><Badge tone={CLS_TONE[r.classification]}>{r.classification}</Badge></td><td className="td num text-right">{r.times_selected} of {r.configurations} ({pct(r.selection_frequency * 100, 0)})</td>
                <td className="td num text-right">{r.avg_rank ?? 'Not eligible'}</td><td className="td num text-right">{r.best_rank ? `${r.best_rank} to ${r.worst_rank}` : 'Not eligible'}</td><td className="td num text-right">{r.score_min} to {r.score_max}</td>
                <td className="td text-[12.5px]">{r.bands_seen.join(', ')}</td><td className="td text-[12.5px] text-mute">{r.moved_by.join('; ') || 'None'}</td></tr>))}</tbody></table></div>
        </Card>
        <div className="flex items-center gap-3"><button className="btn-secondary" onClick={run} disabled={busy}>{runLabel ?? 'Run again'}</button>
          <span className="text-[12px] text-mute">Reproducible: the same analysis and seed always give the same numbers. Parameter ranges: {Object.entries(d.param_bounds).map(([k, v]: [string, any]) => `${k} ${v[0]} to ${v[1]}`).join('; ')}.</span></div>
      </>)}
    </div>
  )
}
