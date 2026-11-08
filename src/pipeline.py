"""End-to-end runner.

    python -m src.pipeline                              # deterministic, no API key needed
    python -m src.pipeline --llm --confirm-paid-calls   # adds Claude reasoning + drafts (paid API calls)
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

import pandas as pd

from src.agent.llm_client import LLMClient
from src.agent.orchestrator import enrich_with_llm, run_deterministic
from src.analytics.feature_engineering import engineer_features
from src.analytics.peer_benchmarking import add_peer_context
from src.analytics.prioritisation import prioritise
from src.analytics.risk_scoring import score_merchants
from src.analytics.sensitivity import run_sensitivity
from src.config import ROOT, load_playbook_cfg, load_scoring, load_settings, resolve
from src.crm.playbook_selector import apply_selection
from src.ingestion.data_validator import build_audit_markdown, validate
from src.ingestion.workbook_loader import load_source
from src.reporting.merchant_reports import write_assessments, write_features
from src.reporting.portfolio_reports import build_portfolio_md
from src.reporting.validation_report import build_report, run_tests


def export_knowledge(src, settings) -> None:
    """Regenerate the playbook/assumption knowledge files straight from the workbook (source of truth)."""
    kdir = resolve(settings["paths"]["knowledge"])
    kdir.mkdir(parents=True, exist_ok=True)
    pb = ["# Playbooks (exact text from P2_Playbooks; auto-generated, do not edit)\n"]
    for _, r in src.playbooks.iterrows():
        pb.append(f"## {r['playbook_id']} - {r['name']}\n- **What happens:** {r['what_happens']}\n- **When it applies:** {r['when_it_applies']}\n")
    (kdir / "playbooks.md").write_text("\n".join(pb), encoding="utf-8")
    asm = ["# Assumptions (exact text from P2_Assumptions; auto-generated, do not edit)\n"]
    asm += [f"- **{r['item']}:** {r['assumption']}" for _, r in src.assumptions.iterrows()]
    (kdir / "assumptions.md").write_text("\n".join(asm) + "\n", encoding="utf-8")


def build_frame(settings=None, scoring=None, pb_cfg=None):
    settings, scoring, pb_cfg = settings or load_settings(), scoring or load_scoring(), pb_cfg or load_playbook_cfg()
    src = load_source(resolve(settings["paths"]["workbook"]), settings["sheets"])
    feats = add_peer_context(engineer_features(src.merchants, settings, scoring))
    df = prioritise(apply_selection(score_merchants(feats, scoring), pb_cfg, src.playbooks), settings)
    return src, feats, df


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="enable Claude reasoning/drafting (paid API calls)")
    ap.add_argument("--confirm-paid-calls", action="store_true", help="required together with --llm")
    ap.add_argument("--skip-tests", action="store_true")
    a = ap.parse_args(argv)

    settings, scoring, pb_cfg = load_settings(), load_scoring(), load_playbook_cfg()
    run_ts = dt.datetime.now().isoformat(timespec="seconds")
    out = resolve(settings["paths"]["outputs"]); out.mkdir(exist_ok=True)
    docs = resolve(settings["paths"]["docs"]); docs.mkdir(exist_ok=True)

    src, feats, df = build_frame(settings, scoring, pb_cfg)
    export_knowledge(src, settings)
    data_report = validate(src, settings)
    (docs / "source_data_audit.md").write_text(build_audit_markdown(src, data_report, settings), encoding="utf-8")
    print(f"[1/6] Data: {len(src.merchants)} merchants, validation {'OK' if data_report['all_passed'] else 'FAILED'}")
    if not data_report["all_passed"]:
        for c in data_report["checks"]:
            if not c["passed"]:
                print("   FAILED:", c["name"], c["detail"])
        return 2

    long, summ, overlap = run_sensitivity(feats, scoring, pb_cfg, src.playbooks, settings)
    long.merge(overlap[["scenario", "jaccard_vs_baseline"]], on="scenario").to_csv(out / "sensitivity_analysis.csv", index=False)
    summ.to_csv(out / "sensitivity_merchant_stability.csv", index=False)
    print(f"[2/6] Scored; {int((df['risk_band'] == 'high').sum())} high, {int((df['risk_band'] == 'medium').sum())} medium, "
          f"{int(df['selected_for_outreach'].sum())} selected for outreach; sensitivity over {len(overlap)} scenarios")

    assessments = run_deterministic(df, pb_cfg, settings, scoring)
    llm_stats = None
    if a.llm:
        client = LLMClient(settings)
        print("[3/6] LLM:", client.status())
        n_calls = len(assessments) + int(df["selected_for_outreach"].sum())
        print(f"      Planned paid calls: ~{n_calls} (cap {client.max_calls}); ~1.5k input + <=1.5k output tokens each, system prompt cached.")
        if not a.confirm_paid_calls:
            print("      Refusing: pass --confirm-paid-calls to authorise paid API calls. Continuing in deterministic mode.")
        elif not client.available:
            print("      No API key configured in .env; continuing in deterministic mode.")
        else:
            llm_stats = enrich_with_llm(assessments, df, src.playbooks, client, settings)
            llm_stats.update({f"api_{k}": v for k, v in client.stats.items()})
            llm_stats["schema_validity_rate"] = round(client.stats["schema_valid"] / max(client.stats["attempts"], 1), 3)
    else:
        print("[3/6] LLM layer skipped (deterministic mode)")

    write_features(df, out / "merchant_features.csv")
    write_assessments(assessments, out / "merchant_risk_assessments.json", out / "merchant_risk_assessments.csv", out / "top_15_outreach.csv")
    (out / "portfolio_insights.md").write_text(build_portfolio_md(df, settings, run_ts, summ, overlap), encoding="utf-8")
    print("[4/6] Wrote features, assessments (JSON+CSV), top-15 and portfolio insights")

    if not a.skip_tests:
        tests = run_tests()
        (out / "validation_report.md").write_text(
            build_report(tests, data_report, df, summ, overlap, llm_stats, run_ts, f"{settings['config_version']} / scoring {scoring['scoring_version']}"),
            encoding="utf-8")
        tp = sum(v["passed"] for v in tests["by_category"].values()); tf = sum(v["failed"] for v in tests["by_category"].values())
        print(f"[5/6] Tests: {tp} passed, {tf} failed")
    print("[6/6] Done. Outputs in", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
