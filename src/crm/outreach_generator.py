"""Deterministic outreach templates and merchant-fact allow-list. Drafts are never sent."""
from __future__ import annotations

import pandas as pd

from src.agent.schemas import OutreachDraft

PLAYBOOK_NUMBERS = {"3", "48"}  # numbers stated in supplied playbook text (PB-1 "3 days", PB-2 "48 hours")


def allowed_facts(r: pd.Series) -> dict[str, str]:
    """Verified merchant facts a draft may cite (the merchant's own data; no internal scores/notes)."""
    facts: dict[str, str] = {}
    if r["success_drop_pp"] <= -2:
        facts["success_rate_earlier"] = f"{r['success_early_pct']:.1f}%"
        facts["success_rate_recent"] = f"{r['success_recent_pct']:.1f}%"
    if r["unresolved"] >= 1:
        facts["open_tickets"] = str(int(r["unresolved"]))
    facts["renewal_days"] = str(int(r["renewal_days"]))
    return facts


def allowed_numbers(r: pd.Series) -> set[str]:
    nums = set(PLAYBOOK_NUMBERS)
    for v in allowed_facts(r).values():
        nums.add(v.replace("%", "").replace(" days", ""))
    return nums


def sign_off(segment: str) -> str:
    return "[Account Manager name], Razorpay" if segment == "Enterprise" else "[CSM name], Razorpay"


def template_draft(r: pd.Series) -> OutreachDraft | None:
    pb, name, f = r["primary_playbook_id"], r["business_name"], allowed_facts(r)
    sig = sign_off(r["segment"])
    small = r["segment"] == "Small"
    if pb == "PB-1":
        if "success_rate_earlier" in f:
            lead = (f"As part of regular reviews, we noticed your payment success rate moved from {f['success_rate_earlier']} to "
                    f"{f['success_rate_recent']} over the last three months compared with the three months before.")
            used = ["success_rate_earlier", "success_rate_recent"]
        else:
            lead = "As part of regular reviews, we want to make sure your payments are performing as well as they should."
            used = []
        body = (f"Hi {name} team,\n\n{lead} I would like to set up a joint call with our Payments Ops team to review where the "
                f"drop is happening by payment method and bank, and we will share a fix plan within 3 days of that call.\n\n"
                f"Could you share a convenient time?\n\n{sig}")
        return OutreachDraft(subject="Reviewing your payment success rates together", body=body, facts_used=used)
    if pb == "PB-2":
        n = f.get("open_tickets", "your")
        body = (f"Hi {name} team,\n\nI understand you have {n} support ticket(s) still open, and I am sorry for the delay. I am taking "
                f"ownership of all of them and will be your single point of contact. I will confirm a closure date for each ticket, and a "
                f"senior colleague will call you back within 48 hours.\n\nPlease let me know the best number to reach you.\n\n{sig}")
        return OutreachDraft(subject="Taking ownership of your open support tickets", body=body, facts_used=["open_tickets"] if "open_tickets" in f else [])
    if pb == "PB-3":
        body = (f"Hi {name} team,\n\nYour agreement with Razorpay is due for renewal in {f['renewal_days']} days. Ahead of that, "
                f"our Account Manager would like to review your rate card, volume tiers and renewal terms with you so that the renewal fits "
                f"how your business works today.\n\nMay I suggest a time to walk through this together?\n\n{sig}")
        return OutreachDraft(subject="Ahead of your renewal: reviewing your plan together", body=body, facts_used=["renewal_days"])
    if pb == "PB-4":
        extra = "" if small else " Our executive sponsor will also reach out personally."
        body = (f"Hi {name} team,\n\nI would like to invite you to a short workshop on Razorpay products and reports available to your "
                f"account that you may not be using yet.{extra} I would also like to re-confirm the right contact person for your account, "
                f"so that the right people receive your updates.\n\nWho is the best person to include?\n\n{sig}")
        return OutreachDraft(subject="A short workshop on getting more from your Razorpay account", body=body, facts_used=[])
    return None
