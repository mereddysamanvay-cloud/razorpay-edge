# Decision Intelligence: change report

Generated from scoring version **1.1.1-hypothesis** and the analysis **Problem 2 demo workspace** (EDGE 1.2 / config 1.0.0 / scoring 1.1.1-hypothesis).

## 1. Methodology actually implemented

EDGE is a rule-based, weighted additive scoring system. There is no machine-learning model and no churn probability. Not used anywhere: machine learning, logistic regression, random forests, gradient boosting, clustering, survival analysis, calibrated churn probabilities.

### Weights and thresholds in force

| Item | Value |
|---|---|
| Dimension weights (P / R / E / C) | 0.35 / 0.25 / 0.15 / 0.25 (sum 1) |
| Strongest-dimension share | 0.2 (weighted-mean share 0.8) |
| Convergence bonus | 5 per extra dimension at 40+, maximum 15 |
| Risk bands | High ≥ 50, Moderate ≥ 28, else Low |
| Driver minimum | 25 |
| Net revenue rate / months | 0.01 / 12 |
| Outreach cost | Rs 1,500 |
| Capacity | 15 |
| Confidence factor (High / Medium / Low) | 1.0 / 0.85 / 0.6 |

### Equations

**1. Weighted mean of the four dimension scores** (weighted additive scoring)

    WM = Σ (S_d × w_d) / Σ w_d

Each dimension score S_d (0 to 100) is multiplied by its weight and added up. Weights: Performance 0.35, Relationship 0.25, Engagement 0.15, Commercial 0.25 (they sum to 1).

**2. Final risk score** (weighted additive scoring with a strongest-dimension term)

    Score = min(100, 0.8 × WM + 0.2 × max(S_d) + Bonus)

0.8 of the score is the weighted mean; 0.2 is the single strongest dimension. The share is fixed by configuration, it is not a cap on a separate adjustment.

**3. Convergence bonus** (rule-based adjustment)

    Bonus = min(15, 5 × max(0, F − 1)),  F = number of dimensions with S_d ≥ 40

When several dimensions agree, up to 15 extra points are added: 5 for each dimension beyond the first that reaches 40.

**4. Capped linear scale (used for TPV change and success-rate change)** (capped linear normalisation)

    S = clamp( (x − x₀) / (x₁ − x₀) × 100, 0, 100 )

x₀ is the value that scores 0 and x₁ the value that scores 100; anything beyond is capped. TPV change: x₀ = -5%, x₁ = -40%. Success-rate change: x₀ = -1pp, x₁ = -10pp. This is NOT min-max scaling across merchants: the anchors are fixed business thresholds.

**5. Performance dimension** (weighted blend)

    S_perf = 0.75 × max(TPV, Success) + 0.25 × min(TPV, Success)

The worse of the two payment signals counts most, so a single severe signal is not diluted by the other being healthy.

**6. TPV trend consistency and seasonal adjustment** (trend analysis with a contextual multiplier)

    TPV score = base × consistency × (seasonal multiplier if dip-and-rebound)

Consistency depends on consecutive month-on-month declines ending at M6 (a fall must exceed 1%): 0: ×0.3, 1: ×0.5, 2: ×0.7, 3: ×0.9, 4: ×1. For a seasonal industry with a dip of 15% or more followed by a rebound of 5%+, the TPV score is multiplied by 0.25.

**7. Risk band** (threshold-based classification)

    High if Score ≥ 50;  Moderate if Score ≥ 28;  otherwise Low

A rule-based band, not a probability of churn.

**8. Annual net-revenue run-rate proxy** (revenue run-rate estimation)

    Run-rate (Rs) = M6 TPV (Rs lakh) × 100,000 × net revenue rate × 12

With the workbook's net revenue rate of 1%: Run-rate (Rs lakh) = M6 TPV (Rs lakh) × 0.01 × 12. This is exposure, not revenue lost and not a guaranteed saving.

**9. Priority index (who to contact first)** (ranking and constrained selection)

    Index = ( w_r × Run-rate − (1 − w_r) × Outreach cost ) × Urgency,   w_r = (Score / 100) × Confidence factor

A ranking aid in rupees. w_r is a weight between 0 and 1 and is NOT a probability of churn or of saving the merchant. Outreach cost and urgency come from the workbook and configuration. It is not an expected-value forecast.

### Features

| Dimension | Feature | Source | Calculation | Limitation |
|---|---|---|---|---|
| Payment and volume performance | TPV trend | tpv_m1_inr_lakh … tpv_m6_inr_lakh | Average of M4-M6 compared with average of M1-M3, as a %. Capped linear: 0 points at -5% or better, 100 at -40% or worse. Multiplied by trend consistency (consecutive declines) | Six monthly points only. Seasonal dip-and-rebound is discounted |
| Payment and volume performance | Recent momentum (M6 vs M5) | tpv_m5, tpv_m6 | Not a separate score input. Used to detect a rebound (seasonal adjustment) and shown on the profile; consecutive declines scale the TPV score instead | One month of change is noisy |
| Payment and volume performance | Payment success-rate change | success_rate_m1_m3_pct, success_rate_m4_m6_pct | Difference in percentage points. Capped linear: 0 at -1pp, 100 at -10pp | Only TWO period averages exist; no monthly success-rate trend is available or inferred |
| Relationship and service experience | Unresolved tickets | unresolved_tickets | Step table: 0: 0, 1: 25, 2: 50, 3: 65, 4: 80, 5: 100 points (5 or more = 100) | Open tickets older than 90 days can exceed the 90-day count |
| Relationship and service experience | CSAT | last_csat_1_to_5 | Step table: 1: 100, 2: 75, 3: 25, 4: 0, 5: 0 points. Missing CSAT scores 0 | A single survey |
| Relationship and service experience | Service notes | account_manager_note | Added points: service_complaint: 20, service_escalation: 25. Combined: 0.7 × larger + 0.3 × smaller of unresolved and CSAT, then notes, then growth damping ×0.5 for a busy but growing merchant | Unverified free text, read by keyword rules |
| Engagement and adoption | Logins | logins_last_30d | Step table (logins ≤ limit → points): ≤2: 100, ≤5: 80, ≤10: 45, ≤15: 15. Counts 0.6 of the dimension | Current 30-day snapshot; no history, so no decline over time can be claimed |
| Engagement and adoption | Products used | products_used | Step table: 1: 60, 2: 20 points (3 or more = 0). Counts 0.4 of the dimension | Current snapshot; no adoption history |
| Engagement and adoption | Disengagement notes | account_manager_note | Added points: unresponsive: 40, decision_maker_change: 25. Small merchants with stable TPV (-5% or better, no note signal) have the usage score ×0.4 | Unverified free text |
| Commercial and renewal risk | Competitor, pricing or rate-card signal | account_manager_note | Highest signal counts: competitor_explicit: 85, exploring_options: 65, rate_card_request: 50, pricing_objection: 50 points | Entirely note-based and unverified; no independent field corroborates it |
| Commercial and renewal risk | Renewal proximity | days_to_contract_renewal | Bonus only when a commercial signal exists: ≤30 days: +15, ≤60 days: +10, ≤90 days: +5 | Timing, not intent to leave |

### Worked example: Lakshya Studio (C2100)

| Dimension | S | w | S × w |
|---|---:|---:|---:|
| performance | 84.3 | 0.35 | 29.49 |
| relationship | 60.0 | 0.25 | 15.00 |
| engagement | 35.0 | 0.15 | 5.25 |
| commercial | 0.0 | 0.25 | 0.00 |

Weighted mean 49.74; strongest 84.27; bonus 5. Score = 0.8 × 49.74 + 0.2 × 84.27 + 5 = **61.6** (High risk).

### Priority is not risk: Dhruva Enterprises (Enterprise, Moderate risk, score 46.2, index Rs 1,129,666, rank 1) ranks above Umang Stores (Small, High risk, score 61.4, index Rs 50,997, rank 13).

## 2. Decision tree (the actual rules)

| Step | Question | Condition and thresholds | Result |
|---|---|---|---|
| Start: score and band | Every merchant first gets four dimension scores, a final score and a band. | Score = 0.8 × weighted mean + 0.2 × strongest dimension + convergence bonus. Band: High ≥ 50, Moderate ≥ 28, else Low. |  |
| Is the evidence complete? | Are CSAT and an account-manager note both available? | Completeness < 100 when CSAT or a note is missing. Confidence is High only with ≥ 50% completeness and ≥ 2 dimensions at 40+. | Complete: normal confidence |
| Is the merchant in the Low band? | Is the score below 28? | Low band = score < 28 | Yes: no churn outreach; check for growth |
| Healthy and growing? | Is the merchant growing with no service or payment concern? | Low band AND TPV up ≥ 8% AND success change ≥ -2pp AND ≤ 1 unresolved AND CSAT ≥ 4 if present | Yes: PB-5 growth check-in |
| Which playbook triggers fire? | Each of PB-1 to PB-4 is tested independently. Several can fire at once. | PB-1: success fell ≥ 5pp or a payment-failure note.  PB-2: ≥ 3 unresolved, or CSAT ≤ 2 with ≥ 1 open.  PB-3: commercial signal and renewal ≤ 60 days.  PB-4: ≤ 5 logins, ≤ 2 products and TPV down 10%+ or an unresponsive / contact-change note. | At least one fires |
| Did more than one fire? | If several triggered, which is primary? | Fit = the matching dimension's score (PB-1 Performance, PB-2 Relationship, PB-3 Commercial, PB-4 Engagement). Highest fit is primary; ties go in the order PB-3, PB-1, PB-2, PB-4. The runner-up is a secondary playbook only if its fit ≥ 30. | Several: highest fit wins; runner-up shown as secondary or as 'triggered but lower fit' |
| Playbook selected: PB-1, PB-2, PB-3 or PB-4 | A risk-action playbook is chosen from the workbook's own text. | Outcome of the fit comparison | PB-1 / PB-2 / PB-3 / PB-4 |
| Is the merchant eligible for outreach capacity? | Is the playbook PB-1 to PB-4, the band at least Moderate, and the priority index positive? | Eligible merchants are ordered by the chosen business priorities, then by priority index, then risk score, then merchant ID. The first 15 are shortlisted. | Eligible: ranked for the shortlist |
| PB-5 Growth / expansion check-in |  | Healthy and growing | PB-5 |
| PB-6 Monitor only |  | Seasonal dip, naturally low volume, or no real risk signal | PB-6 |
| On the shortlist or just outside it |  | Rank ≤ 15: selected. Rank above 15: eligible but outside, with the gap to the last selected merchant shown. | Selected / outside |
| Not selected for churn outreach |  | Playbook PB-5 / PB-6, a Low band, or a non-positive index | Manual review |

Playbook selection is not a fixed top-to-bottom order: PB-1 to PB-4 are tested independently, the highest fit (the matching dimension's score) is primary, ties go in the order PB-3, PB-1, PB-2, PB-4, and the runner-up is secondary only if its fit is at least 30.

## 3. Playbooks

| ID | Name | Rule EDGE uses | Uses a slot |
|---|---|---|---|
| PB-1 | Performance deep-dive | Success rate fell 5pp or more, OR the note records a payment-failure concern. | Yes |
| PB-2 | Support recovery | 3+ unresolved tickets, OR CSAT ≤ 2 with at least 1 unresolved. | Yes |
| PB-3 | Commercial review | A competitor / exploring-options / rate-card / pricing signal in the note AND renewal within 60 days. | Yes |
| PB-4 | Re-engagement and adoption | ≤ 5 logins AND ≤ 2 products AND (TPV down 10%+ OR an unresponsive / contact-change note). | Yes |
| PB-5 | Growth / expansion check-in | Low risk band AND TPV up 8%+ AND success change ≥ -2pp AND ≤ 1 unresolved AND CSAT ≥ 4 if present. | No |
| PB-6 | Monitor only | Default when nothing above applies (and for every Low-band merchant who is not healthy and growing). | No |
