# Razorpay EDGE: final acceptance report (Gate 8)

Scope: the upgrade defined in `Razorpay_EDGE_Master_Implementation_Brief_Claude_Code.md`, Gates 1 to 8. Evidence is from the supplied Problem 2 workbook, run on 2026-11-09.

## 1. Result in one paragraph

All 23 acceptance criteria are met except two that are met only in part (22 and the evidence behind 10), and one item in section 4 of the brief that was missing until this gate (the score histogram), which is now built. 149 automated tests pass and the UI builds with no type errors. The limits that matter: no churn labels exist, so nothing here is an accuracy claim; the 20-case validation uses coarse checks and has no human reviewer judgement yet; Claude-assisted analysis and Claude-written drafts were never run live; and nothing has been deployed.

## 2. Test and build evidence

| Check | Result |
|---|---|
| Automated tests | **149 passed**, 0 failed (`py -m pytest`) |
| Frontend type-check and build | Passes (`npm run build`) |
| Fresh runs of the supplied workbook | Three full runs; selections identical across two runs; capacity 10 gives exactly 10 |
| Score reconciliation | 100 of 100 merchants: total rebuilds from the dimension parts within rounding |
| Draft guardrails | All 24 drafts pass; none mentions risk, churn or a score |
| Probability or accuracy phrases | None in the analysis data or exports |
| Pages | All nine sections and their tabs render with no console errors and no "NaN" or "undefined" text |
| Overflow | Zero horizontal overflow on all nine pages at 1024 and 768 px, and at 390 px except a 3 px overflow on Decision Studio that was not traced |

Tests by area: scoring and features (21), data validation (8), reconciliation (17), playbooks and prioritisation (16), agent safety (16), API (11), weight scenarios, robustness and Validation Lab (14), Ask EDGE and AI disclosure (10), workflow (11), insights and evaluation package (10), UI assets and logo (15).

A defect found during this gate: the Segments table printed "8 of undefined" for band rates (a missing denominator from Gate 6). Fixed, and a test now checks every rate carries its denominator.

## 3. Acceptance criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | All nine sections accessible | Met | Route and tab sweep with no errors; direct-visit test for every route |
| 2 | Workbook is source of truth | Met | Assumptions parsed from the sheet; tests re-read the sheet; `source_audit.md` with SHA-256 |
| 3 | No unsupported churn labels or probabilities | Met | Phrase scan of data and exports; guardrail tests; labels on every card |
| 4 | Risk and priority scores are distinct | Met | Separate fields; risk order differs from priority order; formulas shown |
| 5 | Score components reconcile exactly | Met | 100 of 100; on-screen breakdown shows "Reconciles" |
| 6 | Top 15 reproducible and capacity-aware | Met | Identical across runs; capacity 10 gives 10 |
| 7 | Multiple weight scenarios compared | Met | 5 named scenarios plus 300 sampled; sliders with sum-to-100 validation |
| 8 | Sensitivity visible and exportable | Met | Decision Studio tab, CSVs, evaluation package |
| 9 | At least 20 validation cases | Met | 20 cases, 5 per category, from real merchants |
| 10 | Seasonal, low-volume and growing-with-resolved-tickets decoys tested | Met, with a caveat | Cases B1 to B5 and unit tests pass; the checks are coarse (see 5) |
| 11 | Supporting and contradictory evidence visible | Met | Merchant Intelligence, separated by observed, extracted, inferred, recommended |
| 12 | Only the six workbook playbooks used | Met | Test and fresh run: PB-1 to PB-6 only |
| 13 | Outreach grounded, editable, human-approved | Met | Review pack, guardrails on edited text, named reviewer; live Claude drafts not run |
| 14 | Approval does not imply sending | Met | Separate events; contact recorded manually; tests |
| 15 | Outcome capture exists | Met | Nine outcomes, free text, history export; labelled not a churn label |
| 16 | Exposure not misrepresented | Met | Every figure labelled run-rate proxy, not revenue lost or expected savings |
| 17 | Runtime AI accurately disclosed | Met | Reports table built from recorded use; development use stated separately |
| 18 | Ask EDGE grounded and evidence-linked | Met | All ten brief questions answered by calculation with fields and limits; Claude replies checked |
| 19 | Reports preserve lineage | Met | Evaluation package: workbook hash, sheets, mapping, version, overrides, AI use |
| 20 | Logo and branding intact | Met | Served byte-for-byte; component draws nothing itself |
| 21 | Palette restrained and accessible | Met | Brief's palette; text colours computed at 4.5:1 or better on white; no gradients on Welcome |
| 22 | Responsive behaviour and key interactions | Partly | Overflow measured at three widths; workflow tested through the API and one test analysis in the browser; no keyboard-only walkthrough and no real phone |
| 23 | Limitations and known failures disclosed | Met | `limitations.md`, `failure_analysis.md`, this report |

## 4. Gaps in the brief that were open and are now closed

- **Score histogram and threshold check** (brief section 4): missing through Gates 2 to 7. Built in this gate under Settings, Risk model: histogram with the two cut-offs, counts if a cut-off moves, and merchants within 3 points of a cut-off. It shows the High count is sensitive: 19 at a cut-off of 45, 13 at 50, 5 at 55.

## 5. Known failures, weaknesses and decisions still open

**Validation**
- 19 of 20 cases pass, 1 needs review (a merchant 2.9 points above the High threshold), 0 fail. The checks are coarse, so "0 fail" does not mean the engine is right in subtle cases.
- Human reviewer judgement is built in but pending for every case.
- Expected interpretations are test expectations, not ground truth.

**Analytical**
- **High-risk merchants rarely shortlisted.** Five High-risk merchants (C2001, C2015, C2008, C2020, C2045) have a tiny run-rate (Rs 0.2 to 0.8 lakh) and are almost never in the 15. This follows from the value-weighted selection you confirmed. The Priority Queue now forces a capacity decision for urgent merchants outside the list, but whether to change the rule is your call.
- **Stable shortlist is partly the rule.** Only 24 merchants are eligible for 15 slots and annual run-rate drives their order, so stability to weights is partly a property of the selection rule.
- **Thin cut-off margin.** C2062, C2084 and C2018 sit within 2 points under the High threshold.
- **Single signal cannot reach High.** A deliberate design change in scoring 1.1.0; severe single-dimension cases are Moderate with a critical-trigger flag.
- **Commercial evidence is unverified.** It rests on account-manager notes only, and Business Insights rates it "Limited".

**Not run or not verified**
- **Claude-assisted analysis** (about 115 paid calls) was never run live, so Claude-written evidence text and drafts are tested only with stubs. Two live Ask EDGE questions were sent during testing.
- **Interactions in the browser:** I did not click through approval on the main analysis (to avoid a false "contacted" record) or do a keyboard-only walkthrough. The workflow is covered by API tests.
- **Phone:** measured in emulation only. The 390 px screenshot looked cropped, which I judged a pane artefact; please check on a real phone.
- **Decision Studio at 390 px:** a 3 px overflow, not traced.

**Not built**
- PDF executive summary (the brief says only if reliable).
- Active-filter chips on the Portfolio (it has "Clear filters").
- An editor for feature-level weights. The robustness test varies them; the UI does not edit them.
- Conversation memory in Ask EDGE beyond the last few turns.
- The original moving ticker. The brief allows removing a decorative carousel; it is removed from Welcome and Overview.

**Housekeeping**
- Analyses created before Gate 3 cannot run weight scenarios or the robustness test until re-run.
- `data/` holds 61 saved analyses and 101 uploads, mostly left by test runs. It is excluded from git.
- Only the first commit exists. Everything since Gate 1 is uncommitted.
- Deployment was prepared (Dockerfile, `render.yaml`, optional password gate) but never run; the Render route was blocked on your network and the Hugging Face or tunnel option was not chosen.

## 6. Where everything is

| Item | Location |
|---|---|
| Run the app | `.\run.ps1`, then http://localhost:8000 |
| Audit and methodology | `implementation_audit.md`, `source_audit.md`, `scoring_methodology.md` |
| Sensitivity and validation | `weight_sensitivity_report.md`, `weight_scenario_comparison.csv`, `merchant_rank_stability.csv`, `top15_overlap_matrix.csv`, `manual_validation_log.csv`, `failure_analysis.md` |
| Summary and limits | `evaluation_summary.md`, `limitations.md`, `configuration_snapshot.json` |
| In-app evaluation package | Reports & History, Export, "Export evaluation package" |
| Regenerate the root files | `py scripts/make_gate3_reports.py <session_id>` and `py scripts/make_source_audit.py` |
