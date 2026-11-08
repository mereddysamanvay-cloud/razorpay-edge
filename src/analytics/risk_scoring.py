"""Transparent, configurable heuristic risk scoring (NOT a churn probability).

Dimensions (0-100 each): performance, relationship (service), engagement, commercial.
Every point awarded is recorded in `contributions` so a CSM can audit the score.
"""
from __future__ import annotations

import math

import pandas as pd

DIMENSIONS = ["performance", "relationship", "engagement", "commercial"]
DRIVER_LABELS = {
    "performance": "Payments performance (success-rate and/or volume decline)",
    "relationship": "Service experience (unresolved tickets / low CSAT)",
    "engagement": "Disengagement (low usage / contact change / unresponsive)",
    "commercial": "Commercial displacement (competitor, pricing, renewal)",
}


def _nan(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def lin(x: float, zero: float, full: float) -> float:
    """Linear 0..100 mapping: `zero` -> 0, `full` -> 100 (either direction), clamped."""
    if _nan(x):
        return 0.0
    t = (x - zero) / (full - zero)
    return max(0.0, min(100.0, t * 100.0))


def _step(value: float, table: list[list[float]]) -> float:
    for limit, pts in table:
        if value <= limit:
            return float(pts)
    return 0.0


def _band(score: float, bands: dict) -> str:
    return "high" if score >= bands["high"] else "medium" if score >= bands["medium"] else "low"


def score_row(r: pd.Series, cfg: dict) -> dict:
    contrib: list[dict] = []

    def add(dim, feat, value, pts, why):
        contrib.append({"dimension": dim, "feature": feat, "value": value, "points": round(float(pts), 1), "why": why})

    # ---- performance ------------------------------------------------------------------------
    tcfg, scfg = cfg["tpv"], cfg["seasonal"]
    tpv_base = lin(r["recent_vs_early_pct"], tcfg["zero_at_pct"], tcfg["full_at_pct"])
    cons = tcfg["consistency"][min(int(r["consecutive_declines"]), 4)]
    tpv_score = tpv_base * cons
    seasonal_applied = False
    if scfg["enabled"] and r["is_seasonal_industry"] and r["dip_and_rebound"]:
        tpv_score *= scfg["multiplier"]
        seasonal_applied = True
    succ_score = lin(r["success_drop_pp"], cfg["success"]["zero_at_pp"], cfg["success"]["full_at_pp"])
    ms = cfg["performance"]["max_share"]
    perf = ms * max(tpv_score, succ_score) + (1 - ms) * min(tpv_score, succ_score)
    add("performance", "recent_vs_early_pct", round(r["recent_vs_early_pct"], 1), tpv_score,
        f"base {tpv_base:.0f} x trend consistency {cons} ({int(r['consecutive_declines'])} consecutive declines)"
        + (f" x seasonal dip-and-rebound multiplier {scfg['multiplier']}" if seasonal_applied else ""))
    add("performance", "success_drop_pp", round(r["success_drop_pp"], 1), succ_score,
        "change in success rate, percentage points (M4-M6 minus M1-M3)")

    # ---- relationship / service ---------------------------------------------------------------
    sv = cfg["service"]
    unres = sv["unresolved_points"][min(int(r["unresolved"]), 5)]
    csat_pts = 0.0 if _nan(r["csat"]) else sv["csat_points"][int(round(r["csat"]))]
    hi, lo = max(unres, csat_pts), min(unres, csat_pts)
    rel = sv["max_share"] * hi + (1 - sv["max_share"]) * lo
    add("relationship", "unresolved_tickets", int(r["unresolved"]), unres, "open tickets (resolved tickets are not penalised)")
    add("relationship", "last_csat_1_to_5", None if _nan(r["csat"]) else r["csat"], csat_pts,
        "missing CSAT contributes 0 (unknown, not poor)" if _nan(r["csat"]) else "most recent CSAT")
    for flag, pts in sv["note_points"].items():
        if r[f"note_{flag}"]:
            rel += pts
            add("relationship", f"note:{flag}", r["note_evidence"], pts, "account-manager note")
    gd = sv["growth_damping"]
    if r["unresolved"] <= gd["max_unresolved"] and r["recent_vs_early_pct"] >= gd["min_growth_pct"]:
        rel *= gd["multiplier"]
        add("relationship", "growth_damping", round(r["recent_vs_early_pct"], 1), 0,
            "busy-but-growing: tickets are expected, score x%.2f" % gd["multiplier"])
    rel = min(rel, 100.0)

    # ---- engagement ----------------------------------------------------------------------------
    eg = cfg["engagement"]
    login_pts = _step(r["logins_30d"], eg["login_points"])
    prod_pts = float(eg["product_points"].get(int(r["products_used"]), 0)) if r["products_used"] <= 2 else 0.0
    eng = eg["login_share"] * login_pts + (1 - eg["login_share"]) * prod_pts
    add("engagement", "logins_last_30d", int(r["logins_30d"]), eg["login_share"] * login_pts, "current snapshot only")
    add("engagement", "products_used", int(r["products_used"]), (1 - eg["login_share"]) * prod_pts, "current snapshot only")
    note_eng = 0.0
    for flag, pts in eg["note_points"].items():
        if r[f"note_{flag}"]:
            note_eng += pts
            add("engagement", f"note:{flag}", r["note_evidence"], pts, "account-manager note")
    nl = eg["natural_low_touch"]
    if (r["segment"] == nl["segment"] and r["recent_vs_early_pct"] >= nl["min_tpv_change_pct"] and note_eng == 0):
        eng *= nl["multiplier"]
        add("engagement", "natural_low_touch", r["segment"], 0, "small, stable merchant: low usage is expected, score x%.2f" % nl["multiplier"])
    eng = min(eng + note_eng, 100.0)

    # ---- commercial ------------------------------------------------------------------------------
    cm = cfg["commercial"]
    sigs = [(f, p) for f, p in cm["signal_points"].items() if r[f"note_{f}"]]
    com = 0.0
    if sigs:
        flag, com = max(sigs, key=lambda x: x[1])
        add("commercial", f"note:{flag}", r["note_evidence"], com, "explicit signal in account-manager note")
        bonus = _step(r["renewal_days"], cm["renewal_bonus"])
        if bonus:
            add("commercial", "days_to_contract_renewal", int(r["renewal_days"]), bonus, "renewal proximity (only counted alongside a commercial signal)")
        com = min(100.0, com + bonus)

    dims = {"performance": perf, "relationship": rel, "engagement": eng, "commercial": com}

    # ---- aggregate ----------------------------------------------------------------------------
    ag, w = cfg["aggregation"], cfg["weights"]
    wsum = sum(w.values())
    weighted = sum(dims[d] * w[d] for d in DIMENSIONS) / wsum
    top = max(dims.values())
    fired = sum(1 for d in DIMENSIONS if dims[d] >= ag["convergence_threshold"])
    bonus = min(ag["convergence_cap"], ag["convergence_bonus_per_extra_dim"] * max(0, fired - 1))
    score = min(100.0, ag["weighted_share"] * weighted + (1 - ag["weighted_share"]) * top + bonus)
    band = _band(score, cfg["bands"])

    # ---- critical triggers (human review only) ------------------------------------------------
    ct, trig = cfg["critical_triggers"], []
    if r["recent_vs_early_pct"] <= ct["severe_performance"]["max_recent_vs_early_pct"] and r["success_drop_pp"] <= ct["severe_performance"]["max_success_drop_pp"]:
        trig.append("severe_performance: TPV down >=20% AND success rate down >=5pp")
    if r["note_competitor_explicit"] and r["renewal_days"] <= ct["competitor_near_renewal"]["max_renewal_days"]:
        trig.append("competitor_near_renewal: explicit competitor comparison and renewal <=30 days")
    if r["unresolved"] >= ct["service_breakdown"]["min_unresolved"] and not _nan(r["csat"]) and r["csat"] <= ct["service_breakdown"]["max_csat"]:
        trig.append("service_breakdown: >=4 unresolved tickets and CSAT <=2")
    sd = ct["silent_decline"]
    if r["logins_30d"] <= sd["max_logins"] and r["consecutive_declines"] >= sd["min_consecutive_declines"] and r["recent_vs_early_pct"] <= sd["max_recent_vs_early_pct"]:
        trig.append("silent_decline: <=2 logins with a sustained steep TPV decline")

    # ---- drivers --------------------------------------------------------------------------------
    ranked = sorted(DIMENSIONS, key=lambda d: (-dims[d], DIMENSIONS.index(d)))
    dm = cfg["driver_min_score"]
    drivers = [d for d in ranked if dims[d] >= dm]
    primary = drivers[0] if drivers else None

    # ---- confidence in the assessment (not a probability) ----------------------------------------
    contradictory = bool(seasonal_applied)
    if band in ("high", "medium"):
        conf = "high" if (fired >= 2 and r["completeness_score"] >= cfg["confidence"]["min_completeness_for_high"]) else "medium" if fired >= 1 else "low"
        if contradictory and conf == "high":
            conf = "medium"
    else:
        conf = "high" if (max(dims.values()) < dm and r["completeness_score"] >= cfg["confidence"]["min_completeness_for_high"]) else "medium"
    if r["note_injection_suspect"]:
        conf = "low"

    return {
        "merchant_id": r["merchant_id"],
        "dim_performance": round(perf, 1), "dim_relationship": round(rel, 1),
        "dim_engagement": round(eng, 1), "dim_commercial": round(com, 1),
        "tpv_component": round(tpv_score, 1), "success_component": round(succ_score, 1),
        "dims_firing": fired, "convergence_bonus": bonus, "seasonal_adjustment_applied": seasonal_applied,
        "risk_score": round(score, 1), "risk_band": band, "risk_confidence": conf,
        "primary_dimension": primary, "secondary_dimensions": drivers[1:],
        "critical_triggers": trig, "contributions": contrib,
    }


def score_merchants(feats: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    scored = pd.DataFrame([score_row(r, cfg) for _, r in feats.iterrows()])
    return feats.merge(scored, on="merchant_id", how="left")
