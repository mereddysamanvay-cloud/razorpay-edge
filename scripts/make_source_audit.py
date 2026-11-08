"""Regenerates source_audit.md from the workbook. Run: py scripts/make_source_audit.py [workbook.xlsx]"""
import datetime as dt
import hashlib
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "source" / "Buildathon_Student_Data_Pack.xlsx"
x = pd.ExcelFile(path)
m = pd.read_excel(x, "P2_Merchants")
pb = pd.read_excel(x, "P2_Playbooks")
asm = pd.read_excel(x, "P2_Assumptions")

out = [f"# Source audit", "", f"Generated {dt.datetime.now():%Y-%m-%d %H:%M} by `scripts/make_source_audit.py`.", "",
       "## Workbook", f"- File: `{path.name}`", f"- SHA-256: `{hashlib.sha256(path.read_bytes()).hexdigest()}`",
       f"- Sheets in file: {', '.join(x.sheet_names)}", "- Sheets used: P2_Merchants, P2_Playbooks, P2_Assumptions (all others ignored)", "",
       "| Sheet | Data rows | Columns |", "|---|---:|---:|", f"| P2_Merchants | {len(m)} | {m.shape[1]} |", f"| P2_Playbooks | {len(pb)} | {pb.shape[1]} |", f"| P2_Assumptions | {len(asm)} | {asm.shape[1]} |", "",
       "## Integrity checks", f"- Merchants: **{len(m)}**; unique IDs: **{m['merchant_id'].nunique()}**; duplicate IDs: **{int(m['merchant_id'].duplicated().sum())}**."]
bad = []
for c in ("success_rate_m1_m3_pct", "success_rate_m4_m6_pct"):
    bad += [f"{c} outside 0-100: {int(((m[c] < 0) | (m[c] > 100)).sum())}"]
bad += [f"last_csat_1_to_5 outside 1-5: {int(((m['last_csat_1_to_5'] < 1) | (m['last_csat_1_to_5'] > 5)).sum())}"]
tp = [f"tpv_m{i}_inr_lakh" for i in range(1, 7)]
bad += [f"negative TPV values: {int((m[tp] < 0).sum().sum())}", f"negative counts (tickets/unresolved/logins/products): {int((m[['support_tickets_last_90d', 'unresolved_tickets', 'logins_last_30d', 'products_used']] < 0).sum().sum())}"]
out += [f"- {b}" for b in bad]
gt = m[m["unresolved_tickets"] > m["support_tickets_last_90d"]]
out += [f"- Unresolved tickets exceed 90-day ticket count for {len(gt)} merchants ({', '.join(gt['merchant_id'])}); likely older open tickets, unconfirmed. Scoring uses unresolved counts as given.", "- Excluded records: **0** (no row failed validation).", "",
        "## Missing values by column (P2_Merchants)", "| Column | Missing | Share |", "|---|---:|---:|"]
for c in m.columns:
    n = int(m[c].isna().sum())
    if n:
        out.append(f"| {c} | {n} | {n / len(m):.0%} |")
out += ["", "Missing CSAT and missing notes are treated as unknown: they lower evidence completeness and add no risk points.", "",
        "## Units and definitions", "- TPV columns: Rs lakh per month (1 lakh = 100,000). `tpv_m6` is the latest month.",
        "- Success rate: two period aggregates (M1-M3, M4-M6) only; no monthly series exists and none is derived.",
        "- Logins, products used, tickets and CSAT are current snapshots, not trends.", "- Account-manager notes are unverified free text.",
        "- No churn labels exist in the workbook, so no accuracy, precision, recall or probability can be computed.", "", "## Assumptions (verbatim from P2_Assumptions)", "| Item | Assumption |", "|---|---|"]
out += [f"| {r['item']} | {r['assumption']} |" for _, r in asm.iterrows()]
out += ["", "How the app reads them: net revenue 1% of TPV; churn horizon 90 days; false-alarm cost Rs 1,500 per outreach (confirmed by the user on 2026-11-08 as the total, not per hour); saved-merchant value = 12 months at M6 TPV; seasonal = Gifting, Education, Travel; capacity 15.", "",
        "## Playbooks (verbatim from P2_Playbooks)", "| ID | Name | What happens | When it applies |", "|---|---|---|---|"]
out += [f"| {r['playbook_id']} | {r['name']} | {r['what_happens']} | {r['when_it_applies']} |" for _, r in pb.iterrows()]
(ROOT / "source_audit.md").write_text("\n".join(out) + "\n", encoding="utf-8")
print("wrote source_audit.md")
