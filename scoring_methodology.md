# Scoring methodology (scoring version 1.1.0-hypothesis)

The risk score is a transparent 0-100 **risk-evidence** index. It is not a churn probability. No churn labels exist in the workbook, so no accuracy, precision, recall, AUC or calibration is claimed. All weights, scales and thresholds are design hypotheses held in `config/scoring.yaml`.

## 1. How a score is built

1. Four **dimension scores** (0-100 each): Performance, Relationship, Engagement, Commercial.
2. **Weighted mean** = sum(dimension x weight). Weights: Performance 35%, Relationship 25%, Commercial 25%, Engagement 15% (sum 100%).
3. **Total** = 0.8 x weighted mean + 0.2 x strongest dimension + convergence bonus, capped at 100.
4. **Convergence bonus** = 5 points for each dimension at or above 40 beyond the first, up to 15.
5. **Bands**: High 50 or more, Moderate 28 to 49.9, Low below 28.

Every total reconciles from the parts. The merchant record stores `score_parts` (weighted mean, strongest dimension, share, bonus, uncapped total and the weighted points of each dimension), and `tests/test_reconciliation.py` rebuilds the total from them.

### Why 0.8 (changed from 0.5 in v1.1.0)
At 0.5, one dimension alone at 100 scored 62 to 67 (High) and the Moderate band held 1 merchant (23 High, 1 Moderate, 76 Low). The rule chosen was: **no single dimension alone may reach High**. A single dimension at 100 scores 48.0 (Performance), 40.0 (Commercial), 40.0 (Relationship) and 32.0 (Engagement) at share 0.8; High therefore needs corroboration across dimensions. A severe single-dimension case lands in Moderate and is still flagged for human review by the critical triggers. The value was fixed from this rule and from the score distribution before the shortlist was examined; it was not tuned to produce a preferred top 15.

Result on the supplied workbook: 13 High, 11 Moderate, 76 Low. The shortlist moved by one merchant (C2022 out, C2034 in; 14 of 15 unchanged). Ten merchants moved from High to Moderate; the closest to the threshold are C2062 (49.7), C2084 (48.9) and C2018 (48.5).

### The 76 low-scoring merchants
76 merchants stay Low under every share from 0.5 to 0.9 that was tested, and from 0.6 upward none scores between 17 and 28. The gap between "no signal" and "some signal" comes from the data, not the formula: 24 merchants carry a real signal and the rest carry none. A wider Moderate band reflects how the formula treats the 24, not extra evidence.

## 2. Features

Overlap note: TPV change, last-month momentum and consecutive declines describe the same movement. Only the M4-M6 vs M1-M3 change is scored; consecutive declines only scale it (x0.3 to x1.0) and are never added separately.

| Dimension | Feature | Source column(s) | Transformation | Max points | Missing data | Contextual exceptions |
|---|---|---|---|---|---|---|
| Performance | TPV trend | tpv_m1..m6 | Average M4-M6 vs M1-M3; 0 at -5% or better, 100 at -40% or worse; x trend consistency 0.3-1.0 | 100 | Not applicable | Seasonal industry with dip and rebound: x0.25, TPV component only |
| Performance | Success-rate drop | success_rate_m1_m3_pct, success_rate_m4_m6_pct | Change in pp; 0 at -1pp, 100 at -10pp | 100 | Not applicable | none |
| Performance | Combination | | 0.75 x stronger + 0.25 x weaker of the two | 100 | | |
| Relationship | Unresolved tickets | unresolved_tickets | Steps 0, 25, 50, 65, 80, 100 for 0-5+ | 100 | | Resolved tickets are not penalised |
| Relationship | CSAT | last_csat_1_to_5 | 1=100, 2=75, 3=25, 4-5=0 | 100 | **Missing adds 0** (unknown, not poor) | |
| Relationship | Combination | | 0.7 x stronger + 0.3 x weaker, plus note points (complaint 20, escalation 25) | 100 | | Growing merchant with at most 1 unresolved ticket: x0.5 |
| Engagement | Logins (30 days) | logins_last_30d | Steps: <=2 100, <=5 80, <=10 45, <=15 15; counts 60% | 60 | | Current snapshot only |
| Engagement | Products used | products_used | 1 product 60, 2 products 20; counts 40% | 24 | | Current snapshot only |
| Engagement | Note signals | account_manager_note | unresponsive 40, decision-maker change 25 | 100 total cap | No note adds 0 | Small stable merchant (TPV change -5% or better, no note signal): x0.4 |
| Commercial | Competitor / pricing note | account_manager_note | competitor explicit 85, exploring options 65, rate-card request 50 (highest applies) | 100 | No note adds 0 | Note is unverified; shown as such |
| Commercial | Renewal proximity | days_to_contract_renewal | +15 within 30 days, +10 within 60, +5 within 90 | | | **Only added when a commercial signal exists**; renewal alone is not intent |

Driver naming: a dimension must reach 25 to be named a driver. The primary driver is the highest dimension.

## 3. Critical triggers (human-review flags)

| Trigger | Condition | Score impact | Slot impact | Test |
|---|---|---|---|---|
| severe_performance | TPV down 20% or more and success down 5pp or more | none | none | tests/test_scoring.py |
| competitor_near_renewal | Explicit competitor note and renewal within 30 days | none | none | tests/test_scoring.py |
| service_breakdown | 4 or more unresolved tickets and CSAT 2 or below | none | none | tests/test_scoring.py, test_reconciliation.py |
| silent_decline | 2 or fewer logins, 4 or more consecutive declines, TPV down 25% or more | none | none | tests/test_reconciliation.py |

Triggers set the "immediate review" flag only. They do not add points or reserve outreach slots. Flagged merchants that are not shortlisted are an open workflow question (Gate 5).

## 4. Priority is separate from risk

Risk answers "how much concern evidence exists". Priority answers "who should be contacted first with 15 slots".

`priority index = (risk weight x annual exposure - (1 - risk weight) x outreach cost) x renewal urgency`

- Risk weight = risk score / 100 x confidence factor. It is a ranking weight, **not** a save or churn probability.
- Annual exposure = M6 TPV (Rs lakh) x 100,000 x net revenue rate (1%) x 12.
- Outreach cost = Rs 1,500 per outreach (the workbook's 1.5 hours of CSM time valued at Rs 1,500; confirmed as a total, not hourly).
- Urgency multiplier rises as renewal approaches.
- Eligibility: playbook PB-1 to PB-4, band at least Moderate, and a positive index. PB-5 and PB-6 never receive outreach.
- Ordering: priority index, then risk score, then merchant ID. The top 15 are selected.

The index is a rupee-unit ranking aid. It is not an expected saving and no outcome data supports it.

## 5. Financial labels

- Annual net-revenue run-rate proxy = M6 TPV x 1% x 12. M6 is the latest monthly TPV, in Rs lakh.
- Revenue exposure = the run-rate of Moderate and High merchants. It is **not revenue lost** and **not expected savings**; the workbook has no churn outcomes.

## 6. Known limits

- Weights, scales and thresholds are hypotheses; sensitivity to them is tested in Gate 3.
- Engagement uses a current snapshot, so no adoption trend can be claimed.
- Notes are unverified; commercial signals depend entirely on them.
- Industry groups hold roughly 5 to 12 merchants, too few for reliable industry comparison.
