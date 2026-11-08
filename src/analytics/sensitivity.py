"""Re-run scoring + selection under alternative, defensible configurations and compare the top 15."""
from __future__ import annotations

import pandas as pd

from src.analytics.prioritisation import prioritise
from src.analytics.risk_scoring import score_merchants
from src.config import clone
from src.crm.playbook_selector import apply_selection


def scenarios(base: dict) -> dict[str, dict]:
    s: dict[str, dict] = {"baseline": clone(base)}

    def variant(name, fn):
        c = clone(base)
        fn(c)
        s[name] = c

    variant("equal_weights", lambda c: c["weights"].update({d: 0.25 for d in c["weights"]}))
    variant("performance_heavy", lambda c: c["weights"].update({"performance": 0.5, "relationship": 0.2, "engagement": 0.1, "commercial": 0.2}))
    variant("service_heavy", lambda c: c["weights"].update({"performance": 0.25, "relationship": 0.4, "engagement": 0.15, "commercial": 0.2}))
    variant("commercial_heavy", lambda c: c["weights"].update({"performance": 0.25, "relationship": 0.2, "engagement": 0.1, "commercial": 0.45}))
    variant("max_dimension_only", lambda c: c["aggregation"].update({"weighted_share": 0.0}))
    variant("weighted_mean_only", lambda c: c["aggregation"].update({"weighted_share": 1.0}))
    variant("no_seasonal_adjustment", lambda c: c["seasonal"].update({"enabled": False}))
    variant("stricter_tpv_scale", lambda c: c["tpv"].update({"zero_at_pct": -10, "full_at_pct": -50}))
    variant("looser_tpv_scale", lambda c: c["tpv"].update({"zero_at_pct": 0, "full_at_pct": -30}))
    variant("stricter_success_scale", lambda c: c["success"].update({"zero_at_pp": -2.0, "full_at_pp": -12.0}))
    return s


def run_sensitivity(feats: pd.DataFrame, scoring: dict, pb_cfg: dict, playbooks: pd.DataFrame, settings: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns (per-scenario long table, per-merchant stability summary, per-scenario top-15 overlap)."""
    rows, tops = [], {}
    risk_first = clone(settings)
    risk_first["selection"]["rank_by"] = "risk_score"
    all_scn = {**scenarios(scoring), "risk_first_selection": clone(scoring)}
    for name, cfg in all_scn.items():
        d = score_merchants(feats, cfg)
        d = apply_selection(d, pb_cfg, playbooks)
        d = prioritise(d, risk_first if name == "risk_first_selection" else settings)
        tops[name] = set(d.loc[d["selected_for_outreach"], "merchant_id"])
        for _, r in d.iterrows():
            rows.append({"scenario": name, "merchant_id": r["merchant_id"], "risk_score": r["risk_score"],
                         "risk_band": r["risk_band"], "risk_rank": r["risk_rank"],
                         "primary_playbook_id": r["primary_playbook_id"],
                         "outreach_priority_rank": r["outreach_priority_rank"],
                         "selected_for_outreach": bool(r["selected_for_outreach"])})
    long = pd.DataFrame(rows)
    base = tops["baseline"]
    n = len(tops)
    summary = []
    for mid, g in long.groupby("merchant_id"):
        summary.append({"merchant_id": mid, "scenarios_selected": int(g["selected_for_outreach"].sum()),
                        "scenarios_total": n, "selected_in_baseline": mid in base,
                        "min_risk_rank": int(g["risk_rank"].min()), "max_risk_rank": int(g["risk_rank"].max())})
    summ = pd.DataFrame(summary).sort_values(["scenarios_selected", "merchant_id"], ascending=[False, True])
    overlap = pd.DataFrame([{"scenario": k, "selected": len(v), "overlap_with_baseline": len(v & base),
                             "jaccard_vs_baseline": round(len(v & base) / len(v | base), 3) if (v | base) else 1.0,
                             "added_vs_baseline": ", ".join(sorted(v - base)), "dropped_vs_baseline": ", ".join(sorted(base - v))}
                            for k, v in tops.items()])
    return long, summ, overlap
