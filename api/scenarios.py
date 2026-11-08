"""Transparent, weight-free outreach ranking.

Eligibility comes from the analysis engine (playbook PB-1..PB-4, moderate/high band, positive proxy).
A scenario only re-orders the eligible pool, lexicographically:
  1. number of selected business priorities the merchant matches (more first)
  2. the chosen risk focus (revenue exposure, severity, dissatisfaction, renewal urgency, disengagement)
  3. the engine's own tie-breaks (risk-weighted value, risk score, id)
No numeric weights are introduced, so every change in order can be traced to a stated rule.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PRIORITIES = {
    "high_value": "Protect high-value merchants",
    "payment_performance": "Address payment performance issues",
    "renewals": "Focus on upcoming renewals",
    "service": "Resolve service dissatisfaction",
    "engagement": "Improve merchant engagement",
    "competitor": "Prioritise explicit competitor threats",
}
FOCUS = {
    "revenue": "Revenue exposure",
    "severity": "Severity of deterioration",
    "dissatisfaction": "Relationship dissatisfaction",
    "renewal": "Renewal urgency",
    "disengagement": "Merchant disengagement",
}
RULES = {
    "high_value": "annual run-rate revenue in the top quartile of the portfolio",
    "payment_performance": "payment-performance risk dimension is the driver, or success rate fell 5pp or more",
    "renewals": "renewal due within 60 days",
    "service": "service risk dimension is 25+ (unresolved tickets and/or low CSAT)",
    "engagement": "engagement risk dimension is 25+ (very low logins / few products)",
    "competitor": "account note records an explicit competitor mention",
}


def default_scenario(capacity: int) -> dict:
    return {"name": "Baseline", "capacity": int(capacity), "priorities": [], "risk_focus": "revenue", "segments": [],
            "exclude_industries": [], "renewal_window": None, "include_ids": [], "exclude_ids": [], "exclude_reasons": {}}


def _matches(df: pd.DataFrame) -> dict[str, pd.Series]:
    q75 = df["annual_value_at_stake_inr"].quantile(0.75)
    return {
        "high_value": df["annual_value_at_stake_inr"] >= q75,
        "payment_performance": (df["primary_dimension"] == "performance") | (df["success_drop_pp"] <= -5),
        "renewals": df["renewal_days"] <= 60,
        "service": df["dim_relationship"] >= 25,
        "engagement": df["dim_engagement"] >= 25,
        "competitor": df["note_competitor_explicit"].astype(bool),
    }


def _focus_key(df: pd.DataFrame, focus: str) -> pd.Series:
    return {"revenue": -df["priority_value_inr"], "severity": -df["risk_score"], "dissatisfaction": -df["dim_relationship"],
            "renewal": df["renewal_days"], "disengagement": -df["dim_engagement"]}[focus]


def rank(df: pd.DataFrame, scn: dict) -> pd.DataFrame:
    """Returns one row per merchant considered, ordered, with selected flag and trace columns."""
    cap = int(scn["capacity"])
    m = _matches(df)
    pool = df[df["eligible_for_outreach"]].copy()
    if scn.get("segments"):
        pool = pool[pool["segment"].isin(scn["segments"])]
    if scn.get("exclude_industries"):
        pool = pool[~pool["industry"].isin(scn["exclude_industries"])]
    if scn.get("renewal_window"):
        pool = pool[pool["renewal_days"] <= scn["renewal_window"]]
    excl = set(scn.get("exclude_ids", []))
    pool = pool[~pool["merchant_id"].isin(excl)]
    forced = [i for i in scn.get("include_ids", []) if i not in excl and i in set(df["merchant_id"])]
    pool = pd.concat([pool, df[df["merchant_id"].isin(forced) & ~df["merchant_id"].isin(pool["merchant_id"])]])
    chosen = [p for p in scn.get("priorities", []) if p in PRIORITIES]
    pref = list(scn.get("prefer_segments", []))
    n = sum((m[p].reindex(pool.index).astype(int) for p in chosen), start=pd.Series(0, index=pool.index))
    n = n + (pool["segment"].isin(pref).astype(int) if pref else 0)
    pool["n_match"] = n
    pool["matched"] = [[p for p in chosen if bool(m[p].loc[i])] + ([f"segment:{pool.at[i, 'segment']}"] if pref and pool.at[i, "segment"] in pref else []) for i in pool.index]
    pool["forced"] = pool["merchant_id"].isin(forced)
    pool["_fk"] = _focus_key(pool, scn.get("risk_focus", "revenue"))
    pool = pool.sort_values(["forced", "n_match", "_fk", "priority_value_inr", "risk_score", "merchant_id"],
                            ascending=[False, False, True, False, False, True]).reset_index(drop=True)
    pool["scn_rank"] = np.arange(1, len(pool) + 1)
    pool["scn_selected"] = pool["scn_rank"] <= cap
    return pool[["merchant_id", "scn_rank", "scn_selected", "n_match", "matched", "forced"]]


def narrative_for(r: pd.Series, row: pd.Series, scn: dict) -> str:
    bits = []
    if row["forced"]:
        bits.append("added manually by the manager")
    bits += [f"is in the preferred segment ({p[8:]})" if p.startswith("segment:") else f"matches '{PRIORITIES[p]}' ({RULES[p]})" for p in row["matched"]]
    focus = scn.get("risk_focus", "revenue")
    if not bits:
        bits.append(f"ordered by {FOCUS[focus].lower()}")
    return "; ".join(bits)


def compare(df: pd.DataFrame, base: pd.DataFrame, new: pd.DataFrame, scn: dict) -> dict:
    bsel = list(base[base["scn_selected"]]["merchant_id"])
    nsel = list(new[new["scn_selected"]]["merchant_id"])
    b_rank = dict(zip(base["merchant_id"], base["scn_rank"]))
    n_rank = dict(zip(new["merchant_id"], new["scn_rank"]))
    by = df.set_index("merchant_id")
    ins, outs = [m for m in nsel if m not in bsel], [m for m in bsel if m not in nsel]
    n_row = new.set_index("merchant_id")

    def item(mid: str, why: str) -> dict:
        r = by.loc[mid]
        return {"merchant_id": mid, "business_name": r["business_name"], "segment": r["segment"], "from_rank": b_rank.get(mid),
                "to_rank": n_rank.get(mid), "annual_value_inr": float(r["annual_value_at_stake_inr"]), "reason": why}

    moved_in = [item(m, narrative_for(by.loc[m], n_row.loc[m], scn)) for m in ins]
    moved_out = []
    for m in outs:
        r = by.loc[m]
        if m in n_row.index:
            why = f"now ranks #{n_rank[m]}, behind merchants that match the chosen priorities or focus"
        elif m in set(scn.get("exclude_ids", [])):
            why = "excluded by the manager" + (f": {scn['exclude_reasons'].get(m)}" if scn.get("exclude_reasons", {}).get(m) else "")
        else:
            why = "filtered out by the segment, category or renewal-window filter"
        moved_out.append(item(m, why))

    def covered(sel: list[str]) -> dict:
        sub = by.loc[sel] if sel else by.iloc[0:0]
        d = sub["primary_dimension"].fillna("none").value_counts().to_dict()
        return {k: int(v) for k, v in d.items()}

    def value(sel: list[str]) -> float:
        return float(by.loc[sel, "annual_value_at_stake_inr"].sum()) if sel else 0.0

    bv, nv = value(bsel), value(nsel)
    seg = lambda sel: by.loc[sel, "segment"].value_counts().to_dict() if sel else {}
    sentences = []
    if not ins and not outs:
        sentences.append("The selection is unchanged. Re-ordering only moves merchants inside the shortlist.")
    else:
        sentences.append(f"{len(ins)} merchant(s) move into the shortlist and {len(outs)} move out.")
        if nv != bv:
            sentences.append(f"Run-rate revenue represented by the shortlist changes from Rs {bv / 1e5:.1f} lakh to Rs {nv / 1e5:.1f} lakh a year "
                             f"({(nv - bv) / 1e5:+.1f} lakh).")
        hi_out = [x for x in moved_out if by.loc[x["merchant_id"], "risk_band"] == "high"]
        if hi_out:
            sentences.append(f"{len(hi_out)} high-risk merchant(s) leave the shortlist: " + ", ".join(x["business_name"] for x in hi_out[:4]) + ".")
    return {"before": bsel, "after": nsel, "moved_in": moved_in, "moved_out": moved_out,
            "value_before_inr": bv, "value_after_inr": nv, "drivers_before": covered(bsel), "drivers_after": covered(nsel),
            "segments_before": seg(bsel), "segments_after": seg(nsel), "summary": " ".join(sentences),
            "rank_changes": [{"merchant_id": m, "from": b_rank.get(m), "to": n_rank.get(m)} for m in nsel if b_rank.get(m) != n_rank.get(m)]}

