"""Parse the workbook's assumptions sheet. Workbook text wins; anything unparseable is reported, never defaulted."""
from __future__ import annotations

import re

import pandas as pd

KEYS = {
    "net_revenue_rate": "Net revenue rate (share of TPV)",
    "false_alarm_cost_inr": "Cost of a false alarm (INR)",
    "saved_merchant_months": "Months of net revenue counted for a saved merchant",
    "tpv_unit_inr": "TPV unit (INR per reported unit)",
    "max_outreaches": "Outreach capacity per month",
    "churn_horizon_days": "Churn horizon (days)",
    "seasonal_industries": "Seasonal industries",
}


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def parse_assumptions(df: pd.DataFrame | None, industries: list[str]) -> tuple[dict, list[str], list[dict]]:
    """Returns (values, unresolved_keys, provenance rows). df needs item/assumption-like columns."""
    values: dict = {}
    prov: list[dict] = []
    if df is None or df.empty:
        return values, list(KEYS), prov
    cols = {str(c).lower().strip(): c for c in df.columns}
    ic = cols.get("item") or list(df.columns)[0]
    ac = cols.get("assumption") or list(df.columns)[-1]
    for _, row in df.iterrows():
        item, text = str(row[ic]).strip(), str(row[ac]).strip()
        low, tl = item.lower(), text.lower()
        key = val = None
        if "net revenue" in low and (m := re.search(r"(\d+(?:\.\d+)?)\s*%", text)):
            key, val = "net_revenue_rate", float(m.group(1)) / 100
        elif "false alarm" in low and (m := re.search(r"rs\.?\s*([\d,]+)", tl)):
            key, val = "false_alarm_cost_inr", _num(m.group(1))
        elif "saved" in low and (m := re.search(r"(\d+)\s*months", tl)):
            key, val = "saved_merchant_months", int(m.group(1))
        elif "unit" in low:
            if (m := re.search(r"=\s*([\d,]+)", tl)):
                key, val = "tpv_unit_inr", _num(m.group(1))
            elif "crore" in tl:
                key, val = "tpv_unit_inr", 10_000_000.0
            elif "lakh" in tl:
                key, val = "tpv_unit_inr", 100_000.0
        elif "capacity" in low and (m := re.search(r"(?:at most|up to|maximum of)\s*(\d+)", tl)):
            key, val = "max_outreaches", int(m.group(1))
        elif "horizon" in low and (m := re.search(r"(\d+)\s*days", tl)):
            key, val = "churn_horizon_days", int(m.group(1))
        elif "season" in low:
            hits = [i for i in industries if any(w in i.lower() for w in re.findall(r"[a-z]+", tl) if len(w) > 4 and w in i.lower())]
            key, val = "seasonal_industries", sorted(set(hits))
        if key:
            values[key] = val
            prov.append({"key": key, "label": KEYS[key], "value": val, "workbook_item": item, "workbook_text": text})
    return values, [k for k in KEYS if k not in values], prov
