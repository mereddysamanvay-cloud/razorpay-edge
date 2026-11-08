/* eslint-disable @typescript-eslint/no-explicit-any */
import { ChevronDown, ChevronRight, Download } from 'lucide-react'
import { Fragment, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge, Card, Notice, Select } from '../components/ui'
import { api, type Dict } from '../lib/api'
import { num, pct } from '../lib/format'
import { useSession } from '../lib/session'

const STATUS_TONE: Record<string, 'ok' | 'warn' | 'bad' | 'neutral'> = { Pass: 'ok', 'Needs review': 'warn', Fail: 'bad', 'No matching merchant': 'neutral' }
const JUDGE = [{ value: 'Pending', label: 'Pending review' }, { value: 'agree', label: 'Agree with the result' }, { value: 'disagree', label: 'Disagree' }, { value: 'unsure', label: 'Unsure' }]

export default function ValidationLab() {
  const { sid, patch } = useSession()
  const [v, setV] = useState<Dict | null>(null)
  const [open, setOpen] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const load = () => api.validation(sid).then(setV).catch((e) => setErr(e.message))
  useEffect(() => { load() }, [sid]) // eslint-disable-line react-hooks/exhaustive-deps

  async function review(c: Dict, judgement: string, note: string) {
    await patch({ validation: { [`${c.merchant_id}:${c.case_id}`]: { judgement, note } } })
    load()
  }
  if (err) return <Notice tone="bad">{err}</Notice>
  if (!v) return <p className="text-[13px] text-mute">Loading validation cases…</p>
  const sm = v.summary
  const noSens = v.cases.some((c: Dict) => c.merchant_id && !c.weight_sensitivity)

  return (
    <div className="space-y-5">
      <Notice tone="info" title="How to read this">{v.claims} Merchants are chosen by plain rules on the source data, not by their score. Each expected interpretation is a test expectation, not ground truth. A pass means the engine behaves as the stated design intends; it says nothing about prediction accuracy.</Notice>
      <div className="grid gap-3 md:grid-cols-4">
        {[['Cases reviewed', sm.cases], ['Pass', sm.pass], ['Needs review', sm.needs_review], ['Fail', sm.fail]].map(([l, n]) => (
          <div key={l as string} className="card p-4"><p className="label">{l}</p><p className="num mt-1.5 text-[26px] font-semibold">{n}</p></div>))}
      </div>
      {sm.no_match > 0 && <Notice tone="warn">{sm.no_match} case(s) found no matching merchant in this workbook.</Notice>}
      {noSens && <Notice tone="info">Weight sensitivity is empty until the robustness test has been run (Decision Studio, Ranking robustness).</Notice>}

      <Card title="Required adversarial tests" sub="Each required pattern and the cases that cover it." pad={false}>
        <table className="w-full"><thead><tr><th className="th">Test</th><th className="th">Covered by</th></tr></thead>
          <tbody>{v.coverage.map((x: Dict) => <tr key={x.test}><td className="td">{x.test}</td><td className="td">{x.cases.map((i: string) => <Badge key={i} tone={STATUS_TONE[x.statuses[i]] ?? 'neutral'} className="mr-1">{i} {x.statuses[i]}</Badge>)}</td></tr>)}</tbody></table>
      </Card>

      <Card title="Validation cases" pad={false} action={<a className="btn-secondary" href={api.exportUrl(sid, 'validation', 'csv')}><Download size={13} /> Validation log CSV</a>}>
        <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th w-8" /><th className="th">Case</th><th className="th">Pattern</th><th className="th">Merchant</th><th className="th text-right">Score</th><th className="th">Category</th><th className="th">Playbook</th><th className="th">Shortlisted</th><th className="th">Weight sensitivity</th><th className="th text-right">Completeness</th><th className="th">Result</th></tr></thead>
          <tbody>{v.cases.map((c: Dict) => {
            const k = c.case_id
            const isOpen = open === k
            return (
              <Fragment key={k}>
                <tr className="cursor-pointer hover:bg-bg" onClick={() => setOpen(isOpen ? null : k)}>
                  <td className="td">{isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</td><td className="td num font-semibold">{k}</td>
                  <td className="td"><span className="text-[12px] text-mute">{c.category}</span><br />{c.pattern}</td>
                  {c.merchant_id ? (<>
                    <td className="td"><Link to={`/a/${sid}/merchant/${c.merchant_id}`} onClick={(e) => e.stopPropagation()} className="font-medium hover:text-brand">{c.merchant}</Link><br /><span className="text-[12px] text-mute">{c.merchant_id} · {c.segment === 'Mid' ? 'Mid-market' : c.segment}</span></td>
                    <td className="td num text-right">{num(c.score, 1)}</td><td className="td">{c.band}</td><td className="td text-[12.5px]">{c.playbook}</td><td className="td">{c.shortlisted ? 'Yes' : 'No'}</td>
                    <td className="td text-[12.5px]">{c.weight_sensitivity ? `${c.weight_sensitivity.classification} (${pct(c.weight_sensitivity.selection_frequency * 100, 0)})` : 'Not run'}</td><td className="td num text-right">{c.completeness}%</td>
                  </>) : <td className="td text-mute" colSpan={6}>{c.note}</td>}
                  <td className="td"><Badge tone={STATUS_TONE[c.status]}>{c.status}</Badge></td>
                </tr>
                {isOpen && c.merchant_id && (
                  <tr><td className="td bg-bg" colSpan={11}>
                    <div className="grid gap-4 text-[13px] md:grid-cols-2">
                      <div className="space-y-2">
                        <div><p className="label">Expected interpretation (test expectation, not ground truth)</p><p>{c.expectation}</p></div>
                        <div><p className="label">Checks</p><ul className="space-y-0.5">{c.checks.map((x: Dict, i: number) => <li key={i}>{x.passed ? 'Pass' : 'Fail'}: {x.detail}</li>)}</ul></div>
                        {c.failure_stage && <div><p className="label">Failure stage</p><p>{c.failure_stage}. {c.failure_category}</p><p className="text-mute">Corrective action: {c.corrective_action}</p></div>}
                        {!c.failure_stage && c.corrective_action && <p className="text-mute">{c.corrective_action}</p>}
                        <p className="text-[12px] text-mute">Primary driver: {c.driver}. Matching merchants in the workbook: {c.matching_merchants}.{c.missing_fields?.length ? ` Missing: ${c.missing_fields.join(', ')}.` : ''}</p>
                      </div>
                      <div className="space-y-2">
                        <div><p className="label">Supporting evidence</p>{c.evidence.supporting.length ? <ul className="list-disc pl-4">{c.evidence.supporting.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul> : <p className="text-mute">None recorded</p>}</div>
                        <div><p className="label">Mitigating evidence</p>{c.evidence.mitigating.length ? <ul className="list-disc pl-4">{c.evidence.mitigating.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul> : <p className="text-mute">None recorded</p>}</div>
                        <div><p className="label">Contradictory evidence</p>{c.evidence.contradictory.length ? <ul className="list-disc pl-4">{c.evidence.contradictory.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul> : <p className="text-mute">None recorded</p>}</div>
                        <div className="flex flex-wrap items-end gap-2 border-t border-line pt-2">
                          <Select label="Human reviewer judgement" value={c.reviewer.judgement ?? 'Pending'} onChange={(j) => review(c, j, c.reviewer.note ?? '')} options={JUDGE} className="w-56" />
                          <input className="input flex-1" placeholder="Reviewer note" defaultValue={c.reviewer.note ?? ''} onBlur={(e) => { if ((c.reviewer.note ?? '') !== e.target.value) review(c, c.reviewer.judgement ?? 'Pending', e.target.value) }} aria-label="Reviewer note" />
                        </div>
                      </div>
                    </div>
                  </td></tr>)}
              </Fragment>)
          })}</tbody></table></div>
      </Card>
    </div>
  )
}
