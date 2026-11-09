export const NA = 'Not available'

export const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)

export function inr(v: number | null | undefined, opts: { short?: boolean } = {}): string {
  if (!isNum(v)) return NA
  const a = Math.abs(v)
  if (a >= 1e7) return `Rs ${(v / 1e7).toFixed(2)} Cr`
  if (a >= 1e5) return `Rs ${(v / 1e5).toFixed(1)} L`
  if (a >= 1e3 && opts.short) return `Rs ${(v / 1e3).toFixed(0)}K`
  return `Rs ${Math.round(v).toLocaleString('en-IN')}`
}

export const lakh = (v: number | null | undefined, d = 1) => (isNum(v) ? `Rs ${v.toFixed(d)} L` : NA)
export const pct = (v: number | null | undefined, d = 0, sign = false) =>
  isNum(v) ? `${sign && v > 0 ? '+' : ''}${v.toFixed(d)}%` : NA
export const pp = (v: number | null | undefined) => (isNum(v) ? `${v > 0 ? '+' : ''}${v.toFixed(1)} pp` : NA)
export const num = (v: number | null | undefined, d = 0) => (isNum(v) ? v.toLocaleString('en-IN', { maximumFractionDigits: d }) : NA)

export function when(iso?: string | null): string {
  if (!iso) return NA
  const d = new Date(iso)
  return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export const initials = (name: string) =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join('')

export function hueFor(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 360
  return h
}

export const DRIVER: Record<string, string> = {
  performance: 'Payment & volume performance',
  relationship: 'Service experience',
  commercial: 'Pricing & competition',
  engagement: 'Disengagement',
}
export const DRIVER_SHORT: Record<string, string> = {
  performance: 'Performance', relationship: 'Service', commercial: 'Commercial', engagement: 'Engagement',
}
export const BAND: Record<string, string> = { low: 'Low risk', medium: 'Moderate risk', high: 'High risk' }
export const STATUS: Record<string, string> = {
  not_contacted: 'No draft', pending_review: 'Pending CSM review', reviewed: 'Reviewed / edits made', approved: 'Approved (not sent)',
  contacted: 'Contacted (recorded manually)', follow_up: 'Follow-up set', follow_up_due: 'Follow-up due', outcome_recorded: 'Outcome recorded', closed: 'Closed / monitor',
  draft_prepared: 'Pending CSM review', awaiting_response: 'Awaiting response', resolved: 'Resolved', escalated: 'Escalated',
}
export const STATUS_FLOW = ['pending_review', 'reviewed', 'approved', 'contacted', 'follow_up', 'follow_up_due', 'outcome_recorded', 'closed']
export const VALIDATED: Record<string, string> = { yes: 'Concern confirmed', partly: 'Partly confirmed', no: 'Concern not confirmed', unknown: 'Could not tell' }
export const ISSUE_CATEGORY: Record<string, string> = { payment_performance: 'Payment performance', service: 'Service or support', commercial: 'Pricing or commercial', engagement: 'Engagement or adoption', none: 'No issue found', other: 'Other' }
export const ACTION_TAKEN: Record<string, string> = { call: 'Call held', workshop: 'Workshop or training', ticket_closure: 'Tickets closed', commercial_review: 'Commercial review', payments_review: 'Payments review with Payments Ops', no_action: 'No action needed', other: 'Other' }
export const OUTCOMES: Record<string, string> = {
  issue_confirmed: 'Issue confirmed', commercial_review_scheduled: 'Commercial review scheduled', support_acknowledged: 'Support issue acknowledged', no_churn_concern: 'No churn concern',
  unreachable: 'Unreachable', wrong_contact: 'Wrong contact', follow_up_required: 'Follow-up required', declined: 'Declined', other: 'Other (free text)',
}
export const PRIORITY: Record<string, string> = {
  high_value: 'Protect high-value merchants', payment_performance: 'Address payment performance issues',
  renewals: 'Focus on upcoming renewals', service: 'Resolve service dissatisfaction',
  engagement: 'Improve merchant engagement', competitor: 'Prioritise explicit competitor threats',
}
export const FOCUS: Record<string, string> = {
  revenue: 'Revenue exposure', severity: 'Severity of deterioration', dissatisfaction: 'Relationship dissatisfaction',
  renewal: 'Renewal urgency', disengagement: 'Merchant disengagement',
}
export const PRIORITY_RULE: Record<string, string> = {
  high_value: 'Annual run-rate revenue in the top quartile of the portfolio',
  payment_performance: 'Payment-performance is the driver, or success rate fell 5 pp or more',
  renewals: 'Renewal due within 60 days',
  service: 'Service dimension of 25+ (unresolved tickets and/or low CSAT)',
  engagement: 'Engagement dimension of 25+ (very low logins or few products)',
  competitor: 'Account note records an explicit competitor mention',
}
