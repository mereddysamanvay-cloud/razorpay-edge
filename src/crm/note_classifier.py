"""Deterministic account-manager-note classifier. Notes are untrusted data, never instructions."""
from __future__ import annotations

import re
from functools import lru_cache

from src.config import load_note_signals


@lru_cache(maxsize=1)
def _compiled() -> tuple[dict, list]:
    cfg = load_note_signals()
    sig = {k: [re.compile(p, re.I) for p in pats] for k, pats in cfg["signals"].items()}
    inj = [re.compile(p, re.I) for p in cfg["injection_patterns"]]
    return sig, inj


def signal_names() -> list[str]:
    return list(_compiled()[0].keys())


def classify_note(note: str | None) -> dict:
    """Return {flag: bool} plus evidence (matched fragments) and an injection-suspect marker."""
    sig, inj = _compiled()
    flags = {k: False for k in sig}
    evidence: dict[str, str] = {}
    text = note if isinstance(note, str) else ""
    for name, pats in sig.items():
        for p in pats:
            m = p.search(text)
            if m:
                flags[name] = True
                evidence[name] = m.group(0)
                break
    injection = any(p.search(text) for p in inj)
    return {"flags": flags, "evidence": evidence, "injection_suspect": injection, "has_note": bool(text.strip())}
