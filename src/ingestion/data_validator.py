"""Schema and quality checks plus the source-data audit document. Never imputes or drops rows."""
from __future__ import annotations

import datetime as dt

import pandas as pd

from src.ingestion.workbook_loader import SourceData

EXPECTED_MERCHANT_COLUMNS = [
    "merchant_id", "business_name", "segment", "industry", "city", "tenure_months",
    "tpv_m1_inr_lakh", "tpv_m2_inr_lakh", "tpv_m3_inr_lakh", "tpv_m4_inr_lakh",
    "tpv_m5_inr_lakh", "tpv_m6_inr_lakh", "success_rate_m1_m3_pct", "success_rate_m4_m6_pct",
    "support_tickets_last_90d", "unresolved_tickets", "last_csat_1_to_5", "products_used",
    "logins_last_30d", "days_to_contract_renewal", "account_manager_note",
]
EXPECTED_PLAYBOOK_COLUMNS = ["playbook_id", "name", "what_happens", "when_it_applies"]
EXPECTED_ASSUMPTION_COLUMNS = ["item", "assumption"]
EXPECTED_MERCHANT_COUNT = 100
EXPECTED_PLAYBOOK_IDS = [f"PB-{i}" for i in range(1, 7)]

COLUMN_DICTIONARY = {
    "merchant_id": ("string", "Unique merchant identifier (kept as text)."),
    "business_name": ("string", "Fictional business name."),
    "segment": ("category", "Small / Mid / Enterprise."),
    "industry": ("category", "Business category; used for the seasonality rule."),
    "city": ("category", "City (not used in scoring)."),
    "tenure_months": ("number", "Months since onboarding."),
    **{f"tpv_m{i}_inr_lakh": ("number", f"Monthly TPV in Rs lakh for month {i} (m6 = most recent)." ) for i in range(1, 7)},
    "success_rate_m1_m3_pct": ("number", "Payment success rate (%) aggregated over months 1-3. Period aggregate, not monthly."),
    "success_rate_m4_m6_pct": ("number", "Payment success rate (%) aggregated over months 4-6. Period aggregate."),
    "support_tickets_last_90d": ("count", "All support tickets in last 90 days (resolved + unresolved)."),
    "unresolved_tickets": ("count", "Tickets still open."),
    "last_csat_1_to_5": ("number", "Most recent CSAT, 1 (worst) to 5. Blank = no survey response; NOT poor CSAT."),
    "products_used": ("count", "Number of Razorpay products in use (current snapshot only)."),
    "logins_last_30d": ("count", "Dashboard logins in last 30 days (current snapshot only; no history)."),
    "days_to_contract_renewal": ("count", "Days until contract renewal, as of snapshot date 30 Sep 2026."),
    "account_manager_note": ("free text", "Untrusted free text. Blank = no note recorded."),
}


def _check(name: str, passed: bool, detail: str = "") -> dict:
    return {"name": name, "passed": bool(passed), "detail": detail}


def validate(src: SourceData, settings: dict) -> dict:
    m = src.merchants
    checks: list[dict] = []
    checks.append(_check("merchant sheet has all expected columns",
                         list(m.columns) == EXPECTED_MERCHANT_COLUMNS,
                         f"found {len(m.columns)} columns"))
    checks.append(_check("playbook sheet columns", list(src.playbooks.columns) == EXPECTED_PLAYBOOK_COLUMNS))
    checks.append(_check("assumption sheet columns", list(src.assumptions.columns) == EXPECTED_ASSUMPTION_COLUMNS))
    checks.append(_check(f"exactly {EXPECTED_MERCHANT_COUNT} merchants loaded",
                         len(m) == EXPECTED_MERCHANT_COUNT, f"loaded {len(m)}"))
    checks.append(_check("merchant_id unique", m["merchant_id"].is_unique,
                         f"{int(m['merchant_id'].duplicated().sum())} duplicates"))
    checks.append(_check("six playbooks PB-1..PB-6",
                         list(src.playbooks["playbook_id"]) == EXPECTED_PLAYBOOK_IDS))
    meta_rows = src.meta["sheets"][settings["sheets"]["merchants"]]
    checks.append(_check("no source rows dropped (non-empty rows == rows loaded)",
                         meta_rows["non_empty_rows"] == len(m)))

    ranges = {
        "tpv_*": [c for c in m.columns if c.startswith("tpv_m")],
    }
    issues: list[str] = []
    for c in ranges["tpv_*"]:
        bad = m[m[c].notna() & (m[c] < 0)]
        issues += [f"{c} negative for {i}" for i in bad["merchant_id"]]
    for c in ("success_rate_m1_m3_pct", "success_rate_m4_m6_pct"):
        bad = m[m[c].notna() & ((m[c] < 0) | (m[c] > 100))]
        issues += [f"{c} outside 0-100 for {i}" for i in bad["merchant_id"]]
    bad = m[m["last_csat_1_to_5"].notna() & ~m["last_csat_1_to_5"].between(1, 5)]
    issues += [f"CSAT outside 1-5 for {i}" for i in bad["merchant_id"]]
    # Not an error: unresolved tickets may pre-date the 90-day window. Reported as a warning; ratios guard tickets==0.
    bad = m[m["unresolved_tickets"] > m["support_tickets_last_90d"]]
    warnings = [f"{i}: unresolved_tickets ({int(u)}) > support_tickets_last_90d ({int(t)}) - likely older open tickets"
                for i, u, t in zip(bad["merchant_id"], bad["unresolved_tickets"], bad["support_tickets_last_90d"])]
    for c in ("logins_last_30d", "products_used", "days_to_contract_renewal"):
        bad = m[m[c].notna() & (m[c] < 0)]
        issues += [f"{c} negative for {i}" for i in bad["merchant_id"]]
    checks.append(_check("no impossible values", not issues, "; ".join(issues[:10])))

    numeric_nulls = m.drop(columns=["account_manager_note", "last_csat_1_to_5"]).isna().sum().sum()
    checks.append(_check("no unexpected missing values outside CSAT/note", numeric_nulls == 0,
                         f"{int(numeric_nulls)} missing"))

    missing = {c: int(m[c].isna().sum()) for c in m.columns if m[c].isna().any()}
    categorical = {c: m[c].value_counts(dropna=False).to_dict() for c in ("segment", "industry", "city")}
    industries = set(m["industry"].dropna().unique())
    seasonal = set(settings["source_assumptions"]["seasonal_industries"])
    checks.append(_check("seasonal industries from config exist in data", seasonal <= industries,
                         f"missing: {sorted(seasonal - industries)}"))
    return {
        "checks": checks,
        "all_passed": all(c["passed"] for c in checks),
        "missing_counts": missing,
        "categorical": categorical,
        "issues": issues,
        "warnings": warnings,
    }


def build_audit_markdown(src: SourceData, report: dict, settings: dict) -> str:
    m = src.merchants
    L: list[str] = []
    L.append("# Source data audit (Gate 1)\n")
    L.append(f"_Generated {dt.datetime.now().isoformat(timespec='seconds')} | config {settings['config_version']}_\n")
    L.append("## 1. Files and sheets inspected\n")
    L.append(f"- Workbook: `{src.meta['file']}` (snapshot date per README sheet: **30 Sep 2026**, all datasets).")
    L.append(f"- Sheets in workbook: {', '.join(src.meta['sheet_names'])}")
    L.append("- Sheets used: `P2_Merchants`, `P2_Playbooks`, `P2_Assumptions` (P1/P3 sheets ignored).")
    L.append("- PDF brief: `Razorpay_Campus_AI_Buildathon_Student_Brief.pdf` (Problem 2 on page 4).\n")
    L.append("| Sheet | Rows | Columns | Hidden rows/cols | Formula cells | Data validations |")
    L.append("|---|---|---|---|---|---|")
    for name, info in src.meta["sheets"].items():
        df = {"P2_Merchants": m, "P2_Playbooks": src.playbooks, "P2_Assumptions": src.assumptions}[name]
        L.append(f"| {name} | {len(df)} | {len(df.columns)} | {len(info['hidden_rows'])}/{len(info['hidden_columns'])} "
                 f"| {info['formula_cells']} | {info['data_validations']} |")
    L.append("\n## 2. Automated checks\n")
    L.append("| Check | Result | Detail |\n|---|---|---|")
    for c in report["checks"]:
        L.append(f"| {c['name']} | {'PASS' if c['passed'] else 'FAIL'} | {c['detail']} |")
    L.append(f"\n**Data warnings ({len(report['warnings'])}):** `unresolved_tickets` exceeds `support_tickets_last_90d` for some merchants "
             "(open tickets older than the 90-day window are the likely explanation; unconfirmed). Scoring uses unresolved counts as given.\n")
    for w in report["warnings"]:
        L.append(f"- {w}")
    L.append("\n## 3. Column dictionary (P2_Merchants)\n")
    L.append("| Column | Type | Meaning / unit | Missing | Min | Max |\n|---|---|---|---|---|---|")
    for col in m.columns:
        typ, desc = COLUMN_DICTIONARY[col]
        mn = mx = ""
        if pd.api.types.is_numeric_dtype(m[col]):
            mn, mx = f"{m[col].min():g}", f"{m[col].max():g}"
        miss = int(m[col].isna().sum())
        L.append(f"| `{col}` | {typ} | {desc} | {miss} ({miss / len(m):.0%}) | {mn} | {mx} |")
    L.append("\n## 4. Categorical distributions\n")
    for c, dist in report["categorical"].items():
        L.append(f"**{c}**: " + ", ".join(f"{k} ({v})" for k, v in dist.items()) + "\n")
    L.append("## 5. Account manager note vocabulary\n")
    notes = m["account_manager_note"].value_counts(dropna=False)
    L.append("The notes are templated (short, repeated phrases). Counts:\n")
    for k, v in notes.items():
        L.append(f"- {v} x {k if isinstance(k, str) else '(blank)'}")
    L.append("\n## 6. Playbook catalogue (exact text from `P2_Playbooks`)\n")
    for _, r in src.playbooks.iterrows():
        L.append(f"- **{r['playbook_id']} - {r['name']}**: {r['what_happens']} _When it applies:_ {r['when_it_applies']}")
    L.append("\n## 7. Assumptions catalogue (exact text from `P2_Assumptions`)\n")
    for _, r in src.assumptions.iterrows():
        L.append(f"- **{r['item']}**: {r['assumption']}")
    L.append("\n## 8. Limitations and open interpretation points\n")
    L += [
        "- **No churn labels.** Hidden by the organisers. No supervised training, accuracy, precision/recall or churn probability is possible or reported.",
        "- Success rates are two **period aggregates** (M1-M3, M4-M6), not monthly series. Only the change in percentage points is computable.",
        "- Logins, products and CSAT are **single snapshots**: no claim of decline over time can be made.",
        "- CSAT is blank for a subset of merchants (treated as unknown, never as poor).",
        "- `account_manager_note` is blank for a subset of merchants; notes are templated and treated as untrusted data.",
        "- Assumption wording \"Gifting, Education and Travel\" is mapped to industries `Gifting & Festive`, `Education / Coaching`, `Travel & Hospitality` (interpretation, configurable).",
        "- Only six months of TPV exist; no annual seasonal pattern can be learned. Seasonality is handled by a rule (industry in the supplied list AND a dip-then-rebound shape), and never exempts other risk signals.",
        "- PB-3 text says renewal \"within ~60 days\": implemented as <= 60 days (configurable).",
        "- The PDF says the team can run \"at most 15 proactive outreaches\"; it does not say whether PB-5 (growth check-in) counts. Default: PB-5/PB-6 do **not** use churn-outreach capacity (configurable, needs confirmation).",
        "- No channel/consent rules were supplied: drafts are channel-neutral and are never sent.",
    ]
    return "\n".join(L) + "\n"
