/* eslint-disable @typescript-eslint/no-explicit-any */
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts'
import { DRIVER_SHORT, inr, isNum } from '../lib/format'
import type { M } from '../lib/session'

export const C = { ok: '#17A67D', warn: '#E9A23B', bad: '#C23B3B', brand: '#355CFF', navy: '#10213E', mute: '#94A3B8', grid: '#E3E8F0', soft: '#9DB2FF' }
export const BAND_COLOR: Record<string, string> = { low: C.ok, medium: C.warn, high: C.bad }
const axis = { fontSize: 11, fill: '#5B6B82' }
const tip = { contentStyle: { borderRadius: 6, border: '1px solid #E5EAF2', fontSize: 12, boxShadow: '0 8px 24px rgba(23,43,77,0.12)' } }

export function ChartBox({ h = 240, children, caption }: { h?: number; children: React.ReactElement; caption?: string }) {
  return (
    <div>
      <div style={{ height: h }}><ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer></div>
      {caption && <p className="mt-2 text-[11.5px] leading-snug text-mute">{caption}</p>}
    </div>
  )
}

export function RiskDonut({ ms, onPick }: { ms: M[]; onPick?: (band: string) => void }) {
  const data = (['high', 'medium', 'low'] as const).map((b) => ({ band: b, name: b === 'high' ? 'High' : b === 'medium' ? 'Moderate' : 'Low', value: ms.filter((m) => m.risk_band === b).length }))
  return (
    <div className="flex items-center gap-4">
      <div className="h-[190px] w-[190px] shrink-0">
        <ResponsiveContainer><PieChart>
          <Pie data={data} dataKey="value" innerRadius={55} outerRadius={85} paddingAngle={2} stroke="none" onClick={(d: any) => onPick?.(d.band)} cursor={onPick ? 'pointer' : undefined}>
            {data.map((d) => <Cell key={d.band} fill={BAND_COLOR[d.band]} />)}
          </Pie>
          <Tooltip {...tip} formatter={(v: any, n: any) => [`${v} merchants`, n]} />
        </PieChart></ResponsiveContainer>
      </div>
      <ul className="space-y-2 text-[13px]">
        {data.map((d) => (
          <li key={d.band}><button className="flex items-center gap-2 hover:underline" onClick={() => onPick?.(d.band)}>
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: BAND_COLOR[d.band] }} /><span className="num font-semibold">{d.value}</span><span className="text-mute">{d.name} risk</span></button></li>
        ))}
      </ul>
    </div>
  )
}

export function SegmentStack({ ms }: { ms: M[] }) {
  const data = ['Small', 'Mid', 'Enterprise'].map((s) => ({
    segment: s === 'Mid' ? 'Mid-market' : s, High: ms.filter((m) => m.segment === s && m.risk_band === 'high').length,
    Moderate: ms.filter((m) => m.segment === s && m.risk_band === 'medium').length, Low: ms.filter((m) => m.segment === s && m.risk_band === 'low').length,
  }))
  return (
    <ChartBox h={220} caption="Merchants per segment, split by risk category.">
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 12 }}>
        <CartesianGrid horizontal={false} stroke={C.grid} />
        <XAxis type="number" tick={axis} allowDecimals={false} /><YAxis type="category" dataKey="segment" tick={axis} width={78} />
        <Tooltip {...tip} cursor={{ fill: '#F1F5F9' }} /><Legend iconType="square" wrapperStyle={{ fontSize: 11 }} />
        <Bar dataKey="High" stackId="a" fill={C.bad} /><Bar dataKey="Moderate" stackId="a" fill={C.warn} /><Bar dataKey="Low" stackId="a" fill={C.ok} />
      </BarChart>
    </ChartBox>
  )
}

export function DriverBars({ drivers, onPick }: { drivers: any[]; onPick?: (key: string) => void }) {
  const data = [...drivers].sort((a, b) => b.merchants - a.merchants).map((d) => ({ key: d.key, name: d.name, merchants: d.merchants }))
  return (
    <ChartBox h={200} caption="Primary driver among moderate and high-risk merchants. Select a bar to list the merchants.">
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24 }}>
        <CartesianGrid horizontal={false} stroke={C.grid} />
        <XAxis type="number" tick={axis} allowDecimals={false} /><YAxis type="category" dataKey="name" tick={axis} width={150} />
        <Tooltip {...tip} cursor={{ fill: '#F1F5F9' }} formatter={(v: any) => [`${v} merchants`, 'Count']} />
        <Bar dataKey="merchants" fill={C.brand} radius={[0, 3, 3, 0]} cursor="pointer" onClick={(d: any) => onPick?.(d.key)} label={{ position: 'right', fontSize: 11, fill: '#64748B' }} />
      </BarChart>
    </ChartBox>
  )
}

export function RenewalBars({ ms, onPick }: { ms: M[]; onPick?: (w: string) => void }) {
  const buckets = [['0-30 days', 0, 30], ['31-60', 31, 60], ['61-90', 61, 90], ['91-180', 91, 180], ['181+', 181, 1e9]] as const
  const data = buckets.map(([name, lo, hi]) => {
    const g = ms.filter((m) => m.renewal_days >= lo && m.renewal_days <= hi)
    return { name, High: g.filter((m) => m.risk_band === 'high').length, Moderate: g.filter((m) => m.risk_band === 'medium').length, Low: g.filter((m) => m.risk_band === 'low').length, hi }
  })
  return (
    <ChartBox h={220} caption="When contracts renew, split by risk category. Proximity alone does not raise a merchant's risk score.">
      <BarChart data={data} margin={{ left: -8, right: 8 }} onClick={(e: any) => e?.activePayload && onPick?.(String(e.activePayload[0].payload.hi))}>
        <CartesianGrid vertical={false} stroke={C.grid} /><XAxis dataKey="name" tick={axis} /><YAxis tick={axis} allowDecimals={false} />
        <Tooltip {...tip} cursor={{ fill: '#F1F5F9' }} /><Legend iconType="square" wrapperStyle={{ fontSize: 11 }} />
        <Bar dataKey="High" stackId="a" fill={C.bad} /><Bar dataKey="Moderate" stackId="a" fill={C.warn} /><Bar dataKey="Low" stackId="a" fill={C.ok} />
      </BarChart>
    </ChartBox>
  )
}

export function RiskValueScatter({ ms, onPick }: { ms: M[]; onPick?: (id: string) => void }) {
  const mk = (b: string) => ms.filter((m) => m.risk_band === b).map((m) => ({ id: m.id, name: m.name, x: m.risk_score, y: m.annual_value / 1e5, z: 1 }))
  const bands: [string, string][] = [['high', 'High risk'], ['medium', 'Moderate risk'], ['low', 'Low risk']]
  return (
    <ChartBox h={300} caption="Each point is a merchant. Top-right merchants combine high risk with high run-rate revenue; this is where attention has the most to protect. Select a point to open the profile.">
      <ScatterChart margin={{ left: 0, right: 16, top: 8, bottom: 8 }}>
        <CartesianGrid stroke={C.grid} />
        <XAxis type="number" dataKey="x" name="Risk score" tick={axis} domain={[0, 'dataMax + 5']} label={{ value: 'Risk score (heuristic, 0-100)', position: 'insideBottom', offset: -2, fontSize: 11, fill: '#64748B' }} />
        <YAxis type="number" dataKey="y" name="Annual run-rate revenue" tick={axis} width={48} label={{ value: 'Rs lakh / year', angle: -90, position: 'insideLeft', fontSize: 11, fill: '#64748B' }} />
        <ZAxis dataKey="z" range={[55, 55]} />
        <Tooltip {...tip} cursor={{ strokeDasharray: '3 3' }} content={({ payload }: any) => payload?.[0] ? (
          <div className="rounded-md border border-line bg-white px-3 py-2 text-[12px] shadow-pop"><p className="font-semibold">{payload[0].payload.name}</p>
            <p>Risk score {Math.round(payload[0].payload.x)} · {inr(payload[0].payload.y * 1e5)} / yr</p></div>) : null} />
        <Legend iconType="circle" wrapperStyle={{ fontSize: 11 }} />
        {bands.map(([b, l]) => <Scatter key={b} name={l} data={mk(b)} fill={BAND_COLOR[b]} fillOpacity={0.75} cursor="pointer" onClick={(d: any) => onPick?.(d.id)} />)}
        <ReferenceLine x={50} stroke={C.mute} strokeDasharray="4 4" label={{ value: 'High band', fontSize: 10, fill: '#64748B', position: 'top' }} />
      </ScatterChart>
    </ChartBox>
  )
}

export function TpvConcentration({ ms }: { ms: M[] }) {
  const tot = ms.reduce((a, m) => a + (m.tpv_m6 ?? 0), 0)
  const data = ['Small', 'Mid', 'Enterprise'].map((s) => {
    const g = ms.filter((m) => m.segment === s)
    return { segment: s === 'Mid' ? 'Mid-market' : s, 'Share of M6 TPV': +(g.reduce((a, m) => a + (m.tpv_m6 ?? 0), 0) / tot * 100).toFixed(1), 'Share of merchants': +(g.length / ms.length * 100).toFixed(1) }
  })
  return (
    <ChartBox h={220} caption="Share of latest-month TPV against share of merchants. A short bar for merchants and a long bar for TPV means volume is concentrated.">
      <BarChart data={data} margin={{ left: -8, right: 8 }}>
        <CartesianGrid vertical={false} stroke={C.grid} /><XAxis dataKey="segment" tick={axis} /><YAxis tick={axis} unit="%" />
        <Tooltip {...tip} cursor={{ fill: '#F1F5F9' }} formatter={(v: any) => `${v}%`} /><Legend iconType="square" wrapperStyle={{ fontSize: 11 }} />
        <Bar dataKey="Share of merchants" fill={C.soft} /><Bar dataKey="Share of M6 TPV" fill={C.brand} />
      </BarChart>
    </ChartBox>
  )
}

export function TpvLine({ m }: { m: M }) {
  const data = m.tpv.map((v: number, i: number) => ({ month: `M${i + 1}`, tpv: v, chg: i ? (m.tpv[i - 1] ? ((v - m.tpv[i - 1]) / m.tpv[i - 1]) * 100 : null) : null }))
  const early = m.tpv.slice(0, 3).reduce((a: number, b: number) => a + b, 0) / 3
  const recent = m.tpv.slice(3).reduce((a: number, b: number) => a + b, 0) / 3
  return (
    <ChartBox h={230} caption={`Observed monthly TPV in Rs lakh. Dashed lines mark the M1-M3 average (${early.toFixed(1)}) and M4-M6 average (${recent.toFixed(1)}) used in the comparison.`}>
      <LineChart data={data} margin={{ left: -8, right: 12, top: 8 }}>
        <CartesianGrid stroke={C.grid} vertical={false} /><XAxis dataKey="month" tick={axis} /><YAxis tick={axis} domain={['auto', 'auto']} />
        <Tooltip {...tip} content={({ payload, label }: any) => payload?.[0] ? (
          <div className="rounded-md border border-line bg-white px-3 py-2 text-[12px] shadow-pop"><p className="font-semibold">{label}: Rs {payload[0].value.toFixed(1)} L</p>
            {isNum(payload[0].payload.chg) && <p className="text-mute">{payload[0].payload.chg > 0 ? '+' : ''}{payload[0].payload.chg.toFixed(1)}% vs previous month</p>}</div>) : null} />
        <ReferenceLine y={early} stroke={C.mute} strokeDasharray="4 4" /><ReferenceLine y={recent} stroke={C.brand} strokeDasharray="4 4" />
        <Line type="monotone" dataKey="tpv" stroke={C.brand} strokeWidth={2.2} dot={{ r: 3.5, fill: C.brand }} activeDot={{ r: 5 }} />
      </LineChart>
    </ChartBox>
  )
}

export function ScenarioBars({ items }: { items: { name: string; value: number; kept: number; moved: number }[] }) {
  return (
    <ChartBox h={240} caption="Run-rate revenue (Rs lakh a year) represented by each shortlist.">
      <BarChart data={items} margin={{ left: -4, right: 8 }}>
        <CartesianGrid vertical={false} stroke={C.grid} /><XAxis dataKey="name" tick={axis} /><YAxis tick={axis} />
        <Tooltip {...tip} cursor={{ fill: '#F1F5F9' }} /><Bar dataKey="value" name="Run-rate Rs lakh" fill={C.brand} radius={[3, 3, 0, 0]} />
      </BarChart>
    </ChartBox>
  )
}

export { DRIVER_SHORT }

/** Distribution of risk scores in 10-point bins with the two category thresholds marked. Counts of merchants. */
export function ScoreHistogram({ ms, high, medium }: { ms: M[]; high: number; medium: number }) {
  const data = Array.from({ length: 10 }, (_, i) => ({ bin: `${i * 10}-${i === 9 ? 100 : i * 10 + 9}`, from: i * 10, merchants: ms.filter((m) => (i === 9 ? m.risk_score >= 90 : m.risk_score >= i * 10 && m.risk_score < i * 10 + 10)).length }))
  return (
    <ChartBox h={220} caption={`Merchants by risk score (count). Vertical lines mark Moderate at ${medium} and High at ${high}.`}>
      <BarChart data={data} margin={{ left: 0, right: 12, top: 8 }}>
        <CartesianGrid vertical={false} stroke={C.grid} />
        <XAxis dataKey="bin" tick={axis} /><YAxis tick={axis} allowDecimals={false} />
        <Tooltip {...tip} cursor={{ fill: '#F1F5F9' }} formatter={(v: any) => [`${v} merchants`, 'Count']} />
        <ReferenceLine x={data[Math.floor(medium / 10)].bin} stroke={C.warn} strokeDasharray="4 3" /><ReferenceLine x={data[Math.floor(high / 10)].bin} stroke={C.bad} strokeDasharray="4 3" />
        <Bar dataKey="merchants" fill={C.brand} radius={[3, 3, 0, 0]} label={{ position: 'top', fontSize: 11, fill: '#5B6B82' }} />
      </BarChart>
    </ChartBox>
  )
}
