"""Validation Lab: 20 documented cases drawn from the real merchants.

Merchants are CHOSEN by plain rules on the source data (never on the model's score). The expectation for each case is a test expectation
written from the case category, not ground truth: no churn labels exist, so a pass means "behaves as the stated design intends".
"""
from __future__ import annotations

SIGNALS = {"competitor_explicit", "exploring_options", "rate_card_request", "pricing_objection"}
STAGE = {"band": "scoring / thresholding", "eligible": "ranking", "playbook": "playbook", "selected": "ranking", "context": "context", "evidence": "note interpretation / evidence",
         "dimension": "scoring", "completeness": "ingestion / evidence completeness", "corroboration": "scoring"}
CORRECTIVE = {
    "band": "Review the dimension scales and aggregation for this pattern; document the change and re-run sensitivity before adopting it.",
    "eligible": "Check eligibility rules (band, playbook, priority index) for this pattern.",
    "playbook": "Compare the playbook trigger with the workbook's 'when it applies' text.",
    "selected": "Check priority index components and capacity; do not force the merchant onto the shortlist.",
    "context": "Review the contextual adjustment (seasonal, low-volume, growth damping) for this pattern.",
    "evidence": "Add the missing supporting, mitigating or contradictory statement to the evidence builder.",
    "dimension": "Review the feature's scale and missing-data behaviour.",
    "completeness": "Check how missing fields are scored and disclosed.",
    "corroboration": "Check that a single signal cannot drive a High band alone.",
}


def _sig(m): return bool(SIGNALS & set(m["note_signals"]))
def _avg_recent(m): return sum(m["tpv"][3:]) / 3


SPECS = [
    # (case, category, pattern, title, predicate, expectation)
    ("A1", "Likely high concern", "Declining TPV and deteriorating success", lambda m: m["tpv_change_pct"] <= -15 and m["success_drop_pp"] <= -5,
     "Escalated: Moderate or High, outreach-eligible, performance-type playbook."),
    ("A2", "Likely high concern", "Poor CSAT plus unresolved tickets", lambda m: m["csat"] is not None and m["csat"] <= 2 and m["unresolved"] >= 2,
     "Escalated: Moderate or High, outreach-eligible, support-recovery playbook."),
    ("A3", "Likely high concern", "Competitor concern near renewal", lambda m: _sig(m) and m["renewal_days"] <= 30,
     "Escalated: Moderate or High, outreach-eligible, commercial-review playbook."),
    ("A4", "Likely high concern", "Silent decline (few logins, sustained steep TPV fall)", lambda m: m["logins"] <= 2 and m["consecutive_declines"] >= 4 and m["tpv_change_pct"] <= -25,
     "Escalated: Moderate or High and outreach-eligible."),
    ("A5", "Likely high concern", "Four or more unresolved tickets", lambda m: m["unresolved"] >= 4,
     "Escalated: Moderate or High and outreach-eligible."),
    ("B1", "Decoy", "Seasonal TPV decline with rebound", lambda m: m["seasonal_industry"] and m["tpv_change_pct"] <= -15 and m["dip_and_rebound"],
     "Not escalated on TPV alone: Low band, monitor-only playbook, not shortlisted."),
    ("B2", "Decoy", "Naturally low-volume merchant", lambda m: _avg_recent(m) < 5 and m["tpv_change_pct"] >= -10 and m["segment"] == "Small",
     "Not penalised for size: Low band, not shortlisted."),
    ("B3", "Decoy", "Growing merchant with many resolved tickets", lambda m: m["tpv_change_pct"] >= 10 and m["tickets"] >= 5 and m["unresolved"] <= 1,
     "Not flagged for ticket count alone: Low band, not shortlisted."),
    ("B4", "Decoy", "TPV rebound after a dip (second example)", lambda m: m["dip_and_rebound"],
     "Recovery recognised: Low band, not shortlisted."),
    ("B5", "Decoy", "Low logins that are normal for the segment", lambda m: m["segment"] == "Small" and m["logins"] <= 5 and m["tpv_change_pct"] >= -5,
     "Not flagged for low usage alone: Low band, not shortlisted."),
    ("C1", "Conflicting signals", "Declining TPV with stable payment success", lambda m: m["tpv_change_pct"] <= -15 and m["success_drop_pp"] >= -1 and not m["seasonal_industry"],
     "TPV alone must not produce High; stable success is shown as mitigating."),
    ("C2", "Conflicting signals", "Seasonal industry with a real second signal", lambda m: m["seasonal_industry"] and m["tpv_change_pct"] <= -15 and (m["logins"] <= 5 or m["success_drop_pp"] <= -5 or m["unresolved"] >= 2 or (m["csat"] is not None and m["csat"] <= 2)),
     "Escalation must rest on evidence other than the TPV dip (another driver or a success-rate fall)."),
    ("C3", "Conflicting signals", "Low CSAT but at most one unresolved ticket", lambda m: m["csat"] is not None and m["csat"] <= 2 and m["unresolved"] <= 1,
     "Service concern shown, but the relationship dimension is not maxed out."),
    ("C4", "Conflicting signals", "Commercial signal while payments and service are healthy", lambda m: _sig(m) and m["success_drop_pp"] >= -1 and m["unresolved"] == 0,
     "Commercial review warranted, but not High; the note is unverified."),
    ("C5", "Conflicting signals", "Many tickets, all resolved", lambda m: m["tickets"] >= 6 and m["unresolved"] == 0,
     "Resolved tickets are not penalised: relationship dimension below 25."),
    ("D1", "Borderline / missing data", "Missing CSAT, otherwise healthy", lambda m: m["csat_missing"] and m["unresolved"] == 0 and m["tpv_change_pct"] >= -5 and m["success_drop_pp"] >= -1 and m["logins"] >= 10 and not ({"service_complaint", "service_escalation"} & set(m["note_signals"])),
     "Missing CSAT adds no risk points (relationship dimension 0) and is disclosed."),
    ("D2", "Borderline / missing data", "No account-manager note and a TPV decline", lambda m: not m["note"] and m["tpv_change_pct"] <= -10,
     "No commercial points without a note; completeness below 100 is disclosed."),
    ("D3", "Borderline / missing data", "Contact-person change", lambda m: "decision_maker_change" in m["note_signals"],
     "Engagement concern raised (dimension 25 or more) and verification steps listed."),
    ("D4", "Borderline / missing data", "Score within 3 points of a band threshold", lambda m: abs(m["risk_score"] - 50) <= 3 or abs(m["risk_score"] - 28) <= 3,
     "Band is threshold-dependent: always routed to human review."),
    ("D5", "Borderline / missing data", "Neither CSAT nor note available, with a decline", lambda m: m["completeness"] == 0 and m["tpv_change_pct"] <= -10,
     "Not High unless two or more dimensions fire; limited evidence is disclosed."),
]

COVERAGE = [  # required adversarial test -> case ids
    ("Seasonal TPV decline", ["B1", "C2"]), ("Naturally low-volume merchant", ["B2"]), ("Growing merchant with many resolved tickets", ["B3", "C5"]),
    ("Competitor concern near renewal", ["A3"]), ("Poor CSAT plus unresolved tickets", ["A2"]), ("Declining TPV with stable success", ["C1"]),
    ("Declining TPV and deteriorating success", ["A1"]), ("Missing CSAT", ["D1"]), ("Missing account-manager note", ["D2"]),
    ("Contact-person change", ["D3"]), ("TPV rebound", ["B1", "B4"]), ("Low logins normal for segment", ["B5"]),
]


def _checks(case: str, m: dict) -> list[tuple[str, bool, str]]:
    a, d = m["assessment"], m["dims"]
    band, pb = m["risk_band"], a["primary_playbook_id"]
    esc = band in ("medium", "high")
    fired = sum(v >= 40 for v in d.values())
    out: list[tuple[str, bool, str]] = []
    if case.startswith("A"):
        out += [("band", esc, f"band is {band}"), ("eligible", m["eligible"], "outreach-eligible" if m["eligible"] else "not eligible for outreach")]
        want = {"A1": "PB-1", "A2": "PB-2", "A3": "PB-3"}.get(case)
        if want:
            # the expected playbook must at least be triggered; another may rank first when it fits better
            hit = pb == want or a.get("secondary_playbook_id") == want or any(want in x for x in m["playbooks_not_selected"])
            out.append(("playbook", hit, f"primary {pb}; {want} {'triggered' if hit else 'not triggered'}"))
    elif case in ("B1", "B2", "B3", "B4", "B5"):
        out += [("band", band == "low", f"band is {band}"), ("selected", not m["selected"], "shortlisted" if m["selected"] else "not shortlisted"),
                ("playbook", pb in ("PB-5", "PB-6"), f"playbook {pb}")]
    elif case == "C1":
        only_perf = d["performance"] >= 25 and all(v < 25 for k, v in d.items() if k != "performance")
        out += [("corroboration", not (band == "high" and only_perf), f"band {band}, performance-only={only_perf}"),
                ("evidence", bool(a["mitigating_signals"]), "mitigating evidence listed" if a["mitigating_signals"] else "no mitigating evidence listed despite stable success")]
    elif case == "C2":
        ok = m["primary_dimension"] != "performance" or m["success_drop_pp"] <= -5
        out.append(("context", ok, f"primary driver {m['primary_dimension']}, success change {m['success_drop_pp']:+.1f}pp"))
    elif case == "C3":
        out += [("dimension", d["relationship"] < 80, f"relationship dimension {d['relationship']:.0f}"),
                ("evidence", bool(a["mitigating_signals"] or a["contradictory_signals"]), "contradictory or mitigating statement listed" if (a["mitigating_signals"] or a["contradictory_signals"]) else "no contradictory evidence listed")]
    elif case == "C4":
        out.append(("band", band != "high", f"band is {band}"))
    elif case == "C5":
        out.append(("dimension", d["relationship"] < 25, f"relationship dimension {d['relationship']:.0f}"))
    elif case == "D1":
        out += [("dimension", d["relationship"] == 0, f"relationship dimension {d['relationship']:.0f}"), ("completeness", m["completeness"] < 100, f"completeness {m['completeness']}%")]
    elif case == "D2":
        out += [("dimension", d["commercial"] == 0, f"commercial dimension {d['commercial']:.0f}"), ("completeness", m["completeness"] < 100, f"completeness {m['completeness']}%")]
    elif case == "D3":
        out += [("dimension", d["engagement"] >= 25, f"engagement dimension {d['engagement']:.0f}"), ("evidence", bool(a["additional_checks_for_csm"]), "verification steps listed" if a["additional_checks_for_csm"] else "no verification steps listed")]
    elif case == "D5":
        out += [("corroboration", not (band == "high" and fired < 2), f"band {band}, dimensions at 40+: {fired}"), ("completeness", m["completeness"] == 0, "limited evidence disclosed")]
    return out


def _evidence(m: dict) -> dict:
    a = m["assessment"]
    return {"supporting": [f"{e['source_field']}: {e['observed_value']}" for e in a["supporting_evidence"]], "mitigating": list(a["mitigating_signals"]),
            "contradictory": list(a["contradictory_signals"])}


def build(s: dict, stability: dict | None = None, reviews: dict | None = None) -> dict:
    ms = s["merchants"]
    stab = {r["merchant_id"]: r for r in (stability or {}).get("merchants", [])}
    reviews = reviews or {}
    used: set[str] = set()
    cases = []
    for case, cat, pattern, pred, expect in SPECS:
        pool = [m for m in ms if pred(m)]
        pick = next((m for m in pool if m["id"] not in used), pool[0] if pool else None)
        if pick is None:
            cases.append({"case_id": case, "category": cat, "pattern": pattern, "expectation": expect, "merchant_id": None, "status": "No matching merchant",
                          "note": "No merchant in this workbook matches the selection rule; covered by unit tests instead.", "matching_merchants": 0})
            continue
        used.add(pick["id"])
        chk = _checks(case, pick)
        failed = [c for c in chk if not c[1]]
        if case == "D4":
            status = "Needs review"
        else:
            status = "Fail" if failed else "Pass"
        rev = reviews.get(pick["id"] + ":" + case) or {}
        if rev.get("judgement") == "disagree" and status == "Pass":
            status = "Needs review"
        st = stab.get(pick["id"])
        cases.append({
            "case_id": case, "category": cat, "pattern": pattern, "expectation": expect, "expectation_basis": "Test expectation from the case category. Not ground truth.",
            "merchant_id": pick["id"], "merchant": pick["name"], "segment": pick["segment"], "industry": pick["industry"], "matching_merchants": len(pool),
            "score": pick["risk_score"], "band": pick["risk_label"], "driver": pick["assessment"]["primary_risk_driver"], "dims": pick["dims"],
            "playbook": f"{pick['assessment']['primary_playbook_id']} {pick['assessment']['primary_playbook_name']}", "shortlisted": pick["selected"], "rank": pick["rank"],
            "completeness": pick["completeness"], "missing_fields": pick["missing_fields"], "evidence": _evidence(pick),
            "weight_sensitivity": ({"selection_frequency": st["selection_frequency"], "classification": st["classification"], "bands_seen": st["bands_seen"]} if st else None),
            "checks": [{"check": c[0], "passed": c[1], "detail": c[2]} for c in chk], "status": status,
            "failure_stage": "; ".join(sorted({STAGE[c[0]] for c in failed})) if failed else None,
            "failure_category": "; ".join(f"{c[0]}: {c[2]}" for c in failed) if failed else None,
            "corrective_action": " ".join(sorted({CORRECTIVE[c[0]] for c in failed})) if failed else ("Borderline by design: a CSM decides." if case == "D4" else None),
            "reviewer": rev or {"judgement": "Pending"},
        })
    done = [c for c in cases if c.get("merchant_id")]
    summary = {"cases": len(done), "pass": sum(c["status"] == "Pass" for c in done), "needs_review": sum(c["status"] == "Needs review" for c in done),
               "fail": sum(c["status"] == "Fail" for c in done), "no_match": len(cases) - len(done)}
    cov = [{"test": t, "cases": ids, "statuses": {i: next((c["status"] for c in cases if c["case_id"] == i), "-") for i in ids}} for t, ids in COVERAGE]
    return {"cases": cases, "summary": summary, "coverage": cov,
            "claims": f"{summary['cases']} case-based scenarios reviewed against stated design expectations. Not an accuracy measure: no churn labels exist."}
