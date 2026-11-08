# Weight sensitivity report

Analysis: **Razorpay P2 workbook** (Buildathon_Student_Data_Pack.xlsx), EDGE 1.1 / config 1.0.0 / scoring 1.1.0-hypothesis. Capacity 15.

This measures how stable the shortlist is when the design hypotheses change. It is **ranking robustness, not prediction accuracy**: no churn labels exist.

## Method
- The real engine (scoring, playbook selection, prioritisation) is re-run for all 100 merchants in every configuration.
- 5 named test scenarios plus 300 sampled configurations (fixed seed 20261108, so the run is reproducible). Total 305.
- Dimension weights are sampled between 10% and 50% each and always sum to 100%.
- Feature-level parameters sampled in the same configuration: `aggregation.weighted_share` 0.7 to 0.9; `tpv.zero_at_pct` -10.0 to 0.0; `tpv.full_at_pct` -50.0 to -30.0; `success.zero_at_pp` -2.0 to 0.0; `success.full_at_pp` -12.0 to -8.0; `performance.max_share` 0.6 to 0.9; `engagement.login_share` 0.4 to 0.8.
- Risk-band thresholds and the outreach cost are held fixed.
- Robust priority = shortlisted in at least 90% of configurations. Low priority = at most 10% and not in the baseline shortlist. Everything else is weight-sensitive.

## The five test scenarios (test scenarios, not recommended final weights)

| Scenario | Weights P/R/E/C % | High | Moderate | Low | Overlap with baseline | Moved in | Moved out | Run-rate represented | Seasonal selected | Incomplete-evidence selected |
|---|---|---:|---:|---:|---:|---|---|---:|---:|---:|
| Baseline | 35 / 25 / 15 / 25 | 13 | 11 | 76 | 15 of 15 | None | None | Rs 83.4 lakh | 2 | 9 |
| Equal | 25 / 25 / 25 / 25 | 12 | 12 | 76 | 14 of 15 | C2022 | C2034 | Rs 83.9 lakh | 2 | 8 |
| Performance-led | 45 / 20 / 15 / 20 | 12 | 12 | 76 | 15 of 15 | None | None | Rs 83.4 lakh | 2 | 9 |
| Relationship-led | 25 / 40 / 15 / 20 | 12 | 12 | 76 | 15 of 15 | None | None | Rs 83.4 lakh | 2 | 9 |
| Commercial-led | 25 / 20 / 15 / 40 | 7 | 17 | 76 | 13 of 15 | C2022, C2036 | C2034, C2091 | Rs 83.9 lakh | 2 | 9 |

Run-rate is the annual net-revenue run-rate proxy of the shortlisted merchants: exposure, not revenue lost and not expected savings.

## Merchant stability
- Robust priority: **12**. Weight-sensitive: **5**. Low priority: **83**.

| Merchant | Classification | In shortlist | Average rank | Best to worst | Score range | Moved materially by |
|---|---|---:|---:|---|---|---|
| C2004 Dhruva Enterprises | Robust priority | 305 of 305 | 1.2 | 1 to 2 | 28.5 to 64.6 | None |
| C2018 Banyan Enterprises | Robust priority | 305 of 305 | 3.4 | 3 to 5 | 31.2 to 69.7 | None |
| C2027 Nest Exports | Robust priority | 305 of 305 | 8.3 | 6 to 10 | 28.0 to 64.3 | None |
| C2061 Falcon Labs | Robust priority | 305 of 305 | 9.9 | 7 to 12 | 35.6 to 74.6 | None |
| C2062 Zenith Fashions | Robust priority | 305 of 305 | 7.0 | 6 to 9 | 31.1 to 71.6 | None |
| C2079 Banyan Exports | Robust priority | 305 of 305 | 5.3 | 4 to 7 | 33.6 to 72.2 | None |
| C2084 Cedar Traders | Robust priority | 305 of 305 | 12.2 | 11 to 15 | 29.5 to 75.7 | None |
| C2088 Everest Learning | Robust priority | 305 of 305 | 1.8 | 1 to 2 | 33.6 to 70.6 | None |
| C2090 Quest Studio | Robust priority | 305 of 305 | 3.6 | 3 to 5 | 33.6 to 79.8 | None |
| C2100 Lakshya Studio | Robust priority | 305 of 305 | 8.3 | 5 to 10 | 41.4 to 75.3 | None |
| C2093 Neon Services | Robust priority | 304 of 305 | 11.0 | 9 to 12 | 27.3 to 60.4 | None |
| C2097 Willow Furnishings | Robust priority | 304 of 305 | 6.2 | 5 to 10 | 23.8 to 69.8 | None |
| C2032 Yatra Pharma | Weight-sensitive | 256 of 305 | 14.0 | 11 to 20 | 27.0 to 76.8 | None |
| C2091 Monsoon Pharma | Weight-sensitive | 241 of 305 | 14.5 | 12 to 19 | 34.0 to 72.4 | Commercial-led (15 to 16) |
| C2022 Panchi Furnishings | Weight-sensitive | 178 of 305 | 14.9 | 11 to 18 | 22.9 to 53.5 | Equal (16 to 15); Commercial-led (16 to 13) |
| C2034 Umang Stores | Weight-sensitive | 172 of 305 | 15.5 | 12 to 18 | 36.3 to 75.2 | Equal (13 to 16); Commercial-led (13 to 17) |
| C2036 Orchid Pharma | Weight-sensitive | 54 of 305 | 17.1 | 13 to 20 | 20.5 to 52.8 | Commercial-led (19 to 14) |

## Reading the results
- The baseline shortlist is largely stable: 12 of 15 baseline merchants are robust priorities.
- **Why the shortlist is stable.** Only 24 merchants are eligible for 15 slots, and the order inside that pool is driven mostly by annual run-rate through the priority index. Stability to the weights is therefore partly a property of the value-weighted selection rule, not only evidence that the weights are right.
- Weight-sensitive merchants sit near the capacity line. Treat them as a judgement call, not a model verdict.
- Scenario comparisons use the same workbook with different weights. They are not changes in merchant behaviour over time.

## High-risk merchants that are rarely shortlisted
These are High risk but low priority in nearly every configuration, because the priority index weighs annual run-rate and a small merchant cannot outrank larger ones under the capacity limit. This follows from the value-weighted selection rule; it is a capacity decision, not a score error.

| Merchant | Risk score | Annual run-rate | Times shortlisted |
|---|---:|---:|---:|
| C2001 Vihaan Labs | 59.6 | Rs 0.7 lakh | 7 of 305 |
| C2015 Willow Organics | 53.2 | Rs 0.8 lakh | 6 of 305 |
| C2008 Ivory Pharma | 52.2 | Rs 0.3 lakh | 0 of 305 |
| C2020 Uday Enterprises | 54.3 | Rs 0.2 lakh | 0 of 305 |
| C2045 Falcon Foods | 57.2 | Rs 0.3 lakh | 0 of 305 |
