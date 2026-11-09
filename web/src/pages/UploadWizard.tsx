/* eslint-disable @typescript-eslint/no-explicit-any */
import clsx from 'clsx'
import { ArrowLeft, Check, FileSpreadsheet, Loader2, Upload } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Logo } from '../components/Logo'
import { Badge, Card, Modal, Notice, Segmented, Select, Tip } from '../components/ui'
import { api, type Dict } from '../lib/api'
import { FOCUS, PRIORITY, PRIORITY_RULE } from '../lib/format'

const STEPS = ['Upload', 'Review & map', 'Configure', 'Analyse']
const DEFAULT_CFG = { capacity: 15, priorities: [] as string[], risk_focus: 'revenue', segments: [] as string[], exclude_industries: [] as string[], renewal_window: null as number | null }

function Stepper({ step }: { step: number }) {
  return (
    <ol className="flex items-center gap-2 text-[12.5px]" aria-label="Progress">
      {STEPS.map((s, i) => (
        <li key={s} className="flex items-center gap-2">
          <span className={clsx('flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-semibold', i < step ? 'bg-brand text-white' : i === step ? 'border-2 border-brand text-brand' : 'border border-line text-mute')}>
            {i < step ? <Check size={12} /> : i + 1}
          </span>
          <span className={i === step ? 'font-medium text-ink' : 'text-mute'}>{s}</span>
          {i < STEPS.length - 1 && <span className="mx-1 h-px w-6 bg-line" />}
        </li>
      ))}
    </ol>
  )
}

function Dropzone({ onFile, busy, error, fileName }: { onFile: (f: File) => void; busy: boolean; error: string | null; fileName?: string }) {
  const ref = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)
  return (
    <div>
      <div role="button" tabIndex={0} onClick={() => ref.current?.click()} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && ref.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files[0]; if (f) onFile(f) }}
        className={clsx('flex cursor-pointer flex-col items-center rounded-lg border-2 border-dashed px-6 py-12 text-center transition-colors', over ? 'border-brand bg-brand-soft' : 'border-line bg-white hover:border-brand/60')}>
        {busy ? <Loader2 className="animate-spin text-brand" size={26} /> : <Upload className="text-brand" size={26} />}
        <p className="mt-3 text-[15px] font-medium">{busy ? 'Reading workbook…' : 'Drag a merchant workbook here, or browse'}</p>
        <p className="mt-1 text-[12.5px] text-mute">Accepted: .xlsx, .xls, .csv · Maximum size 25 MB</p>
        <button type="button" className="btn-secondary mt-4" onClick={(e) => { e.stopPropagation(); ref.current?.click() }}>Browse files</button>
        <input ref={ref} type="file" hidden accept=".xlsx,.xls,.csv" onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])} />
      </div>
      {fileName && !error && <p className="mt-3 flex items-center gap-2 text-[13px]"><FileSpreadsheet size={15} className="text-brand" /> {fileName}</p>}
      {error && <div className="mt-3"><Notice tone="bad" title="Upload failed">{error}</Notice></div>}
    </div>
  )
}

function PreviewTable({ data, limit }: { data: Dict; limit?: number }) {
  const rows = limit ? data.rows.slice(0, limit) : data.rows
  return (
    <div className="max-h-[360px] overflow-auto rounded-md border border-line scroll-thin">
      <table className="w-full border-collapse">
        <thead className="sticky top-0"><tr>{data.columns.map((c: string) => <th key={c} className="th">{c}</th>)}</tr></thead>
        <tbody>{rows.map((r: any[], i: number) => <tr key={i}>{r.map((v, j) => <td key={j} className="td max-w-[220px] truncate" title={String(v ?? '')}>{v ?? <span className="text-slate-300">empty</span>}</td>)}</tr>)}</tbody>
      </table>
      {data.truncated && <p className="bg-bg px-3 py-2 text-[12px] text-mute">Showing the first {data.rows.length} of {data.total} rows.</p>}
    </div>
  )
}

export default function UploadWizard() {
  const nav = useNavigate()
  const [step, setStep] = useState(0)
  const [info, setInfo] = useState<Dict | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [mapping, setMapping] = useState<Record<string, string | null>>({})
  const [tab, setTab] = useState('sample')
  const [reviewed, setReviewed] = useState(false)
  const [useRef_, setUseRef] = useState(false)
  const [overrides, setOverrides] = useState<Dict>({})
  const [cfg, setCfg] = useState<Dict>(DEFAULT_CFG)
  const [name, setName] = useState('')
  const [useLlm, setUseLlm] = useState(false)
  const [confirmLlm, setConfirmLlm] = useState(false)
  const [health, setHealth] = useState<Dict>({})
  const [job, setJob] = useState<Dict | null>(null)
  const [done, setDone] = useState<string[]>([])
  const [saved, setSaved] = useState(false)

  useEffect(() => { api.health().then(setHealth).catch(() => setHealth({ ok: false })) }, [])

  const ingest = useCallback(async (p: Promise<Dict>) => {
    setBusy(true); setErr(null)
    try {
      const r = await p
      setInfo(r); setMapping(r.mapping ?? {}); setName((n) => n || r.file_name?.replace(/\.[^.]+$/, '') || '')
      setCfg((c) => ({ ...c, capacity: r.assumptions?.values?.max_outreaches ?? c.capacity }))
      setStep(1)
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }, [])

  async function reinspect(patch: Dict) {
    if (!info) return
    setBusy(true)
    try {
      const body = { merchant_sheet: info.merchant_sheet, playbook_sheet: info.playbook_sheet, assumption_sheet: info.assumption_sheet, mapping, ...patch }
      const r = await api.inspect(info.upload_id, body)
      setInfo(r); setMapping(r.mapping ?? {})
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  const q = info?.quality
  const blockers: string[] = []
  if (info) {
    if (q?.required_missing?.length) blockers.push(`Required fields not mapped: ${q.required_missing.map((k: string) => info.fields.find((f: Dict) => f.key === k)?.label ?? k).join(', ')}`)
    if (q && q.analysable_records === 0) blockers.push('No analysable merchant records')
    if (!info.playbooks.present && !useRef_) blockers.push('No playbook sheet found. Select one, or confirm use of the reference playbooks below.')
    const unresolved = (info.assumptions?.unresolved ?? []).filter((k: string) => overrides[k] === undefined || overrides[k] === '')
    if (unresolved.length && !(useRef_ && !info.assumptions.present)) blockers.push(`Assumptions to supply: ${unresolved.map((k: string) => info.assumptions.labels[k]).join(', ')}`)
  }

  async function run() {
    if (!info) return
    setStep(3); setDone([]); setErr(null)
    try {
      const num = (v: any) => (v === '' || v == null ? undefined : Number(v))
      const ov: Dict = {}
      for (const [k, v] of Object.entries(overrides)) {
        if (v === '' || v == null) continue
        ov[k] = k === 'seasonal_industries' ? String(v).split(',').map((x) => x.trim()).filter(Boolean) : num(v)
      }
      if (ov.net_revenue_rate && ov.net_revenue_rate > 1) ov.net_revenue_rate = ov.net_revenue_rate / 100
      const { job_id } = await api.analyse({
        upload_id: info.upload_id, name, mapping, merchant_sheet: info.merchant_sheet, playbook_sheet: info.playbook_sheet, assumption_sheet: info.assumption_sheet,
        config: cfg, assumption_overrides: ov, use_reference_playbooks: useRef_, use_llm: useLlm, confirm_paid_calls: useLlm,
      })
      const t = setInterval(async () => {
        try {
          const j = await api.job(job_id)
          setJob(j); setDone(j.stages_done ?? [])
          if (j.status === 'done') { clearInterval(t); setTimeout(() => nav(`/a/${j.session_id}/overview`), 500) }
          if (j.status === 'error') { clearInterval(t); setErr(j.error) }
        } catch (e) { clearInterval(t); setErr((e as Error).message) }
      }, 500)
    } catch (e) { setErr((e as Error).message); setStep(2) }
  }

  const STAGE_LABEL: Record<string, string> = {
    validate: 'Validating merchant records', score: 'Analysing merchant signals', queue: 'Building the priority queue',
    recommend: 'Preparing recommendations', llm: 'Claude review and drafting', insights: 'Building portfolio insights',
  }
  const set = (k: string, v: any) => setCfg((c) => ({ ...c, [k]: v }))
  const toggle = (k: string, v: string) => set(k, cfg[k].includes(v) ? cfg[k].filter((x: string) => x !== v) : [...cfg[k], v])
  const segs = ['Small', 'Mid', 'Enterprise']
  const inds: string[] = info?.quality ? Array.from(new Set((info.preview?.rows ?? []).map((r: any[]) => r[info.preview.columns.indexOf(mapping.industry ?? '')]).filter(Boolean))) as string[] : []

  return (
    <div className="min-h-full bg-bg">
      <header className="flex items-center justify-between border-b border-line bg-white px-6 py-3">
        <div className="flex items-center gap-4"><button className="btn-ghost" onClick={() => nav('/')}><ArrowLeft size={14} /> Home</button><Logo height={28} showMissing={false} /></div>
        <Stepper step={step} />
      </header>
      <div className="mx-auto max-w-[1120px] px-6 py-6">
        {step === 0 && (
          <div className="mx-auto max-w-2xl">
            <h1 className="h-page">Start a new analysis</h1>
            <p className="mb-5 mt-1 text-[13px] text-mute">Upload the merchant workbook. Nothing is analysed until you have reviewed what was detected.</p>
            <Dropzone busy={busy} error={err} onFile={(f) => ingest(api.upload(f))} />
            {health.sample_available && (
              <div className="mt-5 rounded-lg border border-line bg-white p-4">
                <p className="text-[13px] font-medium">Using the Problem 2 data pack?</p>
                <p className="mt-0.5 text-[12.5px] text-mute">The supplied workbook (P2_Merchants, P2_Playbooks, P2_Assumptions) is in this project.</p>
                <button className="btn-secondary mt-3" disabled={busy} onClick={() => ingest(api.sample())}>Use the supplied Problem 2 workbook</button>
              </div>
            )}
          </div>
        )}

        {step === 1 && info && (
          <div className="space-y-5">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div><h1 className="h-page">Review what was detected</h1><p className="mt-1 text-[13px] text-mute">{info.file_name} · {info.size_kb} KB · {info.sheets.length} sheet(s)</p></div>
              <button className="btn-ghost" onClick={() => { setInfo(null); setStep(0) }}>Replace file</button>
            </div>
            {err && <Notice tone="bad">{err}</Notice>}
            {info.error && <Notice tone="bad">{info.error}</Notice>}

            {info.sheet_selection && (
              <Notice tone={info.sheet_selection.excluded.length ? 'info' : 'ok'} title="Worksheets selected for the Problem 2 analysis">
                <p><span className="font-medium">Used:</span> {info.sheet_selection.selected.map((x: Dict) => `${x.name} (${x.role})`).join(', ') || 'none found'}.</p>
                {info.sheet_selection.excluded.length > 0 && <p className="mt-1"><span className="font-medium">Excluded, not analysed:</span> {info.sheet_selection.excluded.map((x: Dict) => x.name).join(', ')}. These belong to other problem statements. Nothing from them is read into this analysis.</p>}
                {info.sheet_selection.not_used.length > 0 && <p className="mt-1"><span className="font-medium">Not used:</span> {info.sheet_selection.not_used.join(', ')}.</p>}
                {info.sheet_selection.overridden_into_other_problem.length > 0 && <p className="mt-1 font-medium text-bad">You have assigned a worksheet from another problem statement ({info.sheet_selection.overridden_into_other_problem.join(', ')}). Check this is intended.</p>}
              </Notice>)}

            <Card title="Worksheets" sub="Roles were detected from the headers. Change them if a sheet was identified wrongly.">
              <table className="w-full">
                <thead><tr><th className="th">Sheet</th><th className="th">Detected role</th><th className="th">Rows</th><th className="th">Columns</th></tr></thead>
                <tbody>
                  {info.sheets.map((s: Dict) => (
                    <tr key={s.name}>
                      <td className="td font-medium">{s.name}{s.role === 'excluded' && <span className="mt-0.5 block text-[11.5px] font-normal text-mute">{s.reason}</span>}</td>
                      <td className="td">
                        <select className="input !w-44" value={info.merchant_sheet === s.name ? 'merchants' : info.playbook_sheet === s.name ? 'playbooks' : info.assumption_sheet === s.name ? 'assumptions' : 'ignore'}
                          onChange={(e) => { const r = e.target.value; reinspect({ merchant_sheet: r === 'merchants' ? s.name : info.merchant_sheet, playbook_sheet: r === 'playbooks' ? s.name : info.playbook_sheet === s.name ? null : info.playbook_sheet, assumption_sheet: r === 'assumptions' ? s.name : info.assumption_sheet === s.name ? null : info.assumption_sheet, mapping: undefined }) }}>
                          <option value="merchants">Merchant records</option><option value="playbooks">Playbooks</option><option value="assumptions">Assumptions</option><option value="ignore">Ignore</option>
                        </select>
                      </td>
                      <td className="td num">{s.rows}</td><td className="td num">{s.cols}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>

            {q && (
              <Card title="Data quality" sub="Missing data is treated as unknown. It is never filled in and never read as poor performance.">
                <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
                  {[['Records detected', q.total_records], ['Unique merchant IDs', q.unique_ids], ['Duplicate IDs', q.duplicate_ids.length], ['Invalid values', q.invalid_count], ['Ready to analyse', q.analysable_records]].map(([l, v]) => (
                    <div key={l as string} className="rounded-md bg-bg p-3"><p className="label">{l}</p><p className="num mt-1 text-[22px] font-semibold">{v}</p></div>
                  ))}
                </div>
                <div className="mt-4 grid gap-5 md:grid-cols-2">
                  <div>
                    <p className="label mb-1.5">Missing values by field</p>
                    <div className="max-h-52 overflow-auto scroll-thin">
                      <table className="w-full"><tbody>
                        {q.missing_by_field.filter((m: Dict) => m.missing > 0).map((m: Dict) => <tr key={m.field}><td className="td">{m.label}</td><td className="td num text-right">{m.missing} <span className="text-mute">({m.pct}%)</span></td></tr>)}
                        {q.missing_by_field.every((m: Dict) => m.missing === 0) && <tr><td className="td text-mute">No missing values in mapped fields.</td></tr>}
                      </tbody></table>
                    </div>
                  </div>
                  <div className="space-y-2">
                    {q.duplicate_ids.length > 0 && <Notice tone="warn" title={`Duplicate IDs: ${q.duplicate_ids.slice(0, 6).join(', ')}`}>The first occurrence is kept; later rows are excluded and listed.</Notice>}
                    {q.invalid_count > 0 && <Notice tone="warn" title={`${q.invalid_count} invalid value(s)`}>{q.invalid_records.slice(0, 3).map((i: Dict) => `Row ${i.row}: ${i.field} "${i.value}" (${i.issue})`).join('; ')}. These cells are treated as missing.</Notice>}
                    {Object.keys(q.reformatted_cells).length > 0 && <Notice tone="info" title="Inconsistent formats converted">{Object.entries(q.reformatted_cells).map(([k, v]) => `${k}: ${v} cell(s)`).join('; ')} contained text such as %, commas or currency symbols.</Notice>}
                    {q.excluded_records.length > 0 && <Notice tone="warn" title={`${q.excluded_records.length} record(s) will be excluded`}>{q.excluded_records.slice(0, 3).map((e: Dict) => `${e.merchant_id ?? 'row ' + e.row}: ${e.reason}`).join('; ')}</Notice>}
                    {q.impact.map((i: Dict) => <Notice key={i.field} tone="info" title={`${i.label} not available`}>{i.effect}</Notice>)}
                  </div>
                </div>
              </Card>
            )}

            <Card title="Field mapping" sub="Match your columns to the fields EDGE expects. Auto-detected matches are marked; anything you change is used as-is. No column is discarded."
              action={<Badge tone="brand">{Object.values(mapping).filter(Boolean).length} of {info.fields.length} mapped</Badge>}>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead><tr><th className="th">Uploaded field</th><th className="th">Expected field</th><th className="th">Status</th></tr></thead>
                  <tbody>
                    {info.fields.map((f: Dict) => (
                      <tr key={f.key}>
                        <td className="td w-[360px]">
                          <Select value={mapping[f.key] ?? ''} onChange={(v) => { const m = { ...mapping, [f.key]: v || null }; setMapping(m); reinspect({ mapping: m }) }}
                            options={[{ value: '', label: '— not in workbook —' }, ...info.columns.map((c: Dict) => ({ value: c.column, label: `${c.column}  (${c.kind})` }))]} />
                        </td>
                        <td className="td"><span className="font-medium">{f.label}</span> <span className="text-mute">· {f.key}</span> {f.required && <span className="text-bad">*</span>}</td>
                        <td className="td">{mapping[f.key] ? (f.status === 'mapped' ? <Badge tone="ok">Mapped</Badge> : <Badge tone="warn">Confirm</Badge>) : <Badge tone={f.required ? 'bad' : 'neutral'}>{f.required ? 'Required, unavailable' : 'Unavailable'}</Badge>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {q?.unmapped_source_columns?.length > 0 && <p className="mt-3 text-[12.5px] text-mute">Columns not used by any field (kept in the preview): {q.unmapped_source_columns.join(', ')}</p>}
            </Card>

            <Card title="Playbooks and assumptions" sub="Taken from the workbook. Workbook values always take precedence.">
              <div className="grid gap-5 md:grid-cols-2">
                <div>
                  <p className="label mb-1.5">Playbooks {info.playbooks.present ? `(${info.playbooks.rows.length})` : ''}</p>
                  {info.playbooks.present ? <ul className="space-y-1 text-[13px]">{info.playbooks.rows.map((p: Dict) => <li key={p.playbook_id}><span className="font-medium">{p.playbook_id}</span> {p.name}</li>)}</ul>
                    : <Notice tone="warn" title="No playbook sheet detected">Select a sheet above, or explicitly confirm the reference playbooks from the Problem 2 pack.</Notice>}
                </div>
                <div>
                  <p className="label mb-1.5">Assumptions</p>
                  <ul className="space-y-1 text-[13px]">
                    {info.assumptions.provenance.map((p: Dict) => <li key={p.key}><span className="text-mute">{p.label}:</span> <span className="num font-medium">{Array.isArray(p.value) ? p.value.join(', ') : p.value}</span></li>)}
                  </ul>
                  {info.assumptions.unresolved.length > 0 && (
                    <div className="mt-3 space-y-2">
                      <Notice tone="warn" title="Not found in the workbook">Supply these values. They will be recorded as manager-supplied, not as workbook assumptions.</Notice>
                      {info.assumptions.unresolved.map((k: string) => (
                        <label key={k} className="block"><span className="label">{info.assumptions.labels[k]}</span>
                          <input className="input mt-1" placeholder={k === 'seasonal_industries' ? 'Comma-separated industries' : k === 'net_revenue_rate' ? 'e.g. 1 for 1%' : 'Number'} value={overrides[k] ?? ''} onChange={(e) => setOverrides({ ...overrides, [k]: e.target.value })} />
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              {(!info.playbooks.present || !info.assumptions.present) && (
                <label className="mt-4 flex items-start gap-2 text-[13px]"><input type="checkbox" className="mt-0.5 accent-brand" checked={useRef_} onChange={(e) => setUseRef(e.target.checked)} />
                  <span>Use the Problem 2 reference {!info.playbooks.present && 'playbooks'}{!info.playbooks.present && !info.assumptions.present && ' and '}{!info.assumptions.present && 'assumptions'} for the missing sheet(s). I understand these were not part of my upload.</span></label>
              )}
            </Card>

            <Card title="Data preview" action={<Segmented value={tab} onChange={setTab} options={[{ value: 'sample', label: 'Sample (10)' }, { value: 'all', label: 'Complete data' }]} />}>
              <PreviewTable data={info.preview} limit={tab === 'sample' ? 10 : undefined} />
            </Card>

            <div className="sticky bottom-0 -mx-6 border-t border-line bg-white/95 px-6 py-3 backdrop-blur">
              <div className="mx-auto flex max-w-[1120px] flex-wrap items-center justify-between gap-3">
                <label className="flex items-center gap-2 text-[13px]"><input type="checkbox" className="accent-brand" checked={reviewed} onChange={(e) => setReviewed(e.target.checked)} />I have reviewed the detected data and mapping</label>
                <div className="flex items-center gap-3">
                  {blockers.length > 0 && <span className="max-w-md text-[12px] text-bad">{blockers[0]}</span>}
                  {q?.unmapped_optional?.length > 0 && blockers.length === 0 && <span className="text-[12px] text-mute">Some assessments will be less reliable (see notes above).</span>}
                  <button className="btn-primary" disabled={!reviewed || blockers.length > 0 || busy} onClick={() => setStep(2)}>Continue to configuration</button>
                </div>
              </div>
            </div>
          </div>
        )}

        {step === 2 && info && (
          <div className="mx-auto max-w-3xl space-y-5">
            <div><h1 className="h-page">Analysis configuration</h1><p className="mt-1 text-[13px] text-mute">These choices only re-order the merchants the engine already considers eligible. No numeric weights are introduced; every change in order can be traced to a stated rule.</p></div>
            {err && <Notice tone="bad">{err}</Notice>}
            <Card title="Analysis name"><input className="input" value={name} onChange={(e) => setName(e.target.value)} /></Card>
            <Card title="Outreach capacity" sub={`Workbook default: ${info.assumptions.values.max_outreaches ?? 'not stated'} merchants.`}>
              <label className="flex items-center gap-3 text-[13px]">Maximum merchants to contact this month
                <input type="number" min={1} max={100} className="input !w-24" value={cfg.capacity} onChange={(e) => set('capacity', Math.max(1, Number(e.target.value) || 1))} /></label>
            </Card>
            <Card title="Business priorities" sub="Merchants that match more of the selected priorities are considered first. Select none to rank by the chosen risk focus alone.">
              <div className="grid gap-2 md:grid-cols-2">
                {Object.entries(PRIORITY).map(([k, l]) => (
                  <label key={k} className={clsx('flex cursor-pointer items-start gap-2 rounded-md border p-2.5 text-[13px]', cfg.priorities.includes(k) ? 'border-brand bg-brand-soft' : 'border-line')}>
                    <input type="checkbox" className="mt-0.5 accent-brand" checked={cfg.priorities.includes(k)} onChange={() => toggle('priorities', k)} />
                    <span><span className="font-medium">{l}</span><span className="block text-[11.5px] text-mute">{PRIORITY_RULE[k]}</span></span>
                  </label>
                ))}
              </div>
            </Card>
            <Card title="Risk preference" sub="Used to order merchants that match the same number of priorities.">
              <Select value={cfg.risk_focus} onChange={(v) => set('risk_focus', v)} options={Object.entries(FOCUS).map(([value, label]) => ({ value, label }))} className="max-w-xs" />
            </Card>
            <Card title="Merchant scope" sub="Leave empty to include everyone.">
              <div className="space-y-3">
                <div><p className="label mb-1.5">Segments to include</p><div className="flex gap-4">{segs.map((s) => <label key={s} className="flex items-center gap-1.5 text-[13px]"><input type="checkbox" className="accent-brand" checked={cfg.segments.includes(s)} onChange={() => toggle('segments', s)} />{s === 'Mid' ? 'Mid-market' : s}</label>)}</div></div>
                <div><p className="label mb-1.5">Renewal window</p>
                  <Select value={String(cfg.renewal_window ?? '')} onChange={(v) => set('renewal_window', v ? Number(v) : null)} className="max-w-xs"
                    options={[{ value: '', label: 'Any renewal date' }, { value: '30', label: 'Within 30 days' }, { value: '60', label: 'Within 60 days' }, { value: '90', label: 'Within 90 days' }]} /></div>
                {inds.length > 0 && <div><p className="label mb-1.5">Exclude business categories</p><div className="flex flex-wrap gap-x-4 gap-y-1.5">{inds.map((s) => <label key={s} className="flex items-center gap-1.5 text-[13px]"><input type="checkbox" className="accent-brand" checked={cfg.exclude_industries.includes(s)} onChange={() => toggle('exclude_industries', s)} />{s}</label>)}</div></div>}
              </div>
            </Card>
            <Card title="Claude-assisted review" sub="Optional. Adds plain-language interpretation of notes, extra checks and personalised drafts.">
              <label className="flex items-start gap-2 text-[13px]"><input type="checkbox" className="mt-0.5 accent-brand" disabled={!health.llm_available} checked={useLlm} onChange={(e) => (e.target.checked ? setConfirmLlm(true) : setUseLlm(false))} />
                <span>Use Claude ({health.model ?? 'model'}) {!health.llm_available && <span className="text-mute">· No API key found in <code>.env</code>; the analysis runs fully without it.</span>}
                  <span className="block text-[12px] text-mute">Scores, ranks and playbooks stay deterministic. Claude cannot change them.</span></span></label>
            </Card>
            <div className="flex items-center justify-between">
              <div className="flex gap-2"><button className="btn-secondary" onClick={() => setStep(1)}>View data quality</button><button className="btn-ghost" onClick={() => setCfg({ ...DEFAULT_CFG, capacity: info.assumptions.values.max_outreaches ?? 15 })}>Reset configuration</button>
                <button className="btn-ghost" onClick={async () => { await api.saveSettings({ default_capacity: cfg.capacity, default_risk_focus: cfg.risk_focus }); setSaved(true) }}>{saved ? 'Saved' : 'Save configuration'}</button></div>
              <button className="btn-primary !px-4 !py-2" onClick={run}>Run analysis</button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="mx-auto max-w-lg py-10">
            <h1 className="h-page">{err ? 'Analysis stopped' : 'Analysing your portfolio'}</h1>
            {err ? <div className="mt-4 space-y-3"><Notice tone="bad" title="Could not complete the analysis">{err}</Notice><button className="btn-secondary" onClick={() => { setErr(null); setStep(2) }}>Back to configuration</button></div> : (
              <div className="card mt-5 p-5">
                <div className="h-1.5 overflow-hidden rounded-full bg-slate-100"><div className="h-full bg-brand transition-all duration-500" style={{ width: `${Math.round((job?.progress ?? 0.03) * 100)}%` }} /></div>
                <ul className="mt-4 space-y-2 text-[13.5px]">
                  {done.map((s) => <li key={s} className="flex items-center gap-2 text-mute"><Check size={14} className="text-ok" />{STAGE_LABEL[s]}</li>)}
                  {job?.status !== 'done' && <li className="flex items-center gap-2 font-medium"><Loader2 size={14} className="animate-spin text-brand" />{job?.label ?? 'Starting'}</li>}
                  {job?.status === 'done' && <li className="flex items-center gap-2 font-medium"><Check size={14} className="text-ok" />Analysis complete. Opening overview…</li>}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      <Modal open={confirmLlm} onClose={() => setConfirmLlm(false)} title="Run Claude-assisted analysis?"
        footer={<><button className="btn-secondary" onClick={() => setConfirmLlm(false)}>Cancel</button><button className="btn-primary" onClick={() => { setUseLlm(true); setConfirmLlm(false) }}>Yes, allow paid API calls</button></>}>
        <p>This sends one merchant at a time (pseudonymous ID, metrics and the account-manager note) to the Anthropic API. It makes roughly <strong>{(info?.quality?.analysable_records ?? 100) + (cfg.capacity ?? 15)}</strong> paid calls and can take several minutes.</p>
        <p className="mt-2 text-mute">Without it, the full analysis, explanations and template drafts still work. Claude never changes scores, ranks or playbooks.</p>
      </Modal>
    </div>
  )
}
