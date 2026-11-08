import { Send, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useSession } from '../lib/session'
import { Badge } from './ui'

interface Msg { role: 'user' | 'assistant'; content: string; source?: string; merchants?: string[]; fields?: string[]; limits?: string[] }

const SUGGEST = [
  'Which 5 merchants should I contact first and why?',
  'Which merchants show the strongest payment deterioration?',
  'Which seasonal merchants were not escalated?',
  'What changes if capacity becomes 20?',
  'Which shortlisted merchants lack CSAT?',
  'Which merchants have contradictory signals?',
  'Which driver has the highest annual run-rate exposure?',
  'Which merchants are most weight-sensitive?',
  'Which merchants have renewal dates within 30 days?',
  'Which merchants are excluded from the current shortlist?',
]
const SOURCE_LABEL: Record<string, string> = { claude: 'Written by Claude (runtime AI)', computed: 'Calculated, no runtime AI', unavailable: 'Unavailable' }

function md(t: string) {
  return t.split('\n').map((line, i) => {
    const parts = line.split(/(\*\*[^*]+\*\*)/g).map((p, j) => (p.startsWith('**') ? <strong key={j}>{p.slice(2, -2)}</strong> : <span key={j}>{p}</span>))
    return <p key={i} className={line.startsWith('- ') || /^\d+\./.test(line) ? 'ml-3 mt-1' : line ? 'mt-1.5' : ''}>{parts}</p>
  })
}

export function AskPanel({ open, onClose, merchantId }: { open: boolean; onClose: () => void; merchantId?: string }) {
  const { sid, byId } = useSession()
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const end = useRef<HTMLDivElement>(null)
  const [ai, setAi] = useState<boolean | null>(null)
  useEffect(() => { if (open) api.health().then((h) => setAi(!!h.llm_available)).catch(() => setAi(null)) }, [open])
  const focus = merchantId ? byId[merchantId] : undefined
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs, busy])

  async function send(text: string) {
    if (!text.trim() || busy) return
    const next: Msg[] = [...msgs, { role: 'user', content: text }]
    setMsgs(next); setQ(''); setBusy(true)
    try {
      const r = await api.ask(sid, text, { merchant_id: merchantId }, next.slice(-6).map(({ role, content }) => ({ role, content })))
      setMsgs([...next, { role: 'assistant', content: r.answer, source: r.source, merchants: r.merchants, fields: r.fields, limits: r.limits }])
    } catch (e) {
      setMsgs([...next, { role: 'assistant', content: `Something went wrong: ${(e as Error).message}`, source: 'error' }])
    } finally { setBusy(false) }
  }

  if (!open) return null
  return (
    <aside className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[400px] flex-col border-l border-line bg-white shadow-pop" aria-label="Ask EDGE">
      <header className="flex items-start justify-between border-b border-line px-4 py-3">
        <div>
          <h2 className="h-sec">Ask EDGE</h2>
          <p className="text-[12px] text-mute">{focus ? `Context: ${focus.name} (${focus.id})` : 'Context: whole portfolio'}</p>
          <p className="mt-1">{ai === null ? null : ai ? <Badge tone="brand">Runtime AI available for open questions</Badge> : <Badge>No runtime AI: calculated answers only</Badge>}</p>
        </div>
        <button className="btn-ghost !p-1" onClick={onClose} aria-label="Close"><X size={16} /></button>
      </header>
      <div className="flex-1 overflow-auto px-4 py-3 text-[13px] leading-relaxed scroll-thin">
        {msgs.length === 0 && (
          <div>
            <p className="text-mute">Answers come from this analysis only. Common questions are calculated directly with no AI; open questions use Claude only when an API key is configured, and its reply is checked before it is shown. Ask EDGE cannot change settings or approve outreach.</p>
            <div className="mt-3 flex flex-col gap-1.5">
              {(focus ? [`Why is ${focus.name} ranked where it is?`, `Why was this playbook selected for ${focus.name}?`, `What must the CSM verify before contacting ${focus.name}?`, ...SUGGEST.slice(0, 2)] : SUGGEST).map((s) => (
                <button key={s} className="rounded-md border border-line px-2.5 py-1.5 text-left text-[12.5px] hover:border-brand hover:bg-brand-soft" onClick={() => send(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={m.role === 'user' ? 'mt-3 flex justify-end' : 'mt-3'}>
            <div className={m.role === 'user' ? 'max-w-[85%] rounded-lg bg-brand px-3 py-2 text-white' : 'w-full rounded-lg border border-line bg-bg px-3 py-2.5'}>
              {m.role === 'user' ? m.content : md(m.content)}
              {m.role === 'assistant' && (
                <div className="mt-2 flex flex-wrap items-center gap-1.5 border-t border-line pt-2">
                  <Badge tone={m.source === 'claude' ? 'brand' : m.source === 'unavailable' ? 'warn' : 'neutral'}>{SOURCE_LABEL[m.source ?? ''] ?? 'Note'}</Badge>
                  {(m.merchants ?? []).slice(0, 6).map((id) => byId[id] && <Link key={id} to={`/a/${sid}/merchant/${id}`} onClick={onClose} className="text-[11.5px] font-medium text-brand hover:underline">{byId[id].name}</Link>)}
                </div>
              )}
              {m.role === 'assistant' && ((m.fields?.length ?? 0) > 0 || (m.limits?.length ?? 0) > 0) && (
                <details className="mt-2 text-[12px] text-mute">
                  <summary className="cursor-pointer font-medium text-navy">Fields used and limits</summary>
                  {(m.fields?.length ?? 0) > 0 && <p className="mt-1"><span className="font-medium">Fields:</span> {m.fields!.join(', ')}</p>}
                  {(m.limits ?? []).map((l, i) => <p key={i} className="mt-0.5">{l}</p>)}
                </details>
              )}
            </div>
          </div>
        ))}
        {busy && <p className="mt-3 text-mute">Working on it…</p>}
        <div ref={end} />
      </div>
      <form className="flex gap-2 border-t border-line p-3" onSubmit={(e) => { e.preventDefault(); send(q) }}>
        <input className="input" placeholder="Ask about this portfolio" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Question" />
        <button className="btn-primary" type="submit" disabled={busy || !q.trim()} aria-label="Send"><Send size={14} /></button>
      </form>
    </aside>
  )
}
