"""Deterministic guardrails applied to every LLM output and every outreach draft."""
from __future__ import annotations

import re

FORBIDDEN_OUTREACH = [
    r"\bchurn", r"\brisk\b", r"at[- ]risk", r"risk score", r"\bscore\b", r"\brank(ing|ed)?\b", r"competitor", r"\bMDR\b",
    r"lower (rate|price|fee)", r"waive", r"waiver", r"refund", r"discount", r"cashback", r"free of charge", r"guarantee",
    r"\bpromise", r"we (have )?diagnosed", r"root cause is", r"probabilit", r"account manager('s)? note", r"internal",
    r"leaving us", r"switch(ing)? (to )?(another|a competitor)", r"sk-ant-",
]
FORBIDDEN_ANALYSIS = [
    r"\d+\s*%\s*(chance|probability|likelihood|likely to churn)", r"will (definitely|certainly) churn", r"churn probability",
    r"sk-ant-", r"guaranteed to (leave|churn)",
]
_NUM = re.compile(r"(?<![A-Za-z\[])\d+(?:\.\d+)?")


def check_outreach(subject: str, body: str, allowed_numbers: set[str], min_words: int = 35, max_words: int = 140) -> list[str]:
    text = f"{subject}\n{body}"
    v: list[str] = []
    for pat in FORBIDDEN_OUTREACH:
        if re.search(pat, text, re.I):
            v.append(f"forbidden phrase /{pat}/")
    for n in _NUM.findall(text):
        if n not in allowed_numbers:
            v.append(f"unsupported number '{n}'")
    words = len(body.split())
    if not (min_words <= words <= max_words):
        v.append(f"length {words} words outside {min_words}-{max_words}")
    if "[CSM name]" not in body and "[Account Manager name]" not in body:
        v.append("missing reviewer-fillable sign-off placeholder")
    return v


def check_analysis_text(*texts: str) -> list[str]:
    v: list[str] = []
    for t in texts:
        for pat in FORBIDDEN_ANALYSIS:
            if re.search(pat, t or "", re.I):
                v.append(f"forbidden analysis phrase /{pat}/")
    return v
