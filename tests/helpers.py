"""Synthetic single-merchant scenario builder (fictional rows; expectations are written in the tests)."""
from __future__ import annotations

import pandas as pd

from src.analytics.feature_engineering import engineer_features
from src.analytics.prioritisation import prioritise
from src.analytics.risk_scoring import score_merchants
from src.config import load_playbook_cfg, load_scoring, load_settings, resolve
from src.crm.playbook_selector import apply_selection
from src.ingestion.workbook_loader import load_source

_SETTINGS, _SCORING, _PB = load_settings(), load_scoring(), load_playbook_cfg()
_PLAYBOOKS = load_source(resolve(_SETTINGS["paths"]["workbook"]), _SETTINGS["sheets"]).playbooks


def make_row(mid="T1", **kw) -> dict:
    row = {"merchant_id": mid, "business_name": f"Test {mid}", "segment": "Mid", "industry": "SaaS / Digital Services", "city": "Pune",
           "tenure_months": 30.0, "success_rate_m1_m3_pct": 95.0, "success_rate_m4_m6_pct": 95.0, "support_tickets_last_90d": 2.0,
           "unresolved_tickets": 0.0, "last_csat_1_to_5": 4.0, "products_used": 4.0, "logins_last_30d": 18.0,
           "days_to_contract_renewal": 200.0, "account_manager_note": None}
    tpv = kw.pop("tpv", [20.0] * 6)
    for i, v in enumerate(tpv, 1):
        row[f"tpv_m{i}_inr_lakh"] = float(v)
    row.update(kw)
    return row


def run_rows(rows: list[dict], scoring: dict | None = None, settings: dict | None = None) -> pd.DataFrame:
    settings, scoring = settings or _SETTINGS, scoring or _SCORING
    m = pd.DataFrame(rows)
    feats = engineer_features(m, settings, scoring)
    return prioritise(apply_selection(score_merchants(feats, scoring), _PB, _PLAYBOOKS), settings)


def run_one(**kw) -> pd.Series:
    return run_rows([make_row(**kw)]).iloc[0]
