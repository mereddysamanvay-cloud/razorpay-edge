"""Orchestrator: deterministic assessment first, optional bounded LLM enrichment second.

The LLM can add interpretation, alternatives, CSM checks and wording. It can NOT change scores,
bands, ranks, playbook selection or the 15-contact selection. Invalid or unsafe LLM output falls back
to the deterministic text.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from src.agent import prompts
from src.agent.llm_client import LLMClient
from src.agent.safety import check_analysis_text, check_outreach
from src.agent.schemas import (DataQuality, DimensionScores, Evidence, LLMOutreach, LLMReview, MerchantAssessment,
                               OutreachDraft)
from src.analytics.risk_scoring import DIMENSIONS
from src.crm.evidence import build_evidence, driver_label, plain_language_reason
from src.crm.outreach_generator import allowed_facts, allowed_numbers, template_draft


def _driver_text(r: pd.Series) -> tuple[str, list[str]]:
    if r["risk_band"] == "low" or r["primary_dimension"] is None:
        return "No material risk signal", []
    return driver_label(r, r["primary_dimension"]), [driver_label(r, d) for d in r["secondary_dimensions"]]


def build_assessment(r: pd.Series, pb_cfg: dict, settings: dict, scoring: dict, run_ts: str) -> MerchantAssessment:
    ev = build_evidence(r)
    primary, secondary = _driver_text(r)
    rationale = f"{r['primary_playbook_id']} ({r['primary_playbook_name']}): {r['playbook_trigger_reason']}."
    if isinstance(r["secondary_playbook_id"], str):
        rationale += f" Secondary: {r['secondary_playbook_id']} (coordinate as ONE CSM interaction with internal specialist support)."
    if r["playbooks_not_selected"]:
        rationale += " Not selected: " + "; ".join(r["playbooks_not_selected"]) + "."
    draft = template_draft(r) if r["selected_for_outreach"] else None
    if draft:
        draft.safety_violations = check_outreach(draft.subject, draft.body, allowed_numbers(r))
    rank = r["outreach_priority_rank"]
    return MerchantAssessment(
        merchant_id=r["merchant_id"], business_name=r["business_name"], segment=r["segment"], industry=r["industry"],
        risk_score=r["risk_score"], risk_band=r["risk_band"], risk_confidence=r["risk_confidence"],
        data_quality=DataQuality(completeness_score=r["completeness_score"],
                                 missing_fields=[x.strip() for x in r["missing_fields"].split(",") if x.strip()]),
        dimension_scores=DimensionScores(**{d: r[f"dim_{d}"] for d in DIMENSIONS}),
        primary_risk_driver=primary, secondary_risk_drivers=secondary,
        plain_language_reason=plain_language_reason(r),
        supporting_evidence=[Evidence(**e) for e in ev["supporting_evidence"]],
        mitigating_signals=ev["mitigating_signals"], contradictory_signals=ev["contradictory_signals"],
        alternative_explanations=ev["alternative_explanations"], additional_checks_for_csm=ev["additional_checks_for_csm"],
        critical_review_triggers=list(r["critical_triggers"]),
        primary_playbook_id=r["primary_playbook_id"], primary_playbook_name=r["primary_playbook_name"],
        secondary_playbook_id=r["secondary_playbook_id"] if isinstance(r["secondary_playbook_id"], str) else None,
        playbook_rationale=rationale, contact_style=pb_cfg["segment_contact_style"][r["segment"]],
        risk_rank=int(r["risk_rank"]), outreach_priority_rank=None if pd.isna(rank) else int(rank),
        selected_for_outreach=bool(r["selected_for_outreach"]), outreach_reason=r["outreach_reason"],
        annual_value_at_stake_inr=round(float(r["annual_value_at_stake_inr"]), 0),
        priority_value_inr=round(float(r["priority_value_inr"]), 0), outreach_draft=draft,
        score_contributions=[c for c in r["contributions"] if c["points"] or c["dimension"] == "performance"],
        config_version=f"{settings['config_version']} / scoring {scoring['scoring_version']}", run_timestamp=run_ts,
    )


def run_deterministic(df: pd.DataFrame, pb_cfg: dict, settings: dict, scoring: dict) -> list[MerchantAssessment]:
    run_ts = dt.datetime.now().isoformat(timespec="seconds")
    return [build_assessment(r, pb_cfg, settings, scoring, run_ts) for _, r in df.sort_values("risk_rank").iterrows()]


def _dedupe(base: list[str], extra: list[str]) -> list[str]:
    seen = {x.lower() for x in base}
    return base + [x for x in extra if x.lower() not in seen]


def enrich_with_llm(assessments: list[MerchantAssessment], df: pd.DataFrame, playbooks: pd.DataFrame,
                    client: LLMClient, settings: dict) -> dict:
    """Mutates assessments in place. Returns run statistics for the validation report."""
    system = prompts.system_prompt(settings)
    by_id = df.set_index("merchant_id", drop=False)
    pb_by_id = playbooks.set_index("playbook_id", drop=False)
    stats = {"review_attempted": 0, "review_accepted": 0, "review_rejected_unsafe": 0, "review_failed": 0,
             "outreach_attempted": 0, "outreach_accepted": 0, "outreach_fallback_to_template": 0,
             "playbook_disagreements": [], "note_flag_disagreements": [], "injection_flagged": []}
    for a in assessments:
        r = by_id.loc[a.merchant_id]
        stats["review_attempted"] += 1
        rev = client.call_tool(system=system, user=prompts.analyst_message(r), model_cls=LLMReview, tool_name="submit_merchant_review",
                               description="Submit the structured review of this merchant's deterministic risk assessment.",
                               max_tokens=settings["llm"]["max_tokens_analyst"], tag=f"review:{a.merchant_id}")
        if rev is None:
            stats["review_failed"] += 1
            a.llm_notes.append("LLM review unavailable or schema-invalid; deterministic text used.")
        else:
            bad = check_analysis_text(rev.plain_language_reason, *rev.mitigating_signals, *rev.contradictory_signals,
                                      *rev.alternative_explanations, *rev.additional_checks_for_csm, rev.playbook_review_rationale)
            if bad:
                stats["review_rejected_unsafe"] += 1
                a.llm_notes.append(f"LLM review rejected by guardrails: {bad}")
            else:
                stats["review_accepted"] += 1
                a.llm_used = True
                a.plain_language_reason = rev.plain_language_reason
                a.mitigating_signals = _dedupe(a.mitigating_signals, rev.mitigating_signals)
                a.contradictory_signals = _dedupe(a.contradictory_signals, rev.contradictory_signals)
                a.alternative_explanations = _dedupe(a.alternative_explanations, rev.alternative_explanations)
                a.additional_checks_for_csm = _dedupe(a.additional_checks_for_csm, rev.additional_checks_for_csm)
                det = {c[5:] for c in r.index if c.startswith("note_") and c not in ("note_evidence", "note_missing", "note_injection_suspect") and bool(r[c])}
                llm_labels = {n.label for n in rev.note_interpretation}
                if det != llm_labels:
                    stats["note_flag_disagreements"].append({"merchant_id": a.merchant_id, "deterministic": sorted(det), "llm": sorted(llm_labels)})
                    a.llm_notes.append(f"Note-label disagreement: deterministic={sorted(det)} llm={sorted(llm_labels)} (deterministic labels drive the score)")
                if rev.playbook_review == "disagree":
                    stats["playbook_disagreements"].append(a.merchant_id)
                    a.llm_notes.append(f"LLM reviewer disagrees with {a.primary_playbook_id}: {rev.playbook_review_rationale}")
                    a.additional_checks_for_csm = _dedupe(a.additional_checks_for_csm, [f"Reviewer flagged playbook choice: {rev.playbook_review_rationale}"])
                if rev.injection_suspected or r["note_injection_suspect"]:
                    stats["injection_flagged"].append(a.merchant_id)
                    a.llm_notes.append("Instruction-like text suspected in the account-manager note; it was ignored.")
        if a.selected_for_outreach:
            stats["outreach_attempted"] += 1
            facts = allowed_facts(r)
            out = client.call_tool(system=system, user=prompts.outreach_message(r, facts, pb_by_id.loc[a.primary_playbook_id]),
                                   model_cls=LLMOutreach, tool_name="submit_outreach_draft",
                                   description="Submit the outreach draft for CSM review.", max_tokens=settings["llm"]["max_tokens_outreach"],
                                   tag=f"outreach:{a.merchant_id}")
            viol = None if out is None else check_outreach(out.subject, out.body, allowed_numbers(r))
            if out is not None and not viol:
                stats["outreach_accepted"] += 1
                a.outreach_draft = OutreachDraft(subject=out.subject, body=out.body, source="llm", facts_used=out.facts_used)
            else:
                stats["outreach_fallback_to_template"] += 1
                a.llm_notes.append("LLM outreach " + ("failed" if out is None else f"rejected by guardrails: {viol}") + "; template draft kept.")
    return stats
