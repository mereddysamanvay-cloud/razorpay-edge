"""CSV / Excel exports built from a stored session plus its mutable state (statuses, edited drafts)."""
from __future__ import annotations

import io

import pandas as pd

from api.insights import DRIVER_NAMES

STATUS_LABEL = {"not_contacted": "Not contacted", "draft_prepared": "Draft prepared", "approved": "Approved", "contacted": "Contacted",
                "awaiting_response": "Awaiting response", "follow_up": "Follow-up required", "resolved": "Resolved", "escalated": "Escalated"}


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
            "Priority rank": m["rank"], "Shortlisted": "Yes" if m["selected"] else "", "Review status": STATUS_LABEL.get(st["statuses"].get(m["id"], "not_contacted")),
        })
    return pd.DataFrame(rows)


def _outreach(s: dict, st: dict) -> pd.DataFrame:
    rows = []
    for m in sorted([m for m in s["merchants"] if m["selected"]], key=lambda x: x["rank"] or 999):
        draft = st["drafts"].get(m["id"]) or (m["draft"] or {})
        rows.append({
            "Priority rank": m["rank"], "Merchant ID": m["id"], "Merchant": m["name"], "Segment": m["segment"], "Risk category": m["risk_label"],
            "Why prioritised": m["why_priority"], "Playbook": f"{m['assessment']['primary_playbook_id']} {m['assessment']['primary_playbook_name']}",
            "Status": STATUS_LABEL.get(st["statuses"].get(m["id"], "not_contacted")), "Approved": "Yes" if m["id"] in st["approved"] else "No",
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


KINDS = {"risk_register": "Merchant risk register", "outreach": "Ranked outreach list", "analysis": "Merchant-level analysis",
         "insights": "Business insights report", "scenarios": "Decision scenario comparison"}


def frames(kind: str, s: dict, st: dict) -> dict[str, pd.DataFrame]:
    return {"risk_register": lambda: {"Risk register": _register(s, st)}, "outreach": lambda: {"Outreach list": _outreach(s, st)},
            "analysis": lambda: {"Merchant analysis": _analysis(s)}, "insights": lambda: _insights(s),
            "scenarios": lambda: {"Scenarios": _scenarios(st)}}[kind]()


def to_csv(kind: str, s: dict, st: dict) -> bytes:
    fr = frames(kind, s, st)
    first = next(iter(fr.values()))
    return ("﻿" + first.to_csv(index=False)).encode("utf-8")


def to_xlsx(kind: str | None, s: dict, st: dict) -> bytes:
    kinds = [kind] if kind else list(KINDS)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as xw:
        info = pd.DataFrame([{"Item": "Product", "Value": "Razorpay EDGE - Merchant Relationship Intelligence"}, {"Item": "Analysis", "Value": s["name"]},
                             {"Item": "Source workbook", "Value": s["source_file"]}, {"Item": "Analysis timestamp", "Value": s["created_at"]},
                             {"Item": "Version", "Value": s["version"]},
                             {"Item": "Note", "Value": "Risk scores are transparent heuristics, not churn probabilities. Drafts are for CSM review and are never sent automatically."}])
        info.to_excel(xw, sheet_name="About", index=False)
        for k in kinds:
            for name, df in frames(k, s, st).items():
                df.to_excel(xw, sheet_name=name[:31], index=False)
                ws = xw.sheets[name[:31]]
                for i, c in enumerate(df.columns):
                    ws.set_column(i, i, min(max(12, len(str(c)) + 2), 48))
    return buf.getvalue()
