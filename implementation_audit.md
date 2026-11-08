# Razorpay EDGE: Gate 1 implementation audit

Audit only. No scoring, configuration or UI behaviour was changed in this gate. The one exception is the supplied logo, which is now placed (see 6).
Evidence: `src/` (engine), `api/` (EDGE API), `web/src` (UI), `config/`, the workbook `Buildathon_Student_Data_Pack.xlsx` and the most recent saved analysis (100 merchants).

## 1. Correctly implemented

| Area | Status |
|---|---|
| Source of truth | Workbook sheets `P2_Merchants`, `P2_Playbooks`, `P2_Assumptions` are read; assumptions are parsed from the sheet (net revenue 1%, 90-day churn, Rs 1,500 false alarm, 12 saved months, TPV in Rs lakh/month, capacity 15, seasonal = Gifting, Education, Travel). |
| Ingestion | Header and sheet detection, editable mapping, duplicate IDs, range checks, excluded-record report, missing values left as unknown (not imputed). |
| Scoring | Transparent heuristic 0-100 from four dimensions; every point recorded in `contributions`; no probability, accuracy or churn label anywhere. Verified by hand on the first merchant in the saved analysis: dims 91.6 / 60 / 0 / 0 gives 0.5 x weighted mean + 0.5 x max dimension + 5 convergence bonus = 74.3, matching the stored score. |
| Context handling | Seasonal dip-and-rebound multiplier (TPV component only), natural low-touch Small merchants, growth damping for busy-but-growing merchants, missing CSAT contributes 0, resolved tickets not penalised. |
| Risk vs priority | Separate: `risk_score` vs `priority_value_inr`; outreach cap 15 enforced; value-weighted selection tested. |
| Playbooks | Only the six supplied playbooks exist; PB-1..PB-4 are outreach-eligible, PB-5 and PB-6 never get outreach. |
| Guardrails | Drafts never state risk or churn, no concessions, human approval required, nothing is sent; notes treated as untrusted (injection flag lowers confidence). |
| Existing weight sensitivity (engine) | `src/analytics/sensitivity.py` already re-runs full scoring under 10 scenarios and writes `outputs/sensitivity_*.csv`. |
| Pages | All nine sections load; exports (CSV and Excel), history, compare, persistence, Ask EDGE (deterministic router plus Claude fallback). 72 tests pass. |

## 2. Partially implemented

| Area | Gap |
|---|---|
| Decision Studio | Works, but is deliberately weight-free (priorities, risk focus, capacity, segments). The brief (section 5) asks for dimension weights, 100-500 reproducible configurations, rank-stability classes and a "why did this merchant move" view. The weight engine exists in `src/` but is not exposed through the API or UI. |
| Merchant Intelligence | Shows evidence and drivers; lacks fact / extracted-note / inference / recommendation separation, mitigating and contradictory evidence as first-class items, and an expandable per-feature score breakdown. `score_contributions` is stored but not rendered. |
| Priority Queue | Shows selected, "just outside" and reasons; lacks priority components, mix charts, compare-two-merchants, capacity 10/20 impact and an explicit status for urgent-but-unselected merchants. |
| Action Centre | Status list exists (8 statuses) but approval and contact are tracked in one flat status; it is 15 tall cards, not master-detail; no outcome capture; no verification checklist. |
| Business Insights | Count and exposure both exist, but drivers do not show counter-evidence or independent corroboration; segments lack driver mix and missing-data share. |
| Reports | Exports and lineage exist; no evaluation package, no AI-use disclosure per feature. |
| Settings | Assumptions shown without source cell, override and change time; developer path `config/scoring.yaml` is visible. |
| Ask EDGE | Grounded, but several brief test questions (weight-sensitive merchants, contradictory signals, capacity-20 effect) have no handler. |

## 3. Missing

- Validation Lab (20 documented cases, failure taxonomy) and `manual_validation_log.csv`.
- Rank-stability outputs (`merchant_rank_stability.csv`, overlap matrix) and robust / weight-sensitive / low classification.
- Evaluation package export; `source_audit.md`, `scoring_methodology.md`, `weight_sensitivity_report.md`, `failure_analysis.md`, `evaluation_summary.md`, `configuration_snapshot.json`.
- Outcome capture and the follow-up-due lifecycle.
- Score histogram and threshold-sensitivity view.
- Evidence completeness shown as a column on Portfolio and Queue.
- Settings: feature-level weights, reset to baseline, playbook owner / checks.
- Navigation grouping (Understand / Decide and act / Govern) and tablet layout.

## 4. Inconsistencies and potential defects

1. **Thin moderate band is structural.** Bands are 23 high, 1 moderate, 76 low. Scores are bimodal: 76 merchants sit at or below 17, one at 45.4, then 23 from 52 upward. Cause: the aggregate is 0.5 x weighted mean + 0.5 x strongest single dimension, so any one dimension near 70 or above puts a merchant over 50. 11 of the 23 high merchants have exactly one dimension at or above 40. The thresholds (50 / 28) are therefore not the issue; the aggregation is. Recommendation: document it, show the histogram, and test a lower max-share as a scenario rather than silently changing it.
2. **"Immediate attention" is 19, capacity is 15.** 12 are selected, 7 are eligible but unselected. Today the UI labels both as immediate review. Needs a defined rule for the 7 (next review date, escalation).
3. **Weight-free Studio vs the brief.** The earlier EDGE brief said no numeric weights; this brief requires weight scenarios. The new brief takes precedence, but it replaces how Studio ranks, so it needs your confirmation (see questions).
4. **Priority proxy wording.** `priority_value_inr = (w x annual value - (1 - w) x false-alarm cost) x urgency`, with w = risk score / 100 x confidence factor. It reads like an expected-value formula even though w is not a probability. Rename it as a "priority index (Rs-equivalent proxy)", show components, and never describe it as expected savings.
5. **Seasonal merchants rated High.** C2090 (Education, TPV -31%), C2032 (Gifting, -29%) and C2045 (Travel, -22%) are high risk. This may be right (other dimensions fire, or no rebound), but each needs a case in the Validation Lab to confirm they are not escalated on TPV alone.
6. **False-alarm cost ambiguity.** The sheet says "1.5 hours of CSM time per outreach, valued at Rs 1,500". The code uses Rs 1,500 total per outreach (consistent with Rs 1,000 per hour x 1.5 h). If Rs 1,500 were hourly, cost would be Rs 2,250. The sheet's wording supports the total reading; flagged for your confirmation.
7. **Critical triggers do not change score or slots.** They only set the "immediate" flag. The brief asks every override to document score, priority and slot impact. Currently impact is "none", which is acceptable but must be stated and tested.
8. **Data completeness.** 50 merchants fully complete, 39 half, 11 at 0. 8 of the 15 selected have missing evidence (3 without CSAT). This is shown as a notice but not as a column or filter.
9. **Run-rate labels.** Overview "Rs 89.7 L" is exposure (annual run-rate of moderate plus high merchants), not loss. Labels are correct in most places; the full "not lost / not expected savings" wording is not on every card.
10. **Logo.** The supplied file is `.webp` with large blank margins; it is shown in a masked window (no pixel changes). Details in 6.

## 5. Files and modules that need changes

| Gate | Files |
|---|---|
| 2 Analytical correctness | `api/runner.py`, `api/insights.py`, `src/analytics/prioritisation.py` (labels only), new `tests/test_reconciliation.py`, `scoring_methodology.md`, `source_audit.md` |
| 3 Sensitivity / validation | new `api/sensitivity.py` and `api/validation.py` reusing `src/analytics/risk_scoring.py`; `api/scenarios.py`, `api/main.py`, `pages/Studio.tsx`, new `pages/Validation.tsx` (tab in Reports and History) |
| 4 AI transparency | `api/ask.py`, `api/runner.py` (llm_stats), `pages/Reports.tsx`, `pages/AskPanel` |
| 5 Workflow | `pages/Queue.tsx`, `pages/Actions.tsx`, `pages/Merchant360.tsx`, `api/store.py`, `api/main.py` (events, outcomes) |
| 6 Insights and reports | `api/insights.py`, `pages/Insights.tsx`, `api/exporter.py` |
| 7 UI/UX | `index.css`, `tailwind.config.js`, `Shell.tsx`, `ui.tsx`, `charts.tsx`, all pages for spacing and tables |

## 6. Logo

`web/public/razorpay-edge-logo.webp` is the supplied image, byte-for-byte. `Logo.tsx` shows it inside a clipping window that hides only the blank margin (x 100-1900, y 175-460 of 2000 x 621). It is not redrawn, recoloured, stretched or re-encoded. Verified on the Welcome page; the sidebar uses height 30. If you prefer a trimmed PNG instead, send it and I will swap the path.

## 7. Plan and dependencies

1. **Gate 2** (analytical correctness): reconciliation tests (dims -> total, thresholds, run-rate, tie-breaks), histogram and band explanation, priority-index relabel, false-alarm decision. Blocks everything else.
2. **Gate 3**: weight-based scenario engine and stability, then Validation Lab. Needs Gate 2 numbers fixed.
3. **Gate 4** can run alongside Gate 3 (separate files).
4. **Gate 5** needs Gate 3 outputs (stability, completeness).
5. **Gate 6** needs Gate 3 and 5 outputs.
6. **Gate 7** last, so layout is applied once; Gate 8 acceptance report.

Not planned unless you ask: PDF summary (brief says only if reliable) and anything involving deployment.
