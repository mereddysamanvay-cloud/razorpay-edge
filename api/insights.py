"""Portfolio KPIs, narrative, driver/segment analysis and commercial exposure. All numbers derive from the analysed frame."""
from __future__ import annotations

import numpy as np
import pandas as pd

DRIVER_NAMES = {"performance": "Payment & volume performance", "relationship": "Service experience",
                "commercial": "Pricing & competition", "engagement": "Disengagement"}
DRIVER_RESPONSE = {
    "performance": "Share the merchant-level success-rate breakdown with Payments Ops and review the playbook PB-1 deep-dive for the largest exposures.",
    "relationship": "Assign a single owner to the open tickets and agree closure dates (PB-2). Review ticket ageing for the whole group.",
    "commercial": "Prepare rate-card and volume-tier reviews ahead of renewal (PB-3) and confirm competitor mentions with the Account Manager.",
    "engagement": "Re-confirm the right contact and offer a usage workshop (PB-4). Check whether low usage is natural for the segment first.",
}


def _f(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else float(x)


def _rs(v: float) -> str:
    return f"Rs {v / 1e7:.2f} crore" if abs(v) >= 1e7 else f"Rs {v / 1e5:.1f} lakh"


def kpis(df: pd.DataFrame, capacity: int, selected: int) -> dict:
    nonlow = df[df["risk_band"] != "low"]
    return {
        "total": int(len(df)),
        "high": int((df["risk_band"] == "high").sum()), "medium": int((df["risk_band"] == "medium").sum()), "low": int((df["risk_band"] == "low").sum()),
        "immediate": int(df["critical_triggers"].map(len).gt(0).sum()),
        "capacity": capacity, "selected": selected, "remaining_capacity": max(capacity - selected, 0),
        "exposure_annual_inr": float(nonlow["annual_value_at_stake_inr"].sum()),
        "exposure_weighted_inr": float((nonlow["risk_weight"] * nonlow["annual_value_at_stake_inr"]).sum()),
        "portfolio_annual_inr": float(df["annual_value_at_stake_inr"].sum()),
        "renewals_30": int((df["renewal_days"] <= 30).sum()), "renewals_60": int((df["renewal_days"] <= 60).sum()),
        "renewals_90": int((df["renewal_days"] <= 90).sum()),
        "renewals_30_at_risk": int(((df["renewal_days"] <= 30) & (df["risk_band"] != "low")).sum()),
        "seasonal_protected": int(df["seasonal_adjustment_applied"].sum()),
        "data_incomplete": int((df["completeness_score"] < 100).sum()),
        "tpv_m6_total_lakh": float(df["tpv_m6_inr_lakh"].sum()),
    }


def narrative(df: pd.DataFrame, k: dict) -> list[str]:
    n = k["total"]
    nonlow = df[df["risk_band"] != "low"]
    out = [f"Your portfolio contains {n} merchants. {k['high']} are in the high-risk band and {k['medium']} in the moderate band; "
           f"{k['low']} show no material risk signal."]
    if len(nonlow):
        counts = nonlow["primary_dimension"].value_counts()
        parts = [f"{DRIVER_NAMES[d].lower()} ({c})" for d, c in counts.items()]
        out.append("Among the merchants that need attention, the leading drivers are " + ", ".join(parts) + ".")
        r90 = nonlow[nonlow["renewal_days"] <= 90]
        if len(r90):
            out.append(f"{len(r90)} of them renew within 90 days ({int((nonlow['renewal_days'] <= 30).sum())} within 30), "
                       f"which raises the cost of waiting.")
        out.append(f"Run-rate revenue attached to these {len(nonlow)} merchants is about {_rs(k['exposure_annual_inr'])} a year. "
                   f"This is revenue at stake, not revenue lost; no churn outcomes exist in the data.")
    if k["seasonal_protected"]:
        out.append(f"{k['seasonal_protected']} merchant(s) show a seasonal dip-and-rebound and were deliberately not escalated on volume alone.")
    out.append(f"The team can contact {k['capacity']} merchants this period; {k['selected']} are currently shortlisted.")
    return out


def drivers(df: pd.DataFrame) -> list[dict]:
    nonlow = df[df["risk_band"] != "low"]
    res = []
    for d in ["performance", "relationship", "commercial", "engagement"]:
        g = nonlow[nonlow["primary_dimension"] == d]
        sig = []
        if len(g):
            if d == "performance":
                sig = [f"{int((g['success_drop_pp'] <= -5).sum())} with a success-rate fall of 5pp or more",
                       f"{int((g['recent_vs_early_pct'] <= -10).sum())} with TPV down 10% or more (M4-M6 vs M1-M3)"]
            elif d == "relationship":
                sig = [f"{int((g['unresolved'] >= 3).sum())} with 3+ unresolved tickets", f"{int(g['csat_low'].sum())} with CSAT of 2 or below"]
            elif d == "commercial":
                sig = [f"{int(g['note_competitor_explicit'].astype(bool).sum())} explicit competitor mention(s)",
                       f"{int((g['renewal_days'] <= 60).sum())} renew within 60 days"]
            else:
                sig = [f"{int(g['note_unresponsive'].astype(bool).sum())} unresponsive to check-ins", f"{int(g['note_decision_maker_change'].astype(bool).sum())} with a contact change"]
        res.append({"key": d, "name": DRIVER_NAMES[d], "merchants": int(len(g)), "share_of_portfolio_pct": round(len(g) / len(df) * 100, 1),
                    "annual_value_inr": float(g["annual_value_at_stake_inr"].sum()), "signals": sig, "response": DRIVER_RESPONSE[d],
                    "merchant_ids": list(g.sort_values("risk_score", ascending=False)["merchant_id"])})
    return res


def segments(df: pd.DataFrame) -> list[dict]:
    res = []
    for s in ["Small", "Mid", "Enterprise"]:
        g = df[df["segment"] == s]
        if g.empty:
            continue
        res.append({
            "segment": s, "merchants": int(len(g)), "high": int((g["risk_band"] == "high").sum()), "medium": int((g["risk_band"] == "medium").sum()),
            "low": int((g["risk_band"] == "low").sum()), "tpv_m6_lakh": float(g["tpv_m6_inr_lakh"].sum()), "avg_tpv_m6_lakh": float(g["tpv_m6_inr_lakh"].mean()),
            "median_tpv_change_pct": _f(g["recent_vs_early_pct"].median()), "avg_success_pct": _f(g["success_recent_pct"].mean()),
            "avg_csat": _f(g["csat"].mean()), "csat_known": int(g["csat"].notna().sum()), "avg_tickets_90d": _f(g["tickets_90d"].mean()),
            "avg_unresolved": _f(g["unresolved"].mean()), "avg_products": _f(g["products_used"].mean()), "avg_logins": _f(g["logins_30d"].mean()),
            "renewals_60": int((g["renewal_days"] <= 60).sum()), "annual_value_inr": float(g["annual_value_at_stake_inr"].sum()),
            "exposed_inr": float(g[g["risk_band"] != "low"]["annual_value_at_stake_inr"].sum()),
        })
    return res


def heatmap(df: pd.DataFrame) -> list[dict]:
    nonlow = df[df["risk_band"] != "low"]
    rows = []
    for s in ["Small", "Mid", "Enterprise"]:
        for d in DRIVER_NAMES:
            rows.append({"segment": s, "driver": d, "count": int(((nonlow["segment"] == s) & (nonlow["primary_dimension"] == d)).sum())})
    return rows


def commercial(df: pd.DataFrame, a: dict, selected_ids: list[str]) -> dict:
    nonlow = df[df["risk_band"] != "low"]
    sel = df[df["merchant_id"].isin(selected_ids)]
    unit = a["tpv_unit_inr"]
    return {
        "monthly_tpv_inr": float(df["tpv_m6_inr_lakh"].sum() * unit),
        "monthly_net_revenue_inr": float(df["monthly_net_revenue_inr"].sum()),
        "annual_run_rate_inr": float(df["annual_value_at_stake_inr"].sum()),
        "exposed_annual_inr": float(nonlow["annual_value_at_stake_inr"].sum()),
        "risk_weighted_exposed_inr": float((nonlow["risk_weight"] * nonlow["annual_value_at_stake_inr"]).sum()),
        "shortlist_annual_inr": float(sel["annual_value_at_stake_inr"].sum()),
        "lost_inr": None,
        "net_revenue_rate": a["net_revenue_rate"], "months": a["saved_merchant_months"], "false_alarm_cost_inr": a["false_alarm_cost_inr"],
        "methodology": [
            f"Merchant TPV: latest month (M6) TPV, reported in Rs lakh (1 lakh = {unit:,.0f}).",
            f"Estimated Razorpay revenue (monthly): M6 TPV x {a['net_revenue_rate'] * 100:g}% net revenue (workbook assumption).",
            f"Revenue run-rate: monthly net revenue x {a['saved_merchant_months']} months (workbook: value of a saved merchant).",
            "Revenue potentially exposed: run-rate of merchants in the moderate or high risk band. It is exposure, not a forecast.",
            "Risk-weighted exposure multiplies each run-rate by a hypothesis weight (risk score x confidence factor). It is not a probability.",
            "Revenue actually lost: not available. The workbook contains no churn outcomes.",
        ],
    }


def operational(df: pd.DataFrame) -> list[dict]:
    recs = []
    perf = df[df["success_drop_pp"] <= -5]
    if len(perf) >= 3:
        top = perf["industry"].value_counts()
        recs.append({"title": "Repeated payment-performance deterioration", "count": int(len(perf)),
                     "evidence": f"{len(perf)} merchants lost 5pp or more of payment success rate; the largest cluster is {top.index[0]} ({int(top.iloc[0])}).",
                     "suggestion": "Investigate whether a shared method, bank or integration issue sits behind the drop before treating each case separately. This is a lead to check, not a confirmed cause."})
    svc = df[df["unresolved"] >= 3]
    if len(svc) >= 2:
        recs.append({"title": "Open-ticket backlog on several accounts", "count": int(len(svc)),
                     "evidence": f"{len(svc)} merchants have 3 or more unresolved tickets; {int(svc['csat_low'].sum())} also report CSAT of 2 or below.",
                     "suggestion": "Review ticket ageing and ownership for these accounts to see whether response time or hand-offs are the common factor."})
    price = df[df["note_pricing_objection"].astype(bool) | df["note_rate_card_request"].astype(bool) | df["note_competitor_explicit"].astype(bool)]
    if len(price) >= 2:
        recs.append({"title": "Pricing and competitor conversations", "count": int(len(price)),
                     "evidence": f"{len(price)} account notes mention pricing, rate-card requests or a competitor; {int((price['renewal_days'] <= 60).sum())} renew within 60 days.",
                     "suggestion": "Consider a commercial review of volume tiers ahead of these renewals. Confirm each mention with the Account Manager first."})
    low = df[(df["products_used"] <= 2) & (df["logins_30d"] <= 5)]
    if len(low) >= 3:
        recs.append({"title": "Low adoption of available products", "count": int(len(low)),
                     "evidence": f"{len(low)} merchants use 2 or fewer products with 5 or fewer logins in the last 30 days.",
                     "suggestion": "Check whether onboarding or education content is reaching these merchants. Low usage can be natural for small, stable merchants."})
    if df["seasonal_adjustment_applied"].sum():
        recs.append({"title": "Seasonal dips handled separately", "count": int(df["seasonal_adjustment_applied"].sum()),
                     "evidence": f"{int(df['seasonal_adjustment_applied'].sum())} merchants in seasonal industries show a dip followed by a rebound.",
                     "suggestion": "Re-check these next month. The seasonal industry mapping is an interpretation of the workbook and should be confirmed."})
    return recs
