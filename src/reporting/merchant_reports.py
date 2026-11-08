"""Machine- and human-readable per-merchant outputs."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.agent.schemas import MerchantAssessment

LIST_COLUMNS = ["contributions", "secondary_dimensions", "critical_triggers", "playbook_triggers", "playbooks_not_selected"]


def write_features(df: pd.DataFrame, path: Path) -> None:
    out = df.copy()
    for c in LIST_COLUMNS:
        if c in out.columns:
            out[c] = out[c].map(lambda v: json.dumps(v, default=str) if not isinstance(v, str) else v)
    out.sort_values("risk_rank").to_csv(path, index=False)


def write_assessments(assessments: list[MerchantAssessment], json_path: Path, csv_path: Path, top_path: Path) -> None:
    json_path.write_text(json.dumps([a.model_dump(mode="json") for a in assessments], indent=2, ensure_ascii=False), encoding="utf-8")
    rows = []
    for a in assessments:
        rows.append({
            "risk_rank": a.risk_rank, "merchant_id": a.merchant_id, "business_name": a.business_name, "segment": a.segment,
            "industry": a.industry, "risk_score": a.risk_score, "risk_band": a.risk_band, "risk_confidence": a.risk_confidence,
            "churn_probability": "", "data_completeness": a.data_quality.completeness_score,
            "dim_performance": a.dimension_scores.performance, "dim_relationship": a.dimension_scores.relationship,
            "dim_engagement": a.dimension_scores.engagement, "dim_commercial": a.dimension_scores.commercial,
            "primary_risk_driver": a.primary_risk_driver, "secondary_risk_drivers": " | ".join(a.secondary_risk_drivers),
            "plain_language_reason": a.plain_language_reason, "mitigating_signals": " | ".join(a.mitigating_signals),
            "contradictory_signals": " | ".join(a.contradictory_signals), "alternative_explanations": " | ".join(a.alternative_explanations),
            "additional_checks_for_csm": " | ".join(a.additional_checks_for_csm), "critical_review_triggers": " | ".join(a.critical_review_triggers),
            "primary_playbook_id": a.primary_playbook_id, "primary_playbook_name": a.primary_playbook_name,
            "secondary_playbook_id": a.secondary_playbook_id or "", "playbook_rationale": a.playbook_rationale,
            "contact_style": a.contact_style, "outreach_priority_rank": a.outreach_priority_rank or "",
            "selected_for_outreach": a.selected_for_outreach, "outreach_reason": a.outreach_reason,
            "annual_run_rate_revenue_exposure_inr": a.annual_value_at_stake_inr, "priority_proxy_inr": a.priority_value_inr,
            "outreach_subject": a.outreach_draft.subject if a.outreach_draft else "",
            "outreach_draft": a.outreach_draft.body if a.outreach_draft else "",
            "outreach_source": a.outreach_draft.source if a.outreach_draft else "",
            "review_status": a.outreach_draft.review_status if a.outreach_draft else "", "human_review_required": a.human_review_required,
            "llm_used": a.llm_used, "config_version": a.config_version, "run_timestamp": a.run_timestamp,
        })
    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False)
    top = df[df["selected_for_outreach"]].sort_values("outreach_priority_rank")
    top.to_csv(top_path, index=False)
