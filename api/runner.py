"""Runs the existing analysis engine on an uploaded, mapped workbook and builds the session payload."""
from __future__ import annotations

import datetime as dt
import math
import threading
from typing import Callable

import numpy as np
import pandas as pd

from api import insights, scenarios
from src.agent.llm_client import LLMClient
from src.agent.orchestrator import enrich_with_llm, run_deterministic
from src.analytics.feature_engineering import engineer_features
from src.analytics.peer_benchmarking import add_peer_context
from src.analytics.prioritisation import prioritise
from src.analytics.risk_scoring import score_merchants
from src.config import clone, load_playbook_cfg, load_scoring, load_settings
from src.crm.outreach_generator import template_draft
from src.crm.playbook_selector import apply_selection

VERSION = "EDGE 1.0 / config 1.0.0 / scoring 1.0.0-hypothesis"
BAND_LABEL = {"low": "Low risk", "medium": "Moderate risk", "high": "High risk"}
Progress = Callable[[str, str, float], None]


def jsonable(v):
    if isinstance(v, dict):
        return {str(k): jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [jsonable(x) for x in v]
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return None if math.isnan(v) or math.isinf(v) else float(v)
    if v is pd.NA or v is pd.NaT:
        return None
    return v


def clauses(r: pd.Series) -> list[str]:
    c = []
    if r["recent_vs_early_pct"] <= -10:
        c.append(f"TPV averaging {abs(r['recent_vs_early_pct']):.0f}% lower over the last three months")
    if r["success_drop_pp"] <= -2:
        c.append(f"payment success down {abs(r['success_drop_pp']):.1f} percentage points")
    if r["dim_relationship"] >= 25:
        c.append(f"{int(r['unresolved'])} unresolved ticket(s)" + (f" and CSAT of {int(r['csat'])}" if r["csat_low"] else ""))
    if r["dim_engagement"] >= 25:
        c.append("very low product usage")
    if bool(r["note_competitor_explicit"]):
        c.append("an explicit competitor mention")
    elif r["dim_commercial"] >= 25:
        c.append("a pricing or rate-card signal in the account note")
    if r["renewal_days"] <= 60:
        c.append(f"renewal in {int(r['renewal_days'])} days")
    return c


def sentence(r: pd.Series) -> str:
    c = clauses(r)
    if not c:
        return "No material risk signal in the supplied data."
    return "Because of " + (", ".join(c[:-1]) + " and " + c[-1] if len(c) > 1 else c[0]) + "."


def norm_playbooks(pb: pd.DataFrame) -> pd.DataFrame:
    pb = pb.copy()
    pb.columns = [str(c).strip().lower().replace(" ", "_") for c in pb.columns]
    ren = {}
    for c in pb.columns:
        if "id" in c and "playbook_id" not in ren.values():
            ren[c] = "playbook_id"
        elif c in ("playbook", "name", "playbook_name") and "name" not in ren.values():
            ren[c] = "name"
        elif ("happen" in c or "action" in c or "description" in c) and "what_happens" not in ren.values():
            ren[c] = "what_happens"
        elif ("when" in c or "appl" in c or "trigger" in c) and "when_it_applies" not in ren.values():
            ren[c] = "when_it_applies"
    pb = pb.rename(columns=ren)
    missing = {"playbook_id", "name", "what_happens", "when_it_applies"} - set(pb.columns)
    if missing:
        raise ValueError(f"Playbook sheet is missing: {', '.join(sorted(missing))}")
    return pb[["playbook_id", "name", "what_happens", "when_it_applies"]].astype(str)


def build_engine_frame(clean: pd.DataFrame, playbooks: pd.DataFrame, assumptions: dict, capacity: int):
    settings = clone(load_settings())
    settings["source_assumptions"].update({k: v for k, v in assumptions.items() if k in settings["source_assumptions"]})
    settings["source_assumptions"]["max_outreaches"] = int(capacity)
    scoring, pb_cfg = load_scoring(), load_playbook_cfg()
    feats = add_peer_context(engineer_features(clean, settings, scoring))
    df = prioritise(apply_selection(score_merchants(feats, scoring), pb_cfg, playbooks), settings)
    return settings, scoring, pb_cfg, feats, df


def merchant_record(r: pd.Series, a, extra_draft) -> dict:
    d = a.model_dump()
    note_sig = [c[5:] for c in r.index if c.startswith("note_") and c not in ("note_evidence", "note_missing", "note_injection_suspect") and bool(r[c])]
    rec = {
        "id": r["merchant_id"], "name": r["business_name"], "segment": r["segment"], "industry": r["industry"],
        "city": r.get("city"), "tenure_months": r.get("tenure_months"), "account_manager": r.get("account_manager"), "logo_url": r.get("logo_url"),
        "note": r["account_manager_note"] if isinstance(r["account_manager_note"], str) else None,
        "note_signals": note_sig, "note_injection_suspect": bool(r["note_injection_suspect"]),
        "tpv": [r[f"tpv_m{i}_inr_lakh"] for i in range(1, 7)], "tpv_m6": r["tpv_m6_inr_lakh"],
        "tpv_change_pct": r["recent_vs_early_pct"], "tpv_change_m1_m6_pct": r["tpv_change_m1_m6_pct"], "m6_vs_m5_pct": r["m6_vs_m5_pct"],
        "tpv_trend": r["tpv_trend"], "consecutive_declines": r["consecutive_declines"],
        "success_early": r["success_early_pct"], "success_recent": r["success_recent_pct"], "success_drop_pp": r["success_drop_pp"],
        "csat": r["csat"], "csat_missing": bool(r["csat_missing"]), "tickets": r["tickets_90d"], "unresolved": r["unresolved"],
        "logins": r["logins_30d"], "products": r["products_used"], "renewal_days": r["renewal_days"], "renewal_band": r["renewal_band"],
        "risk_score": r["risk_score"], "risk_band": r["risk_band"], "risk_label": BAND_LABEL[r["risk_band"]], "confidence": r["risk_confidence"],
        "dims": {k: r[f"dim_{k}"] for k in ("performance", "relationship", "engagement", "commercial")},
        "primary_dimension": r["primary_dimension"], "secondary_dimensions": list(r["secondary_dimensions"]),
        "critical_triggers": list(r["critical_triggers"]), "immediate": len(r["critical_triggers"]) > 0,
        "seasonal_industry": bool(r["is_seasonal_industry"]), "seasonal_adjusted": bool(r["seasonal_adjustment_applied"]),
        "dip_and_rebound": bool(r["dip_and_rebound"]),
        "annual_value": r["annual_value_at_stake_inr"], "monthly_net_revenue": r["monthly_net_revenue_inr"],
        "priority_value": r["priority_value_inr"], "risk_weight": r["risk_weight"], "urgency_multiplier": r["urgency_multiplier"],
        "risk_rank": r["risk_rank"], "eligible": bool(r["eligible_for_outreach"]),
        "playbook_trigger_reason": r["playbook_trigger_reason"], "playbooks_not_selected": list(r["playbooks_not_selected"]),
        "peer": {"segment_median_change": r["segment_median_tpv_change_pct"], "vs_segment_pp": r["tpv_change_vs_segment_median_pp"],
                 "industry_median_change": r["industry_median_tpv_change_pct"], "vs_industry_pp": r["tpv_change_vs_industry_median_pp"],
                 "industry_peers": r["industry_peer_count"]},
        "completeness": r["completeness_score"], "missing_fields": d["data_quality"]["missing_fields"],
        "why_priority": sentence(r),
        "assessment": {k: d[k] for k in ("plain_language_reason", "supporting_evidence", "mitigating_signals", "contradictory_signals",
                                         "alternative_explanations", "additional_checks_for_csm", "primary_risk_driver", "secondary_risk_drivers",
                                         "playbook_rationale", "contact_style", "score_contributions", "llm_used", "llm_notes",
                                         "primary_playbook_id", "primary_playbook_name", "secondary_playbook_id")},
    }
    dr = d["outreach_draft"] or extra_draft
    rec["draft"] = dr
    return jsonable(rec)


def run_analysis(clean: pd.DataFrame, playbooks: pd.DataFrame, assumptions: dict, cfg: dict, progress: Progress,
                 use_llm: bool = False, client: LLMClient | None = None) -> dict:
    cap = int(cfg.get("capacity", assumptions["max_outreaches"]))
    progress("validate", "Validating merchant records", 0.08)
    pb = norm_playbooks(playbooks)
    pb_cfg = load_playbook_cfg()
    unknown_seg = clean[~clean["segment"].isin(pb_cfg["segment_contact_style"])]
    excluded_extra = [{"row": None, "merchant_id": r.merchant_id, "reason": f"unrecognised segment '{r.segment}' (expected {', '.join(pb_cfg['segment_contact_style'])})"}
                      for r in unknown_seg.itertuples()]
    clean = clean[clean["segment"].isin(pb_cfg["segment_contact_style"])].reset_index(drop=True)
    if clean.empty:
        raise ValueError("No analysable merchant records after validation.")

    progress("score", "Analysing merchant signals", 0.25)
    settings, scoring, pb_cfg, feats, df = build_engine_frame(clean, pb, assumptions, cap)
    for c in ("account_manager", "logo_url"):
        df[c] = df["merchant_id"].map(dict(zip(clean["merchant_id"], clean[c]))) if c in clean else None

    progress("queue", "Building the priority queue", 0.45)
    base_scn = scenarios.default_scenario(cap)
    cur_scn = {**base_scn, "name": "Current selection", **{k: cfg[k] for k in ("priorities", "risk_focus", "segments", "exclude_industries", "renewal_window") if k in cfg}}
    base_rank = scenarios.rank(df, base_scn)
    cur_rank = scenarios.rank(df, cur_scn)
    bmap, cmap = base_rank.set_index("merchant_id"), cur_rank.set_index("merchant_id")
    df["baseline_rank"] = df["merchant_id"].map(bmap["scn_rank"])
    df["baseline_selected"] = df["merchant_id"].map(bmap["scn_selected"]).fillna(False).astype(bool)
    df["outreach_priority_rank"] = df["merchant_id"].map(cmap["scn_rank"])
    df["selected_for_outreach"] = df["merchant_id"].map(cmap["scn_selected"]).fillna(False).astype(bool)
    for i, r in df.iterrows():
        if r["selected_for_outreach"]:
            df.at[i, "outreach_reason"] = f"Priority #{int(r['outreach_priority_rank'])} of {cap}. {sentence(r)}"

    progress("recommend", "Preparing recommendations", 0.6)
    run_ts = dt.datetime.now().isoformat(timespec="seconds")
    assessments = run_deterministic(df, pb_cfg, settings, scoring)
    llm_stats = None
    if use_llm and client and client.available:
        progress("llm", "Asking Claude to review merchants and draft outreach", 0.65)
        llm_stats = enrich_with_llm(assessments, df, pb, client, settings)
        llm_stats = {**llm_stats, **{f"api_{k}": v for k, v in client.stats.items()}}

    by_id = df.set_index("merchant_id", drop=False)
    merchants = []
    for a in assessments:
        r = by_id.loc[a.merchant_id]
        extra = None
        if a.outreach_draft is None and r["primary_playbook_id"] in settings["selection"]["eligible_playbooks"] and r["risk_band"] != "low":
            d = template_draft(r)
            extra = d.model_dump() if d else None
        rec = merchant_record(r, a, extra)
        rec.update({"selected": bool(r["selected_for_outreach"]), "rank": jsonable(r["outreach_priority_rank"]),
                    "baseline_rank": jsonable(r["baseline_rank"]), "baseline_selected": bool(r["baseline_selected"]),
                    "selection_reason": r["outreach_reason"]})
        merchants.append(rec)

    progress("insights", "Building portfolio insights", 0.92)
    sel_ids = [m["id"] for m in merchants if m["selected"]]
    k = insights.kpis(df, cap, len(sel_ids))
    return {
        "version": VERSION, "created_at": run_ts, "merchant_count": len(merchants), "merchants": merchants,
        "kpis": jsonable(k), "narrative": insights.narrative(df, k), "drivers": jsonable(insights.drivers(df)),
        "segments": jsonable(insights.segments(df)), "heatmap": insights.heatmap(df),
        "commercial": jsonable(insights.commercial(df, assumptions, sel_ids)), "operational": insights.operational(df),
        "playbooks": pb.to_dict("records"), "scenario": cur_scn, "baseline_scenario": base_scn,
        "scoring": {"weights": scoring["weights"], "bands": scoring["bands"], "label": "Design hypotheses. No churn labels exist, so no accuracy is claimed."},
        "llm_used": bool(llm_stats), "llm_stats": jsonable(llm_stats) if llm_stats else None, "extra_excluded": excluded_extra,
        "industries": sorted(df["industry"].unique()), "segments_list": sorted(df["segment"].unique()),
    }
