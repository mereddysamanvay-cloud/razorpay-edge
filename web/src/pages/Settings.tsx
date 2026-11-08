/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from 'react'
import { Badge, Card, Notice, PageHeader, Select } from '../components/ui'
import { api, type Dict } from '../lib/api'
import { FOCUS } from '../lib/format'
import { useSession } from '../lib/session'

const LABEL: Record<string, string> = {
  net_revenue_rate: 'Net revenue rate (share of TPV)', false_alarm_cost_inr: 'Cost of an unnecessary outreach (Rs)', saved_merchant_months: 'Months of revenue counted for a saved merchant',
  tpv_unit_inr: 'TPV unit (Rs)', max_outreaches: 'Outreach capacity per month', churn_horizon_days: 'Churn horizon (days)', seasonal_industries: 'Seasonal industries',
}

export default function Settings() {
  const { s } = useSession()
  const [cfg, setCfg] = useState<Dict | null>(null)
  const [cap, setCap] = useState('')
  const [focus, setFocus] = useState('revenue')
  const [saved, setSaved] = useState(false)
  const [llm, setLlm] = useState<Dict | null>(null)
  const [testing, setTesting] = useState(false)
  useEffect(() => { api.settings().then((c) => { setCfg(c); setCap(c.default_capacity ?? ''); setFocus(c.default_risk_focus ?? 'revenue') }) }, [])
  const prov: Dict = Object.fromEntries((s.assumptions_provenance ?? []).map((p: Dict) => [p.key, p]))

  return (
    <div className="space-y-5">
      <PageHeader title="Settings" sub="Defaults for new analyses, the assumptions in force, and the AI connection." />
      <Card title="Analysis defaults" sub="Applied the next time you start an analysis. The workbook's own capacity takes precedence unless you override it there.">
        <div className="flex flex-wrap items-end gap-3">
          <label className="block"><span className="label">Default outreach capacity</span><input type="number" min={1} className="input mt-1 !w-32" value={cap} onChange={(e) => setCap(e.target.value)} placeholder="Workbook value" /></label>
          <Select label="Default risk focus" value={focus} onChange={setFocus} className="w-64" options={Object.entries(FOCUS).map(([value, label]) => ({ value, label }))} />
          <button className="btn-primary" onClick={async () => { await api.saveSettings({ default_capacity: cap ? Number(cap) : null, default_risk_focus: focus }); setSaved(true); setTimeout(() => setSaved(false), 1500) }}>{saved ? 'Saved' : 'Save defaults'}</button>
        </div>
      </Card>

      <Card title="Business and revenue assumptions in force" sub="Read from the workbook for this analysis. To change one, supply it when starting a new analysis; it will be recorded as manager-supplied.">
        <table className="w-full"><tbody>{Object.entries(s.assumptions).map(([k, v]) => (
          <tr key={k}><td className="td w-80 text-mute">{LABEL[k] ?? k}</td><td className="td num font-medium">{Array.isArray(v) ? (v as string[]).join(', ') || 'None' : k === 'net_revenue_rate' ? `${((v as number) * 100).toFixed(2).replace(/\.?0+$/, '')}%` : String(v)}</td></tr>))}</tbody></table>
      </Card>

      <Card title="Risk model" sub="Transparent design hypotheses. No churn labels exist, so no accuracy, precision or recall is claimed.">
        <div className="grid gap-6 text-[13px] md:grid-cols-2">
          <div><p className="label mb-1">Dimension weights (hypothesis)</p>{Object.entries(s.scoring.weights).map(([k, v]) => <p key={k}>{k}: <span className="num font-medium">{String(v)}</span></p>)}</div>
          <div><p className="label mb-1">Risk category thresholds (hypothesis)</p>{Object.entries(s.scoring.bands).map(([k, v]) => <p key={k}>{k === 'high' ? 'High risk' : 'Moderate risk'}: score of <span className="num font-medium">{String(v)}</span> or more</p>)}</div>
        </div>
        <p className="mt-3 text-[12px] text-mute">Weights and thresholds live in <code>config/scoring.yaml</code>. Changing them changes the methodology, so they are not editable from this screen.</p>
      </Card>

      <Card title="Available playbooks" sub="From the workbook. The engine selects among these only.">
        <div className="divide-y divide-line">{s.playbooks.map((p: Dict) => <div key={p.playbook_id} className="py-2 first:pt-0 last:pb-0 text-[13px]"><p className="font-medium">{p.playbook_id} · {p.name}</p><p className="text-mute">{p.what_happens}</p><p className="text-[12px] text-mute">When: {p.when_it_applies}</p></div>)}</div>
      </Card>

      <Card title="Field mapping used" sub="How your workbook columns were matched for this analysis.">
        <div className="grid gap-x-8 gap-y-1 text-[13px] md:grid-cols-2">{Object.entries(s.mapping).map(([k, v]) => <p key={k}><span className="text-mute">{k}</span> ← {v ? <span className="font-medium">{String(v)}</span> : <Badge>not in workbook</Badge>}</p>)}</div>
      </Card>

      <Card title="AI provider">
        <div className="space-y-3 text-[13px]">
          <p>Provider: Anthropic Claude · Model: <span className="font-medium">{cfg?.model}</span> · API key: {cfg?.llm_available ? <Badge tone="ok">Found in .env</Badge> : <Badge tone="warn">Not set</Badge>}</p>
          <p className="text-mute">{cfg?.key_hint} Set <code>ANTHROPIC_API_KEY</code> and <code>CLAUDE_MODEL</code> in the project's <code>.env</code> file and restart the API.</p>
          <div className="flex items-center gap-3"><button className="btn-secondary" disabled={testing || !cfg?.llm_available} onClick={async () => { setTesting(true); setLlm(await api.testLlm()); setTesting(false) }}>{testing ? 'Testing…' : 'Test connection'}</button>
            {llm && <span className={llm.ok ? 'text-ok' : 'text-bad'}>{llm.message}</span>}</div>
          <Notice tone="info">Without an API key everything except open-ended Ask EDGE questions and Claude-written drafts still works.</Notice>
        </div>
      </Card>
    </div>
  )
}
