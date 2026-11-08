# Methodology

**Status:** v1.0.0 (scoring `1.0.0-hypothesis`). Weights and thresholds are **design hypotheses**, not learned. No churn labels exist, so nothing here is, or is reported as, a churn probability, precision, recall or accuracy.

## 0. What is fact, what is calculation, what is assumption

| Layer | Examples | Where |
|---|---|---|
| Source facts | 100 merchants, TPV M1-M6, success-rate aggregates, tickets, CSAT, logins, renewal days, notes; 6 playbooks; 7 assumptions | workbook |
| Deterministic calculations | % change, pp change, consecutive declines, run-rate revenue = M6 TPV x Rs 1,00,000 x 1% x 12 | `src/analytics/feature_engineering.py` |
| Design hypotheses | dimension weights, point scales, band cut-offs, playbook trigger thresholds, urgency multiplier | `config/*.yaml` |
| LLM interpretation (optional) | note labels, plain-language reason, alternative explanations, CSM checks, outreach wording | `src/agent/` |
| Unknowns | whether churn happened, cause of any decline, competitor activity, consent/channel rules | stated in outputs |

## 1. Churn definition
Source: the merchant moves *most of its volume away within the next 90 days*. A TPV decline is a **signal**, not the definition.

## 2. Features (all from existing columns)
- **TPV:** avg(M4-M6) vs avg(M1-M3) % change (main), M1-M6 change, M6 vs M5, consecutive monthly declines ending at M6 (>1% fall counts), slope, coefficient of variation, trend label, `dip_and_rebound` shape.
- **Payments:** success-rate change in **percentage points** (M4-M6 minus M1-M3). Only two period aggregates exist, so no monthly series is invented.
- **Service:** unresolved tickets, CSAT, `csat_missing` (missing is **not** poor). Resolved tickets are never penalised (busy-but-healthy decoy).
- **Engagement:** logins and products (snapshot only; no claim of decline over time).
- **Commercial:** renewal days (bands <=30/31-60/61-90/>90) and note signals.
- **Notes:** deterministic regex classifier (`config/note_signals.yaml`); injection heuristics flag instruction-like text.
- **Peer context:** segment/industry median TPV change (informational only, never scored; industries have ~10 merchants each).
- **Value:** `annual_value_at_stake_inr = M6 TPV x 100000 x 0.01 x 12` - labelled *run-rate revenue exposure*, not guaranteed loss.

## 3. Risk score (0-100, heuristic)
Four dimensions, each 0-100, with every contributing point stored in `score_contributions`:

1. **Performance** = 0.75 x max(TPV, success) + 0.25 x min(...).
   TPV points: linear 0 at -5% to 100 at -40%, times a **trend-consistency factor** (0.3 / 0.5 / 0.7 / 0.9 / 1.0 for 0-4+ consecutive declines). A one-month dip that rebounds is worth little by itself.
   Success points: 0 at -1pp to 100 at -10pp.
   **Seasonality:** if industry is Gifting & Festive, Education / Coaching or Travel & Hospitality **and** the shape is dip (>=15% under early average) then rebound (M6 >=5% above M5), the **TPV component only** is multiplied by 0.25. Other dimensions are untouched.
2. **Relationship / service** = 0.7 x max(unresolved pts, CSAT pts) + 0.3 x min, plus note points (service complaint +20, escalation +25); halved for growing merchants (>=+10%) with <=1 open ticket.
3. **Engagement** = 0.6 x login pts + 0.4 x product pts, plus note points (unresponsive +40, contact change +25); x0.4 for *Small, stable* merchants with no note flags (low usage is natural).
4. **Commercial** = strongest note signal (explicit competitor 85, "exploring options" 65, rate-card request 50) + renewal bonus (<=30d +15, <=60d +10, <=90d +5). Renewal proximity alone adds nothing.

**Aggregate:** `0.5 x weighted mean (0.35/0.25/0.15/0.25) + 0.5 x strongest dimension + 5 per extra dimension >=40 (cap 15)`.
**Bands:** high >= 50, medium >= 28, else low. Chosen after inspecting the score distribution (a clear gap exists between 45 and 19), not tuned to outcomes.

**Correlated variables:** `unresolved_tickets` and `support_tickets_last_90d` are not both scored; total tickets are used only for context. TPV decline and success-rate drop are combined by max-weighted blend, not summed, to limit double counting.

**Critical triggers** (human-review flags only; score unchanged): severe performance (TPV <= -20% and success <= -5pp), explicit competitor with renewal <= 30 days, >=4 unresolved and CSAT <= 2, <=2 logins with sustained steep decline.

## 4. Confidence and data quality
- `data_quality.completeness_score` = 100 minus 50 for each missing optional field (CSAT, note).
- `risk_confidence` (confidence in the *assessment*, not churn): high when >=2 dimensions agree and completeness >= 50; reduced when seasonality contradicts the signal or a note looks like prompt injection.

## 5. Playbook selection (`config/playbook_mapping.yaml`)
Only the six supplied playbooks are used. Triggers follow each playbook's *when it applies* text:
PB-1 success drop >= 5pp or performance complaint; PB-2 >= 3 unresolved, or CSAT <= 2 with >= 1 unresolved; PB-3 competitor/rate-card/exploring signal and renewal <= 60 days; PB-4 <= 5 logins and <= 2 products plus a decline or contact change/unresponsive; PB-5 low band, TPV >= +8%, stable success, <= 1 open ticket, CSAT >= 4 if present; PB-6 otherwise.
When several fire, the one whose dimension scores highest is primary (tie-break PB-3, PB-1, PB-2, PB-4); a secondary is recorded if its fit >= 30. Recommend **one coordinated CSM interaction**, specialists internal.

## 6. Prioritisation under the 15-contact cap
1. **Risk ranking** of all 100 by score (ties: value, then ID).
2. **Outreach ranking** only among eligible merchants: playbook in PB-1..PB-4, band medium or high, positive priority proxy.
3. `risk_weight = (score/100) x confidence factor (1.0/0.85/0.6)` - a weight, **not** a probability.
4. `priority proxy = (weight x annual run-rate value - (1 - weight) x Rs 1,500) x urgency (1.10 if renewal <= 30d, 1.05 if <= 60d)`.
5. Top 15 by proxy. The first excluded merchant's gap is printed in `portfolio_insights.md`.
PB-5/PB-6 do not consume churn-outreach capacity (**needs confirmation**: the brief does not say).

## 7. Sensitivity
`outputs/sensitivity_analysis.csv` re-runs the whole pipeline under 12 configurations (alternative weights, max-only/mean-only aggregation, no seasonality adjustment, stricter/looser scales, and `risk_first_selection`). 7 merchants are selected in every scenario; the value-weighted vs risk-first choice moves 6 of 15 picks, which is the main open decision.

## 8. Honest limitations
See `outputs/validation_report.md` section 5.
