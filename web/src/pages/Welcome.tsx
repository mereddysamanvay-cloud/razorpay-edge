import { ArrowRight, FolderOpen, Loader2, Play, Upload } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { DESCRIPTOR, Logo, TAGLINE } from '../components/Logo'
import { Modal } from '../components/ui'
import { api, type Dict } from '../lib/api'
import { when } from '../lib/format'

/** Layered signal-network backdrop. Decorative only; analytical charts elsewhere stay flat and exact. */
function SignalField() {
  const layers = [0, 1, 2]
  return (
    <div aria-hidden className="pointer-events-none absolute inset-y-0 right-0 hidden w-[58%] overflow-hidden lg:block" style={{ perspective: '1100px' }}>
      <div className="absolute inset-0" style={{ transform: 'rotateX(58deg) rotateZ(-28deg) translate(8%, -6%)', transformStyle: 'preserve-3d' }}>
        {layers.map((l) => (
          <svg key={l} viewBox="0 0 520 520" className="absolute left-1/4 top-1/4 w-[70%]" style={{ transform: `translateZ(${l * 70}px)`, opacity: 0.95 - l * 0.22 }}>
            <rect x="10" y="10" width="500" height="500" rx="10" fill={l === 2 ? '#EAF0FF' : '#fff'} stroke="#C9D6FF" strokeWidth="1.5" />
            {Array.from({ length: 6 }).map((_, i) => <line key={`h${i}`} x1="10" x2="510" y1={95 + i * 70} y2={95 + i * 70} stroke="#E5EAF2" />)}
            {Array.from({ length: 6 }).map((_, i) => <line key={`v${i}`} y1="10" y2="510" x1={95 + i * 70} x2={95 + i * 70} stroke="#E5EAF2" />)}
            {[[120, 160], [260, 110], [390, 210], [190, 330], [340, 400], [90, 420]].map(([x, y], i) => (
              <g key={i}>
                {i > 0 && <line x1={[120, 260, 390, 190, 340, 90][i - 1]} y1={[160, 110, 210, 330, 400, 420][i - 1]} x2={x} y2={y} stroke="#355CFF" strokeOpacity={0.35} strokeWidth="1.5" />}
                <circle cx={x} cy={y} r={i === 2 && l === 2 ? 11 : 7} fill={i === 2 && l === 2 ? '#355CFF' : '#fff'} stroke="#355CFF" strokeWidth="2" />
              </g>
            ))}
          </svg>
        ))}
      </div>
    </div>
  )
}

export default function Welcome() {
  const nav = useNavigate()
  const [prev, setPrev] = useState<Dict[] | null>(null)
  const [open, setOpen] = useState(false)
  const [demo, setDemo] = useState<Dict | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { api.sessions().then(setPrev).catch(() => setPrev([])); api.demoStatus().then(setDemo).catch(() => setDemo(null)) }, [])
  async function openDemo() {
    setBusy(true); setErr(null)
    try { const r = await api.openDemo(); nav(`/a/${r.session_id}/overview`) } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <div className="flex min-h-full flex-col bg-bg">
      <div className="relative flex-1 overflow-hidden border-b border-line bg-white">
        <SignalField />
        <div className="relative mx-auto flex min-h-[540px] max-w-[1180px] flex-col justify-center px-6 py-14">
          <Logo height={88} />
          <p className="mt-5 text-[17px] font-semibold tracking-tight text-navy">{DESCRIPTOR}</p>
          <p className="mt-0.5 text-[15px] text-brand">{TAGLINE}</p>
          <p className="mt-6 max-w-lg text-[15px] leading-relaxed text-mute">
            Understand merchant behaviour, identify emerging risks and prioritise the relationships that matter most.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            {demo?.available && <button className="btn-primary !px-4 !py-2.5 !text-[14px]" onClick={openDemo} disabled={busy}>{busy ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />} Open Demo Workspace</button>}
            <button className={demo?.available ? 'btn-secondary !px-4 !py-2.5 !text-[14px]' : 'btn-primary !px-4 !py-2.5 !text-[14px]'} onClick={() => nav('/new')}><Upload size={15} /> Upload New Workbook</button>
            <button className="btn-secondary !px-4 !py-2.5 !text-[14px]" onClick={() => setOpen(true)}><FolderOpen size={15} /> Open Previous Analysis</button>
          </div>
          {err && <p className="mt-3 max-w-md text-[12.5px] text-bad" role="alert">{err}</p>}
          {demo?.available && <p className="mt-3 max-w-md text-[12px] leading-snug text-mute">The demo workspace is the Problem 2 data ({demo.sheets.join(', ')}), already analysed. Uploading your own workbook never changes it.</p>}
          <p className="mt-6 max-w-md text-[12px] leading-snug text-mute">
            Internal decision-support tool. Risk scores are transparent heuristics, not churn probabilities. Every outreach draft needs human review before it is used.
          </p>
        </div>
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title="Previous analyses" wide>
        {prev === null ? <p className="text-mute">Loading…</p> : prev.length === 0 ? (
          <p className="text-mute">No saved analyses yet. Start a new analysis by uploading a workbook.</p>
        ) : (
          <ul className="divide-y divide-line">
            {prev.map((p) => (
              <li key={p.id}>
                <button className="flex w-full items-center justify-between gap-3 py-3 text-left hover:bg-bg" onClick={() => nav(`/a/${p.id}/overview`)}>
                  <span>
                    <span className="block font-medium text-ink">{p.name}</span>
                    <span className="block text-[12px] text-mute">{p.source_file} · {p.merchant_count} merchants · {when(p.created_at)}{p.llm_used ? ' · Claude-assisted' : ''}</span>
                  </span>
                  <ArrowRight size={15} className="text-brand" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </Modal>
    </div>
  )
}
