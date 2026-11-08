"""Deterministic evidence, mitigating/contradictory signals, alternatives and CSM checks."""
from __future__ import annotations

import math

import pandas as pd

from src.analytics.risk_scoring import DRIVER_LABELS


def _nan(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def driver_label(r: pd.Series, dim: str) -> str:
    if dim == "performance":
        succ, tpv = r["success_component"], r["tpv_component"]
        if succ >= 40 and tpv >= 40:
            return "Payment success-rate deterioration together with a sustained volume decline"
        if succ >= tpv:
            return "Payment success-rate deterioration"
        return "Sustained volume (TPV) decline"
    if dim == "relationship":
        return "Unresolved support issues and/or low CSAT"
    if dim == "engagement":
        if r["note_decision_maker_change"]:
            return "Disengagement after a contact / decision-maker change"
        if r["note_unresponsive"]:
            return "Disengagement (merchant unresponsive, low usage)"
        return "Disengagement (very low logins / few products)"
    return {"commercial": "Commercial displacement (competitor, pricing or rate-card signal near renewal)"}.get(dim, DRIVER_LABELS[dim])


def build_evidence(r: pd.Series) -> dict:
    ev, mit, con, alt, chk = [], [], [], [], []
    tpv_txt = (f"M1 Rs {r['tpv_m1_inr_lakh']:.1f}L -> M6 Rs {r['tpv_m6_inr_lakh']:.1f}L; avg M4-M6 {r['recent_vs_early_pct']:+.0f}% vs M1-M3; "
               f"{int(r['consecutive_declines'])} consecutive monthly decline(s)")
    if r["recent_vs_early_pct"] <= -10:
        ev.append({"source_field": "tpv_m1..m6_inr_lakh", "observed_value": tpv_txt,
                   "interpretation": "consistent with a volume decline; a TPV fall is a risk signal, not proof of churn"})
    if r["success_drop_pp"] <= -2:
        ev.append({"source_field": "success_rate_m1_m3_pct / success_rate_m4_m6_pct",
                   "observed_value": f"{r['success_early_pct']:.1f}% -> {r['success_recent_pct']:.1f}% ({r['success_drop_pp']:+.1f}pp)",
                   "interpretation": "success rate deterioration; may be affecting checkout conversion (requires validation)"})
    if r["unresolved"] >= 1:
        ev.append({"source_field": "unresolved_tickets / support_tickets_last_90d",
                   "observed_value": f"{int(r['unresolved'])} of {int(r['tickets_90d'])} tickets unresolved",
                   "interpretation": "open service issues may indicate a poor support experience"})
    if r["csat_low"]:
        ev.append({"source_field": "last_csat_1_to_5", "observed_value": f"{int(r['csat'])}", "interpretation": "low satisfaction on the latest survey"})
    if r["dim_engagement"] >= 25:
        ev.append({"source_field": "logins_last_30d / products_used", "observed_value": f"{int(r['logins_30d'])} logins, {int(r['products_used'])} product(s)",
                   "interpretation": "low current usage (snapshot only; no history, so a decline over time cannot be claimed)"})
    if isinstance(r["account_manager_note"], str) and r["note_evidence"]:
        ev.append({"source_field": "account_manager_note", "observed_value": r["account_manager_note"],
                   "interpretation": f"note signals: {r['note_evidence']} (untrusted free text, verify with the AM)"})
    if r["dim_commercial"] > 0:
        ev.append({"source_field": "days_to_contract_renewal", "observed_value": f"{int(r['renewal_days'])} days",
                   "interpretation": "renewal proximity raises the stakes of any commercial signal"})

    # mitigating
    if r["recent_vs_early_pct"] >= 5:
        mit.append(f"TPV growing ({r['recent_vs_early_pct']:+.0f}% avg M4-M6 vs M1-M3)")
    if not _nan(r["csat"]) and r["csat"] >= 4:
        mit.append(f"CSAT {int(r['csat'])}/5")
    if r["logins_30d"] >= 15:
        mit.append(f"{int(r['logins_30d'])} logins in the last 30 days")
    if r["products_used"] >= 4:
        mit.append(f"{int(r['products_used'])} products in use")
    if r["success_drop_pp"] >= -1:
        mit.append(f"success rate stable ({r['success_drop_pp']:+.1f}pp)")
    if r["unresolved"] == 0 and r["tickets_90d"] > 0:
        mit.append(f"all {int(r['tickets_90d'])} recent tickets resolved")
    for flag, text in (("positive_growth", "AM note: growing fast"), ("expansion_interest", "AM note: interested in more products"),
                       ("no_concerns", "AM note: no concerns at last check-in"), ("resolved_minor", "AM note: past issue resolved")):
        if r[f"note_{flag}"]:
            mit.append(text)
    if r["seasonal_adjustment_applied"]:
        mit.append("seasonal-industry dip followed by a rebound in M6")
    if r["m6_vs_m5_pct"] >= 5 and r["recent_vs_early_pct"] < -5:
        mit.append(f"M6 recovered {r['m6_vs_m5_pct']:+.0f}% vs M5")

    # contradictory
    if r["seasonal_adjustment_applied"]:
        con.append("Industry is seasonal and the TPV pattern is a dip-and-rebound, which conflicts with a churn reading")
    if r["risk_band"] != "low" and not _nan(r["csat"]) and r["csat"] >= 4:
        con.append(f"CSAT is {int(r['csat'])}/5 despite risk signals")
    if r["risk_band"] != "low" and r["note_no_concerns"]:
        con.append("AM note says no concerns while metrics show risk")
    if r["dim_commercial"] > 0 and r["recent_vs_early_pct"] >= -5:
        con.append("Commercial signal present but TPV is stable or growing")
    if r["dim_performance"] >= 40 and r["success_drop_pp"] > -2 and r["unresolved"] == 0 and r["dim_engagement"] < 25:
        con.append("Volume is falling but success rate, service and engagement look normal (single-signal case)")

    # alternatives
    if r["is_seasonal_industry"] and r["recent_vs_early_pct"] < -5:
        alt.append("Seasonal industry: post-festive/seasonal dips are expected and are not churn")
    if r["tpv_avg_m4_m6"] < 5:
        alt.append("Naturally low volume: small absolute TPV makes percentage moves noisy")
    if r["tickets_90d"] >= 5 and r["recent_vs_early_pct"] >= 5:
        alt.append("High ticket count may reflect growth and integration activity")
    if r["note_decision_maker_change"] or r["note_unresponsive"]:
        alt.append("Contact change or silence may be internal at the merchant, not an intent to leave")
    if r["recent_vs_early_pct"] <= -10 and r["success_drop_pp"] > -2:
        alt.append("Volume decline without a success-rate drop could be demand-side (merchant's own sales) rather than a provider issue")

    # checks
    dims = {"performance": r["dim_performance"], "relationship": r["dim_relationship"], "engagement": r["dim_engagement"], "commercial": r["dim_commercial"]}
    if dims["performance"] >= 25:
        chk.append("Ask Payments Ops for the success-rate breakdown by method and bank for this merchant")
        chk.append("Ask the merchant whether volume has moved to another provider (not visible in the data)")
    if dims["relationship"] >= 25:
        chk.append("Review the open tickets: age, owner and whether a closure date was ever given")
    if dims["engagement"] >= 25:
        chk.append("Confirm the current decision-maker / best contact for this account")
    if dims["commercial"] >= 25:
        chk.append("Confirm with the Account Manager what exactly was said about competitors or pricing and when")
        chk.append("Check renewal terms and rate-card history before the renewal date")
    if r["csat_missing"]:
        chk.append("CSAT is missing (no survey response); do not read it as satisfied or unsatisfied")
    if r["note_missing"]:
        chk.append("No account-manager note recorded; ask the AM for any context")
    if r["note_injection_suspect"]:
        chk.append("Account-manager note contains instruction-like text; it was ignored and should be reviewed")

    return {"supporting_evidence": ev, "mitigating_signals": mit, "contradictory_signals": con,
            "alternative_explanations": alt, "additional_checks_for_csm": chk}


def plain_language_reason(r: pd.Series) -> str:
    if r["risk_band"] == "low" or r["primary_dimension"] is None:
        why = ""
        if r["seasonal_adjustment_applied"]:
            why = "The volume dip fits a seasonal-industry pattern (dip then rebound) and no independent risk signal was found."
        elif r["tpv_avg_m4_m6"] < 5 and r["recent_vs_early_pct"] >= -10:
            why = "Volume is low but stable, which is natural for a small merchant, and no independent risk signal was found."
        elif r["recent_vs_early_pct"] >= 8:
            why = "Volume is growing and service and performance signals are healthy."
        else:
            why = "No material risk signal was found in the supplied data."
        return why
    parts = []
    if r["dim_performance"] >= 25:
        bits = []
        if r["success_drop_pp"] <= -2:
            bits.append(f"a success-rate drop of {abs(r['success_drop_pp']):.1f}pp ({r['success_early_pct']:.1f}% to {r['success_recent_pct']:.1f}%)")
        if r["recent_vs_early_pct"] <= -10:
            bits.append(f"TPV averaging {abs(r['recent_vs_early_pct']):.0f}% lower in M4-M6 than in M1-M3")
        parts.append(" and ".join(bits))
    if r["dim_relationship"] >= 25:
        parts.append(f"{int(r['unresolved'])} unresolved ticket(s)" + (f" with CSAT {int(r['csat'])}" if r["csat_low"] else ""))
    if r["dim_engagement"] >= 25:
        parts.append(f"very low usage ({int(r['logins_30d'])} logins, {int(r['products_used'])} product(s))" +
                     (" after a contact change" if r["note_decision_maker_change"] else " and no response to check-ins" if r["note_unresponsive"] else ""))
    if r["dim_commercial"] >= 25:
        parts.append(f"a commercial signal in the AM note ('{r['account_manager_note']}') with renewal in {int(r['renewal_days'])} days")
    return "Consistent with " + "; ".join(p for p in parts if p) + ". Requires CSM validation; cause not confirmed."
