"""Runs the test suite and writes an honest validation report (NOT churn-prediction accuracy)."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict

import pandas as pd

from src.config import ROOT

CATEGORY = {"test_data_validation": "A. Data", "test_features": "B. Features", "test_scoring": "C. CRM / scenario logic",
            "test_playbooks": "C. CRM / playbook mapping", "test_prioritisation": "D. Ranking", "test_agent_safety": "E. LLM safety guardrails"}


def run_tests() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        xml_path = f"{tmp}/junit.xml"
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", f"--junitxml={xml_path}", "-p", "no:cacheprovider"],
                              cwd=ROOT, capture_output=True, text=True)
        tree = ET.parse(xml_path)
    by_cat: dict[str, dict] = defaultdict(lambda: {"passed": 0, "failed": 0, "failures": []})
    for tc in tree.iter("testcase"):
        mod = tc.get("classname", "").split(".")[-1]
        cat = CATEGORY.get(mod, mod)
        bad = tc.find("failure") is not None or tc.find("error") is not None
        by_cat[cat]["failed" if bad else "passed"] += 1
        if bad:
            by_cat[cat]["failures"].append(tc.get("name"))
    return {"returncode": proc.returncode, "by_category": dict(by_cat)}


def build_report(tests: dict, data_report: dict, df: pd.DataFrame, sens_summary: pd.DataFrame, sens_overlap: pd.DataFrame,
                 llm_stats: dict | None, run_ts: str, config_version: str) -> str:
    L = ["# Validation report\n", f"_Run {run_ts} | config {config_version}_\n",
         "> **What this report is NOT.** It contains no precision, recall, F1, AUC, accuracy or calibrated probability of churn. Actual churn labels "
         "are withheld, so none can be computed. Everything below measures *implementation correctness and robustness*, not predictive accuracy.\n"]
    L.append("## 1. Data-quality results\n")
    L.append("| Check | Result | Detail |\n|---|---|---|")
    for c in data_report["checks"]:
        L.append(f"| {c['name']} | {'PASS' if c['passed'] else 'FAIL'} | {c['detail']} |")
    L.append(f"\nMissing values (preserved, never imputed): {data_report['missing_counts']}\n")

    L.append("## 2. Automated tests (rules, scenarios, ranking, safety)\n")
    L.append("| Category | Passed | Failed |\n|---|---|---|")
    tp = tf = 0
    for cat, v in sorted(tests["by_category"].items()):
        L.append(f"| {cat} | {v['passed']} | {v['failed']} |")
        tp, tf = tp + v["passed"], tf + v["failed"]
    L.append(f"\n**Total: {tp} passed, {tf} failed** (pass rate {tp / max(tp + tf, 1):.0%}). These are logical/scenario tests with expectations written before running; not hidden-label ground truth.")
    for cat, v in tests["by_category"].items():
        for f in v["failures"]:
            L.append(f"- FAILED in {cat}: `{f}`")

    L.append("\n## 3. Selection sensitivity\n")
    base = sens_overlap[sens_overlap["scenario"] == "baseline"].iloc[0]
    L.append(f"Baseline selects {base['selected']} merchants. Overlap with baseline across {len(sens_overlap) - 1} alternative configurations:\n")
    L.append("| Scenario | Overlap | Jaccard |\n|---|---|---|")
    for _, r in sens_overlap.iterrows():
        L.append(f"| {r['scenario']} | {r['overlap_with_baseline']}/{r['selected']} | {r['jaccard_vs_baseline']} |")
    fragile = sens_summary[sens_summary["selected_in_baseline"] & (sens_summary["scenarios_selected"] < sens_summary["scenarios_total"])]
    L.append(f"\nSelected in baseline but dropped in at least one scenario ({len(fragile)}): " +
             (", ".join(f"{r['merchant_id']} ({r['scenarios_selected']}/{r['scenarios_total']})" for _, r in fragile.iterrows()) or "none"))

    L.append("\n## 4. LLM layer\n")
    if llm_stats is None:
        L.append("The LLM layer was **not run** in this execution (deterministic mode; no paid API calls). Schema-validity rate, guardrail rejections and "
                 "note-label agreement will be reported here when the pipeline is run with `--llm --confirm-paid-calls`.")
    else:
        L.append("```\n" + "\n".join(f"{k}: {v}" for k, v in llm_stats.items()) + "\n```")

    L.append("\n## 5. Known limitations and failure modes\n")
    L += ["- No ground truth: the ranking is unvalidated against real churn. Weights/thresholds are hypotheses (see `config/scoring.yaml`).",
          "- Thresholds were reviewed by inspecting the *score distribution* (clear gap between flagged and unflagged merchants), not tuned to outcomes.",
          "- Success rate is two period aggregates; a recovery inside M4-M6 would be invisible.",
          "- Logins/products/CSAT are snapshots; engagement decline over time cannot be observed.",
          "- Only six months of TPV: seasonality is a rule on a supplied industry list + dip-and-rebound shape, not a learned annual pattern. A seasonal merchant that quietly leaves during a dip could be under-ranked unless another signal fires.",
          "- Eligible merchants outside the 15-contact cap are not contacted this month; they stay on the watchlist.",
          "- Notes are templated phrases; the keyword classifier would need review if real free-text notes were used.",
          "- Value-weighted selection favours larger merchants; see the `risk_first_selection` scenario for the alternative."]
    return "\n".join(L) + "\n"
