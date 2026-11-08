"""CSV / Excel exports built from a stored session plus its mutable state (statuses, edited drafts)."""
from __future__ import annotations

import io

import pandas as pd

from api import workflow
from api.insights import DRIVER_NAMES

STATUS_LABEL = {"not_contacted": "No draft", "pending_review": "Pending CSM review", "reviewed": "Reviewed / edits made", "approved": "Approved (not sent)",
                "contacted": "Contacted (recorded manually)", "follow_up": "Follow-up set", "outcome_recorded": "Outcome recorded", "closed": "Closed / monitor",
                "draft_prepared": "Pending CSM review", "awaiting_response": "Awaiting response", "resolved": "Resolved", "escalated": "Escalated"}


def _last(st: dict, mid: str, kind: str) -> dict:
    return next((e for e in reversed((st.get("events") or {}).get(mid, [])) if e["type"] == kind), {})


def _status(s: dict, st: dict, m: dict) -> str:
    return STATUS_LABEL.get(workflow.current_status(st, m), "No draft")


def _register(s: dict, st: dict) -> pd.DataFrame:
    rows = []
    for m in s["merchants"]:
        rows.append({
            "Merchant ID": m["id"], "Merchant": m["name"], "Segment": m["segment"], "Industry": m["industry"],
            "M6 TPV (Rs lakh)": m["tpv_m6"], "TPV change, M4-M6 vs M1-M3 (%)": m["tpv_change_pct"],
            "Success rate recent (%)": m["success_recent"], "Success rate change (pp)": m["success_drop_pp"], "CSAT": m["csat"],
            "Unresolved tickets": m["unresolved"], "Logins (30d)": m["logins"], "Products used": m["products"], "Days to renewal": m["renewal_days"],
            "Risk score (0-100, heuristic)": m["risk_score"], "Risk category": m["risk_label"], "Confidence": m["confidence"],
            "Primary risk driver": m["assessment"]["primary_risk_driver"], "Annual run-rate revenue (Rs)": m["annual_value"],
            "Immediate review": "Yes" if m["immediate"] else "", "Recommended playbook": f"{m['assessment']['primary_playbook_id']} {m['assessment']['primary_playbook_name']}",
            "Priority rank": m["rank"], "Shortlisted": "Yes" if m["selected"] else "", "Review status": _status(s, st, m),
            "Evidence completeness (%)": m["completeness"], "Priority index (Rs)": m["priority_value"],
        })
    return pd.DataFrame(rows)


def _outreach(s: dict, st: dict) -> pd.DataFrame:
    rows = []
    for m in sorted([m for m in s["merchants"] if m["selected"]], key=lambda x: x["rank"] or 999):
        draft = st["drafts"].get(m["id"]) or (m["draft"] or {})
        rows.append({
            "Priority rank": m["rank"], "Merchant ID": m["id"], "Merchant": m["name"], "Segment": m["segment"], "Risk category": m["risk_label"],
            "Why prioritised": m["why_priority"], "Playbook": f"{m['assessment']['primary_playbook_id']} {m['assessment']['primary_playbook_name']}",
            "Status": _status(s, st, m), "Approved": "Yes" if m["id"] in st["approved"] else "No",
            "Approved by": _last(st, m["id"], "approved").get("reviewer", ""), "Approved at": _last(st, m["id"], "approved").get("at", ""),
            "Contacted on (recorded manually)": _last(st, m["id"], "contacted").get("date", ""), "Contact channel": _last(st, m["id"], "contacted").get("channel", ""),
            "Latest outcome (CSM observation, not a churn label)": (st.get("outcomes", {}).get(m["id"]) or [{}])[-1].get("label", ""),
            "Draft subject": draft.get("subject"), "Draft body (DRAFT, pending CSM review)": draft.get("body"),
            "Checks before contact": " | ".join(m["assessment"]["additional_checks_for_csm"]),
        })
    return pd.DataFrame(rows)


def _analysis(s: dict) -> pd.DataFrame:
    rows = []
    for m in s["merchants"]:
        a = m["assessment"]
        rows.append({
            "Merchant ID": m["id"], "Merchant": m["name"], "Risk score": m["risk_score"], "Risk category": m["risk_label"],
            "Performance dimension": m["dims"]["performance"], "Service dimension": m["dims"]["relationship"],
            "Engagement dimension": m["dims"]["engagement"], "Commercial dimension": m["dims"]["commercial"],
            "Plain-language reason": a["plain_language_reason"],
            "Supporting evidence": " | ".join(f"{e['source_field']}: {e['observed_value']}" for e in a["supporting_evidence"]),
            "Mitigating signals": " | ".join(a["mitigating_signals"]), "Contradictory signals": " | ".join(a["contradictory_signals"]),
            "Alternative explanations": " | ".join(a["alternative_explanations"]), "Critical review triggers": " | ".join(m["critical_triggers"]),
            "Data completeness": m["completeness"], "Missing fields": ", ".join(m["missing_fields"]),
        })
    return pd.DataFrame(rows)


def _workflow_log(s: dict, st: dict) -> pd.DataFrame:
    names = {m["id"]: m["name"] for m in s["merchants"]}
    rows = []
    for mid, evs in (st.get("events") or {}).items():
        for e in evs:
            rows.append({"Merchant ID": mid, "Merchant": names.get(mid, ""), "Event": e["type"].replace("_", " "), "At": e["at"], "Reviewer": e.get("reviewer", ""),
                         "Date": e.get("date", ""), "Detail": " ".join(str(e.get(k, "")) for k in ("detail", "note", "channel", "outcome")).strip()})
    return pd.DataFrame(sorted(rows, key=lambda r: r["At"]), columns=["Merchant ID", "Merchant", "Event", "At", "Reviewer", "Date", "Detail"])


def _insights(s: dict) -> dict[str, pd.DataFrame]:
    d = pd.DataFrame([{"Driver": x["name"], "Merchants": x["merchants"], "Share of portfolio (%)": x["share_of_portfolio_pct"],
                       "Annual run-rate revenue (Rs)": x["annual_value_inr"], "Common signals": "; ".join(x["signals"]), "Recommended response": x["response"]}
                      for x in s["drivers"]])
    seg = pd.DataFrame(s["segments"])
    c = s["commercial"]
    com = pd.DataFrame([{"Measure": k, "Value": v} for k, v in c.items() if k != "methodology"] + [{"Measure": "methodology", "Value": " / ".join(c["methodology"])}])
    ops = pd.DataFrame(s["operational"])
    return {"Drivers": d, "Segments": seg, "Commercial": com, "Operational": ops}


def _scenarios(st: dict) -> pd.DataFrame:
    rows = []
    for sc in st.get("scenarios", []):
        rows.append({"Scenario": sc["name"], "Capacity": sc["spec"]["capacity"], "Priorities": ", ".join(sc["spec"].get("priorities", [])),
                     "Risk focus": sc["spec"].get("risk_focus"), "Moved in": ", ".join(x["business_name"] for x in sc["result"]["moved_in"]),
                     "Moved out": ", ".join(x["business_name"] for x in sc["result"]["moved_out"]), "Run-rate value shortlisted (Rs)": sc["result"]["value_after_inr"],
                     "Summary": sc["result"]["summary"]})
    return pd.DataFrame(rows)


def _weight_scenarios(x: dict) -> pd.DataFrame:
    rows = []
    for sc in x["scenarios"]:
        w = sc["weights"]
        rows.append({"Scenario": sc["scenario"], "Performance %": w["performance"], "Relationship %": w["relationship"], "Engagement %": w["engagement"], "Commercial %": w["commercial"],
                     "High": sc["high"], "Moderate": sc["medium"], "Low": sc["low"], "Top list": ", ".join(sc["top_n"]), "Overlap with baseline": sc["overlap_with_baseline"],
                     "Moved in": ", ".join(sc["moved_in"]), "Moved out": ", ".join(sc["moved_out"]), "Annual run-rate represented (Rs)": sc["run_rate_inr"],
                     "Driver mix": ", ".join(f"{k} {v}" for k, v in sc["drivers"].items()), "Segment mix": ", ".join(f"{k} {v}" for k, v in sc["segments"].items()),
                     "Seasonal merchants selected": sc["seasonal_selected"], "Incomplete-evidence merchants selected": sc["incomplete_selected"]})
    return pd.DataFrame(rows)


def _stability(x: dict) -> pd.DataFrame:
    return pd.DataFrame([{"Merchant ID": r["merchant_id"], "Merchant": r["name"], "Segment": r["segment"], "Baseline shortlisted": "Yes" if r["baseline_selected"] else "",
                          "Baseline rank": r["baseline_rank"], "Configurations tested": r["configurations"], "Times in shortlist": r["times_selected"],
                          "Selection frequency": r["selection_frequency"], "Average rank": r["avg_rank"], "Best rank": r["best_rank"], "Worst rank": r["worst_rank"],
                          "Times eligible": r["times_eligible"], "Score min": r["score_min"], "Score max": r["score_max"], "Bands seen": ", ".join(r["bands_seen"]),
                          "Classification": r["classification"], "Moved materially by": "; ".join(r["moved_by"])} for r in x["merchants"]])


def _overlap(x: dict) -> pd.DataFrame:
    m = pd.DataFrame(x["overlap_matrix"])
    m.insert(0, "Scenario", m.index)
    return m


def _validation(v: dict) -> pd.DataFrame:
    rows = []
    for c in v["cases"]:
        if not c.get("merchant_id"):
            rows.append({"Case": c["case_id"], "Category": c["category"], "Pattern": c["pattern"], "Status": c["status"], "Note": c.get("note")})
            continue
        e = c["evidence"]
        rows.append({"Case": c["case_id"], "Category": c["category"], "Pattern": c["pattern"], "Merchant ID": c["merchant_id"], "Merchant": c["merchant"], "Segment": c["segment"],
                     "Industry": c["industry"], "Expected interpretation (test expectation, not ground truth)": c["expectation"], "Score": c["score"], "Band": c["band"],
                     "Primary driver": c["driver"], "Supporting evidence": " | ".join(e["supporting"]), "Mitigating evidence": " | ".join(e["mitigating"]),
                     "Contradictory evidence": " | ".join(e["contradictory"]), "Playbook": c["playbook"], "In shortlist": "Yes" if c["shortlisted"] else "No",
                     "Weight sensitivity": (f"{c['weight_sensitivity']['classification']} ({c['weight_sensitivity']['selection_frequency']:.0%} of configurations)" if c["weight_sensitivity"] else "Not run"),
                     "Data completeness (%)": c["completeness"], "Human reviewer judgement": c["reviewer"].get("judgement", "Pending"), "Reviewer note": c["reviewer"].get("note", ""),
                     "Status": c["status"], "Failure stage": c["failure_stage"], "Failure category": c["failure_category"], "Corrective action": c["corrective_action"]})
    return pd.DataFrame(rows)


KINDS = {"risk_register": "Merchant risk register", "outreach": "Ranked outreach list", "analysis": "Merchant-level analysis",
         "insights": "Business insights report", "scenarios": "Decision scenario comparison", "workflow": "Review, approval, contact and outcome log"}


EXTRA_KINDS = {"weight_scenarios": "Weight scenario comparison", "stability": "Merchant rank stability", "overlap": "Top-list overlap matrix", "validation": "Validation Lab log"}


def frames(kind: str, s: dict, st: dict, extra: dict | None = None) -> dict[str, pd.DataFrame]:
    extra = extra or {}
    if kind == "validation":
        return {"Validation log": _validation(extra["validation"])}
    if kind in EXTRA_KINDS:
        stab = extra.get("stability")
        if not stab:
            raise KeyError("Run the robustness test first.")
        return {"weight_scenarios": {"Weight scenarios": _weight_scenarios(stab)}, "stability": {"Rank stability": _stability(stab)}, "overlap": {"Overlap matrix": _overlap(stab)}}[kind]
    return {"risk_register": lambda: {"Risk register": _register(s, st)}, "outreach": lambda: {"Outreach list": _outreach(s, st)},
            "analysis": lambda: {"Merchant analysis": _analysis(s)}, "insights": lambda: _insights(s),
            "scenarios": lambda: {"Scenarios": _scenarios(st)}, "workflow": lambda: {"Workflow log": _workflow_log(s, st)}}[kind]()


def to_csv(kind: str, s: dict, st: dict, extra: dict | None = None) -> bytes:
    fr = frames(kind, s, st, extra)
    first = next(iter(fr.values()))
    return ("﻿" + first.to_csv(index=False)).encode("utf-8")


def to_xlsx(kind: str | None, s: dict, st: dict, extra: dict | None = None) -> bytes:
    extra = extra or {}
    kinds = [kind] if kind else list(KINDS) + [k for k in EXTRA_KINDS if k == "validation" or extra.get("stability")]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as xw:
        info = pd.DataFrame([{"Item": "Product", "Value": "Razorpay EDGE - Merchant Relationship Intelligence"}, {"Item": "Analysis", "Value": s["name"]},
                             {"Item": "Source workbook", "Value": s["source_file"]}, {"Item": "Analysis timestamp", "Value": s["created_at"]},
                             {"Item": "Version", "Value": s["version"]},
                             {"Item": "Note", "Value": "Risk scores are transparent heuristics, not churn probabilities. Drafts are for CSM review and are never sent automatically."}])
        info.to_excel(xw, sheet_name="About", index=False)
        for k in kinds:
            for name, df in frames(k, s, st, extra).items():
                df.to_excel(xw, sheet_name=name[:31], index=False)
                ws = xw.sheets[name[:31]]
                for i, c in enumerate(df.columns):
                    ws.set_column(i, i, min(max(12, len(str(c)) + 2), 48))
    return buf.getvalue()
