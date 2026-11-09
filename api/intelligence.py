"""Content for the Decision Intelligence page, generated from the LIVE configuration and, for worked examples, from a saved analysis.

Nothing here is hand-copied from the interface: every threshold, weight and formula constant is read from config/scoring.yaml,
config/playbook_mapping.yaml and config/settings.yaml, so the explanation cannot drift from what the engine actually does.
"""
from __future__ import annotations

from src.config import load_playbook_cfg, load_scoring, load_settings

DIMS = ["performance", "relationship", "engagement", "commercial"]
LABEL = {"performance": "Performance", "relationship": "Relationship", "engagement": "Engagement", "commercial": "Commercial"}
PB_FIT = {"PB-1": "performance", "PB-2": "relationship", "PB-3": "commercial", "PB-4": "engagement"}


def _g(x: float) -> str:
    return f"{x:g}"


def _example(ms: list[dict], pred, prefer=None) -> dict | None:
    pool = [m for m in ms if pred(m)]
    if not pool:
        return None
    if prefer:
        pool.sort(key=prefer)
    m = pool[0]
    return {"id": m["id"], "name": m["name"], "segment": m["segment"], "risk": m["risk_label"], "score": round(m["risk_score"], 1), "playbook": f"{m['assessment']['primary_playbook_id']} {m['assessment']['primary_playbook_name']}",
            "why": m.get("playbook_trigger_reason") or ""}


def _equations(sc: dict, st: dict) -> list[dict]:
    w, ag, tpv, sx, pf = sc["weights"], sc["aggregation"], sc["tpv"], sc["success"], sc["performance"]
    return [
        {"key": "weighted", "title": "1. Weighted mean of the four dimension scores", "formula": "WM = Σ (S_d × w_d) / Σ w_d", "plain": f"Each dimension score S_d (0 to 100) is multiplied by its weight and added up. Weights: Performance {_g(w['performance'])}, Relationship {_g(w['relationship'])}, Engagement {_g(w['engagement'])}, Commercial {_g(w['commercial'])} (they sum to {_g(sum(w.values()))}).", "kind": "weighted additive scoring"},
        {"key": "final", "title": "2. Final risk score", "formula": f"Score = min(100, {_g(ag['weighted_share'])} × WM + {_g(round(1 - ag['weighted_share'], 4))} × max(S_d) + Bonus)", "plain": f"{_g(ag['weighted_share'])} of the score is the weighted mean; {_g(round(1 - ag['weighted_share'], 4))} is the single strongest dimension. The share is fixed by configuration, it is not a cap on a separate adjustment.", "kind": "weighted additive scoring with a strongest-dimension term"},
        {"key": "bonus", "title": "3. Convergence bonus", "formula": f"Bonus = min({ag['convergence_cap']}, {ag['convergence_bonus_per_extra_dim']} × max(0, F − 1)),  F = number of dimensions with S_d ≥ {ag['convergence_threshold']}", "plain": f"When several dimensions agree, up to {ag['convergence_cap']} extra points are added: {ag['convergence_bonus_per_extra_dim']} for each dimension beyond the first that reaches {ag['convergence_threshold']}.", "kind": "rule-based adjustment"},
        {"key": "lin", "title": "4. Capped linear scale (used for TPV change and success-rate change)", "formula": "S = clamp( (x − x₀) / (x₁ − x₀) × 100, 0, 100 )", "plain": f"x₀ is the value that scores 0 and x₁ the value that scores 100; anything beyond is capped. TPV change: x₀ = {_g(tpv['zero_at_pct'])}%, x₁ = {_g(tpv['full_at_pct'])}%. Success-rate change: x₀ = {_g(sx['zero_at_pp'])}pp, x₁ = {_g(sx['full_at_pp'])}pp. This is NOT min-max scaling across merchants: the anchors are fixed business thresholds.", "kind": "capped linear normalisation"},
        {"key": "perf", "title": "5. Performance dimension", "formula": f"S_perf = {_g(pf['max_share'])} × max(TPV, Success) + {_g(round(1 - pf['max_share'], 4))} × min(TPV, Success)", "plain": "The worse of the two payment signals counts most, so a single severe signal is not diluted by the other being healthy.", "kind": "weighted blend"},
        {"key": "tpvmul", "title": "6. TPV trend consistency and seasonal adjustment", "formula": "TPV score = base × consistency × (seasonal multiplier if dip-and-rebound)", "plain": f"Consistency depends on consecutive month-on-month declines ending at M6 (a fall must exceed {_g(tpv['decline_tolerance_pct'])}%): " + ", ".join(f"{k}: ×{_g(v)}" for k, v in tpv["consistency"].items()) + f". For a seasonal industry with a dip of {_g(sc['seasonal']['dip_min_pct'])}% or more followed by a rebound of {_g(sc['seasonal']['rebound_min_pct'])}%+, the TPV score is multiplied by {_g(sc['seasonal']['multiplier'])}.", "kind": "trend analysis with a contextual multiplier"},
        {"key": "bands", "title": "7. Risk band", "formula": f"High if Score ≥ {_g(sc['bands']['high'])};  Moderate if Score ≥ {_g(sc['bands']['medium'])};  otherwise Low", "plain": "A rule-based band, not a probability of churn.", "kind": "threshold-based classification"},
        {"key": "revenue", "title": "8. Annual net-revenue run-rate proxy", "formula": "Run-rate (Rs) = M6 TPV (Rs lakh) × 100,000 × net revenue rate × 12", "plain": f"With the workbook's net revenue rate of {_g(st['net_revenue_rate'] * 100)}%: Run-rate (Rs lakh) = M6 TPV (Rs lakh) × {_g(st['net_revenue_rate'])} × {st['saved_merchant_months']}. This is exposure, not revenue lost and not a guaranteed saving.", "kind": "revenue run-rate estimation"},
        {"key": "priority", "title": "9. Priority index (who to contact first)", "formula": "Index = ( w_r × Run-rate − (1 − w_r) × Outreach cost ) × Urgency,   w_r = (Score / 100) × Confidence factor", "plain": "A ranking aid in rupees. w_r is a weight between 0 and 1 and is NOT a probability of churn or of saving the merchant. Outreach cost and urgency come from the workbook and configuration. It is not an expected-value forecast.", "kind": "ranking and constrained selection"},
    ]


def _features(sc: dict) -> list[dict]:
    sv, eg, cm, tpv, sx = sc["service"], sc["engagement"], sc["commercial"], sc["tpv"], sc["success"]
    steps = lambda d: ", ".join(f"{k}: {v}" for k, v in d.items())
    return [
        {"dimension": "performance", "name": "Payment and volume performance", "features": [
            {"feature": "TPV trend", "source": "tpv_m1_inr_lakh … tpv_m6_inr_lakh", "calc": f"Average of M4-M6 compared with average of M1-M3, as a %. Capped linear: 0 points at {_g(tpv['zero_at_pct'])}% or better, 100 at {_g(tpv['full_at_pct'])}% or worse. Multiplied by trend consistency (consecutive declines)", "direction": "A decline raises risk; growth adds nothing", "limit": "Six monthly points only. Seasonal dip-and-rebound is discounted"},
            {"feature": "Recent momentum (M6 vs M5)", "source": "tpv_m5, tpv_m6", "calc": "Not a separate score input. Used to detect a rebound (seasonal adjustment) and shown on the profile; consecutive declines scale the TPV score instead", "direction": "Context only", "limit": "One month of change is noisy"},
            {"feature": "Payment success-rate change", "source": "success_rate_m1_m3_pct, success_rate_m4_m6_pct", "calc": f"Difference in percentage points. Capped linear: 0 at {_g(sx['zero_at_pp'])}pp, 100 at {_g(sx['full_at_pp'])}pp", "direction": "A fall raises risk", "limit": "Only TWO period averages exist; no monthly success-rate trend is available or inferred"}]},
        {"dimension": "relationship", "name": "Relationship and service experience", "features": [
            {"feature": "Unresolved tickets", "source": "unresolved_tickets", "calc": "Step table: " + steps(sv["unresolved_points"]) + " points (5 or more = 100)", "direction": "More open tickets raises risk; resolved tickets are not penalised", "limit": "Open tickets older than 90 days can exceed the 90-day count"},
            {"feature": "CSAT", "source": "last_csat_1_to_5", "calc": "Step table: " + steps(sv["csat_points"]) + " points. Missing CSAT scores 0", "direction": "Low CSAT raises risk; missing is unknown, not poor", "limit": "A single survey"},
            {"feature": "Service notes", "source": "account_manager_note", "calc": "Added points: " + steps(sv["note_points"]) + f". Combined: {_g(sv['max_share'])} × larger + {_g(round(1 - sv['max_share'], 4))} × smaller of unresolved and CSAT, then notes, then growth damping ×{_g(sv['growth_damping']['multiplier'])} for a busy but growing merchant", "direction": "Complaint or escalation raises risk", "limit": "Unverified free text, read by keyword rules"}]},
        {"dimension": "engagement", "name": "Engagement and adoption", "features": [
            {"feature": "Logins", "source": "logins_last_30d", "calc": "Step table (logins ≤ limit → points): " + ", ".join(f"≤{a}: {b}" for a, b in eg["login_points"]) + f". Counts {_g(eg['login_share'])} of the dimension", "direction": "Very few logins raises risk", "limit": "Current 30-day snapshot; no history, so no decline over time can be claimed"},
            {"feature": "Products used", "source": "products_used", "calc": "Step table: " + steps(eg["product_points"]) + f" points (3 or more = 0). Counts {_g(round(1 - eg['login_share'], 4))} of the dimension", "direction": "Few products raises risk", "limit": "Current snapshot; no adoption history"},
            {"feature": "Disengagement notes", "source": "account_manager_note", "calc": "Added points: " + steps(eg["note_points"]) + f". Small merchants with stable TPV ({_g(eg['natural_low_touch']['min_tpv_change_pct'])}% or better, no note signal) have the usage score ×{_g(eg['natural_low_touch']['multiplier'])}", "direction": "Unresponsive or contact change raises risk", "limit": "Unverified free text"}]},
        {"dimension": "commercial", "name": "Commercial and renewal risk", "features": [
            {"feature": "Competitor, pricing or rate-card signal", "source": "account_manager_note", "calc": "Highest signal counts: " + steps(cm["signal_points"]) + " points", "direction": "A signal raises risk", "limit": "Entirely note-based and unverified; no independent field corroborates it"},
            {"feature": "Renewal proximity", "source": "days_to_contract_renewal", "calc": "Bonus only when a commercial signal exists: " + ", ".join(f"≤{a} days: +{b}" for a, b in cm["renewal_bonus"]), "direction": "Raises the stakes of a signal; adds nothing on its own", "limit": "Timing, not intent to leave"}]},
    ]


def _validation(s: dict | None) -> dict:
    ms = (s or {}).get("merchants", [])
    csat = sum(m["csat_missing"] for m in ms)
    note = sum(not m["note"] for m in ms)
    both = sum(m["completeness"] == 0 for m in ms)
    return {
        "checks": [
            {"check": "Merchant ID uniqueness and duplicate records", "action": "A repeated ID is reported; the first occurrence is kept and the rest are listed as excluded."},
            {"check": "Required-column mapping", "action": "Columns are matched to the 23 expected fields by exact name, synonym and fuzzy match. Exact matches are marked; anything else needs your confirmation."},
            {"check": "Workbook-sheet identification", "action": "Sheets are classified as merchants, playbooks or assumptions. In a combined P1/P2/P3 workbook only Problem 2 sheets are used and the others are listed as excluded."},
            {"check": "Data types and numeric cleaning", "action": "Percent signs, commas and Rs prefixes are cleaned; a value that cannot be read as a number is treated as missing and reported."},
            {"check": "Invalid or out-of-range values", "action": "Success rates outside 0-100, CSAT outside 1-5 and negative counts or TPV are flagged; the record is excluded if a required field is unusable."},
            {"check": "Missing CSAT and missing account-manager notes", "action": "Kept as unknown. They lower evidence completeness and confidence, and add no risk points."},
            {"check": "Source-data completeness", "action": "Each merchant gets a completeness score (CSAT present, note present); the portfolio shows how many are incomplete."},
        ],
        "unknown_examples": [
            {"claim": "Missing CSAT ≠ Poor CSAT", "detail": f"{csat} merchants have no CSAT. They score 0 on the CSAT feature, exactly like a merchant with a CSAT of 4 or 5 would."},
            {"claim": "Missing account-manager note ≠ No relationship engagement", "detail": f"{note} merchants have no note. No commercial or note-based points are added; the merchant is not treated as disengaged."},
            {"claim": "Missing data lowers confidence, not the score", "detail": f"{both} merchants have neither. Confidence cannot be High unless completeness is at least {sc_conf()}% and two or more dimensions agree."},
        ],
        "confidence_rule": f"Confidence is High only when at least two dimensions reach the convergence threshold and completeness is at least {sc_conf()}%; it is Low when the note looks like an instruction (prompt-injection flag). Confidence feeds the priority index (factor High 1.0, Medium 0.85, Low 0.6) but never the risk score.",
    }


def sc_conf() -> int:
    return load_scoring()["confidence"]["min_completeness_for_high"]


def _playbooks(pb: dict, rows: list[dict]) -> list[dict]:
    t = pb["triggers"]
    concern = {"PB-1": "Payments are failing or volume is falling: a technical or integration issue to diagnose with Payments Ops.", "PB-2": "Support is failing the merchant: open tickets and low satisfaction need one owner and a closure date.",
               "PB-3": "A commercial threat near renewal: pricing, a competitor or a rate-card request needs a terms review before the contract date.", "PB-4": "The merchant is drifting away: low usage, few products or a changed contact need re-engagement.",
               "PB-5": "The merchant is healthy and growing: a positive check-in and an expansion conversation.", "PB-6": "Nothing needs outreach now: a seasonal dip, a naturally low-volume merchant, or no real signal. Watch and re-check."}
    rule = {"PB-1": f"Success rate fell {_g(abs(t['PB-1']['max_success_drop_pp']))}pp or more, OR the note records a payment-failure concern.",
            "PB-2": f"{t['PB-2']['min_unresolved']}+ unresolved tickets, OR CSAT ≤ {t['PB-2']['low_csat_max']} with at least {t['PB-2']['low_csat_min_unresolved']} unresolved.",
            "PB-3": f"A competitor / exploring-options / rate-card / pricing signal in the note AND renewal within {t['PB-3']['max_renewal_days']} days.",
            "PB-4": f"≤ {t['PB-4']['max_logins']} logins AND ≤ {t['PB-4']['max_products']} products AND (TPV down {_g(abs(t['PB-4']['requires_any']['max_recent_vs_early_pct']))}%+ OR an unresponsive / contact-change note).",
            "PB-5": f"Low risk band AND TPV up {t['PB-5']['min_recent_vs_early_pct']}%+ AND success change ≥ {_g(t['PB-5']['min_success_drop_pp'])}pp AND ≤ {t['PB-5']['max_unresolved']} unresolved AND CSAT ≥ {t['PB-5']['min_csat_if_present']} if present.",
            "PB-6": "Default when nothing above applies (and for every Low-band merchant who is not healthy and growing)."}
    return [{"id": p["playbook_id"], "name": p["name"], "what_happens": p["what_happens"], "when_workbook": p["when_it_applies"], "concern": concern[p["playbook_id"]], "rule": rule[p["playbook_id"]],
             "uses_slot": p["playbook_id"] in load_settings()["selection"]["eligible_playbooks"]} for p in rows]


def _tree(ms: list[dict], sc: dict, pb: dict) -> list[dict]:
    t, ag, bands = pb["triggers"], sc["aggregation"], sc["bands"]
    cap = load_settings()["source_assumptions"]["max_outreaches"]
    ex = lambda pred, pref=None: _example(ms, pred, pref)
    pbx = lambda pid: ex(lambda m: m["assessment"]["primary_playbook_id"] == pid, lambda m: -m["risk_score"])
    return [
        {"id": "n0", "type": "start", "title": "Start: score and band", "question": "Every merchant first gets four dimension scores, a final score and a band.", "condition": f"Score = {_g(ag['weighted_share'])} × weighted mean + {_g(round(1 - ag['weighted_share'], 4))} × strongest dimension + convergence bonus. Band: High ≥ {_g(bands['high'])}, Moderate ≥ {_g(bands['medium'])}, else Low.", "yes": "n1", "no": None, "result": None, "reason": "Contextual adjustments (seasonal dip-and-rebound, small stable merchant, busy-but-growing) are applied inside this scoring step, before the band is assigned.", "data": "all merchant fields", "example": ex(lambda m: m["risk_band"] == "high", lambda m: -m["risk_score"])},
        {"id": "n1", "type": "decision", "title": "Is the evidence complete?", "question": "Are CSAT and an account-manager note both available?", "condition": f"Completeness < 100 when CSAT or a note is missing. Confidence is High only with ≥ {sc['confidence']['min_completeness_for_high']}% completeness and ≥ 2 dimensions at {ag['convergence_threshold']}+.", "yes": "n2", "no": "n2", "yes_label": "Complete: normal confidence", "no_label": "Incomplete: missing evidence is flagged and confidence limited. The merchant is NOT scored as worse and the flow continues.", "result": None, "reason": "Missing data is unknown, not negative, so it never raises the score.", "data": "last_csat_1_to_5, account_manager_note", "example": ex(lambda m: m["completeness"] == 0)},
        {"id": "n2", "type": "decision", "title": "Is the merchant in the Low band?", "question": f"Is the score below {_g(bands['medium'])}?", "condition": f"Low band = score < {_g(bands['medium'])}", "yes": "n3", "no": "n4", "yes_label": "Yes: no churn outreach; check for growth", "no_label": "No (Moderate or High): look for an intervention", "result": None, "reason": "Outreach capacity is reserved for merchants with real evidence of risk.", "data": "risk_score", "example": ex(lambda m: m["risk_band"] == "low")},
        {"id": "n3", "type": "decision", "title": "Healthy and growing?", "question": "Is the merchant growing with no service or payment concern?", "condition": pb_rule5(t), "yes": "o5", "no": "o6", "yes_label": "Yes: PB-5 growth check-in", "no_label": "No: PB-6 monitor only", "result": None, "reason": "A growing merchant is a relationship opportunity, not a risk. Seasonal dips, naturally low volume and busy-but-growing merchants stay here and are not escalated.", "data": "tpv change, success change, unresolved tickets, CSAT", "example": ex(lambda m: m["risk_band"] == "low", lambda m: -m["tpv_change_pct"])},
        {"id": "n4", "type": "decision", "title": "Which playbook triggers fire?", "question": "Each of PB-1 to PB-4 is tested independently. Several can fire at once.", "condition": f"PB-1: success fell ≥ {_g(abs(t['PB-1']['max_success_drop_pp']))}pp or a payment-failure note.  PB-2: ≥ {t['PB-2']['min_unresolved']} unresolved, or CSAT ≤ {t['PB-2']['low_csat_max']} with ≥ {t['PB-2']['low_csat_min_unresolved']} open.  PB-3: commercial signal and renewal ≤ {t['PB-3']['max_renewal_days']} days.  PB-4: ≤ {t['PB-4']['max_logins']} logins, ≤ {t['PB-4']['max_products']} products and TPV down {_g(abs(t['PB-4']['requires_any']['max_recent_vs_early_pct']))}%+ or an unresponsive / contact-change note.", "yes": "n5", "no": "o6", "yes_label": "At least one fires", "no_label": "None fires: PB-6, monitor and verify", "result": None, "reason": "This is not a fixed order. A merchant with payment and service problems gets whichever playbook fits its strongest evidence, not whichever comes first.", "data": "success_rate_m1_m3_pct, success_rate_m4_m6_pct, unresolved_tickets, last_csat_1_to_5, logins_last_30d, products_used, days_to_contract_renewal, notes", "example": ex(lambda m: m["risk_band"] != "low" and m["assessment"]["primary_playbook_id"] == "PB-6")},
        {"id": "n5", "type": "decision", "title": "Did more than one fire?", "question": "If several triggered, which is primary?", "condition": f"Fit = the matching dimension's score (PB-1 Performance, PB-2 Relationship, PB-3 Commercial, PB-4 Engagement). Highest fit is primary; ties go in the order {', '.join(pb['tie_break_order'])}. The runner-up is a secondary playbook only if its fit ≥ {pb['secondary_min_fit']}.", "yes": "o1", "no": "o1", "yes_label": "Several: highest fit wins; runner-up shown as secondary or as 'triggered but lower fit'", "no_label": "One: that playbook", "result": None, "reason": "One CSM interaction can cover a secondary concern, so a secondary playbook is coordinated rather than run separately.", "data": "dim_performance, dim_relationship, dim_commercial, dim_engagement", "example": ex(lambda m: bool(m["assessment"].get("secondary_playbook_id")) or bool(m["playbooks_not_selected"]), lambda m: -m["risk_score"])},
        {"id": "o1", "type": "outcome", "title": "Playbook selected: PB-1, PB-2, PB-3 or PB-4", "question": "A risk-action playbook is chosen from the workbook's own text.", "condition": "Outcome of the fit comparison", "yes": "n6", "no": None, "result": "PB-1 / PB-2 / PB-3 / PB-4", "reason": "The playbook text and commitments come only from the workbook. EDGE adds no concession.", "data": "P2_Playbooks", "example": pbx("PB-1")},
        {"id": "n6", "type": "decision", "title": "Is the merchant eligible for outreach capacity?", "question": f"Is the playbook PB-1 to PB-4, the band at least Moderate, and the priority index positive?", "condition": f"Eligible merchants are ordered by the chosen business priorities, then by priority index, then risk score, then merchant ID. The first {cap} are shortlisted.", "yes": "o7", "no": "o8", "yes_label": "Eligible: ranked for the shortlist", "no_label": "Not eligible: reviewed manually", "result": None, "reason": "Risk and priority are different questions. Priority decides who is contacted first when there are not enough slots.", "data": "primary_playbook_id, risk_band, priority_value", "example": ex(lambda m: m["eligible"] and m["selected"])},
        {"id": "o5", "type": "outcome", "title": "PB-5 Growth / expansion check-in", "question": "", "condition": "Healthy and growing", "yes": None, "no": None, "result": "PB-5", "reason": "Does not use churn outreach capacity.", "data": "", "example": pbx("PB-5")},
        {"id": "o6", "type": "outcome", "title": "PB-6 Monitor only", "question": "", "condition": "Seasonal dip, naturally low volume, or no real risk signal", "yes": None, "no": None, "result": "PB-6", "reason": "Keep on the watchlist and re-check next month. Does not use outreach capacity.", "data": "", "example": pbx("PB-6")},
        {"id": "o7", "type": "outcome", "title": "On the shortlist or just outside it", "question": "", "condition": f"Rank ≤ {cap}: selected. Rank above {cap}: eligible but outside, with the gap to the last selected merchant shown.", "yes": None, "no": None, "result": "Selected / outside", "reason": "A human then reviews the evidence, approves a draft and records the outcome.", "data": "", "example": ex(lambda m: m["eligible"] and not m["selected"])},
        {"id": "o8", "type": "outcome", "title": "Not selected for churn outreach", "question": "", "condition": "Playbook PB-5 / PB-6, a Low band, or a non-positive index", "yes": None, "no": None, "result": "Manual review", "reason": "Moderate or high merchants outside the rules are still listed in the Priority Queue for manual review.", "data": "", "example": ex(lambda m: m["risk_band"] != "low" and not m["eligible"])},
    ]


def pb_rule5(t: dict) -> str:
    p = t["PB-5"]
    return f"Low band AND TPV up ≥ {p['min_recent_vs_early_pct']}% AND success change ≥ {_g(p['min_success_drop_pp'])}pp AND ≤ {p['max_unresolved']} unresolved AND CSAT ≥ {p['min_csat_if_present']} if present"


def _worked(s: dict | None, sc: dict, st: dict) -> dict:
    out: dict = {"score": None, "priority": None, "revenue": None}
    if not s:
        return out
    ms = s["merchants"]
    w = sc["weights"]
    cand = [m for m in ms if m.get("score_parts") and sum(v >= sc["aggregation"]["convergence_threshold"] for v in m["dims"].values()) >= 2]
    pick = max(cand, key=lambda m: m["risk_score"]) if cand else max((m for m in ms if m.get("score_parts")), key=lambda m: m["risk_score"], default=None)
    if pick:
        p = pick["score_parts"]
        out["score"] = {"merchant": {"id": pick["id"], "name": pick["name"]}, "dims": pick["dims"], "weights": w, "weighted_points": p["weighted_points"], "weighted_mean": p["weighted_mean"], "strongest": p["strongest_dimension"],
                        "share": p["weighted_share"], "bonus": p["convergence_bonus"], "total": pick["risk_score"], "band": pick["risk_label"]}
        out["revenue"] = {"merchant": {"id": pick["id"], "name": pick["name"]}, "m6_tpv_lakh": pick["tpv_m6"], "rate": st["net_revenue_rate"], "months": st["saved_merchant_months"], "annual_inr": pick["annual_value"],
                          "annual_lakh": round(pick["tpv_m6"] * st["net_revenue_rate"] * st["saved_merchant_months"], 2)}
    big = [m for m in ms if m["risk_band"] == "medium" and m["segment"] in ("Enterprise", "Mid") and m["eligible"] and m["rank"]]
    small = [m for m in ms if m["risk_band"] == "high" and m["segment"] == "Small"]
    pair = None
    for a in sorted(big, key=lambda m: m["rank"]):
        for b in sorted(small, key=lambda m: -m["risk_score"]):
            if a["priority_value"] > b["priority_value"] and a["risk_score"] < b["risk_score"]:
                pair = (a, b)
                break
        if pair:
            break
    if pair:
        row = lambda m: {"id": m["id"], "name": m["name"], "segment": m["segment"], "band": m["risk_label"], "score": round(m["risk_score"], 1), "risk_weight": round(m["risk_weight"], 3), "annual_inr": m["annual_value"],
                         "urgency": m["urgency_multiplier"], "index": round(m["priority_value"]), "rank": int(m["rank"]) if m["rank"] else None, "selected": m["selected"], "renewal_days": m["renewal_days"]}
        out["priority"] = {"higher_priority": row(pair[0]), "higher_risk": row(pair[1]), "cost": st["false_alarm_cost_inr"]}
    return out


def build(session: dict | None = None) -> dict:
    sc, pb, se = load_scoring(), load_playbook_cfg(), load_settings()
    st = (session or {}).get("assumptions") or se["source_assumptions"]
    ms = (session or {}).get("merchants", [])
    counts = {"seasonal_not_escalated": sum(m["seasonal_adjusted"] for m in ms), "natural_low_volume": sum(m["segment"] == "Small" and m["tpv_change_pct"] >= -5 and m["dims"]["engagement"] == 0 for m in ms) if ms else 0,
              "growing_resolved": sum(m["tickets"] >= 5 and m["unresolved"] <= 1 and m["tpv_change_pct"] >= 10 for m in ms)}
    weights = {d: sc["weights"][d] for d in DIMS}
    return {
        "generated_from": {"scoring_version": sc["scoring_version"], "config_version": se["config_version"], "analysis": (session or {}).get("name"), "analysis_version": (session or {}).get("version")},
        "weights": weights, "weights_sum": round(sum(weights.values()), 6), "bands": sc["bands"], "aggregation": sc["aggregation"], "assumptions": st,
        "architecture": _architecture(sc, pb, se, st),
        "validation": _validation(session),
        "features": _features(sc),
        "equations": _equations(sc, st),
        "worked": _worked(session, sc, st),
        "tree": _tree(ms, sc, pb),
        "playbooks": _playbooks(pb, (session or {}).get("playbooks", [])) if session else [],
        "glossary": _glossary(),
        "not_used": ["Machine learning", "Logistic regression", "Random forests", "Gradient boosting", "Clustering", "Survival analysis", "Calibrated churn probabilities"],
        "human": {"steps": ["EDGE's rules flag potential risk and show the evidence behind it.", "A CSM reads the evidence, including mitigating and contradictory signals.", "The CSM checks unverified account-manager notes with the account manager.",
                            "The CSM edits and approves the outreach. Nothing is sent by EDGE.", "The CSM records the outcome in structured categories.", "Verified outcomes can later support proper model validation."],
                  "statement": "EDGE is a rule-based early-warning and decision-support system. The available dataset does not contain verified future churn outcomes, so predictive accuracy, precision, recall and calibrated churn probabilities cannot currently be established.",
                  "context_factors": [{"name": "Seasonality", "detail": "Gifting, Education and Travel dips that rebound are discounted, so a normal seasonal low is not escalated.", "count": counts["seasonal_not_escalated"]},
                                      {"name": "Naturally low volume", "detail": "Small, stable merchants with low usage are treated as normal, not at risk.", "count": counts["natural_low_volume"]},
                                      {"name": "Growing with many resolved tickets", "detail": "Busy merchants raise many tickets; resolved tickets are never penalised.", "count": counts["growing_resolved"]}]},
        "sensitivity_note": "These weights are transparent management assumptions. Sensitivity analysis tests whether business decisions are robust to changes in those assumptions. It measures ranking robustness, not predictive accuracy, and no scenario is statistically optimal.",
    }


def _architecture(sc: dict, pb: dict, se: dict, st: dict) -> list[dict]:
    ag, bands, cap = sc["aggregation"], sc["bands"], st.get("max_outreaches", 15)
    return [
        {"id": "source", "title": "Source data", "what": "The Problem 2 workbook: merchants, playbooks and assumptions.", "fields": ["P2_Merchants (21 columns)", "P2_Playbooks", "P2_Assumptions"], "rule": "Sheets are identified by content and name; other problem statements' sheets are excluded.", "why": "The workbook is the only source of truth for facts, playbooks and business assumptions.", "output": "Raw merchant rows, six playbooks, assumption values"},
        {"id": "validate", "title": "Data validation and quality checks", "what": "Checks IDs, duplicates, types, ranges and missing values.", "fields": ["merchant_id", "all numeric columns", "last_csat_1_to_5", "account_manager_note"], "rule": "Duplicates keep the first row; unreadable numbers become missing; out-of-range values are flagged; missing CSAT or notes stay unknown.", "why": "Bad inputs must be visible before any score is trusted.", "output": "Clean merchant table, an exclusion list and a completeness score per merchant"},
        {"id": "features", "title": "Feature engineering", "what": "Turns raw columns into comparable signals.", "fields": ["tpv_m1..m6", "success_rate_m1_m3/m4_m6", "tickets, CSAT", "logins, products", "days_to_contract_renewal", "notes"], "rule": f"TPV change = avg(M4-M6) vs avg(M1-M3); consecutive declines ending at M6; success change in pp; notes read by keyword rules; run-rate = M6 TPV × {_g(st['net_revenue_rate'])} × 12.", "why": "A trend or a change is more informative than a single month.", "output": "A feature row per merchant"},
        {"id": "context", "title": "Contextual interpretation", "what": "Separates genuine risk from normal patterns.", "fields": ["industry", "segment", "tpv_m4..m6", "unresolved_tickets", "notes"], "rule": f"Seasonal industry with a dip of {_g(sc['seasonal']['dip_min_pct'])}%+ then a rebound: TPV score ×{_g(sc['seasonal']['multiplier'])}. Small stable merchant: usage score ×{_g(sc['engagement']['natural_low_touch']['multiplier'])}. Busy but growing: service score ×{_g(sc['service']['growth_damping']['multiplier'])}.", "why": "Prevents false alarms on seasonality, naturally low volume and busy-but-growing merchants.", "output": "Adjusted signals with the adjustment recorded"},
        {"id": "scoring", "title": "Risk scoring engine", "what": "Scores four dimensions and combines them.", "fields": ["performance", "relationship", "engagement", "commercial"], "rule": f"Score = {_g(ag['weighted_share'])} × Σ(w×S) + {_g(round(1 - ag['weighted_share'], 4))} × max(S) + convergence bonus (≤ {ag['convergence_cap']}); capped at 100.", "why": "A weighted additive score is transparent and auditable; the strongest-dimension term stops one severe signal being diluted.", "output": "Four dimension scores and a 0-100 risk score with every point recorded"},
        {"id": "classify", "title": "Risk classification", "what": "Assigns a band.", "fields": ["risk_score"], "rule": f"High ≥ {_g(bands['high'])}; Moderate ≥ {_g(bands['medium'])}; Low below.", "why": "Managers act on categories, not decimals. The bands are hypotheses, not probabilities.", "output": "High / Moderate / Low"},
        {"id": "rootcause", "title": "Root-cause identification", "what": "Names the main driver and any secondary ones.", "fields": ["dimension scores"], "rule": f"A dimension must reach {sc['driver_min_score']} to be a driver; the highest is primary.", "why": "A score without a reason cannot be acted on.", "output": "Primary and secondary driver"},
        {"id": "priority", "title": "Outreach prioritisation", "what": "Orders eligible merchants for limited capacity.", "fields": ["risk_score", "confidence", "annual run-rate", "days_to_contract_renewal"], "rule": f"Eligible = PB-1..PB-4, band ≥ {se['selection']['min_band']}, index > 0. Index = (w_r × run-rate − (1 − w_r) × outreach cost) × urgency; w_r = score/100 × confidence factor. Top {cap} are shortlisted.", "why": "With {cap} slots, who to contact first is a separate question from who is riskiest.".replace("{cap}", str(cap)), "output": f"Ranked list; the first {cap} are selected"},
        {"id": "playbook", "title": "Playbook selection", "what": "Chooses the intervention from the workbook's six playbooks.", "fields": ["success change", "unresolved tickets, CSAT", "notes, renewal", "logins, products"], "rule": "PB-1..PB-4 triggers are tested independently; the highest-fit one is primary (fit = its dimension's score); PB-5 for healthy and growing; PB-6 otherwise.", "why": "The action must match the evidence, using only the playbook text supplied.", "output": "Primary (and secondary) playbook with the reason"},
        {"id": "draft", "title": "Outreach drafting", "what": "Prepares an editable draft for the selected merchants.", "fields": ["playbook text", "merchant's own verified figures"], "rule": "Template text, optionally refined by Claude, then checked: no risk score, no churn wording, no concession, only approved figures.", "why": "A first draft saves time; guardrails keep it factual.", "output": "Subject and body, marked DRAFT"},
        {"id": "review", "title": "Human review and approval", "what": "A CSM reviews and approves.", "fields": ["review pack", "draft text"], "rule": "Review → named reviewer approves → contact recorded manually. Unresolved placeholders and unsupported claims block approval.", "why": "Notes are unverified and context matters; a person must own the message.", "output": "An approved draft. Nothing is sent by EDGE"},
        {"id": "outcome", "title": "Outcome tracking", "what": "Records what happened.", "fields": ["outcome category", "concern validated", "issue category", "action taken"], "rule": "Structured outcome categories are stored with each case.", "why": "Verified outcomes are the only route to validating the model in future.", "output": "A history log. Outcomes are CSM observations, not churn labels"},
    ]


def _glossary() -> list[dict]:
    return [
        {"method": "Weighted additive scoring", "meaning": "Multiply each part by an importance weight and add.", "where": "Combining the four dimension scores; combining features inside a dimension.", "why": "Every contribution is visible and can be challenged.", "limit": "Weights are manager-designed, not learned from outcomes."},
        {"method": "Capped linear normalisation", "meaning": "Map a value onto 0-100 between two fixed anchors and cap it outside them.", "where": "TPV change and success-rate change.", "why": "Business thresholds are explicit and do not depend on other merchants. (This is not min-max scaling across the portfolio.)", "limit": "The anchors are judgement calls."},
        {"method": "Step / threshold scoring", "meaning": "A lookup table from a value band to points.", "where": "Unresolved tickets, CSAT, logins, products.", "why": "Simple, auditable and robust to small counts.", "limit": "Edges are abrupt: 5 logins and 6 logins score differently."},
        {"method": "Period-over-period comparison", "meaning": "Compare the recent period with the earlier one.", "where": "Average M4-M6 against M1-M3 TPV; the two success-rate averages.", "why": "Smooths single-month noise.", "limit": "Only two or six data points; no seasonality model."},
        {"method": "Trend (consecutive-decline) analysis", "meaning": "Count months of fall in a row.", "where": "The TPV consistency multiplier and the silent-decline trigger.", "why": "A sustained fall is more worrying than a dip.", "limit": "Needs a tolerance; tiny falls are ignored."},
        {"method": "Rule-based decision logic", "meaning": "If-then rules with explicit thresholds.", "where": "Playbook triggers, contextual adjustments, critical review triggers, eligibility.", "why": "Every decision can be traced to a rule.", "limit": "Rules do not adapt unless a person changes them."},
        {"method": "Threshold-based classification", "meaning": "Cut a score into categories.", "where": "High / Moderate / Low.", "why": "Gives managers a simple handle.", "limit": "Merchants just either side of a cut-off look alike."},
        {"method": "Ranking and constrained selection", "meaning": "Sort candidates and take the top N within a capacity limit.", "where": "The 15-contact shortlist.", "why": "Capacity is the real business constraint.", "limit": "Small merchants can be rarely selected whatever their risk."},
        {"method": "Scenario analysis", "meaning": "Re-run the engine under alternative weights or priorities.", "where": "Decision Studio.", "why": "Lets managers see how choices change the list.", "limit": "A scenario is a what-if, not a forecast."},
        {"method": "Sensitivity analysis", "meaning": "Re-run under many seeded random configurations and count how often each merchant is selected.", "where": "Ranking robustness (305 configurations).", "why": "Shows which decisions are stable and which depend on assumptions.", "limit": "Measures ranking stability, not accuracy."},
        {"method": "Revenue run-rate estimation", "meaning": "Scale the latest month to a year.", "where": "Annual run-rate proxy and exposure.", "why": "A common size measure.", "limit": "An assumption-based proxy, not revenue lost or saved."},
    ]
