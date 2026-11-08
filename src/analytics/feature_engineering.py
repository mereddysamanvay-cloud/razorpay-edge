"""Reproducible derived features. Uses only fields that exist in P2_Merchants."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.crm.note_classifier import classify_note, signal_names

TPV_COLS = [f"tpv_m{i}_inr_lakh" for i in range(1, 7)]


def pct_change(new: float, old: float) -> float:
    """Percentage change; NaN when the denominator is zero/missing (never inf)."""
    if new is None or old is None or math.isnan(new) or math.isnan(old) or old == 0:
        return float("nan")
    return (new - old) / old * 100.0


def consecutive_declines(values: list[float], tolerance_pct: float = 1.0) -> int:
    """Count month-on-month declines (> tolerance) ending at the latest month."""
    n = 0
    for i in range(len(values) - 1, 0, -1):
        prev, cur = values[i - 1], values[i]
        if prev and not math.isnan(prev) and not math.isnan(cur) and (cur - prev) / prev * 100 < -tolerance_pct:
            n += 1
        else:
            break
    return n


def slope_pct_per_month(values: list[float]) -> float:
    arr = np.asarray(values, dtype=float)
    mean = arr.mean()
    if np.isnan(mean) or mean == 0:
        return float("nan")
    return float(np.polyfit(np.arange(len(arr)), arr, 1)[0] / mean * 100)


def coefficient_of_variation(values: list[float]) -> float:
    arr = np.asarray(values, dtype=float)
    mean = arr.mean()
    return float("nan") if mean == 0 or np.isnan(mean) else float(arr.std(ddof=0) / mean)


def engineer_features(merchants: pd.DataFrame, settings: dict, scoring: dict) -> pd.DataFrame:
    sa = settings["source_assumptions"]
    seasonal_set = set(sa["seasonal_industries"])
    tol = scoring["tpv"]["decline_tolerance_pct"]
    sc = scoring["seasonal"]
    rows = []
    for _, r in merchants.iterrows():
        v = [float(r[c]) for c in TPV_COLS]
        early, recent = float(np.mean(v[:3])), float(np.mean(v[3:]))
        f: dict = {"merchant_id": r["merchant_id"]}
        f["tpv_change_m1_m6_pct"] = pct_change(v[5], v[0])
        f["tpv_change_m1_m6_abs_lakh"] = v[5] - v[0]
        f["tpv_avg_m1_m3"], f["tpv_avg_m4_m6"] = early, recent
        f["recent_vs_early_pct"] = pct_change(recent, early)
        f["m6_vs_m5_pct"] = pct_change(v[5], v[4])
        f["m6_vs_peak_pct"] = pct_change(v[5], max(v))
        f["consecutive_declines"] = consecutive_declines(v, tol)
        f["tpv_slope_pct_per_month"] = slope_pct_per_month(v)
        f["tpv_cv"] = coefficient_of_variation(v)
        rve = f["recent_vs_early_pct"]
        f["tpv_trend"] = ("unknown" if math.isnan(rve) else
                          "deteriorating" if rve <= -10 else "improving" if rve >= 10 else "stable")
        f["is_seasonal_industry"] = r["industry"] in seasonal_set
        dip = early > 0 and min(v[3], v[4]) <= early * (1 - sc["dip_min_pct"] / 100)
        rebound = v[4] > 0 and v[5] >= v[4] * (1 + sc["rebound_min_pct"] / 100)
        f["dip_and_rebound"] = bool(dip and rebound)

        f["success_drop_pp"] = float(r["success_rate_m4_m6_pct"] - r["success_rate_m1_m3_pct"])
        f["success_recent_pct"] = float(r["success_rate_m4_m6_pct"])
        f["success_early_pct"] = float(r["success_rate_m1_m3_pct"])
        f["tpv_and_success_deteriorating"] = bool((not math.isnan(rve)) and rve <= -10 and f["success_drop_pp"] <= -2)

        tickets, unresolved = float(r["support_tickets_last_90d"]), float(r["unresolved_tickets"])
        f["tickets_90d"], f["unresolved"] = tickets, unresolved
        f["unresolved_ratio"] = unresolved / tickets if tickets > 0 else float("nan")
        csat = r["last_csat_1_to_5"]
        f["csat"] = float(csat) if pd.notna(csat) else float("nan")
        f["csat_missing"] = bool(pd.isna(csat))
        f["csat_low"] = bool(pd.notna(csat) and csat <= 2)

        f["logins_30d"], f["products_used"] = float(r["logins_last_30d"]), float(r["products_used"])
        f["renewal_days"] = float(r["days_to_contract_renewal"])
        f["renewal_band"] = ("<=30d" if f["renewal_days"] <= 30 else "31-60d" if f["renewal_days"] <= 60
                             else "61-90d" if f["renewal_days"] <= 90 else ">90d")

        cl = classify_note(r["account_manager_note"])
        f["note_missing"] = not cl["has_note"]
        f["note_injection_suspect"] = cl["injection_suspect"]
        for name in signal_names():
            f[f"note_{name}"] = cl["flags"][name]
        f["note_evidence"] = "; ".join(f"{k}='{v}'" for k, v in cl["evidence"].items())

        monthly_net = v[5] * sa["tpv_unit_inr"] * sa["net_revenue_rate"]
        f["monthly_net_revenue_inr"] = monthly_net
        f["annual_value_at_stake_inr"] = monthly_net * sa["saved_merchant_months"]
        missing = int(f["csat_missing"]) + int(f["note_missing"])
        f["completeness_score"] = 100 - 50 * missing
        f["missing_fields"] = ", ".join(n for n, m in (("last_csat_1_to_5", f["csat_missing"]),
                                                       ("account_manager_note", f["note_missing"])) if m)
        rows.append(f)
    feats = pd.DataFrame(rows)
    out = merchants[["merchant_id", "business_name", "segment", "industry", "city", "tenure_months",
                     "account_manager_note", *TPV_COLS]].merge(feats, on="merchant_id", how="left")
    return out
