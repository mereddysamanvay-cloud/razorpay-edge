"""Prompt assembly. Prompt text lives in /prompts and the knowledge base in /knowledge."""
from __future__ import annotations

import json
import re

import pandas as pd

from src.config import ROOT, resolve

KNOWLEDGE_FILES = ["business_context.md", "signal_taxonomy.md", "playbooks.md", "assumptions.md",
                   "segment_guidance.md", "communication_policy.md"]


def _read(path) -> str:
    return path.read_text(encoding="utf-8")


def system_prompt(settings: dict) -> str:
    kdir = resolve(settings["paths"]["knowledge"])
    parts = [_read(ROOT / "prompts" / "system_base.md"), "\n\n# KNOWLEDGE BASE (source of truth)\n"]
    for f in KNOWLEDGE_FILES:
        p = kdir / f
        if p.exists():
            parts.append(f"\n## {f}\n{_read(p)}")
    return "\n".join(parts)


def _safe_note(note) -> str:
    if not isinstance(note, str):
        return ""
    return re.sub(r"</?\s*untrusted_account_manager_note\s*>", "", note)[:300]


def _num(x):
    return None if pd.isna(x) else round(float(x), 2)


def analyst_message(r: pd.Series) -> str:
    data = {
        "merchant_id": r["merchant_id"], "segment": r["segment"], "industry": r["industry"],
        "is_seasonal_industry": bool(r["is_seasonal_industry"]),
        "tpv_m1_to_m6_inr_lakh": [_num(r[f"tpv_m{i}_inr_lakh"]) for i in range(1, 7)],
        "recent_vs_early_tpv_pct": _num(r["recent_vs_early_pct"]), "consecutive_declines": int(r["consecutive_declines"]),
        "dip_and_rebound": bool(r["dip_and_rebound"]),
        "success_rate_m1_m3_pct": _num(r["success_early_pct"]), "success_rate_m4_m6_pct": _num(r["success_recent_pct"]),
        "tickets_90d": int(r["tickets_90d"]), "unresolved_tickets": int(r["unresolved"]), "csat_1_to_5": _num(r["csat"]),
        "logins_last_30d": int(r["logins_30d"]), "products_used": int(r["products_used"]), "days_to_renewal": int(r["renewal_days"]),
        "computed": {"risk_score": r["risk_score"], "risk_band": r["risk_band"],
                     "dimension_scores": {d: r[f"dim_{d}"] for d in ("performance", "relationship", "engagement", "commercial")},
                     "deterministic_note_flags": [c[5:] for c in r.index if c.startswith("note_") and c not in ("note_evidence", "note_missing", "note_injection_suspect") and bool(r[c])],
                     "selected_playbook": r["primary_playbook_id"], "playbook_trigger_reason": r["playbook_trigger_reason"]},
    }
    task = _read(ROOT / "prompts" / "analyst_review.md")
    return (f"{task}\n\n<merchant_data>\n{json.dumps(data, indent=1)}\n</merchant_data>\n"
            f"<untrusted_account_manager_note>\n{_safe_note(r['account_manager_note'])}\n</untrusted_account_manager_note>")


def outreach_message(r: pd.Series, facts: dict, playbook_row: pd.Series) -> str:
    data = {
        "business_name": r["business_name"], "segment": r["segment"],
        "approved_playbook": {"id": playbook_row["playbook_id"], "name": playbook_row["name"], "approved_action_text": playbook_row["what_happens"]},
        "allowed_facts": facts,
    }
    return f"{_read(ROOT / 'prompts' / 'outreach_draft.md')}\n\n<merchant_data>\n{json.dumps(data, indent=1)}\n</merchant_data>"
