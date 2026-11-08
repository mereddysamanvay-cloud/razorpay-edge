/* eslint-disable @typescript-eslint/no-explicit-any */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, type Dict } from './api'

export interface M { id: string; name: string; [k: string]: any }

interface Ctx {
  sid: string
  s: Dict
  st: Dict
  merchants: M[]
  byId: Record<string, M>
  loading: boolean
  error: string | null
  patch: (p: Dict) => Promise<void>
  setSession: (s: Dict) => void
  reload: () => Promise<void>
  status: (id: string) => string
}

const C = createContext<Ctx | null>(null)
export const useSession = () => {
  const c = useContext(C)
  if (!c) throw new Error('No analysis loaded')
  return c
}

export function SessionProvider({ sid, children }: { sid: string; children: ReactNode }) {
  const [s, setS] = useState<Dict | null>(null)
  const [st, setSt] = useState<Dict>({})
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    try {
      const r = await api.session(sid)
      setS(r.session); setSt(r.state); setError(null)
    } catch (e) { setError((e as Error).message) }
  }, [sid])
  useEffect(() => { setS(null); reload() }, [reload])

  const patch = useCallback(async (p: Dict) => {
    // optimistic merge, server is the source of truth
    setSt((cur) => {
      const n = { ...cur }
      for (const [k, v] of Object.entries(p)) {
        if (v && typeof v === 'object' && !Array.isArray(v) && typeof cur[k] === 'object' && !Array.isArray(cur[k])) {
          const m = { ...cur[k] }
          for (const [kk, vv] of Object.entries(v as Dict)) { if (vv === null) delete m[kk]; else m[kk] = vv }
          n[k] = m
        } else n[k] = v
      }
      return n
    })
    try { setSt(await api.patchState(sid, p)) } catch (e) { setError((e as Error).message) }
  }, [sid])

  const merchants = useMemo(() => (s?.merchants ?? []) as M[], [s])
  const byId = useMemo(() => Object.fromEntries(merchants.map((m) => [m.id, m])), [merchants])
  const status = useCallback((id: string) => st.statuses?.[id] ?? 'not_contacted', [st])

  if (error && !s) return <div className="p-10 text-sm text-bad">Could not load this analysis: {error}</div>
  if (!s) return <div className="p-10 text-sm text-mute">Loading analysis…</div>
  return (
    <C.Provider value={{ sid, s, st, merchants, byId, loading: false, error, patch, setSession: setS, reload, status }}>
      {children}
    </C.Provider>
  )
}
