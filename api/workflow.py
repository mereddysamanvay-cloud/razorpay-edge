"""Outreach workflow: review, approval, contact and outcome are separate, recorded events. EDGE never sends anything.

Lifecycle: draft generated (pending CSM review) -> reviewed / edits made -> approved -> contacted (recorded manually) -> follow-up -> outcome recorded -> closed.
Outcomes are CSM observations. They are not churn labels unless the actual churn definition has been verified.
"""
from __future__ import annotations

import datetime as dt
import hashlib

from src.agent.safety import check_outreach

PENDING, REVIEWED, APPROVED, CONTACTED, FOLLOW_UP, OUTCOME, CLOSED = "pending_review", "reviewed", "approved", "contacted", "follow_up", "outcome_recorded", "closed"
OUTCOMES = {"issue_confirmed": "Issue confirmed", "commercial_review_scheduled": "Commercial review scheduled", "support_acknowledged": "Support issue acknowledged",
            "no_churn_concern": "No churn concern", "unreachable": "Unreachable", "wrong_contact": "Wrong contact", "follow_up_required": "Follow-up required",
            "declined": "Declined", "other": "Other (free text)"}
FACT_SOURCE = {"success_rate_earlier": "success_rate_m1_m3_pct", "success_rate_recent": "success_rate_m4_m6_pct", "open_tickets": "unresolved_tickets", "renewal_days": "days_to_contract_renewal"}


class WorkflowError(ValueError):
    def __init__(self, msg: str, code: int = 400):
        super().__init__(msg)
        self.code = code


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def text_hash(subject: str, body: str) -> str:
    return hashlib.sha1(f"{subject}\n{body}".encode("utf-8")).hexdigest()[:12]


def allowed_numbers(m: dict) -> set[str]:
    """Numbers a draft may quote: the playbook's own (3 days, 48 hours) and this merchant's verified figures."""
    nums = {"3", "48", str(int(m["renewal_days"]))}
    if m["success_drop_pp"] is not None and m["success_drop_pp"] <= -2:
        nums |= {f"{m['success_early']:.1f}", f"{m['success_recent']:.1f}"}
    if m["unresolved"] and m["unresolved"] >= 1:
        nums.add(str(int(m["unresolved"])))
    return nums


def check_draft(m: dict, subject: str, body: str) -> dict:
    """Guardrail result for the CURRENT text. 'violations' block approval; 'warnings' do not."""
    raw = check_outreach(subject, body, allowed_numbers(m), min_words=20, max_words=180)
    violations = [v for v in raw if not v.startswith("missing reviewer-fillable")]
    warnings = []
    if any(v.startswith("missing reviewer-fillable") for v in raw):
        warnings.append("The sign-off placeholder has been replaced. Check the name and wording before you send it yourself.")
    if "[CSM name]" in body or "[Account Manager name]" in body:
        warnings.append("The sign-off still contains a placeholder. Replace it with your name before sending.")
    return {"violations": violations, "warnings": warnings}


def review_pack(m: dict, playbooks: list[dict], subject: str, body: str, draft: dict | None) -> dict:
    """Everything a reviewer should see before approving."""
    pb = next((p for p in playbooks if p["playbook_id"] == m["assessment"]["primary_playbook_id"]), None)
    values = {"success_rate_earlier": f"{m['success_early']:.1f}%", "success_rate_recent": f"{m['success_recent']:.1f}%", "open_tickets": str(int(m["unresolved"] or 0)),
              "renewal_days": f"{int(m['renewal_days'])} days"}
    used = [{"fact": f, "value": values.get(f, ""), "source_field": FACT_SOURCE.get(f, f)} for f in ((draft or {}).get("facts_used") or [])]
    verify = []
    if m["note"]:
        verify.append(f"The account-manager note is unverified: \"{m['note'][:200]}\". The draft does not quote it.")
    verify += [f"{x} is missing and treated as unknown." for x in m["missing_fields"]]
    verify += [f"Critical review trigger: {t}" for t in m["critical_triggers"]]
    chk = check_draft(m, subject, body)
    return {"facts_used": used, "note_excerpt": m["note"], "facts_requiring_verification": verify, "unsupported_claims": chk["violations"], "warnings": chk["warnings"],
            "playbook_commitments": pb["what_happens"] if pb else None, "playbook": f"{m['assessment']['primary_playbook_id']} {m['assessment']['primary_playbook_name']}",
            "allowed_numbers": sorted(allowed_numbers(m))}


def current_status(state: dict, m: dict) -> str:
    s = (state.get("statuses") or {}).get(m["id"])
    if s == "draft_prepared":
        return PENDING
    if s:
        return s
    return PENDING if (m["selected"] and (m.get("draft") or (state.get("drafts") or {}).get(m["id"]))) else "not_contacted"


def _event(state: dict, mid: str, kind: str, **detail) -> None:
    state.setdefault("events", {}).setdefault(mid, []).append({"type": kind, "at": _now(), **{k: v for k, v in detail.items() if v not in (None, "")}})


def apply(state: dict, m: dict, action: str, p: dict) -> dict:
    """Validate and record one workflow action. Raises WorkflowError. Mutates and returns state."""
    mid = m["id"]
    st = current_status(state, m)
    state.setdefault("statuses", {})
    state.setdefault("approved", [])
    draft = (state.get("drafts") or {}).get(mid) or m.get("draft")
    reviewer = (p.get("reviewer") or "").strip()

    if action == "save_draft":
        if not draft and not p.get("body"):
            raise WorkflowError("There is no draft for this merchant.")
        state.setdefault("drafts", {})[mid] = {"subject": p["subject"], "body": p["body"], "edited": True, "facts_used": (draft or {}).get("facts_used", []), "source": (draft or {}).get("source", "template")}
        if mid in state["approved"]:
            state["approved"].remove(mid)
            _event(state, mid, "approval_withdrawn", detail="Draft edited after approval; approval must be given again.")
        if st in (CONTACTED, FOLLOW_UP, OUTCOME, CLOSED):
            _event(state, mid, "draft_edited", detail="Edited after contact was recorded.")
        else:
            state["statuses"][mid] = REVIEWED
            _event(state, mid, "edited", reviewer=reviewer)
    elif action == "review":
        if not draft:
            raise WorkflowError("There is no draft to review.")
        if st not in (PENDING, REVIEWED, "not_contacted"):
            raise WorkflowError(f"This merchant is already '{st}'.", 409)
        state["statuses"][mid] = REVIEWED
        _event(state, mid, "reviewed", reviewer=reviewer, note=p.get("note"))
    elif action == "approve":
        if st != REVIEWED:
            raise WorkflowError("A CSM must review the draft before it can be approved. Mark it as reviewed first.", 409)
        if not p.get("acknowledged"):
            raise WorkflowError("Confirm that you have checked the facts and the wording before approving.")
        if not reviewer:
            raise WorkflowError("Enter the reviewer's name to approve.")
        subject, body = (draft or {}).get("subject", ""), (draft or {}).get("body", "")
        chk = check_draft(m, subject, body)
        if chk["violations"]:
            raise WorkflowError("The draft cannot be approved: " + "; ".join(chk["violations"]))
        state["statuses"][mid] = APPROVED
        if mid not in state["approved"]:
            state["approved"].append(mid)
        _event(state, mid, "approved", reviewer=reviewer, text_hash=text_hash(subject, body), detail="Approval is not sending. EDGE never sends messages.")
    elif action == "withdraw":
        if st != APPROVED:
            raise WorkflowError("Only an approved draft can be withdrawn.", 409)
        state["statuses"][mid] = REVIEWED
        if mid in state["approved"]:
            state["approved"].remove(mid)
        _event(state, mid, "approval_withdrawn", reviewer=reviewer)
    elif action == "contact":
        if st != APPROVED:
            raise WorkflowError("Contact can only be recorded for an approved draft.", 409)
        if not p.get("date"):
            raise WorkflowError("Enter the date you contacted the merchant.")
        state["statuses"][mid] = CONTACTED
        _event(state, mid, "contacted", date=p["date"], channel=p.get("channel"), reviewer=reviewer, detail="Recorded manually. EDGE did not send anything.")
    elif action == "follow_up":
        if st not in (CONTACTED, FOLLOW_UP):
            raise WorkflowError("A follow-up date can be set once contact has been recorded.", 409)
        if not p.get("date"):
            raise WorkflowError("Enter a follow-up date.")
        state["statuses"][mid] = FOLLOW_UP
        state.setdefault("notes", {}).setdefault(mid, {})["follow_up"] = p["date"]
        _event(state, mid, "follow_up_set", date=p["date"], note=p.get("note"))
    elif action == "outcome":
        if st not in (CONTACTED, FOLLOW_UP, OUTCOME):
            raise WorkflowError("An outcome can be recorded once contact has been recorded.", 409)
        out = p.get("outcome")
        if out not in OUTCOMES:
            raise WorkflowError("Choose one of the listed outcomes.")
        if out == "other" and not (p.get("text") or "").strip():
            raise WorkflowError("Describe the outcome in the free-text box.")
        state["statuses"][mid] = OUTCOME
        state.setdefault("outcomes", {}).setdefault(mid, []).append({"outcome": out, "label": OUTCOMES[out], "text": p.get("text") or "", "at": _now(), "reviewer": reviewer,
                                                                    "note": "A CSM observation. Not a churn label."})
        _event(state, mid, "outcome_recorded", outcome=OUTCOMES[out], detail=p.get("text"), reviewer=reviewer)
    elif action == "close":
        if st not in (OUTCOME, FOLLOW_UP, CONTACTED):
            raise WorkflowError("Record contact or an outcome before closing.", 409)
        state["statuses"][mid] = CLOSED
        _event(state, mid, "closed", detail=p.get("reason") or "Closed / monitor", reviewer=reviewer)
    else:
        raise WorkflowError(f"Unknown action '{action}'.")
    return state
