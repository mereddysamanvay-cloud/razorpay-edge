# Failure analysis

Source: Validation Lab, Razorpay P2 workbook, EDGE 1.1 / config 1.0.0 / scoring 1.1.0-hypothesis.

**20 case-based scenarios reviewed against stated design expectations: 19 pass, 1 need human review, 0 fail.** This is not an accuracy measure: no churn labels exist, and each expectation is a test expectation, not ground truth.

## Automated failures
None. Every automated check passed.

That is a weaker statement than it sounds. The checks are deliberately coarse (band, eligibility, playbook family, whether a dimension is zero, whether mitigating or contradictory text exists). They catch gross design errors, not subtle mis-rankings. Human reviewer judgement is recorded separately in the Validation Lab.

## Needs human review
- **D4 Score within 3 points of a band threshold**: C2090 Quest Studio, score 52.9 (High risk). Borderline by design: a CSM decides.

Human reviewer judgement recorded for 0 of 20 cases.

## Observations that deserve a decision
- **High risk but not shortlisted.** C2001 (7 of 305), C2015 (6 of 305), C2008 (0 of 305), C2020 (0 of 305), C2045 (0 of 305). They rarely reach the capacity limit because selection is value-weighted.
- **Single-signal severity lands in Moderate.** One dimension alone cannot reach High, so severe single-dimension cases are Moderate with a critical-trigger flag.
- **Pool sizes.** Some patterns match very few merchants (see the matching count per case), so a pass can rest on one example.

## Cases by required adversarial test
| Required test | Cases | Result |
|---|---|---|
| Seasonal TPV decline | B1, C2 | Pass, Pass |
| Naturally low-volume merchant | B2 | Pass |
| Growing merchant with many resolved tickets | B3, C5 | Pass, Pass |
| Competitor concern near renewal | A3 | Pass |
| Poor CSAT plus unresolved tickets | A2 | Pass |
| Declining TPV with stable success | C1 | Pass |
| Declining TPV and deteriorating success | A1 | Pass |
| Missing CSAT | D1 | Pass |
| Missing account-manager note | D2 | Pass |
| Contact-person change | D3 | Pass |
| TPV rebound | B1, B4 | Pass, Pass |
| Low logins normal for segment | B5 | Pass |
