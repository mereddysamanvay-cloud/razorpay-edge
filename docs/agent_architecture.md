# Agent architecture

```
Excel workbook (read-only)
   -> ingestion/workbook_loader + data_validator        (typed data, audit, no imputation)
   -> analytics/feature_engineering (+ crm/note_classifier, peer_benchmarking)
   -> analytics/risk_scoring            deterministic, every point traceable
   -> crm/playbook_selector             maps to the 6 supplied playbooks
   -> analytics/prioritisation          risk rank vs outreach rank, 15 cap
   -> analytics/sensitivity             12 alternative configurations
   -> agent/orchestrator:
        1. build_assessment()           deterministic record + template draft  (no API key needed)
        2. enrich_with_llm()  [optional, Claude]
              Analyst/Risk-Reviewer call  (all 100): note interpretation, plain-language reason,
                                          mitigating/contradictory/alternatives, CSM checks, playbook review
              Retention-Strategist call   (<=15 selected): outreach draft
        3. guardrails (agent/safety.py) + Pydantic validation (agent/schemas.py) -> fallback to templates
   -> reporting/*                        outputs/ + docs/
```

## Why one orchestrated workflow, not many autonomous agents
The five logical roles from the brief (Data Analyst, CRM Analyst, Risk Reviewer, Retention Strategist, Orchestrator) are separate *functions/stages*. Numbers and decisions are deterministic (reproducible, auditable). The LLM is a bounded interpreter/writer. A multi-agent framework would add cost and non-determinism with no measurable benefit.

## What the LLM may and may not do
| May | May not |
|---|---|
| Label the account-manager note (with exact supporting text) | Change score, band, rank, playbook or the 15 selected |
| Write a hedged plain-language reason | State a churn probability or certainty |
| Add mitigating/contradictory signals, alternatives, CSM checks | Invent facts, dates, amounts, commitments |
| Flag disagreement with the chosen playbook (human review) | Promise refunds, waivers, pricing, fixes |
| Draft outreach from allowed facts + approved playbook text | Reveal scores, internal notes, competitor intel |

## Prompt files and knowledge base
- `prompts/system_base.md` (hard rules), `prompts/analyst_review.md`, `prompts/outreach_draft.md`.
- `knowledge/` is concatenated into one cached system block: business context, signal taxonomy, **playbooks.md and assumptions.md (auto-generated verbatim from the workbook on every run)**, segment guidance, communication policy.
- Merchant data and the note are passed in delimited tags; notes are `<untrusted_account_manager_note>` data, and a closing-tag escape is stripped.
- Data minimisation: one merchant per call, pseudonymous ID, no other rows.

## Guardrails (`src/agent/safety.py`, `schemas.py`)
- Structured output via forced tool-use; every response validated by Pydantic (retry with error feedback, then fallback).
- Outreach: forbidden phrases (churn, risk, score, competitor, MDR, refund, waive, discount, guarantee, ...), **every number must be in the merchant's allowed facts or a playbook-stated number**, 35-140 words, reviewer sign-off placeholder, always `DRAFT - pending CSM review`.
- Analysis text: rejects probability/certainty claims.
- `churn_probability` is structurally `None`; `human_review_required` cannot be `False`.
- Nothing is ever sent; there is no email/WhatsApp integration.
- Injection: instruction-like note text is flagged, ignored, lowers confidence, and is surfaced to the CSM.

## Secrets and cost control
`ANTHROPIC_API_KEY` is read from `.env` / environment only (git-ignored), never logged (`LLMClient.status()` prints found/not-set). Paid calls require `--llm --confirm-paid-calls`; capped by `LLM_MAX_CALLS` (default 130 = 100 reviews + 15 drafts + retries); the large system prompt uses prompt caching; audit log `outputs/llm_audit_log.jsonl` stores outcomes only, not prompts.
