"""Evaluation package: everything a reviewer needs to judge an analysis, generated from the saved analysis itself.

Every number comes from the stored analysis, the robustness run and the Validation Lab; nothing is hand-typed. The text states limits plainly:
no churn labels exist, so nothing here is an accuracy, precision, recall or probability claim.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import zipfile
from pathlib import Path

import pandas as pd
import yaml

from api import ai_disclosure, exporter, weights
from src.config import CONFIG_DIR, ROOT, load_scoring, load_settings

DIMS = weights.DIMS
_inr_l = lambda v: f"Rs {v / 1e5:.1f} lakh"


def _wl(w: dict) -> str:
    return " / ".join(f"{w[d]:g}" for d in DIMS)


def upload_file(upload_dir: Path | None) -> Path | None:
    if upload_dir and upload_dir.exists():
        files = [f for f in upload_dir.glob("*") if f.is_file()]
        return files[0] if files else None
    return None


# ---------------------------------------------------------------- source audit
def source_audit_md(path: Path | None, s: dict) -> str:
    sheets = s.get("sheets") or {}
    out = ["# Source audit", "", f"Generated {dt.datetime.now():%Y-%m-%d %H:%M}.", "", "## Workbook", f"- File: `{s.get('source_file')}`"]
    if not path:
        q = s.get("quality") or {}
        out += ["- The original workbook is no longer stored, so this audit uses the validation report saved with the analysis.", "",
                f"- Records: {q.get('total_records')}; unique IDs: {q.get('unique_ids')}; duplicate IDs: {len(q.get('duplicate_ids') or [])}; analysable: {q.get('analysable_records')}.",
                f"- Excluded records: {len(s.get('excluded_records') or [])}."]
        return "\n".join(out) + "\n"
    x = pd.ExcelFile(path) if path.suffix.lower() != ".csv" else None
    m = pd.read_excel(x, sheets.get("merchants") or "P2_Merchants") if x else pd.read_csv(path)
    pb = pd.read_excel(x, sheets.get("playbooks") or "P2_Playbooks") if x and sheets.get("playbooks") else None
    asm = pd.read_excel(x, sheets.get("assumptions") or "P2_Assumptions") if x and sheets.get("assumptions") else None
    out += [f"- SHA-256: `{hashlib.sha256(path.read_bytes()).hexdigest()}`", f"- Sheets in file: {', '.join(x.sheet_names) if x else 'CSV'}",
            f"- Sheets used: {', '.join(str(v) for v in (sheets.get('merchants'), sheets.get('playbooks'), sheets.get('assumptions')) if v)}", "",
            "## Integrity checks", f"- Merchant rows: **{len(m)}**; unique IDs: **{m.iloc[:, 0].nunique()}**; duplicate IDs: **{int(m.iloc[:, 0].duplicated().sum())}**.",
            f"- Excluded records: **{len(s.get('excluded_records') or [])}**" + "".join(f"; {e.get('merchant_id')}: {e.get('reason')}" for e in (s.get('excluded_records') or [])[:5]) + ".", "",
            "## Missing values by column"]
    miss = [(c, int(m[c].isna().sum())) for c in m.columns if int(m[c].isna().sum())]
    out += (["| Column | Missing | Share |", "|---|---:|---:|"] + [f"| {c} | {k} | {k / len(m):.0%} |" for c, k in miss]) if miss else ["No missing values."]
    out += ["", "Missing CSAT and missing notes are treated as unknown: they lower evidence completeness and add no risk points.", "",
            "## Units and definitions", "- TPV columns are in Rs lakh per month (1 lakh = 100,000); M6 is the latest month.", "- Success rate exists as two period aggregates (M1-M3, M4-M6) only.",
            "- Logins, products, tickets and CSAT are current snapshots. Account-manager notes are unverified free text.", "- No churn labels exist, so no accuracy, precision, recall or probability can be computed."]
    if asm is not None:
        out += ["", "## Assumptions (verbatim from the workbook)", "| Item | Assumption |", "|---|---|"] + [f"| {r.iloc[0]} | {r.iloc[1]} |" for _, r in asm.iterrows()]
    if pb is not None:
        out += ["", "## Playbooks (verbatim from the workbook)", "| ID | Name | What happens | When it applies |", "|---|---|---|---|"] + [f"| {r.iloc[0]} | {r.iloc[1]} | {r.iloc[2]} | {r.iloc[3]} |" for _, r in pb.iterrows()]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- sensitivity and validation text
def weight_report_md(s: dict, stab: dict) -> str:
    by = {m["id"]: m for m in s["merchants"]}
    c = stab["counts"]
    rob = [r for r in stab["merchants"] if r["classification"] == "Robust priority"]
    sens = [r for r in stab["merchants"] if r["classification"] == "Weight-sensitive"]
    hi_low = [r for r in stab["merchants"] if by[r["merchant_id"]]["risk_band"] == "high" and r["classification"] == "Low priority"]
    L = ["# Weight sensitivity report", "", f"Analysis: **{s['name']}** ({s['source_file']}), {s['version']}. Capacity {stab['capacity']}.", "",
         "This measures how stable the shortlist is when the design hypotheses change. It is **ranking robustness, not prediction accuracy**: no churn labels exist.", "",
         "## Method", f"- The real engine (scoring, playbook selection, prioritisation) is re-run for all {len(by)} merchants in every configuration.",
         f"- {len(weights.PRESETS)} named test scenarios plus {stab['grid_size']} sampled configurations (fixed seed {stab['seed']}, so the run is reproducible). Total {stab['configurations']}.",
         f"- Dimension weights are sampled between {stab['weight_bounds_pct'][0]}% and {stab['weight_bounds_pct'][1]}% each and always sum to 100%.",
         "- Feature-level parameters sampled in the same configuration: " + "; ".join(f"`{k}` {v[0]} to {v[1]}" for k, v in stab["param_bounds"].items()) + ".",
         "- Risk-band thresholds and the outreach cost are held fixed.",
         f"- Robust priority = shortlisted in at least {stab['robust_at']:.0%} of configurations. Low priority = at most {stab['low_at']:.0%} and not in the baseline shortlist. Everything else is weight-sensitive.", "",
         "## The five test scenarios (test scenarios, not recommended final weights)", "",
         "| Scenario | Weights P/R/E/C % | High | Moderate | Low | Overlap with baseline | Moved in | Moved out | Run-rate represented | Seasonal selected | Incomplete-evidence selected |", "|---|---|---:|---:|---:|---:|---|---|---:|---:|---:|"]
    for x in stab["scenarios"]:
        L.append(f"| {x['scenario']} | {_wl(x['weights'])} | {x['high']} | {x['medium']} | {x['low']} | {x['overlap_with_baseline']} of {len(x['top_n'])} | {', '.join(x['moved_in']) or 'None'} | {', '.join(x['moved_out']) or 'None'} | {_inr_l(x['run_rate_inr'])} | {x['seasonal_selected']} | {x['incomplete_selected']} |")
    L += ["", "Run-rate is the annual net-revenue run-rate proxy of the shortlisted merchants: exposure, not revenue lost and not expected savings.", "",
          "## Merchant stability", f"- Robust priority: **{c['Robust priority']}**. Weight-sensitive: **{c['Weight-sensitive']}**. Low priority: **{c['Low priority']}**.", "",
          "| Merchant | Classification | In shortlist | Average rank | Best to worst | Score range | Moved materially by |", "|---|---|---:|---:|---|---|---|"]
    for r in rob + sens:
        L.append(f"| {r['merchant_id']} {r['name']} | {r['classification']} | {r['times_selected']} of {r['configurations']} | {r['avg_rank']} | {r['best_rank']} to {r['worst_rank']} | {r['score_min']} to {r['score_max']} | {'; '.join(r['moved_by']) or 'None'} |")
    L += ["", "## Reading the results",
          f"- The baseline shortlist is largely stable: {sum(1 for r in stab['merchants'] if r['baseline_selected'] and r['classification'] == 'Robust priority')} of {len(stab['baseline_top'])} baseline merchants are robust priorities.",
          f"- **Why the shortlist is stable.** Only {sum(m['eligible'] for m in s['merchants'])} merchants are eligible for {stab['capacity']} slots, and the order inside that pool is driven mostly by annual run-rate through the priority index. Stability to the weights is therefore partly a property of the value-weighted selection rule, not only evidence that the weights are right.",
          "- Weight-sensitive merchants sit near the capacity line. Treat them as a judgement call, not a model verdict.",
          "- Scenario comparisons use the same workbook with different weights. They are not changes in merchant behaviour over time."]
    if hi_low:
        L += ["", "## High-risk merchants that are rarely shortlisted",
              "These are High risk but low priority in nearly every configuration, because the priority index weighs annual run-rate and a small merchant cannot outrank larger ones under the capacity limit. This follows from the value-weighted selection rule; it is a capacity decision, not a score error.", "",
              "| Merchant | Risk score | Annual run-rate | Times shortlisted |", "|---|---:|---:|---:|"]
        L += [f"| {r['merchant_id']} {r['name']} | {by[r['merchant_id']]['risk_score']} | {_inr_l(by[r['merchant_id']]['annual_value'])} | {r['times_selected']} of {r['configurations']} |" for r in hi_low]
    return "\n".join(L) + "\n"


def failure_md(s: dict, val: dict, stab: dict | None) -> str:
    sm = val["summary"]
    cases = [x for x in val["cases"] if x.get("merchant_id")]
    by = {m["id"]: m for m in s["merchants"]}
    hi_low = [r for r in (stab or {}).get("merchants", []) if by[r["merchant_id"]]["risk_band"] == "high" and r["classification"] == "Low priority"]
    F = ["# Failure analysis", "", f"Source: Validation Lab, {s['name']}, {s['version']}.", "",
         f"**{sm['cases']} case-based scenarios reviewed against stated design expectations: {sm['pass']} pass, {sm['needs_review']} need human review, {sm['fail']} fail.** This is not an accuracy measure: no churn labels exist, and each expectation is a test expectation, not ground truth.", "",
         "## Automated failures"]
    fails = [x for x in cases if x["status"] == "Fail"]
    if not fails:
        F += ["None. Every automated check passed.", "", "That is a weaker statement than it sounds. The checks are deliberately coarse (band, eligibility, playbook family, whether a dimension is zero, whether mitigating or contradictory text exists). They catch gross design errors, not subtle mis-rankings. Human reviewer judgement is recorded separately in the Validation Lab."]
    for x in fails:
        F += [f"### {x['case_id']} {x['pattern']}: {x['merchant_id']} {x['merchant']}", f"- Failure stage: {x['failure_stage']}", f"- Detail: {x['failure_category']}", f"- Corrective action: {x['corrective_action']}", ""]
    F += ["", "## Needs human review"] + [f"- **{x['case_id']} {x['pattern']}**: {x['merchant_id']} {x['merchant']}, score {x['score']} ({x['band']}). {x['corrective_action']}" for x in cases if x["status"] == "Needs review"]
    judged = [x for x in cases if (x.get("reviewer") or {}).get("judgement", "Pending") != "Pending"]
    F += ["", f"Human reviewer judgement recorded for {len(judged)} of {len(cases)} cases."]
    F += ["", "## Observations that deserve a decision"]
    if hi_low:
        F.append("- **High risk but not shortlisted.** " + ", ".join(f"{r['merchant_id']} ({r['times_selected']} of {r['configurations']})" for r in hi_low) + ". They rarely reach the capacity limit because selection is value-weighted.")
    F += ["- **Single-signal severity lands in Moderate.** One dimension alone cannot reach High, so severe single-dimension cases are Moderate with a critical-trigger flag.",
          "- **Pool sizes.** Some patterns match very few merchants (see the matching count per case), so a pass can rest on one example.", "",
          "## Cases by required adversarial test", "| Required test | Cases | Result |", "|---|---|---|"]
    F += [f"| {t['test']} | {', '.join(t['cases'])} | {', '.join(t['statuses'].values())} |" for t in val["coverage"]]
    return "\n".join(F) + "\n"


# ---------------------------------------------------------------- config, lineage, limitations, summary
def config_snapshot(s: dict) -> dict:
    def y(name: str):
        return yaml.safe_load((CONFIG_DIR / name).read_text(encoding="utf-8"))
    return {"generated_at": dt.datetime.now().isoformat(timespec="seconds"), "analysis_version": s["version"], "scoring": y("scoring.yaml"), "settings": y("settings.yaml"),
            "playbook_mapping": y("playbook_mapping.yaml"), "note_signals": y("note_signals.yaml"), "assumptions_in_force": s["assumptions"], "weights_pct": s.get("weights_pct"),
            "scoring_overrides": s.get("scoring_overrides"), "analysis_config": s["config"], "current_scenario": s["scenario"], "baseline_scenario": s["baseline_scenario"],
            "note": "Weights, scales and thresholds are design hypotheses, not learned values."}


def lineage(s: dict, st: dict, ai: dict, path: Path | None) -> dict:
    return {"analysis": s["name"], "analysis_id": s["id"], "created_at": s["created_at"], "version": s["version"], "source_file": s["source_file"],
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path else "workbook no longer stored", "sheets_used": s["sheets"], "field_mapping": s["mapping"],
            "assumptions": s["assumptions"], "assumption_provenance": s.get("assumptions_provenance"), "excluded_records": s.get("excluded_records", []),
            "scoring_overrides": s.get("scoring_overrides"), "weights_pct": s.get("weights_pct"), "manager_exclusions": st.get("exclusions", {}), "manager_inclusions": st.get("marked", []),
            "capacity_decisions": st.get("capacity_decisions", {}), "runtime_ai": {"claude_used_in_analysis": ai["claude_used_in_analysis"], "tasks": ai["rows"], "notes": ai["notes"], "development": ai["development"]},
            "scenario_vs_behaviour": "Scenario comparisons re-score the same workbook under different weights. They are not changes in merchant behaviour over time."}


def limitations_md() -> str:
    return """# Limitations

1. **No churn labels.** The workbook records no outcome, so the risk score is a heuristic evidence index. No accuracy, precision, recall, AUC, calibrated probability or churn-likelihood percentage is claimed.
2. **Hypothesis weights.** Dimension weights, scales and thresholds are design hypotheses. The sensitivity test shows how stable the ranking is to them; it does not show they are right.
3. **Single six-month snapshot.** Payment success exists as two period averages only. Logins, products used, tickets and CSAT are current snapshots, so no adoption or service trend can be claimed.
4. **Unverified notes.** Account-manager notes are free text. Commercial signals depend on them entirely and need confirmation with the account manager.
5. **Missing data is unknown.** Missing CSAT or notes lower evidence completeness; they add no risk points.
6. **Exposure is not loss.** Annual run-rate is M6 TPV x net revenue rate x 12 months, an assumption-based proxy. It is not revenue lost, not expected savings and not a forecast.
7. **Value-weighted selection.** With limited capacity, small merchants can be High risk yet rarely shortlisted. This is a capacity decision, recorded in the Priority Queue.
8. **Small groups.** Industry groups hold roughly 5 to 12 merchants and some validation patterns match a handful, so conclusions about them are weak.
9. **Validation is design-conformance.** A pass means the engine behaves as the stated design intends. Expected interpretations are test expectations, not ground truth.
10. **Outcome capture is not a label.** Recorded outcomes are CSM observations and are not churn labels unless the actual churn definition is verified.
11. **Human review.** EDGE sends nothing. Every draft needs a named reviewer's approval, and contact is recorded manually.
"""


def summary_md(s: dict, stab: dict | None, val: dict, ai: dict) -> str:
    k, sc = s["kpis"], load_scoring()
    a = s["assumptions"]
    sel = [m for m in s["merchants"] if m["selected"]]
    L = [f"# Evaluation summary: {s['name']}", "", f"Source workbook `{s['source_file']}`, analysed {s['created_at']}, {s['version']}.", "",
         "## What EDGE is", "An explainable decision-support system. It combines transaction performance, payment health, service experience, engagement, commercial signals and renewal context to help a CSM team spend limited outreach capacity. It is not a churn predictor.", "",
         "## Deterministic, templated and AI-assisted parts",
         "| Task | How it was produced | Runtime AI |", "|---|---|---|"] + [f"| {r['task']} | {r['method']} | {'Used' if r['runtime_ai'] else 'Not used'} |" for r in ai["rows"]] + ["", ai["development"], "",
         "## Scoring and weights",
         f"Four dimensions are scored 0-100 and combined: {_wl(s.get('weights_pct') or {d: sc['weights'][d] * 100 for d in DIMS})} (Performance / Relationship / Engagement / Commercial, %). Total = {sc['aggregation']['weighted_share']} x weighted mean + {round(1 - sc['aggregation']['weighted_share'], 2)} x strongest dimension + a convergence bonus. Bands: High {sc['bands']['high']}+, Moderate {sc['bands']['medium']}+, Low below.",
         "Rationale: performance and payment signals are direct operational evidence; relationship and commercial signals show friction or displacement; engagement is the weakest evidence because it is a snapshot. One dimension alone cannot reach High, so High needs corroboration. All of this is hypothesis.", "",
         f"Result: {k['high']} High, {k['medium']} Moderate, {k['low']} Low of {k['total']} merchants; {k['immediate']} meet a critical review trigger.", "",
         "## Top-list logic", f"Eligible merchants have playbook PB-1 to PB-4, a Moderate or High band and a positive priority index. They are ordered by the configured business priorities, then the priority index = (risk weight x annual exposure - (1 - risk weight) x outreach cost) x renewal urgency, then risk score, then merchant ID. The first {k['capacity']} are shortlisted ({len(sel)} now). The index is a ranking aid, not an expected saving.", "",
         "## Financial assumptions (from the workbook)", f"- Net revenue rate {a['net_revenue_rate'] * 100:g}% of TPV; TPV unit Rs {a['tpv_unit_inr']:,.0f} (lakh); saved-merchant value {a['saved_merchant_months']} months at M6 TPV.",
         f"- Outreach cost Rs {a['false_alarm_cost_inr']:,.0f} per outreach; capacity {a['max_outreaches']}; churn horizon {a['churn_horizon_days']} days; seasonal industries: {', '.join(a['seasonal_industries'])}.",
         f"- Exposure of Moderate and High merchants: {_inr_l(k['exposure_annual_inr'])} a year. This is exposure, not revenue lost or expected savings.", ""]
    if stab:
        c = stab["counts"]
        L += ["## Sensitivity results", f"{stab['configurations']} configurations (5 named scenarios plus {stab['grid_size']} sampled, seed {stab['seed']}): {c['Robust priority']} robust priorities, {c['Weight-sensitive']} weight-sensitive, {c['Low priority']} low priority. Stability is partly a property of the value-weighted selection rule. This measures ranking robustness, not accuracy.", ""]
    else:
        L += ["## Sensitivity results", "The robustness test has not been run for this analysis.", ""]
    sm = val["summary"]
    L += ["## Validation", f"{sm['cases']} case-based scenarios reviewed: {sm['pass']} pass, {sm['needs_review']} need review, {sm['fail']} fail. Checks are coarse and expectations are test expectations, not ground truth. See `failure_analysis.md`.", "",
          "## Human safeguards", "Every draft needs a named reviewer who confirms the facts. Approval, contact and outcome are separate recorded events; contact is recorded manually; EDGE never sends a message. Drafts never mention risk scores or churn and offer no concession.", "",
          "## Limitations", "See `limitations.md`. The main ones: no churn labels, hypothesis weights, a single snapshot, unverified notes."]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- package
def build_package(s: dict, st: dict, stab: dict | None, val: dict, ai: dict, upload_dir: Path | None) -> bytes:
    path = upload_file(upload_dir)
    extra = {"stability": stab, "validation": val}
    files: dict[str, bytes | str] = {}
    files["source_audit.md"] = source_audit_md(path, s)
    meth = ROOT / "scoring_methodology.md"
    files["scoring_methodology.md"] = meth.read_text(encoding="utf-8") if meth.exists() else "# Scoring methodology\n\nSee configuration_snapshot.json.\n"
    files["configuration_snapshot.json"] = json.dumps(config_snapshot(s), indent=2, default=str)
    files["merchant_register.csv"] = exporter.to_csv("risk_register", s, st)
    files["top_outreach_list.csv"] = exporter.to_csv("outreach", s, st)
    elig = set(load_settings()["selection"]["eligible_playbooks"])
    files["playbook_mapping.csv"] = (pd.DataFrame(s["playbooks"]).assign(used_for_outreach=lambda d: d["playbook_id"].isin(elig)).to_csv(index=False))
    if stab:
        files["weight_scenario_comparison.csv"] = exporter.to_csv("weight_scenarios", s, st, extra)
        files["merchant_rank_stability.csv"] = exporter.to_csv("stability", s, st, extra)
        files["top15_overlap_matrix.csv"] = exporter.to_csv("overlap", s, st, extra)
        files["weight_sensitivity_report.md"] = weight_report_md(s, stab)
    else:
        files["weight_sensitivity_report.md"] = "# Weight sensitivity report\n\nThe robustness test has not been run for this analysis.\n"
    files["manual_validation_log.csv"] = exporter.to_csv("validation", s, st, extra)
    files["failure_analysis.md"] = failure_md(s, val, stab)
    files["limitations.md"] = limitations_md()
    files["analysis_lineage.json"] = json.dumps(lineage(s, st, ai, path), indent=2, default=str)
    files["evaluation_summary.md"] = summary_md(s, stab, val, ai)
    files["edge_full_export.xlsx"] = exporter.to_xlsx(None, s, st, extra)
    readme = ["# Razorpay EDGE evaluation package", "", f"Analysis **{s['name']}**, generated {dt.datetime.now():%Y-%m-%d %H:%M}, {s['version']}.", "",
              "Start with `evaluation_summary.md`. Every file below was generated from the saved analysis.", ""] + [f"- `{n}`" for n in files] + \
             ["", "No churn labels exist: nothing here is an accuracy, precision, recall or probability claim."]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.md", "\n".join(readme) + "\n")
        for n, c in files.items():
            z.writestr(n, c)
    return buf.getvalue()
