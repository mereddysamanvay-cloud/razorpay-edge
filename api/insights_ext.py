"""Business Insights built from saved merchant records: counts beside exposure, selection rules kept apart from independent evidence,
counter-evidence, denominators on every rate, and operational leads ranked on stated criteria. Nothing here claims a recoverable amount."""
from __future__ import annotations

DRIVERS = {"performance": "Payment & volume performance", "relationship": "Service experience", "commercial": "Pricing & competition", "engagement": "Disengagement"}
RULE = {
    "performance": "Selected because the performance dimension (TPV trend and payment success rate) is the highest of the four and at least 25.",
    "relationship": "Selected because the service dimension (unresolved tickets, CSAT, service notes) is the highest of the four and at least 25.",
    "commercial": "Selected because the commercial dimension (pricing or competitor signal in the account-manager note, plus renewal proximity) is the highest and at least 25.",
    "engagement": "Selected because the engagement dimension (logins, products used, contact-change or unresponsive notes) is the highest of the four and at least 25.",
}
COMMERCIAL_SIGNALS = {"competitor_explicit", "exploring_options", "rate_card_request", "pricing_objection"}
SEG = ["Small", "Mid", "Enterprise"]


def _pct(n: int, of: int) -> float | None:
    return round(n / of * 100, 1) if of else None


def _item(text: str, n: int, of: int) -> dict:
    return {"text": text, "n": n, "of": of, "pct": _pct(n, of)}


def _sum(ms) -> float:
    return float(sum(m["annual_value"] for m in ms))


def _driver_evidence(key: str, g: list[dict]) -> tuple[list[dict], list[dict], str]:
    n = len(g)
    if key == "performance":
        corr = [_item("TPV down 10% or more AND payment success down 2pp or more (two separate measures agree)", sum(m["tpv_change_pct"] <= -10 and m["success_drop_pp"] <= -2 for m in g), n)]
        counter = [_item("Payment success stable (within 1pp) despite the TPV fall", sum(m["tpv_change_pct"] <= -10 and m["success_drop_pp"] >= -1 for m in g), n),
                   _item("Seasonal industry", sum(m["seasonal_industry"] for m in g), n), _item("Latest month up 5% or more on the month before", sum(m["m6_vs_m5_pct"] >= 5 for m in g), n)]
    elif key == "relationship":
        known = [m for m in g if not m["csat_missing"]]
        corr = [_item("2+ unresolved tickets AND CSAT of 2 or below (among merchants with a CSAT)", sum(m["unresolved"] >= 2 and m["csat"] <= 2 for m in known), len(known)),
                _item("TPV also down 10% or more (independent measure)", sum(m["tpv_change_pct"] <= -10 for m in g), n)]
        counter = [_item("CSAT missing (unknown, not poor)", sum(m["csat_missing"] for m in g), n), _item("TPV growing 10% or more with at most 1 unresolved ticket", sum(m["tpv_change_pct"] >= 10 and m["unresolved"] <= 1 for m in g), n)]
    elif key == "commercial":
        corr = [_item("TPV also down 10% or more (independent of the note)", sum(m["tpv_change_pct"] <= -10 for m in g), n), _item("Renewal within 60 days (timing only, not intent)", sum(m["renewal_days"] <= 60 for m in g), n)]
        counter = [_item("TPV growing 5% or more", sum(m["tpv_change_pct"] >= 5 for m in g), n), _item("No independent field supports the note: it is unverified free text", n, n)]
    else:
        corr = [_item("TPV also down 10% or more (independent measure)", sum(m["tpv_change_pct"] <= -10 for m in g), n)]
        counter = [_item("Small merchant with stable TPV (low usage can be normal)", sum(m["segment"] == "Small" and m["tpv_change_pct"] >= -5 for m in g), n),
                   _item("Usage is a current snapshot; no decline over time can be shown", n, n)]
    best = max((c["pct"] or 0) for c in corr) if corr else 0
    strength = "Limited" if (key == "commercial" or not n) else "Strong" if best >= 60 else "Moderate" if best >= 30 else "Limited"
    return corr, counter, strength


def build(s: dict) -> dict:
    ms = s["merchants"]
    n = len(ms)
    flagged = [m for m in ms if m["risk_band"] != "low"]
    fx = _sum(flagged)
    drv, cmp_rows = [], []
    for key, name in DRIVERS.items():
        g = [m for m in flagged if m["primary_dimension"] == key]
        corr, counter, strength = _driver_evidence(key, g)
        base = next((d for d in s["drivers"] if d["key"] == key), {})
        drv.append({"key": key, "name": name, "merchants": len(g), "exposure_inr": _sum(g), "share_of_flagged_pct": _pct(len(g), len(flagged)), "share_of_exposure_pct": _pct(_sum(g), fx),
                    "selection_rule": RULE[key], "corroboration": corr, "counter_evidence": counter, "evidence_strength": strength, "response": base.get("response", ""),
                    "caveat": "The selection rule is how merchants were grouped. It is not evidence of a systemic problem; only the independent measures above can support that."})
        cmp_rows.append({"driver": name, "key": key, "merchants_pct": _pct(len(g), len(flagged)), "exposure_pct": _pct(_sum(g), fx), "merchants": len(g), "exposure_inr": _sum(g)})
    by_count = max(cmp_rows, key=lambda r: r["merchants"])
    by_exp = max(cmp_rows, key=lambda r: r["exposure_inr"])

    segs = []
    tot_tpv = sum(m["tpv_m6"] for m in ms) or 1
    for sg in SEG:
        g = [m for m in ms if m["segment"] == sg]
        if not g:
            continue
        gf = [m for m in g if m["risk_band"] != "low"]
        segs.append({"segment": sg, "merchants": len(g), "bands": {b: _item(b, sum(m["risk_band"] == b for m in g), len(g)) for b in ("high", "medium", "low")},
                     "tpv_share_pct": _pct(sum(m["tpv_m6"] for m in g), tot_tpv), "exposure_inr": _sum(gf), "exposure_share_pct": _pct(_sum(gf), fx),
                     "flagged_rate": {"n": len(gf), "of": len(g), "pct": _pct(len(gf), len(g))},
                     "drivers": {k: sum(m["primary_dimension"] == k for m in gf) for k in DRIVERS},
                     "missing": {"incomplete": _item("Evidence incomplete", sum(m["completeness"] < 100 for m in g), len(g)), "csat": _item("CSAT missing", sum(m["csat_missing"] for m in g), len(g)),
                                 "note": _item("No account-manager note", sum(not m["note"] for m in g), len(g))}})

    wins = [("Within 30 days", 0, 30), ("31 to 60 days", 31, 60), ("61 to 90 days", 61, 90), ("Beyond 90 days", 91, 10**6)]
    renew = [{"window": w, "merchants": sum(lo <= m["renewal_days"] <= hi for m in ms), "flagged": sum(lo <= m["renewal_days"] <= hi and m["risk_band"] != "low" for m in ms),
              "exposure_inr": _sum([m for m in flagged if lo <= m["renewal_days"] <= hi])} for w, lo, hi in wins]
    csig = [m for m in ms if COMMERCIAL_SIGNALS & set(m["note_signals"])]
    commercial = {"annual_run_rate_inr": _sum(ms), "flagged_exposure_inr": fx, "flagged_merchants": len(flagged), "of": n,
                  "segment_concentration": [{"segment": x["segment"], "exposure_inr": x["exposure_inr"], "share_pct": x["exposure_share_pct"]} for x in segs], "renewal_windows": renew,
                  "commercial_evidence": {"merchants_with_signal": len(csig), "exposure_inr": _sum(csig), "renewing_60": sum(m["renewal_days"] <= 60 for m in csig),
                                          "status": "Unverified: these signals come from account-manager notes only."}}

    def lead(title, group, strength, effort, suggestion, evidence, owner="", implication=""):
        segset = {m["segment"] for m in group}
        return {"title": title, "merchants": len(group), "exposure_inr": _sum(group), "evidence_strength": strength, "urgent_renewals_60": sum(m["renewal_days"] <= 60 for m in group), "effort": effort,
                "scope": "Possibly systemic" if len(group) >= 5 and len(segset) >= 2 else "Merchant-specific or small cluster", "segments": sorted(segset), "evidence": evidence, "suggestion": suggestion,
                "owner": owner, "implication": implication, "merchant_ids": [m["id"] for m in group]}
    ops = []
    perf = [m for m in ms if m["success_drop_pp"] <= -5]
    if len(perf) >= 3:
        both = sum(m["tpv_change_pct"] <= -10 for m in perf)
        ops.append(lead("Repeated payment-performance deterioration", perf, "Strong" if both / len(perf) >= 0.6 else "Moderate", "Medium to high (needs Payments Ops)",
                        "Check whether a shared method, bank or integration issue sits behind the drop before treating each case on its own. A lead to check, not a confirmed cause.",
                        f"{len(perf)} merchants lost 5pp or more of payment success; {both} of them also show TPV down 10% or more.",
                        "Payments Operations", "If one method, bank or integration is involved, one fix could help several merchants; confirm before handling merchants one at a time."))
    back = [m for m in ms if m["unresolved"] >= 3]
    if len(back) >= 2:
        known = [m for m in back if not m["csat_missing"]]
        ops.append(lead("Open-ticket backlog on several accounts", back, "Moderate" if known and sum(m["csat"] <= 2 for m in known) / len(known) >= 0.5 else "Limited", "Low to medium (ticket ownership review)",
                        "Review ticket ageing and ownership to see whether response time or hand-offs are the common factor.",
                        f"{len(back)} merchants have 3 or more unresolved tickets; {sum(m['csat'] <= 2 for m in known)} of {len(known)} with a CSAT report 2 or below.",
                        "Support operations lead", "Check whether ticket ownership or hand-offs are common to these accounts before adding capacity."))
    price = [m for m in ms if COMMERCIAL_SIGNALS & set(m["note_signals"])]
    if len(price) >= 2:
        ops.append(lead("Pricing and competitor conversations", price, "Limited", "Medium (commercial review before renewals)",
                        "Consider a commercial review of volume tiers ahead of these renewals. Confirm each mention with the account manager first.",
                        f"{len(price)} account notes mention pricing, a rate card or a competitor; {sum(m['renewal_days'] <= 60 for m in price)} renew within 60 days. Notes are unverified.",
                        "Account Management with the pricing team", "Renewal conversations may need prepared options; confirm each note with the account manager first."))
    low = [m for m in ms if m["products"] <= 2 and m["logins"] <= 5]
    if len(low) >= 3:
        ops.append(lead("Low adoption of available products", low, "Limited", "Low (education and onboarding content)",
                        "Check whether onboarding or education content reaches these merchants. Low usage can be natural for small, stable merchants.",
                        f"{len(low)} merchants use 2 or fewer products with 5 or fewer logins; {sum(m['segment'] == 'Small' and m['tpv_change_pct'] >= -5 for m in low)} are small with stable TPV. Usage is a snapshot.",
                        "Customer Success enablement", "Low usage may be an onboarding gap or simply normal for the segment; check before acting."))
    seas = [m for m in ms if m["seasonal_adjusted"]]
    if seas:
        ops.append(lead("Seasonal dips handled separately", seas, "Moderate", "Low (re-check next month)", "Re-check these next month. The seasonal industry mapping is an interpretation of the workbook and should be confirmed.",
                        f"{len(seas)} merchants in seasonal industries show a dip followed by a rebound.",
                        "Customer Success manager", "No outreach now; keep these on the monthly watchlist."))
    for o in ops:
        o["informational"] = o["title"].startswith("Seasonal")  # not a risk group: shown last and never ranked by exposure
        if o["informational"]:
            o["exposure_inr"] = None
    ops.sort(key=lambda r: (r["informational"], -(r["exposure_inr"] or 0), -r["merchants"]))
    return {"drivers": drv, "comparison": cmp_rows, "leader_by_count": by_count["driver"], "leader_by_exposure": by_exp["driver"], "same_leader": by_count["key"] == by_exp["key"],
            "flagged_total": len(flagged), "flagged_exposure_inr": fx, "segments": segs, "commercial": commercial, "operational": ops,
            "operational_order": "Ordered by exposure of the affected merchants, then by how many are affected. Evidence strength, urgency, effort and scope are shown for judgement. No amount recoverable is claimed.",
            "denominator_note": "Rates use the stated denominator. Segment sizes differ, so compare shares rather than counts."}
