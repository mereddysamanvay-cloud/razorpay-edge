/* eslint-disable @typescript-eslint/no-explicit-any */
import clsx from 'clsx'
import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { DraftWorkflow } from '../components/DraftWorkflow'
import { Badge, BandBadge, Card, Empty, Notice, PageHeader } from '../components/ui'
import { api } from '../lib/api'
import { STATUS, inr } from '../lib/format'
import { useSession } from '../lib/session'

const FILTERS: [string, string, string[]][] = [
  ['all', 'All', []], ['pending', 'Pending review', ['pending_review', 'reviewed']], ['approved', 'Approved', ['approved']], ['contacted', 'Contacted', ['contacted', 'follow_up']],
  ['due', 'Follow-up due', ['follow_up_due']], ['outcome', 'Outcome recorded', ['outcome_recorded']], ['closed', 'Closed', ['closed']],
]
const tone = (s: string) => (s === 'approved' ? 'ok' : s === 'follow_up_due' ? 'bad' : s === 'pending_review' ? 'warn' : s === 'not_contacted' ? 'neutral' : 'brand') as 'ok' | 'bad' | 'warn' | 'neutral' | 'brand'

export default function Actions() {
  const { sid, s, merchants, st, status } = useSession()
  const [sp, setSp] = useSearchParams()
  const f = sp.get('filter') ?? 'all'
  const list = useMemo(() => merchants.filter((m) => m.selected && (m.draft || st.drafts?.[m.id])).sort((a, b) => a.rank - b.rank), [merchants, st.drafts])
  const counts = Object.fromEntries(FILTERS.map(([k, , keys]) => [k, keys.length ? list.filter((m) => keys.includes(status(m.id))).length : list.length]))
  const keys = FILTERS.find(([k]) => k === f)?.[2] ?? []
  const shown = keys.length ? list.filter((m) => keys.includes(status(m.id))) : list
  const sel = shown.find((m) => m.id === sp.get('m')) ?? shown[0]
  const set = (k: string, v: string) => { const n = new URLSearchParams(sp); n.set(k, v); if (k === 'filter') n.delete('m'); setSp(n, { replace: true }) }
  const pb = sel && s.playbooks.find((p: any) => p.playbook_id === sel.assessment.primary_playbook_id)

  return (
    <div className="space-y-5">
      <PageHeader title="Action Centre" sub="Turn the shortlist into reviewed, approved outreach. EDGE never sends anything; you send approved drafts yourself and record that you did."
        actions={<><a className="btn-secondary" href={api.exportUrl(sid, 'outreach', 'csv')}>Export outreach list</a><a className="btn-secondary" href={api.exportUrl(sid, 'workflow', 'csv')}>Export history</a></>} />
      <Notice tone="info" title="Human review is mandatory">Review, approval, contact and outcome are separate steps. Approving a draft does not mean it was sent. Drafts quote only the merchant's own verified figures and the playbook's stated commitments, never mention risk scores or churn, and make no concession.</Notice>
      <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Filter by status">
        {FILTERS.map(([k, l]) => <button key={k} role="tab" aria-selected={f === k} className={f === k ? 'btn-primary' : 'btn-secondary'} onClick={() => set('filter', k)}>{l} ({counts[k]})</button>)}
      </div>
      {shown.length === 0 ? <Empty title="Nothing to action here">{list.length === 0 ? 'No merchants are shortlisted. Check the Priority Queue or Decision Studio.' : 'No merchants have this status.'}</Empty> : (
        <div className="grid items-start gap-5 lg:grid-cols-[320px_1fr]">
          <Card pad={false} className="lg:max-h-[calc(100vh-260px)] lg:overflow-auto">
            <ul>{shown.map((m) => { const cur = status(m.id); const fu = st.notes?.[m.id]?.follow_up; return (
              <li key={m.id}><button onClick={() => set('m', m.id)} aria-current={sel?.id === m.id} className={clsx('block w-full border-b border-line px-3.5 py-3 text-left hover:bg-bg', sel?.id === m.id && 'bg-brand-soft/60')}>
                <span className="flex items-center justify-between gap-2"><span className="text-[13.5px] font-semibold"><span className="num text-mute">#{m.rank}</span> {m.name}</span><Badge tone={tone(cur)}>{STATUS[cur]}</Badge></span>
                <span className="mt-1 flex items-center gap-2 text-[12px] text-mute">{m.id} · <BandBadge band={m.risk_band} label={m.risk_label} />{fu ? <span>Follow-up {fu}</span> : null}</span>
              </button></li>) })}</ul>
          </Card>
          {sel && (
            <Card>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div><Link to={`/a/${sid}/merchant/${sel.id}`} className="text-[17px] font-semibold hover:text-brand">{sel.name}</Link>
                  <p className="mt-0.5 text-[12.5px] text-mute">{sel.id} · {sel.segment === 'Mid' ? 'Mid-market' : sel.segment} · {sel.industry} · renewal in {Math.round(sel.renewal_days)} days · {inr(sel.annual_value)} run-rate proxy</p></div>
                <BandBadge band={sel.risk_band} label={sel.risk_label} />
              </div>
              <div className="mt-4 grid gap-4 text-[13px] md:grid-cols-2">
                <div><p className="label">Recommended playbook</p><p className="mt-0.5 font-semibold">{sel.assessment.primary_playbook_id} · {sel.assessment.primary_playbook_name}</p><p className="mt-0.5 text-mute">{pb?.what_happens}</p></div>
                <div><p className="label">Reason for selection</p><p className="mt-0.5">{sel.assessment.playbook_rationale}</p></div>
                <div className="md:col-span-2"><p className="label">Check before contact</p>{sel.assessment.additional_checks_for_csm.length ? <ul className="mt-0.5 list-disc space-y-0.5 pl-4">{sel.assessment.additional_checks_for_csm.slice(0, 4).map((x: string, i: number) => <li key={i}>{x}</li>)}</ul> : <p className="mt-0.5 text-mute">Standard review only.</p>}</div>
              </div>
              <div className="mt-4 border-t border-line pt-4"><DraftWorkflow m={sel} key={sel.id} /></div>
            </Card>)}
        </div>)}
    </div>
  )
}
