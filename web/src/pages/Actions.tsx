/* eslint-disable @typescript-eslint/no-explicit-any */
import { Check, Copy } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge, BandBadge, Card, Empty, Notice, PageHeader, Select } from '../components/ui'
import { api } from '../lib/api'
import { STATUS } from '../lib/format'
import { useSession, type M } from '../lib/session'

function Item({ m }: { m: M }) {
  const { sid, s, st, patch, status } = useSession()
  const [open, setOpen] = useState(false)
  const saved = st.drafts?.[m.id]
  const base = saved ?? m.draft
  const [subject, setSubject] = useState<string>(base?.subject ?? '')
  const [body, setBody] = useState<string>(base?.body ?? '')
  const [copied, setCopied] = useState(false)
  const [follow, setFollow] = useState<string>(st.notes?.[m.id]?.follow_up ?? '')
  const approved = (st.approved ?? []).includes(m.id)
  const pb = s.playbooks.find((p: any) => p.playbook_id === m.assessment.primary_playbook_id)
  const dirty = !!base && (subject !== base.subject || body !== base.body)
  const persist = (extra: any = {}) => patch({ drafts: { [m.id]: { subject, body, edited: true } }, ...extra })

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2"><span className="num text-[13px] font-semibold text-mute">#{m.rank}</span><Link to={`/a/${sid}/merchant/${m.id}`} className="text-[15px] font-semibold hover:text-brand">{m.name}</Link><BandBadge band={m.risk_band} label={m.risk_label} />{approved && <Badge tone="ok">Approved</Badge>}</div>
          <p className="mt-1 text-[12.5px] text-mute">{m.id} · {m.segment === 'Mid' ? 'Mid-market' : m.segment} · {m.industry}</p>
        </div>
        <Select value={status(m.id)} onChange={(v) => patch({ statuses: { [m.id]: v } })} options={Object.entries(STATUS).map(([value, label]) => ({ value, label }))} className="w-48" />
      </div>
      <div className="mt-4 grid gap-5 lg:grid-cols-[1fr_1.25fr]">
        <div className="space-y-3 text-[13px]">
          <div><p className="label">Recommended playbook</p><p className="mt-0.5 font-semibold">{m.assessment.primary_playbook_id} · {m.assessment.primary_playbook_name}</p></div>
          <div><p className="label">Reason for selection</p><p className="mt-0.5">{m.assessment.playbook_rationale}</p></div>
          <div><p className="label">Suggested intervention</p><p className="mt-0.5">{pb?.what_happens}</p></div>
          <div><p className="label">Check before contact</p>{m.assessment.additional_checks_for_csm.length ? <ul className="mt-0.5 list-disc space-y-0.5 pl-4">{m.assessment.additional_checks_for_csm.slice(0, 4).map((x: string, i: number) => <li key={i}>{x}</li>)}</ul> : <p className="mt-0.5 text-mute">Standard review only.</p>}</div>
          <label className="block"><span className="label">Follow-up date</span><input type="date" className="input mt-1 !w-44" value={follow} onChange={(e) => { setFollow(e.target.value); patch({ notes: { [m.id]: { ...(st.notes?.[m.id] ?? {}), follow_up: e.target.value } }, statuses: e.target.value && status(m.id) === 'contacted' ? { [m.id]: 'follow_up' } : {} }) }} /></label>
        </div>
        <div>
          <div className="flex items-center justify-between"><p className="label">Outreach draft</p><Badge tone="warn">DRAFT - pending CSM review</Badge></div>
          <input className="input mt-2" value={subject} onChange={(e) => setSubject(e.target.value)} aria-label="Subject" />
          <textarea className="input mt-2 min-h-[200px] leading-relaxed" value={body} onChange={(e) => setBody(e.target.value)} aria-label="Draft body" />
          <div className="mt-2 flex flex-wrap gap-2">
            <button className="btn-secondary" disabled={!dirty} onClick={() => persist({ statuses: { [m.id]: status(m.id) === 'not_contacted' ? 'draft_prepared' : status(m.id) } })}>Save edits</button>
            <button className="btn-secondary" onClick={async () => { await navigator.clipboard.writeText(`${subject}\n\n${body}`); setCopied(true); setTimeout(() => setCopied(false), 1500) }}>{copied ? <><Check size={14} /> Copied</> : <><Copy size={14} /> Copy draft</>}</button>
            <button className={approved ? 'btn-secondary' : 'btn-primary'} onClick={() => persist({ approved: approved ? (st.approved ?? []).filter((x: string) => x !== m.id) : [...(st.approved ?? []), m.id], statuses: { [m.id]: approved ? 'draft_prepared' : 'approved' } })}>{approved ? 'Withdraw approval' : 'Approve draft'}</button>
            <button className="btn-secondary" disabled={!approved} title={approved ? '' : 'Approve the draft first'} onClick={() => patch({ statuses: { [m.id]: 'contacted' } })}>Mark as contacted</button>
          </div>
          {open && <p className="mt-2 text-[12px] text-mute">Facts quoted in the draft: {(base?.facts_used ?? []).join(', ') || 'none'}.</p>}
          <button className="mt-1 text-[12px] text-brand hover:underline" onClick={() => setOpen(!open)}>{open ? 'Hide' : 'Show'} facts used</button>
        </div>
      </div>
    </Card>
  )
}

export default function Actions() {
  const { sid, merchants, st, status } = useSession()
  const [f, setF] = useState('all')
  const sel = merchants.filter((m) => m.selected && (m.draft || st.drafts?.[m.id])).sort((a, b) => a.rank - b.rank)
  const counts = Object.keys(STATUS).map((k) => [k, sel.filter((m) => status(m.id) === k).length] as const)
  const shown = f === 'all' ? sel : sel.filter((m) => status(m.id) === f)
  return (
    <div className="space-y-5">
      <PageHeader title="Action Centre" sub="Turn the shortlist into reviewed, approved outreach. EDGE never sends anything; copy approved drafts into your own channel."
        actions={<a className="btn-secondary" href={api.exportUrl(sid, 'outreach', 'csv')}>Export outreach list</a>} />
      <Notice tone="info" title="Human review is mandatory">Drafts quote only the merchant's own verified figures and the playbook's stated commitments. They never mention risk scores or churn, and they make no discount or concession.</Notice>
      <div className="flex flex-wrap gap-1.5">
        <button className={f === 'all' ? 'btn-primary' : 'btn-secondary'} onClick={() => setF('all')}>All ({sel.length})</button>
        {counts.filter(([, n]) => n > 0).map(([k, n]) => <button key={k} className={f === k ? 'btn-primary' : 'btn-secondary'} onClick={() => setF(k)}>{STATUS[k]} ({n})</button>)}
      </div>
      {shown.length === 0 ? <Empty title="Nothing to action here">{sel.length === 0 ? 'No merchants are shortlisted. Check the Priority Queue or Decision Studio.' : 'No merchants have this status.'}</Empty> : shown.map((m) => <Item key={m.id} m={m} />)}
    </div>
  )
}
