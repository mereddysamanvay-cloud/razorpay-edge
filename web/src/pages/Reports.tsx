/* eslint-disable @typescript-eslint/no-explicit-any */
import { Download, FileSpreadsheet, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Badge, Card, Notice, PageHeader, Select } from '../components/ui'
import { api, type Dict } from '../lib/api'
import { FOCUS, PRIORITY, num, when } from '../lib/format'
import { useSession } from '../lib/session'

const KINDS: [string, string, string][] = [
  ['risk_register', 'Merchant risk register', 'Every merchant with metrics, risk category, driver and playbook.'],
  ['outreach', 'Ranked outreach list', 'The shortlist with reasons, status and the current draft text.'],
  ['analysis', 'Merchant-level analysis', 'Evidence, mitigating and contradictory signals per merchant.'],
  ['insights', 'Business insights report', 'Drivers, segments, commercial exposure and operational leads.'],
  ['scenarios', 'Decision scenario comparison', 'Saved scenarios with who moves in and out.'],
]

export default function Reports() {
  const { sid, s } = useSession()
  const nav = useNavigate()
  const [hist, setHist] = useState<Dict[]>([])
  const [other, setOther] = useState('')
  const [cmp, setCmp] = useState<Dict | null>(null)
  const load = () => api.sessions().then(setHist)
  useEffect(() => { load() }, [])

  return (
    <div className="space-y-5">
      <PageHeader title="Reports & History" sub="Export this analysis, reopen earlier ones and compare them where the data allows." />
      <Card title="Current analysis" sub="Every export names its source workbook and analysis version.">
        <dl className="grid gap-x-8 gap-y-2 text-[13px] md:grid-cols-3">
          <div><dt className="label">Analysis</dt><dd>{s.name}</dd></div><div><dt className="label">Source workbook</dt><dd>{s.source_file}</dd></div><div><dt className="label">Version</dt><dd>{s.version}</dd></div>
          <div><dt className="label">Analysed</dt><dd>{when(s.created_at)}</dd></div><div><dt className="label">Capacity</dt><dd>{s.kpis.capacity} contacts</dd></div>
          <div><dt className="label">Risk focus / priorities</dt><dd>{FOCUS[s.config.risk_focus ?? 'revenue']} · {(s.config.priorities ?? []).map((p: string) => PRIORITY[p]).join(', ') || 'no extra priorities'}</dd></div>
          <div><dt className="label">Claude assistance</dt><dd>{s.llm_used ? 'Used for note interpretation and drafts' : 'Not used (deterministic)'}</dd></div>
          <div><dt className="label">Sheets used</dt><dd>{[s.sheets.merchants, s.sheets.playbooks, s.sheets.assumptions].filter(Boolean).join(', ')}{s.sheets.reference_used?.length ? ` · reference ${s.sheets.reference_used.join(' and ')} from the Problem 2 pack` : ''}</dd></div>
          <div><dt className="label">Records excluded</dt><dd>{s.excluded_records.length}{s.excluded_records.length ? `: ${s.excluded_records.slice(0, 2).map((e: Dict) => e.reason).join('; ')}` : ''}</dd></div>
        </dl>
      </Card>

      <Card title="Export" action={<a className="btn-primary" href={api.exportUrl(sid, 'all', 'xlsx')}><FileSpreadsheet size={14} /> Everything (Excel)</a>}>
        <div className="divide-y divide-line">
          {KINDS.map(([k, l, d]) => (
            <div key={k} className="flex flex-wrap items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
              <div><p className="text-[13.5px] font-medium">{l}</p><p className="text-[12.5px] text-mute">{d}</p></div>
              <div className="flex gap-2"><a className="btn-secondary" href={api.exportUrl(sid, k, 'csv')}><Download size={13} /> CSV</a><a className="btn-secondary" href={api.exportUrl(sid, k, 'xlsx')}><Download size={13} /> Excel</a></div>
            </div>))}
        </div>
        <p className="mt-3 text-[12px] text-mute">A PDF summary is not generated in this version. Print the Overview page from the browser for a one-page view.</p>
      </Card>

      <Card title="Analysis history" pad={false}>
        <table className="w-full"><thead><tr><th className="th">Analysis</th><th className="th">Source workbook</th><th className="th">Analysed</th><th className="th">Merchants</th><th className="th">High / Moderate</th><th className="th">Capacity</th><th className="th" /></tr></thead>
          <tbody>{hist.map((h) => (
            <tr key={h.id} className={h.id === sid ? 'bg-brand-soft/40' : ''}>
              <td className="td font-medium">{h.name} {h.id === sid && <Badge tone="brand">Open</Badge>}{h.llm_used && <Badge className="ml-1">Claude</Badge>}</td><td className="td">{h.source_file}</td><td className="td">{when(h.created_at)}</td>
              <td className="td num">{h.merchant_count}</td><td className="td num">{h.summary?.high} / {h.summary?.medium}</td><td className="td num">{h.config?.capacity}</td>
              <td className="td"><div className="flex gap-1"><button className="btn-secondary" onClick={() => nav(`/a/${h.id}/overview`)}>Reopen</button>
                {h.id !== sid && <button className="btn-ghost !p-1" aria-label="Delete analysis" onClick={async () => { if (window.confirm(`Delete "${h.name}" permanently?`)) { await api.deleteSession(h.id); load() } }}><Trash2 size={14} /></button>}</div></td></tr>))}</tbody></table>
      </Card>

      <Card title="Compare with another analysis">
        <div className="flex flex-wrap items-end gap-2">
          <Select label="Compare current with" value={other} onChange={setOther} className="w-72" options={[{ value: '', label: 'Choose an analysis…' }, ...hist.filter((h) => h.id !== sid).map((h) => ({ value: h.id, label: `${h.name} · ${when(h.created_at)}` }))]} />
          <button className="btn-secondary" disabled={!other} onClick={async () => setCmp(await api.compare(other, sid))}>Compare</button>
        </div>
        {cmp && (<div className="mt-4">
          <Notice tone={cmp.comparable ? 'info' : 'warn'} title={cmp.comparable ? `${cmp.common} merchants appear in both analyses` : 'These analyses share few merchants'}>{cmp.caveat}</Notice>
          <div className="mt-3 grid gap-3 md:grid-cols-2">{(['a', 'b'] as const).map((k) => <div key={k} className="rounded-md bg-bg p-3 text-[13px]"><p className="font-medium">{k === 'a' ? 'Earlier' : 'Current'}: {cmp[k].name}</p><p className="text-mute">{cmp[k].source} · {when(cmp[k].created_at)}</p><p className="mt-1">High {cmp[k].kpis.high} · Moderate {cmp[k].kpis.medium} · Low {cmp[k].kpis.low}</p></div>)}</div>
          {cmp.rows.length > 0 && <table className="mt-3 w-full"><thead><tr><th className="th">Merchant</th><th className="th text-right">Earlier score</th><th className="th text-right">Current score</th><th className="th text-right">Change</th><th className="th">Category</th></tr></thead>
            <tbody>{cmp.rows.slice(0, 15).map((r: Dict) => <tr key={r.id}><td className="td">{r.name}</td><td className="td num text-right">{num(r.score_a)}</td><td className="td num text-right">{num(r.score_b)}</td><td className="td num text-right">{r.delta > 0 ? '+' : ''}{num(r.delta, 1)}</td><td className="td">{r.band_a} → {r.band_b}</td></tr>)}</tbody></table>}
        </div>)}
      </Card>
    </div>
  )
}
