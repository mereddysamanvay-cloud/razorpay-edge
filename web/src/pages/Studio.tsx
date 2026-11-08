/* eslint-disable @typescript-eslint/no-explicit-any */
import clsx from 'clsx'
import { ArrowDownRight, ArrowUpRight, Save, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ScenarioBars } from '../components/charts'
import { Badge, Card, Empty, Notice, PageHeader, Select, Tip } from '../components/ui'
import { api, type Dict } from '../lib/api'
import { DRIVER, FOCUS, PRIORITY, PRIORITY_RULE, inr } from '../lib/format'
import { useSession } from '../lib/session'

const PRESETS: { name: string; spec: Dict }[] = [
  { name: 'A: Prioritise enterprise merchants', spec: { prefer_segments: ['Enterprise'] } },
  { name: 'B: Prioritise upcoming renewals', spec: { priorities: ['renewals'], risk_focus: 'renewal' } },
  { name: 'C: Prioritise payment-performance deterioration', spec: { priorities: ['payment_performance'], risk_focus: 'severity' } },
  { name: 'D: Prioritise unresolved service issues', spec: { priorities: ['service'], risk_focus: 'dissatisfaction' } },
]

export default function Studio() {
  const { sid, s, merchants, byId, st, patch, setSession, reload } = useSession()
  const cur = s.scenario
  const [spec, setSpec] = useState<Dict>(() => ({
    capacity: cur.capacity, priorities: [...(cur.priorities ?? [])], risk_focus: cur.risk_focus ?? 'revenue', segments: [...(cur.segments ?? [])],
    prefer_segments: [...(cur.prefer_segments ?? [])], exclude_industries: [...(cur.exclude_industries ?? [])], renewal_window: cur.renewal_window ?? null,
    include_ids: [...new Set([...(cur.include_ids ?? []), ...(st.marked ?? [])])], exclude_ids: Object.keys(st.exclusions ?? {}), exclude_reasons: { ...(st.exclusions ?? {}) },
  }))
  const [res, setRes] = useState<Dict | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [addInc, setAddInc] = useState('')
  const [addExc, setAddExc] = useState('')
  const seq = useRef(0)

  useEffect(() => {
    const n = ++seq.current
    setBusy(true)
    const t = setTimeout(async () => {
      try { const r = await api.scenario(sid, spec, 'current'); if (n === seq.current) { setRes(r); setErr(null) } }
      catch (e) { if (n === seq.current) setErr((e as Error).message) } finally { if (n === seq.current) setBusy(false) }
    }, 250)
    return () => clearTimeout(t)
  }, [spec, sid])

  const set = (k: string, v: any) => setSpec((p) => ({ ...p, [k]: v }))
  const tog = (k: string, v: string) => set(k, spec[k].includes(v) ? spec[k].filter((x: string) => x !== v) : [...spec[k], v])
  const r = res?.result
  const saved: Dict[] = st.scenarios ?? []
  const name_of = (id: string) => byId[id]?.name ?? id
  const changed = useMemo(() => JSON.stringify({ ...spec }) !== JSON.stringify({ ...spec, ...{} }), [spec])
  const pick = merchants.filter((m) => !spec.include_ids.includes(m.id) && !spec.exclude_ids.includes(m.id))

  async function save() {
    if (!r) return
    const item = { id: Date.now().toString(36), name: name.trim() || `Scenario ${saved.length + 1}`, spec, result: r, saved_at: new Date().toISOString() }
    await patch({ scenarios: [...saved, item] }); setName('')
  }
  async function apply() {
    if (!window.confirm('Make this the current shortlist? Queue and Action Centre will follow it. The original baseline stays available for comparison.')) return
    setBusy(true)
    try { const out = await api.applyScenario(sid, { ...spec, name: name.trim() || 'Applied scenario' }); setSession(out.session); await reload() } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <div className="space-y-5">
      <PageHeader title="Decision Studio" sub="Change the rules and see exactly who moves in or out of the shortlist, and why. Nothing changes the live shortlist until you apply it." />
      <div className="flex flex-wrap gap-2">
        <span className="label self-center">Start from</span>
        {PRESETS.map((p) => <button key={p.name} className="btn-secondary" onClick={() => setSpec({ ...spec, capacity: cur.capacity, priorities: [], prefer_segments: [], risk_focus: 'revenue', ...p.spec })}>{p.name}</button>)}
        <button className="btn-ghost" onClick={() => setSpec({ ...spec, priorities: [], prefer_segments: [], risk_focus: 'revenue', segments: [], exclude_industries: [], renewal_window: null, capacity: cur.capacity, include_ids: [], exclude_ids: [], exclude_reasons: {} })}>Reset</button>
      </div>

      <div className="grid gap-5 lg:grid-cols-[340px_1fr]">
        <div className="space-y-4">
          <Card title="Decision controls">
            <div className="space-y-4 text-[13px]">
              <label className="block"><span className="label">Outreach capacity</span>
                <div className="mt-1 flex items-center gap-3"><input type="range" min={1} max={40} value={spec.capacity} onChange={(e) => set('capacity', Number(e.target.value))} className="flex-1 accent-brand" aria-label="Outreach capacity" /><span className="num w-8 text-right font-semibold">{spec.capacity}</span></div></label>
              <div><span className="label">Business priorities</span>
                <div className="mt-1.5 space-y-1.5">{Object.entries(PRIORITY).map(([k, l]) => (
                  <label key={k} className="flex items-start gap-2" title={PRIORITY_RULE[k]}><input type="checkbox" className="mt-0.5 accent-brand" checked={spec.priorities.includes(k)} onChange={() => tog('priorities', k)} /><span>{l}</span></label>))}</div></div>
              <div><span className="label">Segment priority</span>
                <div className="mt-1.5 flex gap-3">{['Small', 'Mid', 'Enterprise'].map((x) => <label key={x} className="flex items-center gap-1.5"><input type="checkbox" className="accent-brand" checked={spec.prefer_segments.includes(x)} onChange={() => tog('prefer_segments', x)} />{x === 'Mid' ? 'Mid-market' : x}</label>)}</div></div>
              <Select label="Risk focus (orders merchants with equal matches)" value={spec.risk_focus} onChange={(v) => set('risk_focus', v)} options={Object.entries(FOCUS).map(([value, label]) => ({ value, label }))} />
              <Select label="Renewal window" value={String(spec.renewal_window ?? '')} onChange={(v) => set('renewal_window', v ? Number(v) : null)}
                options={[{ value: '', label: 'Any renewal date' }, { value: '30', label: 'Within 30 days' }, { value: '60', label: 'Within 60 days' }, { value: '90', label: 'Within 90 days' }]} />
              <div><span className="label">Only include segments</span>
                <div className="mt-1.5 flex gap-3">{['Small', 'Mid', 'Enterprise'].map((x) => <label key={x} className="flex items-center gap-1.5"><input type="checkbox" className="accent-brand" checked={spec.segments.includes(x)} onChange={() => tog('segments', x)} />{x === 'Mid' ? 'Mid-market' : x}</label>)}</div></div>
            </div>
          </Card>
          <Card title="Specific merchants" sub="Inclusions take the first slots. Exclusions are removed from the ranking, with a reason.">
            <div className="space-y-3 text-[13px]">
              <div><span className="label">Always include</span>
                {spec.include_ids.map((id: string) => <div key={id} className="mt-1 flex items-center justify-between rounded bg-bg px-2 py-1"><span>{name_of(id)}</span><button className="btn-ghost !p-0.5" onClick={() => set('include_ids', spec.include_ids.filter((x: string) => x !== id))} aria-label="Remove"><Trash2 size={13} /></button></div>)}
                <Select value={addInc} onChange={(v) => { if (v) { set('include_ids', [...spec.include_ids, v]); setAddInc('') } }} className="mt-1" options={[{ value: '', label: 'Add a merchant…' }, ...pick.map((m) => ({ value: m.id, label: `${m.name} (${m.id})` }))]} /></div>
              <div><span className="label">Exclude</span>
                {spec.exclude_ids.map((id: string) => <div key={id} className="mt-1 rounded bg-bg px-2 py-1"><div className="flex items-center justify-between"><span>{name_of(id)}</span><button className="btn-ghost !p-0.5" onClick={() => { set('exclude_ids', spec.exclude_ids.filter((x: string) => x !== id)); patch({ exclusions: { [id]: null } }) }} aria-label="Remove"><Trash2 size={13} /></button></div>
                  <input className="input mt-1 !py-1" placeholder="Reason (required)" value={spec.exclude_reasons[id] ?? ''} onChange={(e) => set('exclude_reasons', { ...spec.exclude_reasons, [id]: e.target.value })} onBlur={(e) => patch({ exclusions: { [id]: e.target.value || 'Excluded in Decision Studio' } })} /></div>)}
                <Select value={addExc} onChange={(v) => { if (v) { set('exclude_ids', [...spec.exclude_ids, v]); setAddExc('') } }} className="mt-1" options={[{ value: '', label: 'Exclude a merchant…' }, ...pick.map((m) => ({ value: m.id, label: `${m.name} (${m.id})` }))]} /></div>
            </div>
          </Card>
        </div>

        <div className="space-y-4">
          {err && <Notice tone="bad">{err}</Notice>}
          {!r ? <Empty title="Calculating…" /> : (<>
            <Card title="What changes" sub={`Proposed selection compared with the current shortlist (${cur.name}).`} action={busy ? <Badge>Updating…</Badge> : undefined}>
              <p className="text-[14px] leading-relaxed">{r.summary}</p>
              <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
                {[['Moving in', r.moved_in.length], ['Moving out', r.moved_out.length], ['Run-rate represented', inr(r.value_after_inr)], ['Change', `${r.value_after_inr - r.value_before_inr >= 0 ? '+' : ''}${inr(r.value_after_inr - r.value_before_inr)}`]].map(([l, v]) => (
                  <div key={l as string} className="rounded-md bg-bg p-3"><p className="label">{l}</p><p className="num mt-1 text-[20px] font-semibold">{v}</p></div>))}
              </div>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <div><p className="label mb-1.5 flex items-center gap-1"><ArrowUpRight size={13} className="text-ok" />Moving into the shortlist</p>
                  {r.moved_in.length === 0 ? <p className="text-[13px] text-mute">None</p> : r.moved_in.map((x: Dict) => (
                    <div key={x.merchant_id} className="border-b border-line py-2 text-[13px] last:border-0"><Link to={`/a/${sid}/merchant/${x.merchant_id}`} className="font-medium hover:text-brand">{x.business_name}</Link> <span className="text-mute">now #{x.to_rank}{x.from_rank ? `, was #${x.from_rank}` : ''}</span><p className="text-[12px] text-mute">{x.reason}</p></div>))}</div>
                <div><p className="label mb-1.5 flex items-center gap-1"><ArrowDownRight size={13} className="text-bad" />Moving out</p>
                  {r.moved_out.length === 0 ? <p className="text-[13px] text-mute">None</p> : r.moved_out.map((x: Dict) => (
                    <div key={x.merchant_id} className="border-b border-line py-2 text-[13px] last:border-0"><Link to={`/a/${sid}/merchant/${x.merchant_id}`} className="font-medium hover:text-brand">{x.business_name}</Link> <span className="text-mute">was #{x.from_rank}{x.to_rank ? `, now #${x.to_rank}` : ''}</span><p className="text-[12px] text-mute">{x.reason}</p></div>))}</div>
              </div>
              <div className="mt-4 grid gap-4 border-t border-line pt-4 md:grid-cols-2">
                <div><p className="label mb-1.5">Risk drivers covered</p><p className="text-[13px]">Current: {Object.entries(r.drivers_before).map(([k, v]) => `${DRIVER[k] ?? k} ${v}`).join(', ') || 'none'}</p><p className="text-[13px]">Proposed: {Object.entries(r.drivers_after).map(([k, v]) => `${DRIVER[k] ?? k} ${v}`).join(', ') || 'none'}</p></div>
                <div><p className="label mb-1.5">Segment mix</p><p className="text-[13px]">Current: {Object.entries(r.segments_before).map(([k, v]) => `${k} ${v}`).join(', ') || 'none'}</p><p className="text-[13px]">Proposed: {Object.entries(r.segments_after).map(([k, v]) => `${k} ${v}`).join(', ') || 'none'}</p></div>
              </div>
              <p className="mt-4 rounded-md bg-bg px-3 py-2 text-[13px]"><span className="font-medium">Business implication. </span>
                {r.moved_in.length + r.moved_out.length === 0 ? 'No change in who is contacted.' : `The team's ${spec.capacity} contacts shift towards ${spec.priorities.length || spec.prefer_segments.length ? 'the selected priorities' : 'a different ordering'}; ${r.moved_out.length} merchant(s) that the current rules would contact will not be contacted this month unless capacity grows. Run-rate revenue is exposure, not a forecast of savings.`}</p>
              <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-4">
                <input className="input !w-56" placeholder="Scenario name" value={name} onChange={(e) => setName(e.target.value)} aria-label="Scenario name" />
                <button className="btn-secondary" onClick={save}><Save size={14} /> Save scenario</button>
                <button className="btn-primary" onClick={apply} disabled={busy}>Apply as current shortlist</button>
              </div>
            </Card>

            <Card title={`Proposed ranking (top ${Math.min(res.ranking.length, spec.capacity + 6)})`} pad={false}>
              <table className="w-full"><thead><tr><th className="th">Rank</th><th className="th">Merchant</th><th className="th">Selection</th><th className="th">Why it sits here</th></tr></thead>
                <tbody>{res.ranking.slice(0, spec.capacity + 6).map((x: Dict) => (
                  <tr key={x.merchant_id} className={clsx(x.rank === spec.capacity && 'border-b-2 border-b-brand')}><td className="td num font-semibold">#{x.rank}</td>
                    <td className="td"><Link to={`/a/${sid}/merchant/${x.merchant_id}`} className="hover:text-brand">{x.name}</Link></td>
                    <td className="td">{x.selected ? <Badge tone="brand">Selected</Badge> : <Badge>Outside</Badge>}</td>
                    <td className="td text-[12.5px] text-mute">{x.forced ? 'Added manually. ' : ''}{x.matched.length ? x.matched.map((p: string) => (p.startsWith('segment:') ? `Segment ${p.slice(8)}` : PRIORITY[p])).join('; ') : 'No extra priority matched; ordered by risk focus and value'}</td></tr>))}</tbody></table>
            </Card>
          </>)}
        </div>
      </div>

      <Card title="Saved scenarios" sub="Compare alternative decisions side by side.">
        {saved.length === 0 ? <p className="text-[13px] text-mute">No saved scenarios yet. Adjust the controls and choose Save scenario.</p> : (<>
          <ScenarioBars items={saved.map((x) => ({ name: x.name, value: +(x.result.value_after_inr / 1e5).toFixed(1), kept: x.result.after.length, moved: x.result.moved_in.length }))} />
          <div className="mt-3 overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Scenario</th><th className="th">Capacity</th><th className="th">Priorities</th><th className="th">In</th><th className="th">Out</th><th className="th">Run-rate</th><th className="th">Trade-off</th><th className="th" /></tr></thead>
            <tbody>{saved.map((x) => (
              <tr key={x.id}><td className="td font-medium">{x.name}</td><td className="td num">{x.spec.capacity}</td><td className="td text-[12.5px]">{[...x.spec.priorities.map((p: string) => PRIORITY[p]), ...(x.spec.prefer_segments ?? []).map((p: string) => `Segment ${p}`)].join('; ') || 'None'}</td>
                <td className="td num">{x.result.moved_in.length}</td><td className="td num">{x.result.moved_out.length}</td><td className="td num">{inr(x.result.value_after_inr)}</td><td className="td max-w-xs text-[12.5px] text-mute">{x.result.summary}</td>
                <td className="td"><div className="flex gap-1"><button className="btn-ghost" onClick={() => setSpec(x.spec)}>Load</button><button className="btn-ghost !p-1" aria-label="Delete scenario" onClick={() => patch({ scenarios: saved.filter((y) => y.id !== x.id) })}><Trash2 size={14} /></button></div></td></tr>))}</tbody></table></div></>)}
      </Card>
    </div>
  )
}
