import { api, type Dict } from './api'

/** Polls a background job until it finishes. Rejects with the job's error message. */
export async function waitForJob(jobId: string, onProgress?: (j: Dict) => void): Promise<Dict> {
  for (;;) {
    const j = await api.job(jobId)
    onProgress?.(j)
    if (j.status === 'done') return j
    if (j.status === 'error') throw new Error(j.error ?? 'The job failed')
    await new Promise((r) => setTimeout(r, 700))
  }
}
