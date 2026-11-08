# Evaluation summary: Razorpay P2 workbook

Source workbook `Buildathon_Student_Data_Pack.xlsx`, analysed 2026-11-08T23:48:08, EDGE 1.1 / config 1.0.0 / scoring 1.1.0-hypothesis.

## What EDGE is
An explainable decision-support system. It combines transaction performance, payment health, service experience, engagement, commercial signals and renewal context to help a CSM team spend limited outreach capacity. It is not a churn predictor.

## Deterministic, templated and AI-assisted parts
| Task | How it was produced | Runtime AI |
|---|---|---|
| Scores, risk categories, ranking, shortlist, revenue figures, playbook selection | Calculated | Not used |
| Account-manager note signals | Calculated | Not used |
| Evidence summaries (plain-language reason, alternatives, CSM checks) | Template text | Not used |
| Outreach drafts | Template | Not used |
| Ask EDGE answers | Calculated, with Claude for open questions | Used |

Claude Code was used while developing this application. That is development tooling, not a runtime feature, and it is not counted in the table above.

## Scoring and weights
Four dimensions are scored 0-100 and combined: 35 / 25 / 15 / 25 (Performance / Relationship / Engagement / Commercial, %). Total = 0.8 x weighted mean + 0.2 x strongest dimension + a convergence bonus. Bands: High 50+, Moderate 28+, Low below.
Rationale: performance and payment signals are direct operational evidence; relationship and commercial signals show friction or displacement; engagement is the weakest evidence because it is a snapshot. One dimension alone cannot reach High, so High needs corroboration. All of this is hypothesis.

Result: 13 High, 11 Moderate, 76 Low of 100 merchants; 19 meet a critical review trigger.

## Top-list logic
Eligible merchants have playbook PB-1 to PB-4, a Moderate or High band and a positive priority index. They are ordered by the configured business priorities, then the priority index = (risk weight x annual exposure - (1 - risk weight) x outreach cost) x renewal urgency, then risk score, then merchant ID. The first 15 are shortlisted (15 now). The index is a ranking aid, not an expected saving.

## Financial assumptions (from the workbook)
- Net revenue rate 1% of TPV; TPV unit Rs 100,000 (lakh); saved-merchant value 12 months at M6 TPV.
- Outreach cost Rs 1,500 per outreach; capacity 15; churn horizon 90 days; seasonal industries: Education / Coaching, Gifting & Festive, Travel & Hospitality.
- Exposure of Moderate and High merchants: Rs 89.7 lakh a year. This is exposure, not revenue lost or expected savings.

## Sensitivity results
305 configurations (5 named scenarios plus 300 sampled, seed 20261108): 12 robust priorities, 5 weight-sensitive, 83 low priority. Stability is partly a property of the value-weighted selection rule. This measures ranking robustness, not accuracy.

## Validation
20 case-based scenarios reviewed: 19 pass, 1 need review, 0 fail. Checks are coarse and expectations are test expectations, not ground truth. See `failure_analysis.md`.

## Human safeguards
Every draft needs a named reviewer who confirms the facts. Approval, contact and outcome are separate recorded events; contact is recorded manually; EDGE never sends a message. Drafts never mention risk scores or churn and offer no concession.

## Limitations
See `limitations.md`. The main ones: no churn labels, hypothesis weights, a single snapshot, unverified notes.
