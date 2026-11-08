"""Strict output contracts. churn_probability is structurally forced to None (no labels exist)."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

REVIEW_STATUS = "DRAFT - pending CSM review"
RISK_DISCLAIMER = ("Heuristic risk score on a 0-100 scale built from supplied signals. It is NOT a churn probability "
                   "and has not been validated against actual churn labels (withheld).")


class Evidence(BaseModel):
    source_field: str
    observed_value: str
    interpretation: str


class DataQuality(BaseModel):
    completeness_score: float = Field(ge=0, le=100)
    missing_fields: list[str] = []


class DimensionScores(BaseModel):
    performance: float = Field(ge=0, le=100)
    relationship: float = Field(ge=0, le=100)
    engagement: float = Field(ge=0, le=100)
    commercial: float = Field(ge=0, le=100)


class OutreachDraft(BaseModel):
    subject: str
    body: str
    review_status: str = REVIEW_STATUS
    source: Literal["template", "llm"] = "template"
    facts_used: list[str] = []
    safety_violations: list[str] = []


class MerchantAssessment(BaseModel):
    merchant_id: str
    business_name: str
    segment: str
    industry: str
    risk_score: float = Field(ge=0, le=100)
    risk_band: Literal["low", "medium", "high"]
    churn_probability: None = None
    risk_confidence: Literal["low", "medium", "high"]
    data_quality: DataQuality
    dimension_scores: DimensionScores
    primary_risk_driver: str
    secondary_risk_drivers: list[str] = []
    plain_language_reason: str
    supporting_evidence: list[Evidence] = []
    mitigating_signals: list[str] = []
    contradictory_signals: list[str] = []
    alternative_explanations: list[str] = []
    additional_checks_for_csm: list[str] = []
    critical_review_triggers: list[str] = []
    primary_playbook_id: str
    primary_playbook_name: str
    secondary_playbook_id: Optional[str] = None
    playbook_rationale: str
    contact_style: str
    risk_rank: int = Field(ge=1)
    outreach_priority_rank: Optional[int] = None
    selected_for_outreach: bool
    outreach_reason: str
    annual_value_at_stake_inr: float
    priority_value_inr: float
    outreach_draft: Optional[OutreachDraft] = None
    human_review_required: bool = True
    llm_used: bool = False
    llm_notes: list[str] = []
    score_contributions: list[dict] = []
    risk_basis: str = RISK_DISCLAIMER
    config_version: str
    run_timestamp: str

    @field_validator("human_review_required")
    @classmethod
    def _always_human(cls, v: bool) -> bool:
        if not v:
            raise ValueError("every assessment requires human CSM review")
        return v


# ---- LLM tool schemas (validated before use) -------------------------------------------------
class LLMNoteLabel(BaseModel):
    label: str
    supporting_text: str
    confidence: Literal["low", "medium", "high"]


class LLMReview(BaseModel):
    note_interpretation: list[LLMNoteLabel] = []
    plain_language_reason: str = Field(max_length=700)
    mitigating_signals: list[str] = Field(default=[], max_length=4)
    contradictory_signals: list[str] = Field(default=[], max_length=4)
    alternative_explanations: list[str] = Field(default=[], max_length=4)
    additional_checks_for_csm: list[str] = Field(default=[], max_length=4)
    playbook_review: Literal["agree", "disagree"]
    playbook_review_rationale: str = Field(max_length=400)
    injection_suspected: bool = False


class LLMOutreach(BaseModel):
    subject: str = Field(max_length=120)
    body: str = Field(max_length=1200)
    facts_used: list[str] = []
