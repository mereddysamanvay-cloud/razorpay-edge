"""Separate risk ranking from outreach priority under the 15-contact cap.

priority_value_inr is a PRIORITISATION PROXY, not an expected value from real probabilities:
    w = (risk_score / 100) * confidence_factor        # a weight in [0,1], NOT a churn/save probability
    proxy = w * annual_value_at_stake - (1 - w) * false_alarm_cost
annual_value_at_stake and false_alarm_cost come from P2_Assumptions; w and urgency are hypotheses.
"""
from __future__ import annotations

import pandas as pd


def _urgency(days: float, table: list[list[float]]) -> float:
    for limit, mult in table:
        if days <= limit:
            return float(mult)
    return 1.0


def prioritise(df: pd.DataFrame, settings: dict) -> pd.DataFrame:
    sa, sel = settings["source_assumptions"], settings["selection"]
    out = df.copy()

    out = out.sort_values(["risk_score", "annual_value_at_stake_inr", "merchant_id"],
                          ascending=[False, False, True]).reset_index(drop=True)
    out["risk_rank"] = range(1, len(out) + 1)

    out["risk_weight"] = out["risk_score"] / 100 * out["risk_confidence"].map(sel["confidence_factor"])
    out["urgency_multiplier"] = out["renewal_days"].map(lambda d: _urgency(d, sel["urgency_multiplier"]))
    w = out["risk_weight"]
    out["priority_value_inr"] = (w * out["annual_value_at_stake_inr"] - (1 - w) * sa["false_alarm_cost_inr"]) * out["urgency_multiplier"]

    band_ok = {"high": ["high"], "medium": ["high", "medium"], "low": ["high", "medium", "low"]}[sel["min_band"]]
    out["eligible_for_outreach"] = (out["primary_playbook_id"].isin(sel["eligible_playbooks"])
                                    & out["risk_band"].isin(band_ok) & (out["priority_value_inr"] > 0))

    keys = (["risk_score", "priority_value_inr", "merchant_id"] if sel.get("rank_by") == "risk_score"
            else ["priority_value_inr", "risk_score", "merchant_id"])
    elig = out[out["eligible_for_outreach"]].sort_values(keys, ascending=[False, False, True])
    ranks = {m: i + 1 for i, m in enumerate(elig["merchant_id"])}
    out["outreach_priority_rank"] = out["merchant_id"].map(ranks)
    cap = sa["max_outreaches"]
    out["selected_for_outreach"] = out["outreach_priority_rank"].le(cap).fillna(False)
    out["outreach_reason"] = out.apply(lambda r: _reason(r, out, cap), axis=1)
    return out


def _reason(r: pd.Series, df: pd.DataFrame, cap: int) -> str:
    if r["selected_for_outreach"]:
        return (f"Outreach priority #{int(r['outreach_priority_rank'])} of {cap}: {r['risk_band']} risk (score {r['risk_score']:.0f}), "
                f"{r['primary_playbook_id']} trigger ({r['playbook_trigger_reason']}); Rs {r['annual_value_at_stake_inr'] / 1e5:.1f} lakh/yr run-rate revenue exposure.")
    if r["eligible_for_outreach"]:
        cut = df[df["outreach_priority_rank"] == cap]
        gap = ""
        if len(cut):
            c = cut.iloc[0]
            gap = (f" Priority proxy Rs {r['priority_value_inr'] / 1e5:.1f} lakh vs Rs {c['priority_value_inr'] / 1e5:.1f} lakh for the #{cap} pick ({c['merchant_id']}).")
        return f"Eligible but outside the {cap}-contact capacity (outreach rank {int(r['outreach_priority_rank'])}).{gap}"
    if r["primary_playbook_id"] in ("PB-5", "PB-6"):
        return f"No churn outreach: {r['primary_playbook_id']} ({r['playbook_trigger_reason']})."
    if r["risk_band"] == "low":
        return "No outreach: risk band is low."
    return "Not eligible: priority proxy not positive."
