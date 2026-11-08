/* eslint-disable @typescript-eslint/no-explicit-any */
export type Dict = Record<string, any>

async function j<T = any>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`/api${path}`, init)
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`
    try { const b = await r.json(); msg = typeof b.detail === 'string' ? b.detail : JSON.stringify(b.detail ?? b) } catch { /* ignore */ }
    throw new Error(msg)
  }
  return r.json()
}
const post = (path: string, body?: unknown) =>
  j(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body ?? {}) })

export const api = {
  health: () => j('/health'),
  sessions: () => j<Dict[]>('/sessions'),
  session: (id: string) => j<{ session: Dict; state: Dict }>(`/sessions/${id}`),
  deleteSession: (id: string) => j(`/sessions/${id}`, { method: 'DELETE' }),
  upload: (file: File) => { const f = new FormData(); f.append('file', file); return j<Dict>('/uploads', { method: 'POST', body: f }) },
  sample: () => post('/uploads/sample'),
  inspect: (id: string, body: Dict) => post(`/uploads/${id}/inspect`, body),
  analyse: (body: Dict) => post('/analyses', body),
  job: (id: string) => j<Dict>(`/jobs/${id}`),
  patchState: (id: string, patch: Dict) => post(`/sessions/${id}/state`, patch),
  scenario: (id: string, spec: Dict, compare_to = 'baseline') => post(`/sessions/${id}/scenario`, { spec, compare_to }),
  applyScenario: (id: string, spec: Dict) => post(`/sessions/${id}/apply-scenario`, { spec }),
  ask: (id: string, question: string, context: Dict, history: Dict[]) => post(`/sessions/${id}/ask`, { question, context, history }),
  compare: (a: string, b: string) => j<Dict>(`/compare?a=${a}&b=${b}`),
  settings: () => j<Dict>('/settings'),
  saveSettings: (b: Dict) => j('/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  testLlm: () => post('/llm/test'),
  exportUrl: (id: string, kind: string, format: string) => `/api/sessions/${id}/export?kind=${kind}&format=${format}`,
}
