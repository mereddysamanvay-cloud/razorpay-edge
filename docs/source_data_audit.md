# Source data audit (Gate 1)

_Generated 2026-11-08T16:49:52 | config 1.0.0_

## 1. Files and sheets inspected

- Workbook: `Buildathon_Student_Data_Pack.xlsx` (snapshot date per README sheet: **30 Sep 2026**, all datasets).
- Sheets in workbook: README, P1_Tickets, P1_Merchants, P1_KnowledgeBase, P2_Merchants, P2_Playbooks, P2_Assumptions, P3_Applications, P3_RejectionCatalog
- Sheets used: `P2_Merchants`, `P2_Playbooks`, `P2_Assumptions` (P1/P3 sheets ignored).
- PDF brief: `Razorpay_Campus_AI_Buildathon_Student_Brief.pdf` (Problem 2 on page 4).

| Sheet | Rows | Columns | Hidden rows/cols | Formula cells | Data validations |
|---|---|---|---|---|---|
| P2_Merchants | 100 | 21 | 0/0 | 0 | 0 |
| P2_Playbooks | 6 | 4 | 0/0 | 0 | 0 |
| P2_Assumptions | 7 | 2 | 0/0 | 0 | 0 |

## 2. Automated checks

| Check | Result | Detail |
|---|---|---|
| merchant sheet has all expected columns | PASS | found 21 columns |
| playbook sheet columns | PASS |  |
| assumption sheet columns | PASS |  |
| exactly 100 merchants loaded | PASS | loaded 100 |
| merchant_id unique | PASS | 0 duplicates |
| six playbooks PB-1..PB-6 | PASS |  |
| no source rows dropped (non-empty rows == rows loaded) | PASS |  |
| no impossible values | PASS |  |
| no unexpected missing values outside CSAT/note | PASS | 0 missing |
| seasonal industries from config exist in data | PASS | missing: [] |

**Data warnings (5):** `unresolved_tickets` exceeds `support_tickets_last_90d` for some merchants (open tickets older than the 90-day window are the likely explanation; unconfirmed). Scoring uses unresolved counts as given.

- C2044: unresolved_tickets (1) > support_tickets_last_90d (0) - likely older open tickets
- C2073: unresolved_tickets (1) > support_tickets_last_90d (0) - likely older open tickets
- C2081: unresolved_tickets (1) > support_tickets_last_90d (0) - likely older open tickets
- C2087: unresolved_tickets (1) > support_tickets_last_90d (0) - likely older open tickets
- C2094: unresolved_tickets (1) > support_tickets_last_90d (0) - likely older open tickets

## 3. Column dictionary (P2_Merchants)

| Column | Type | Meaning / unit | Missing | Min | Max |
|---|---|---|---|---|---|
| `merchant_id` | string | Unique merchant identifier (kept as text). | 0 (0%) |  |  |
| `business_name` | string | Fictional business name. | 0 (0%) |  |  |
| `segment` | category | Small / Mid / Enterprise. | 0 (0%) |  |  |
| `industry` | category | Business category; used for the seasonality rule. | 0 (0%) |  |  |
| `city` | category | City (not used in scoring). | 0 (0%) |  |  |
| `tenure_months` | number | Months since onboarding. | 0 (0%) | 8 | 60 |
| `tpv_m1_inr_lakh` | number | Monthly TPV in Rs lakh for month 1 (m6 = most recent). | 0 (0%) | 1 | 393.5 |
| `tpv_m2_inr_lakh` | number | Monthly TPV in Rs lakh for month 2 (m6 = most recent). | 0 (0%) | 1 | 389.9 |
| `tpv_m3_inr_lakh` | number | Monthly TPV in Rs lakh for month 3 (m6 = most recent). | 0 (0%) | 1 | 392.5 |
| `tpv_m4_inr_lakh` | number | Monthly TPV in Rs lakh for month 4 (m6 = most recent). | 0 (0%) | 1 | 405.2 |
| `tpv_m5_inr_lakh` | number | Monthly TPV in Rs lakh for month 5 (m6 = most recent). | 0 (0%) | 1 | 411.7 |
| `tpv_m6_inr_lakh` | number | Monthly TPV in Rs lakh for month 6 (m6 = most recent). | 0 (0%) | 1 | 430.7 |
| `success_rate_m1_m3_pct` | number | Payment success rate (%) aggregated over months 1-3. Period aggregate, not monthly. | 0 (0%) | 93 | 97.5 |
| `success_rate_m4_m6_pct` | number | Payment success rate (%) aggregated over months 4-6. Period aggregate. | 0 (0%) | 81.5 | 98.3 |
| `support_tickets_last_90d` | count | All support tickets in last 90 days (resolved + unresolved). | 0 (0%) | 0 | 8 |
| `unresolved_tickets` | count | Tickets still open. | 0 (0%) | 0 | 5 |
| `last_csat_1_to_5` | number | Most recent CSAT, 1 (worst) to 5. Blank = no survey response; NOT poor CSAT. | 22 (22%) | 1 | 5 |
| `products_used` | count | Number of Razorpay products in use (current snapshot only). | 0 (0%) | 1 | 5 |
| `logins_last_30d` | count | Dashboard logins in last 30 days (current snapshot only; no history). | 0 (0%) | 0 | 29 |
| `days_to_contract_renewal` | count | Days until contract renewal, as of snapshot date 30 Sep 2026. | 0 (0%) | 13 | 356 |
| `account_manager_note` | free text | Untrusted free text. Blank = no note recorded. | 39 (39%) |  |  |

## 4. Categorical distributions

**segment**: Small (63), Mid (26), Enterprise (11)

**industry**: Health & Pharmacy (12), Fitness & Sports (12), SaaS / Digital Services (11), Beauty & Wellness (10), Electronics (9), Apparel & Fashion (8), Gifting & Festive (8), Education / Coaching (7), Books & Stationery (7), Travel & Hospitality (6), Home & Furniture (5), Grocery & Food (5)

**city**: Mumbai (11), Hyderabad (10), Jaipur (10), Lucknow (10), Bengaluru (9), Ahmedabad (7), Indore (7), Kochi (7), Surat (6), Kolkata (6), Chandigarh (6), Pune (6), Chennai (4), Delhi NCR (1)

## 5. Account manager note vocabulary

The notes are templated (short, repeated phrases). Counts:

- 39 x (blank)
- 10 x Complained once about invoice format; fixed
- 6 x Growing fast; many integration questions, all resolved
- 6 x Asked about settlement reports; resolved
- 5 x Interested in adding subscriptions product
- 5 x Quarterly check-in done, no concerns
- 4 x Never raised tickets
- 4 x Seasonal dip as per last year pattern
- 3 x Seasonal business; volumes dip after the festive season every year
- 2 x Merchant complained about UPI drop-offs on last call
- 2 x Comparing quotes from two providers
- 2 x Dashboard rarely used since new manager joined
- 2 x Said 'we are exploring options'
- 1 x Owner handed operations to a new manager, unclear contact
- 1 x Small merchant, low touch
- 1 x Mentioned a competitor offering lower MDR
- 1 x Asked for a review of success rates; no clear answer yet
- 1 x Raised several tickets on settlements; still not closed
- 1 x Merchant said slow quarter after peak season, expects pickup
- 1 x Says support replies take too long
- 1 x No response to last two check-ins
- 1 x Escalated to AM twice this quarter
- 1 x Asked for the rate card ahead of renewal

## 6. Playbook catalogue (exact text from `P2_Playbooks`)

- **PB-1 - Performance deep-dive**: Joint call with merchant and Payments Ops to review success-rate drop by method/bank; share fix plan within 3 days. _When it applies:_ Success rate fell sharply or merchant complains of failures
- **PB-2 - Support recovery**: CSM takes ownership of all open tickets, gives a single point of contact and a closure date; senior callback within 48 hours. _When it applies:_ Multiple unresolved tickets, low CSAT
- **PB-3 - Commercial review**: Account Manager reviews rate card, volume tiers and renewal terms before the renewal date. _When it applies:_ Competitor mention, renewal within ~60 days
- **PB-4 - Re-engagement and adoption**: Executive-sponsor outreach plus a short workshop on unused products and reports; re-confirm the right contact person. _When it applies:_ Low logins, few products used, no response to outreach
- **PB-5 - Growth / expansion check-in**: Positive check-in; offer new products or higher-limit plans. _When it applies:_ Healthy and growing
- **PB-6 - Monitor only**: No outreach; keep on watchlist and re-check next month. _When it applies:_ Seasonal dip, low-volume stable, or no real risk signal

## 7. Assumptions catalogue (exact text from `P2_Assumptions`)

- **Net revenue**: Razorpay earns about 1% of TPV as net revenue (assumption for this exercise).
- **Time horizon**: 'Churn' means the merchant moves most of its volume away within the next 90 days.
- **Cost of a false alarm**: 1.5 hours of CSM time per outreach, valued at Rs 1,500.
- **Value of a saved merchant**: Net revenue for 12 months at the merchant's most recent monthly TPV (m6).
- **TPV unit**: All TPV figures are in Rs lakh per month (1 lakh = 100,000).
- **Seasonality**: Gifting, Education and Travel merchants have seasonal dips that are not churn.
- **Capacity**: The CSM team can run at most 15 proactive outreaches this month.

## 8. Limitations and open interpretation points

- **No churn labels.** Hidden by the organisers. No supervised training, accuracy, precision/recall or churn probability is possible or reported.
- Success rates are two **period aggregates** (M1-M3, M4-M6), not monthly series. Only the change in percentage points is computable.
- Logins, products and CSAT are **single snapshots**: no claim of decline over time can be made.
- CSAT is blank for a subset of merchants (treated as unknown, never as poor).
- `account_manager_note` is blank for a subset of merchants; notes are templated and treated as untrusted data.
- Assumption wording "Gifting, Education and Travel" is mapped to industries `Gifting & Festive`, `Education / Coaching`, `Travel & Hospitality` (interpretation, configurable).
- Only six months of TPV exist; no annual seasonal pattern can be learned. Seasonality is handled by a rule (industry in the supplied list AND a dip-then-rebound shape), and never exempts other risk signals.
- PB-3 text says renewal "within ~60 days": implemented as <= 60 days (configurable).
- The PDF says the team can run "at most 15 proactive outreaches"; it does not say whether PB-5 (growth check-in) counts. Default: PB-5/PB-6 do **not** use churn-outreach capacity (configurable, needs confirmation).
- No channel/consent rules were supplied: drafts are channel-neutral and are never sent.
