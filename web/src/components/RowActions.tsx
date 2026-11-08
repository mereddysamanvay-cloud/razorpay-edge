import { MoreHorizontal } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSession, type M } from '../lib/session'
import { Modal } from './ui'

/** Row-level actions: view, review list, compare, mark for outreach, exclude with a reason. */
export function RowActions({ m, compare, setCompare }: { m: M; compare?: string[]; setCompare?: (v: string[]) => void }) {
  const { sid, st, patch } = useSession()
  const nav = useNavigate()
  const [open, setOpen] = useState(false)
  const [why, setWhy] = useState(false)
  const [reason, setReason] = useState('')
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  const inReview = (st.review_list ?? []).includes(m.id)
  const marked = (st.marked ?? []).includes(m.id)
  const excluded = st.exclusions?.[m.id]
  const toggle = (key: string, list: string[], id: string) => patch({ [key]: list.includes(id) ? list.filter((x) => x !== id) : [...list, id] })
  const item = 'block w-full rounded px-2.5 py-1.5 text-left text-[13px] hover:bg-bg'
  return (
    <div className="relative" ref={ref}>
      <button className="btn-ghost !p-1" aria-label={`Actions for ${m.name}`} onClick={() => setOpen(!open)}><MoreHorizontal size={16} /></button>
      {open && (
        <div className="absolute right-0 top-full z-30 mt-1 w-56 rounded-md border border-line bg-white p-1 shadow-pop">
          <button className={item} onClick={() => nav(`/a/${sid}/merchant/${m.id}`)}>View profile</button>
          <button className={item} onClick={() => { toggle('review_list', st.review_list ?? [], m.id); setOpen(false) }}>{inReview ? 'Remove from review list' : 'Add to review list'}</button>
          {setCompare && <button className={item} onClick={() => { const c = compare ?? []; setCompare(c.includes(m.id) ? c.filter((x) => x !== m.id) : [...c, m.id].slice(-4)); setOpen(false) }}>{compare?.includes(m.id) ? 'Remove from comparison' : 'Compare'}</button>}
          <button className={item} onClick={() => { toggle('marked', st.marked ?? [], m.id); setOpen(false) }}>{marked ? 'Unmark for outreach' : 'Mark for outreach'}</button>
          {excluded ? <button className={item} onClick={() => { patch({ exclusions: { [m.id]: null } }); setOpen(false) }}>Restore to shortlist</button>
            : <button className={item} onClick={() => { setWhy(true); setOpen(false) }}>Exclude from shortlist…</button>}
        </div>
      )}
      <Modal open={why} onClose={() => setWhy(false)} title={`Exclude ${m.name} from the current shortlist`}
        footer={<><button className="btn-secondary" onClick={() => setWhy(false)}>Cancel</button><button className="btn-primary" disabled={!reason.trim()} onClick={() => { patch({ exclusions: { [m.id]: reason.trim() } }); setWhy(false); setReason('') }}>Exclude</button></>}>
        <p className="mb-2 text-mute">A reason is required so the decision can be reviewed later. It is recorded on this analysis; open Decision Studio to apply exclusions to the ranking.</p>
        <textarea className="input min-h-[80px]" placeholder="e.g. Already in an active escalation with the Account Manager" value={reason} onChange={(e) => setReason(e.target.value)} />
      </Modal>
    </div>
  )
}
