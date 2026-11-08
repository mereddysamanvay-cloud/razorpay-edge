# Source audit

Generated 2026-11-08 23:42 by `scripts/make_source_audit.py`.

## Workbook
- File: `Buildathon_Student_Data_Pack.xlsx`
- SHA-256: `9dd4af798e75d4527796a6011bcfba24517158c6e598c60ac5dddba6ff08201b`
- Sheets in file: README, P1_Tickets, P1_Merchants, P1_KnowledgeBase, P2_Merchants, P2_Playbooks, P2_Assumptions, P3_Applications, P3_RejectionCatalog
- Sheets used: P2_Merchants, P2_Playbooks, P2_Assumptions (all others ignored)

| Sheet | Data rows | Columns |
|---|---:|---:|
| P2_Merchants | 100 | 21 |
| P2_Playbooks | 6 | 4 |
| P2_Assumptions | 7 | 2 |

## Integrity checks
- Merchants: **100**; unique IDs: **100**; duplicate IDs: **0**.
- success_rate_m1_m3_pct outside 0-100: 0
- success_rate_m4_m6_pct outside 0-100: 0
- last_csat_1_to_5 outside 1-5: 0
- negative TPV values: 0
- negative counts (tickets/unresolved/logins/products): 0
- Unresolved tickets exceed 90-day ticket count for 5 merchants (C2044, C2073, C2081, C2087, C2094); likely older open tickets, unconfirmed. Scoring uses unresolved counts as given.
- Excluded records: **0** (no row failed validation).

## Missing values by column (P2_Merchants)
| Column | Missing | Share |
|---|---:|---:|
| last_csat_1_to_5 | 22 | 22% |
| account_manager_note | 39 | 39% |

Missing CSAT and missing notes are treated as unknown: they lower evidence completeness and add no risk points.

## Units and definitions
- TPV columns: Rs lakh per month (1 lakh = 100,000). `tpv_m6` is the latest month.
- Success rate: two period aggregates (M1-M3, M4-M6) only; no monthly series exists and none is derived.
- Logins, products used, tickets and CSAT are current snapshots, not trends.
- Account-manager notes are unverified free text.
- No churn labels exist in the workbook, so no accuracy, precision, recall or probability can be computed.

## Assumptions (verbatim from P2_Assumptions)
| Item | Assumption |
|---|---|
| Net revenue | Razorpay earns about 1% of TPV as net revenue (assumption for this exercise). |
| Time horizon | 'Churn' means the merchant moves most of its volume away within the next 90 days. |
| Cost of a false alarm | 1.5 hours of CSM time per outreach, valued at Rs 1,500. |
| Value of a saved merchant | Net revenue for 12 months at the merchant's most recent monthly TPV (m6). |
| TPV unit | All TPV figures are in Rs lakh per month (1 lakh = 100,000). |
| Seasonality | Gifting, Education and Travel merchants have seasonal dips that are not churn. |
| Capacity | The CSM team can run at most 15 proactive outreaches this month. |

How the app reads them: net revenue 1% of TPV; churn horizon 90 days; false-alarm cost Rs 1,500 per outreach (confirmed by the user on 2026-11-08 as the total, not per hour); saved-merchant value = 12 months at M6 TPV; seasonal = Gifting, Education, Travel; capacity 15.

## Playbooks (verbatim from P2_Playbooks)
| ID | Name | What happens | When it applies |
|---|---|---|---|
| PB-1 | Performance deep-dive | Joint call with merchant and Payments Ops to review success-rate drop by method/bank; share fix plan within 3 days. | Success rate fell sharply or merchant complains of failures |
| PB-2 | Support recovery | CSM takes ownership of all open tickets, gives a single point of contact and a closure date; senior callback within 48 hours. | Multiple unresolved tickets, low CSAT |
| PB-3 | Commercial review | Account Manager reviews rate card, volume tiers and renewal terms before the renewal date. | Competitor mention, renewal within ~60 days |
| PB-4 | Re-engagement and adoption | Executive-sponsor outreach plus a short workshop on unused products and reports; re-confirm the right contact person. | Low logins, few products used, no response to outreach |
| PB-5 | Growth / expansion check-in | Positive check-in; offer new products or higher-limit plans. | Healthy and growing |
| PB-6 | Monitor only | No outreach; keep on watchlist and re-check next month. | Seasonal dip, low-volume stable, or no real risk signal |
