"""Maps evidence to the six SUPPLIED playbooks. No playbook text is invented here."""
from __future__ import annotations

import math

import pandas as pd

FIT_DIMENSION = {"PB-1": "dim_performance", "PB-2": "dim_relationship", "PB-3": "dim_commercial", "PB-4": "dim_engagement"}


def _nan(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def triggered_playbooks(r: pd.Series, cfg: dict) -> dict[str, str]:
    """Return {playbook_id: human-readable trigger reason} for risk-action playbooks PB-1..PB-4."""
    t, out = cfg["triggers"], {}
    p1 = t["PB-1"]
    if r["success_drop_pp"] <= p1["max_success_drop_pp"]:
        out["PB-1"] = f"success rate fell {abs(r['success_drop_pp']):.1f}pp ({r['success_early_pct']:.1f}% -> {r['success_recent_pct']:.1f}%)"
    elif any(r[f"note_{n}"] for n in p1["notes"]):
        out["PB-1"] = f"merchant raised payment-failure concern in note ({r['note_evidence']})"
    p2 = t["PB-2"]
    if r["unresolved"] >= p2["min_unresolved"]:
        out["PB-2"] = f"{int(r['unresolved'])} unresolved tickets"
    elif r["csat_low"] and r["unresolved"] >= p2["low_csat_min_unresolved"]:
        out["PB-2"] = f"CSAT {int(r['csat'])} with {int(r['unresolved'])} unresolved ticket(s)"
    p3 = t["PB-3"]
    if any(r[f"note_{n}"] for n in p3["notes"]) and r["renewal_days"] <= p3["max_renewal_days"]:
        out["PB-3"] = f"commercial signal in note ({r['note_evidence']}) and renewal in {int(r['renewal_days'])} days"
    p4 = t["PB-4"]
    if r["logins_30d"] <= p4["max_logins"] and r["products_used"] <= p4["max_products"]:
        ra = p4["requires_any"]
        why = []
        if r["recent_vs_early_pct"] <= ra["max_recent_vs_early_pct"]:
            why.append(f"TPV down {abs(r['recent_vs_early_pct']):.0f}%")
        why += [f"note: {n}" for n in ra["notes"] if r[f"note_{n}"]]
        if why:
            out["PB-4"] = f"{int(r['logins_30d'])} logins, {int(r['products_used'])} product(s); " + ", ".join(why)
    return out


def healthy_and_growing(r: pd.Series, cfg: dict) -> bool:
    p5 = cfg["triggers"]["PB-5"]
    return bool(r["risk_band"] == "low"
                and r["recent_vs_early_pct"] >= p5["min_recent_vs_early_pct"]
                and r["success_drop_pp"] >= p5["min_success_drop_pp"]
                and r["unresolved"] <= p5["max_unresolved"]
                and (_nan(r["csat"]) or r["csat"] >= p5["min_csat_if_present"]))


def select_playbooks(r: pd.Series, cfg: dict, playbook_names: dict[str, str]) -> dict:
    trig = triggered_playbooks(r, cfg)
    order = cfg["tie_break_order"]
    why_not: list[str] = []
    primary = secondary = None
    reason = ""
    if r["risk_band"] != "low" and trig:
        ranked = sorted(trig, key=lambda p: (-float(r[FIT_DIMENSION[p]]), order.index(p)))
        primary = ranked[0]
        reason = trig[primary]
        if len(ranked) > 1 and float(r[FIT_DIMENSION[ranked[1]]]) >= cfg["secondary_min_fit"]:
            secondary = ranked[1]
        for p in ranked[1:]:
            if p != secondary:
                why_not.append(f"{p} triggered ({trig[p]}) but fit below secondary threshold")
    elif r["risk_band"] != "low":
        primary = "PB-6"
        reason = ("risk score above low band but no playbook trigger fired (e.g. volume decline without corroborating "
                  "success-rate, service, engagement or commercial evidence): monitor and verify")
    elif healthy_and_growing(r, cfg):
        primary = "PB-5"
        reason = f"healthy and growing: TPV {r['recent_vs_early_pct']:+.0f}% vs earlier quarter, success stable, no open service issues"
    else:
        primary = "PB-6"
        if r["seasonal_adjustment_applied"]:
            reason = "seasonal-industry dip with rebound and no independent risk signal"
        elif r["is_seasonal_industry"] and r["recent_vs_early_pct"] < -10:
            reason = "seasonal industry with a dip; no independent risk signal"
        elif r["tpv_avg_m4_m6"] < 5 and r["recent_vs_early_pct"] >= -10:
            reason = "naturally low-volume and stable; no real risk signal"
        else:
            reason = "no real risk signal"
        if trig:
            why_not += [f"{p} triggered ({v}) but overall risk is low" for p, v in trig.items()]
    return {
        "primary_playbook_id": primary,
        "primary_playbook_name": playbook_names.get(primary, ""),
        "secondary_playbook_id": secondary,
        "playbook_triggers": trig,
        "playbook_trigger_reason": reason,
        "playbooks_not_selected": why_not,
    }


def apply_selection(df: pd.DataFrame, cfg: dict, playbooks: pd.DataFrame) -> pd.DataFrame:
    names = dict(zip(playbooks["playbook_id"], playbooks["name"]))
    sel = pd.DataFrame([{"merchant_id": r["merchant_id"], **select_playbooks(r, cfg, names)} for _, r in df.iterrows()])
    return df.merge(sel, on="merchant_id", how="left")
