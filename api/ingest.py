"""Workbook inspection, header detection, field mapping and data-quality review.

Nothing is imputed. Columns that cannot be mapped stay unavailable and the consequences are reported.
"""
from __future__ import annotations

import difflib
import re
from pathlib import Path

import numpy as np
import pandas as pd

TPV = [f"tpv_m{i}_inr_lakh" for i in range(1, 7)]

# key, label, required, kind, synonyms (normalised)
FIELDS: list[dict] = [
    {"key": "merchant_id", "label": "Merchant ID", "required": True, "kind": "id", "syn": ["merchant_id", "mid", "merchantid", "id", "account_id", "client_id"]},
    {"key": "business_name", "label": "Merchant name", "required": True, "kind": "text", "syn": ["business_name", "merchant_name", "name", "company", "company_name", "legal_name"]},
    {"key": "segment", "label": "Merchant segment", "required": True, "kind": "cat", "syn": ["segment", "merchant_segment", "tier", "size"]},
    {"key": "industry", "label": "Industry / category", "required": True, "kind": "cat", "syn": ["industry", "category", "business_category", "vertical", "sector"]},
    {"key": "city", "label": "City", "required": False, "kind": "cat", "syn": ["city", "location", "region"]},
    {"key": "tenure_months", "label": "Tenure (months)", "required": False, "kind": "num", "syn": ["tenure_months", "tenure", "vintage_months", "age_months"]},
    *[{"key": k, "label": f"Monthly TPV M{i + 1} (Rs lakh)", "required": True, "kind": "num",
       "syn": [k, f"tpv_m{i + 1}", f"m{i + 1}_tpv", f"tpv_month_{i + 1}", f"month_{i + 1}_tpv"]} for i, k in enumerate(TPV)],
    {"key": "success_rate_m1_m3_pct", "label": "Payment success rate, earlier period (%)", "required": True, "kind": "num",
     "syn": ["success_rate_m1_m3_pct", "success_rate_m1_m3", "success_rate_early", "success_rate_prev", "success_rate_earlier"]},
    {"key": "success_rate_m4_m6_pct", "label": "Payment success rate, recent period (%)", "required": True, "kind": "num",
     "syn": ["success_rate_m4_m6_pct", "success_rate_m4_m6", "success_rate_recent", "success_rate_latest", "success_rate_current", "payment_success_rate", "success_rate"]},
    {"key": "support_tickets_last_90d", "label": "Support tickets (last 90 days)", "required": True, "kind": "num",
     "syn": ["support_tickets_last_90d", "support_tickets", "tickets_90d", "total_tickets", "tickets"]},
    {"key": "unresolved_tickets", "label": "Unresolved tickets", "required": True, "kind": "num",
     "syn": ["unresolved_tickets", "open_tickets", "tickets_unresolved", "pending_tickets"]},
    {"key": "last_csat_1_to_5", "label": "CSAT (1 to 5)", "required": False, "kind": "num", "syn": ["last_csat_1_to_5", "csat", "csat_score", "last_csat"]},
    {"key": "products_used", "label": "Products used", "required": True, "kind": "num", "syn": ["products_used", "products", "product_count", "no_of_products"]},
    {"key": "logins_last_30d", "label": "Logins (last 30 days)", "required": True, "kind": "num", "syn": ["logins_last_30d", "logins", "logins_30d", "dashboard_logins"]},
    {"key": "days_to_contract_renewal", "label": "Days to contract renewal", "required": True, "kind": "num",
     "syn": ["days_to_contract_renewal", "days_to_renewal", "renewal_days", "days_until_renewal"]},
    {"key": "account_manager_note", "label": "Account manager note", "required": False, "kind": "text",
     "syn": ["account_manager_note", "am_note", "notes", "note", "comments", "account_notes"]},
    {"key": "account_manager", "label": "Account manager (name)", "required": False, "kind": "cat", "syn": ["account_manager", "am", "csm", "owner", "relationship_manager"]},
    {"key": "logo_url", "label": "Merchant logo URL", "required": False, "kind": "text", "syn": ["logo_url", "logo", "logo_link"]},
]
FIELD_BY_KEY = {f["key"]: f for f in FIELDS}

IMPACT = {  # what is weaker when an optional/required field is absent
    "last_csat_1_to_5": "Satisfaction is unknown for every merchant; CSAT is treated as missing, not as poor.",
    "account_manager_note": "Commercial and engagement signals that come from account-manager notes (competitor, pricing, unresponsive) cannot be detected.",
    "city": "City is not shown. No effect on scoring.",
    "tenure_months": "Tenure is not shown. No effect on scoring.",
    "account_manager": "Account manager is not shown on profiles.",
    "logo_url": "Initials-based identity marks are used instead of logos.",
}

PLAYBOOK_COLS = ["playbook_id", "name", "what_happens", "when_it_applies"]


def norm(s) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).strip().lower()).strip("_")


def _empty(v) -> bool:
    return v is None or (isinstance(v, float) and np.isnan(v)) or (isinstance(v, str) and not v.strip())


def read_raw(path: Path, sheet: str | None):
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, header=None, dtype=object, keep_default_na=False, na_values=[""])
    return pd.read_excel(path, sheet_name=sheet, header=None, dtype=object)


def sheet_names(path: Path) -> list[str]:
    if path.suffix.lower() == ".csv":
        return [path.stem]
    return list(pd.ExcelFile(path).sheet_names)


def detect_header(raw: pd.DataFrame) -> int:
    best, best_n = 0, -1
    for i in range(min(10, len(raw))):
        row = raw.iloc[i]
        n = sum(1 for v in row if isinstance(v, str) and v.strip())
        if n > best_n:
            best, best_n = i, n
    return best


def frame_from_raw(raw: pd.DataFrame, header_row: int) -> pd.DataFrame:
    header = list(raw.iloc[header_row])
    keep = [i for i, h in enumerate(header) if not _empty(h)]
    cols, seen = [], {}
    for i in keep:
        c = str(header[i]).strip()
        seen[c] = seen.get(c, 0) + 1
        cols.append(c if seen[c] == 1 else f"{c}.{seen[c]}")
    body = raw.iloc[header_row + 1:, keep].copy()
    body.columns = cols
    body = body[~body.apply(lambda r: all(_empty(v) for v in r), axis=1)].reset_index(drop=True)
    return body


def auto_map(columns: list[str]) -> dict[str, dict]:
    """canonical key -> {source, confidence: exact|suggested|none, candidates}."""
    normed = {c: norm(c) for c in columns}
    used: set[str] = set()
    out: dict[str, dict] = {}
    for f in FIELDS:  # pass 1: exact synonym matches
        hit = next((c for c, n in normed.items() if n in f["syn"] and c not in used), None)
        if hit and f["key"] != "success_rate_m4_m6_pct":
            out[f["key"]] = {"source": hit, "confidence": "exact"}
            used.add(hit)
    for f in FIELDS:
        if f["key"] in out:
            continue
        if f["key"] == "success_rate_m4_m6_pct":  # bare "success rate" is ambiguous when two periods exist
            hit = next((c for c, n in normed.items() if n in f["syn"] and c not in used), None)
            if hit:
                out[f["key"]] = {"source": hit, "confidence": "exact" if norm(hit) != "success_rate" else "suggested"}
                used.add(hit)
                continue
        pool = [c for c in columns if c not in used]
        m = difflib.get_close_matches(norm(f["key"]), [normed[c] for c in pool], n=1, cutoff=0.72)
        if not m:
            labels = difflib.get_close_matches(norm(f["label"]), [normed[c] for c in pool], n=1, cutoff=0.8)
            m = labels
        if m:
            src = next(c for c in pool if normed[c] == m[0])
            out[f["key"]] = {"source": src, "confidence": "suggested"}
            used.add(src)
        else:
            out[f["key"]] = {"source": None, "confidence": "none"}
    for f in FIELDS:
        out.setdefault(f["key"], {"source": None, "confidence": "none"})
    return out


def classify_sheets(path: Path) -> list[dict]:
    res = []
    for name in sheet_names(path):
        raw = read_raw(path, name)
        if raw.empty:
            res.append({"name": name, "role": "empty", "rows": 0, "cols": 0, "score": 0, "header_row": 0})
            continue
        h = detect_header(raw)
        df = frame_from_raw(raw, h)
        cols = [norm(c) for c in df.columns]
        mapping = auto_map(list(df.columns))
        score = sum(1 for k, v in mapping.items() if v["confidence"] == "exact" and FIELD_BY_KEY[k]["required"])
        role = "other"
        if "playbook_id" in cols or (len(df) and df.iloc[:, 0].astype(str).str.upper().str.startswith("PB-").mean() > 0.6):
            role = "playbooks"
        elif {"item", "assumption"} <= set(cols):
            role = "assumptions"
        elif score >= 6 or "merchant_id" in cols:
            role = "merchants"
        res.append({"name": name, "role": role, "rows": int(len(df)), "cols": int(len(df.columns)), "score": score, "header_row": int(h)})
    if sum(1 for s in res if s["role"] == "merchants") > 1:  # keep the best candidate
        best = max((s for s in res if s["role"] == "merchants"), key=lambda s: (s["score"], s["rows"]))
        for s in res:
            if s["role"] == "merchants" and s is not best:
                s["role"] = "other"
    return res


_CLEAN = re.compile(r"[,\s₹]|rs\.?|inr|%", re.I)


def to_number(v) -> tuple[float, bool]:
    """(value, was_reformatted). NaN when not numeric."""
    if _empty(v):
        return float("nan"), False
    if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
        return float(v), False
    s = _CLEAN.sub("", str(v))
    try:
        return float(s), True
    except ValueError:
        return float("nan"), False


def column_kind(series: pd.Series) -> str:
    vals = [v for v in series if not _empty(v)]
    if not vals:
        return "empty"
    if all(isinstance(v, (pd.Timestamp, np.datetime64)) or hasattr(v, "year") and hasattr(v, "month") for v in vals):
        return "date"
    nums = sum(1 for v in vals if not np.isnan(to_number(v)[0]))
    if nums / len(vals) >= 0.9:
        return "numeric"
    uniq = len({str(v) for v in vals})
    return "categorical" if uniq <= max(20, len(vals) * 0.3) else "text"


RANGES = {"success_rate_m1_m3_pct": (0, 100), "success_rate_m4_m6_pct": (0, 100), "last_csat_1_to_5": (1, 5)}


def prepare(df: pd.DataFrame, mapping: dict[str, str | None]) -> dict:
    """Apply a mapping. Returns canonical frame, excluded records and the quality report."""
    mapped = {k: s for k, s in mapping.items() if s and s in df.columns}
    n_raw = len(df)
    canon = pd.DataFrame(index=df.index)
    reformatted: dict[str, int] = {}
    invalid: list[dict] = []
    for f in FIELDS:
        k = f["key"]
        src = mapped.get(k)
        if not src:
            canon[k] = np.nan if f["kind"] == "num" else None
            continue
        col = df[src]
        if f["kind"] == "num":
            conv = [to_number(v) for v in col]
            canon[k] = [c[0] for c in conv]
            reformatted[k] = sum(1 for c in conv if c[1])
            bad = [i for i, v in enumerate(col) if not _empty(v) and np.isnan(conv[i][0])]
            for i in bad:
                invalid.append({"row": int(i) + 2, "field": k, "value": str(col.iloc[i]), "issue": "not a number"})
            if k in RANGES:
                lo, hi = RANGES[k]
                for i, (v, _) in enumerate(conv):
                    if not np.isnan(v) and not lo <= v <= hi:
                        invalid.append({"row": i + 2, "field": k, "value": v, "issue": f"outside {lo}-{hi}"})
                        canon.iloc[i, canon.columns.get_loc(k)] = np.nan
            elif k in TPV + ["support_tickets_last_90d", "unresolved_tickets", "products_used", "logins_last_30d"]:
                for i, (v, _) in enumerate(conv):
                    if not np.isnan(v) and v < 0:
                        invalid.append({"row": i + 2, "field": k, "value": v, "issue": "negative value"})
                        canon.iloc[i, canon.columns.get_loc(k)] = np.nan
        else:
            canon[k] = [None if _empty(v) else str(v).strip() for v in col]
    ids = canon["merchant_id"] if "merchant_id" in mapped else pd.Series([None] * n_raw, index=df.index)
    dup_mask = ids.notna() & ids.duplicated(keep="first")
    dup_ids = sorted(set(ids[ids.notna() & ids.duplicated(keep=False)]))
    required_missing_cols = [f["key"] for f in FIELDS if f["required"] and f["key"] not in mapped]
    # records the engine cannot score without inventing values
    need = [f["key"] for f in FIELDS if f["required"] and f["key"] in mapped]
    row_missing = canon[need].isna().any(axis=1) if need else pd.Series(False, index=canon.index)
    excluded: list[dict] = []
    for i in canon.index[ids.isna() | dup_mask | row_missing]:
        why = ("missing merchant ID" if pd.isna(ids[i]) else "duplicate merchant ID (first occurrence kept)" if dup_mask[i]
               else "missing or invalid required values: " + ", ".join(c for c in need if pd.isna(canon.at[i, c])))
        excluded.append({"row": int(i) + 2, "merchant_id": None if pd.isna(ids[i]) else ids[i], "reason": why})
    keep_mask = ~(ids.isna() | dup_mask | row_missing)
    clean = canon[keep_mask].reset_index(drop=True) if not required_missing_cols else canon.iloc[0:0]

    missing_by_field = []
    for f in FIELDS:
        k = f["key"]
        if k in mapped:
            miss = int(canon[k].isna().sum())
            missing_by_field.append({"field": k, "label": f["label"], "missing": miss, "pct": round(miss / max(n_raw, 1) * 100, 1)})
    seen_ids = set(ids.dropna())
    report = {
        "total_records": n_raw, "unique_ids": len(seen_ids), "duplicate_ids": dup_ids, "duplicate_rows": int(dup_mask.sum()),
        "missing_by_field": missing_by_field, "invalid_records": invalid[:200], "invalid_count": len(invalid),
        "reformatted_cells": {k: v for k, v in reformatted.items() if v}, "excluded_records": excluded,
        "analysable_records": int(len(clean)), "required_missing": required_missing_cols,
        "mapped_count": len(mapped), "total_fields": len(FIELDS),
        "unmapped_optional": [k for k in (f["key"] for f in FIELDS if not f["required"]) if k not in mapped],
        "impact": [{"field": k, "label": FIELD_BY_KEY[k]["label"], "effect": IMPACT[k]} for k in IMPACT if k not in mapped],
        "unmapped_source_columns": [c for c in df.columns if c not in mapped.values()],
    }
    return {"clean": clean, "report": report}


def column_profiles(df: pd.DataFrame) -> list[dict]:
    out = []
    for c in df.columns:
        s = df[c]
        out.append({"column": c, "kind": column_kind(s), "missing": int(sum(_empty(v) for v in s)), "sample": [str(v) for v in s.dropna().head(3)]})
    return out


def df_preview(df: pd.DataFrame, limit: int = 1000) -> dict:
    rows = []
    for _, r in df.head(limit).iterrows():
        rows.append([None if _empty(v) else (v.isoformat() if hasattr(v, "isoformat") else (float(v) if isinstance(v, (np.floating,)) else str(v) if not isinstance(v, (int, float)) else v)) for v in r])
    return {"columns": list(df.columns), "rows": rows, "total": int(len(df)), "truncated": len(df) > limit}
