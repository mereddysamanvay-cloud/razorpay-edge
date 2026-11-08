/* eslint-disable @typescript-eslint/no-explicit-any */
import { Check, Copy } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api, type Dict } from '../lib/api'
import { OUTCOMES, STATUS } from '../lib/format'
import { useSession, type M } from '../lib/session'
import { Badge, Notice, Select } from './ui'

const CHANNELS = ['Phone call', 'Email', 'WhatsApp or chat', 'Meeting', 'Other']
const today = () => new Date().toISOString().slice(0, 10)
const EVENT: Record<string, string> = {
  reviewed: 'Reviewed', edited: 'Draft edited', approved: 'Approved (not sent)', approval_withdrawn: 'Approval withdrawn', contacted: 'Contact recorded manually', follow_up_set: 'Follow-up set',
  outcome_recorded: 'Outcome recorded', closed: 'Closed', draft_edited: 'Edited after contact',
}
const when = (iso: string) => new Date(iso).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })

/** Review pack, editor and lifecycle controls for one merchant's outreach draft. Review, approval, contact and outcome are separate steps. */
export function DraftWorkflow({ m }: { m: M }) {
  const { sid, st, status, workflow } = useSession()
  const saved = st.drafts?.[m.id]
  const base = saved ?? m.draft
  const [subject, setSubject] = useState<string>(base?.subject ?? '')
  const [body, setBody] = useState<string>(base?.body ?? '')
  const [pack, setPack] = useState<Dict | null>(null)
  const [reviewer, setReviewer] = useState<string>(() => { try { return localStorage.getItem('edge_reviewer') ?? '' } catch { return '' } })
  const [ack, setAck] = useState(false)
  const [channel, setChannel] = useState(CHANNELS[0])
  const [date, setDate] = useState(today())
  const [follow, setFollow] = useState<string>(st.notes?.[m.id]?.follow_up ?? '')
  const [outcome, setOutcome] = useState('')
  const [otext, setOtext] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState(false)
  const cur = status(m.id)
  const events: Dict[] = st.events?.[m.id] ?? []
  const outcomes: Dict[] = st.outcomes?.[m.id] ?? []
  const dirty = !!base && (subject !== base.subject || body !== base.body)

  useEffect(() => { setSubject(base?.subject ?? ''); setBody(base?.body ?? ''); setAck(false); setErr(null); setFollow(st.notes?.[m.id]?.follow_up ?? '') }, [m.id, base?.subject, base?.body]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!base) return
    const t = setTimeout(() => { api.reviewPack(sid, m.id, subject, body).then(setPack).catch(() => setPack(null)) }, 250)
    return () => clearTimeout(t)
  }, [sid, m.id, subject, body, !!base]) // eslint-disable-line react-hooks/exhaustive-deps

  async function run(action: string, payload: Dict = {}) {
    setBusy(true); setErr(null)
    try {
      if (reviewer) { try { localStorage.setItem('edge_reviewer', reviewer) } catch { /* ignore */ } }
      await workflow(m.id, action, { reviewer, ...payload })
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  if (!base) return <p className="text-[13px] text-mute">No churn-outreach draft: this merchant's playbook ({m.assessment.primary_playbook_id}) does not use outreach capacity.</p>
  const blocked = (pack?.unsupported_claims?.length ?? 0) > 0
  const label = (l: string) => <label className="label mb-1 block">{l}</label>

  return (
    <div className="space-y-4 text-[13px]">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="label">Outreach draft</p>
        <span className="flex items-center gap-1.5"><Badge tone={cur === 'approved' ? 'ok' : cur === 'follow_up_due' ? 'bad' : cur === 'pending_review' ? 'warn' : 'brand'}>{STATUS[cur]}</Badge><Badge tone="warn">DRAFT for CSM review</Badge></span>
      </div>

      {pack && (
        <details className="rounded-md border border-line bg-bg px-3 py-2" open>
          <summary className="cursor-pointer text-[12.5px] font-semibold text-navy">Review pack: check before you approve</summary>
          <div className="mt-2 grid gap-3 md:grid-cols-2">
            <div><p className="label mb-1">Facts the draft uses</p>
              {pack.facts_used.length ? <ul className="space-y-0.5">{pack.facts_used.map((f: Dict) => <li key={f.fact}><span className="font-medium">{f.value}</span> <span className="text-mute">from {f.source_field}</span></li>)}</ul> : <p className="text-mute">No merchant figures are quoted.</p>}</div>
            <div><p className="label mb-1">Playbook commitments (from the workbook)</p><p>{pack.playbook_commitments ?? 'Not available'}</p><p className="mt-0.5 text-[12px] text-mute">Do not promise anything beyond this.</p></div>
            <div><p className="label mb-1">Facts requiring verification</p>
              {pack.facts_requiring_verification.length ? <ul className="list-disc space-y-0.5 pl-4">{pack.facts_requiring_verification.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul> : <p className="text-mute">None flagged.</p>}</div>
            <div><p className="label mb-1">Unsupported claims in the current text</p>
              {pack.unsupported_claims.length ? <ul className="list-disc space-y-0.5 pl-4 text-bad">{pack.unsupported_claims.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul> : <p className="text-ok">None found. No risk score, churn wording, concession or unsupported figure.</p>}
              {pack.warnings.map((w: string, i: number) => <p key={i} className="mt-1 text-[12px] text-mute">{w}</p>)}</div>
          </div>
        </details>)}

      <div>
        <input className="input" value={subject} onChange={(e) => setSubject(e.target.value)} aria-label="Subject" />
        <textarea className="input mt-2 min-h-[210px] leading-relaxed" value={body} onChange={(e) => setBody(e.target.value)} aria-label="Draft body" />
        <div className="mt-2 flex flex-wrap gap-2">
          <button className="btn-secondary" disabled={!dirty || busy} onClick={() => run('save_draft', { subject, body })}>Save edits</button>
          <button className="btn-secondary" onClick={async () => { await navigator.clipboard.writeText(`${subject}\n\n${body}`); setCopied(true); setTimeout(() => setCopied(false), 1500) }}>{copied ? <><Check size={14} /> Copied</> : <><Copy size={14} /> Copy draft</>}</button>
        </div>
        {dirty && <p className="mt-1 text-[12px] text-warn">Unsaved edits. Save them before reviewing; editing an approved draft withdraws its approval.</p>}
      </div>

      {err && <Notice tone="bad">{err}</Notice>}

      <div className="space-y-3 rounded-md border border-line p-3">
        {(cur === 'pending_review' || cur === 'not_contacted') && (<div className="flex flex-wrap items-center gap-2"><p className="flex-1 text-mute">Step 1 of 4. A CSM reads the draft and the review pack.</p>
          <button className="btn-primary" disabled={busy || dirty} onClick={() => run('review')}>Mark as reviewed</button></div>)}
        {cur === 'reviewed' && (<div className="space-y-2"><p className="text-mute">Step 2 of 4. Approval records that a named person checked the draft. It does not send anything.</p>
          <div className="flex flex-wrap items-end gap-3">
            <div>{label('Reviewer name')}<input className="input !w-48" value={reviewer} onChange={(e) => setReviewer(e.target.value)} aria-label="Reviewer name" /></div>
            <label className="flex max-w-md items-start gap-2"><input type="checkbox" className="mt-0.5 accent-brand" checked={ack} onChange={(e) => setAck(e.target.checked)} />I have checked the facts and wording above against the source data.</label>
            <button className="btn-primary" disabled={busy || dirty || !ack || !reviewer.trim() || blocked} onClick={() => run('approve', { acknowledged: true })}>Approve draft</button>
          </div>{blocked && <p className="text-[12px] text-bad">Remove the unsupported claims before approving.</p>}</div>)}
        {cur === 'approved' && (<div className="space-y-2"><div className="flex items-center justify-between"><p className="text-mute">Step 3 of 4. Send it yourself, then record that you did. EDGE never sends messages.</p>
          <button className="btn-ghost" disabled={busy} onClick={() => run('withdraw')}>Withdraw approval</button></div>
          <div className="flex flex-wrap items-end gap-3">
            <div>{label('Contact date')}<input type="date" className="input !w-40" value={date} max={today()} onChange={(e) => setDate(e.target.value)} /></div>
            <Select label="Channel used" value={channel} onChange={setChannel} options={CHANNELS.map((c) => ({ value: c, label: c }))} className="w-44" />
            <button className="btn-primary" disabled={busy || !date} onClick={() => run('contact', { date, channel })}>Record that I contacted the merchant</button>
          </div></div>)}
        {(cur === 'contacted' || cur === 'follow_up' || cur === 'follow_up_due') && (<div className="space-y-3"><p className="text-mute">Step 4 of 4. Record what happened. Outcomes are your observations, not churn labels.</p>
          <div className="flex flex-wrap items-end gap-3">
            <div>{label('Follow-up date')}<input type="date" className="input !w-40" value={follow} onChange={(e) => setFollow(e.target.value)} /></div>
            <button className="btn-secondary" disabled={busy || !follow} onClick={() => run('follow_up', { date: follow })}>Set follow-up</button></div>
          <div className="flex flex-wrap items-end gap-3">
            <Select label="Outcome" value={outcome} onChange={setOutcome} options={[{ value: '', label: 'Choose…' }, ...Object.entries(OUTCOMES).map(([value, l]) => ({ value, label: l }))]} className="w-60" />
            <div className="min-w-[200px] flex-1">{label('Note')}<input className="input" value={otext} onChange={(e) => setOtext(e.target.value)} placeholder={outcome === 'other' ? 'Describe the outcome (required)' : 'Optional'} /></div>
            <button className="btn-primary" disabled={busy || !outcome} onClick={() => run('outcome', { outcome, text: otext })}>Record outcome</button></div></div>)}
        {cur === 'outcome_recorded' && (<div className="flex flex-wrap items-center gap-2"><p className="flex-1 text-mute">Outcome recorded. Close the case, or record another outcome after a follow-up.</p>
          <button className="btn-secondary" disabled={busy} onClick={() => run('close', { reason: 'Closed / monitor' })}>Close / monitor</button></div>)}
        {cur === 'closed' && <p className="text-mute">Closed. The history below is kept.</p>}
      </div>

      {outcomes.length > 0 && <div><p className="label mb-1">Outcomes (CSM observations, not churn labels)</p>{outcomes.map((o, i) => <p key={i}>{when(o.at)}: <span className="font-medium">{o.label}</span>{o.text ? `. ${o.text}` : ''}</p>)}</div>}
      {events.length > 0 && (
        <details><summary className="cursor-pointer text-[12.5px] font-semibold text-navy">History ({events.length})</summary>
          <ul className="mt-1 space-y-0.5 text-[12.5px]">{events.map((e, i) => <li key={i}><span className="text-mute">{when(e.at)}</span> {EVENT[e.type] ?? e.type}{e.reviewer ? ` by ${e.reviewer}` : ''}{e.date ? `, ${e.date}` : ''}{e.channel ? `, ${e.channel}` : ''}{e.detail ? `. ${e.detail}` : ''}</li>)}</ul></details>)}
    </div>
  )
}
