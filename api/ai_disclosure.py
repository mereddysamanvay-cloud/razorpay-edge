"""What in an analysis was done by calculation, by template and by runtime AI. Built only from what was actually recorded."""
from __future__ import annotations

from collections import Counter

DEV_NOTE = ("Claude Code was used while developing this application. That is development tooling, not a runtime feature, "
            "and it is not counted in the table above.")


def build(s: dict, ask_log: list[dict], configured: bool, model: str) -> dict:
    st = s.get("llm_stats") or {}
    requested = bool((s.get("config") or {}).get("use_llm"))
    ran = bool(st) and st.get("review_attempted", 0) > 0
    drafts = Counter((m.get("draft") or {}).get("source", "template") for m in s["merchants"] if m.get("draft"))
    asks = Counter(x["method"] for x in ask_log)

    def row(task, method, ai, detail):
        return {"task": task, "method": method, "runtime_ai": ai, "detail": detail}

    rows = [
        row("Scores, risk categories, ranking, shortlist, revenue figures, playbook selection", "Calculated", False,
            "Fixed formulas and rules in code. Runtime AI cannot change any of these."),
        row("Account-manager note signals", "Calculated" + (" and cross-checked by Claude" if ran else ""), ran,
            "Keyword rules set the signals that feed the score." + (f" Claude re-read each note as a cross-check; it disagreed on {len(st.get('note_flag_disagreements', []))} merchant(s) and the calculated labels were kept." if ran else " Claude was not used.")),
        row("Evidence summaries (plain-language reason, alternatives, CSM checks)", "Template text" + (" refined by Claude" if ran else ""), ran,
            (f"Claude reviews accepted for {st.get('review_accepted', 0)} of {st.get('review_attempted', 0)} merchants; {st.get('review_rejected_unsafe', 0)} rejected by guardrails and {st.get('review_failed', 0)} failed, "
             "and those kept the template text.") if ran else "Template text only."),
        row("Outreach drafts", "Template" if not drafts.get("llm") else "Claude, checked by guardrails", bool(drafts.get("llm")),
            f"{drafts.get('llm', 0)} written by Claude, {drafts.get('template', 0)} from templates" + (f"; {st.get('outreach_fallback_to_template', 0)} Claude draft(s) fell back to the template." if ran else ".") +
            " Every draft needs CSM review and is never sent automatically."),
        row("Ask EDGE answers", "Calculated, with Claude for open questions", bool(asks.get("claude")),
            f"{asks.get('computed', 0)} calculated, {asks.get('claude', 0)} answered by Claude, {asks.get('unavailable', 0)} unavailable (no runtime AI or reply withheld)."),
    ]
    notes = []
    if requested and not ran:
        notes.append("Claude assistance was requested for this analysis but did not run; deterministic text was used.")
    if not requested:
        notes.append("Claude assistance was not requested for this analysis; everything above is calculated or templated.")
    if ran and (st.get("review_failed", 0) or st.get("outreach_fallback_to_template", 0)):
        notes.append("Some Claude calls failed or were rejected; the deterministic fallback was used for those merchants.")
    if not configured:
        notes.append("No Anthropic API key is configured on this server, so open-ended Ask EDGE questions are unavailable.")
    return {"development": DEV_NOTE, "rows": rows, "notes": notes, "runtime_ai_configured": configured, "model": model if configured else None,
            "claude_used_in_analysis": ran, "analysis_stats": st or None}
