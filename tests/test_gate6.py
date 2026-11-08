"""Gate 6: Business Insights (counts beside exposure, denominators, independent evidence) and the evaluation package."""
import io
import json
import re
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

import api.main as main
from api import weights

client = TestClient(main.app)


@pytest.fixture(scope="module")
def sid():
    up = client.post("/api/uploads/sample").json()
    jid = client.post("/api/analyses", json={"upload_id": up["upload_id"], "mapping": up["mapping"], "config": {"capacity": 15}}).json()["job_id"]
    for _ in range(120):
        j = client.get(f"/api/jobs/{jid}").json()
        if j["status"] != "running":
            break
        time.sleep(0.5)
    assert j["status"] == "done", j
    return j["session_id"]


def _ins(sid):
    return client.get(f"/api/sessions/{sid}/insights").json()


def test_driver_shares_add_up_and_match_the_flagged_group(sid):
    x = _ins(sid)
    s = client.get(f"/api/sessions/{sid}").json()["session"]
    flagged = [m for m in s["merchants"] if m["risk_band"] != "low"]
    assert x["flagged_total"] == len(flagged)
    assert sum(d["merchants"] for d in x["drivers"]) == len(flagged)
    assert sum(d["exposure_inr"] for d in x["drivers"]) == pytest.approx(sum(m["annual_value"] for m in flagged))
    assert sum(r["merchants_pct"] for r in x["comparison"]) == pytest.approx(100, abs=0.5)
    assert sum(r["exposure_pct"] for r in x["comparison"]) == pytest.approx(100, abs=0.5)


def test_count_and_exposure_leaders_are_both_reported(sid):
    x = _ins(sid)
    by_count = max(x["comparison"], key=lambda r: r["merchants"])["driver"]
    by_exp = max(x["comparison"], key=lambda r: r["exposure_inr"])["driver"]
    assert x["leader_by_count"] == by_count and x["leader_by_exposure"] == by_exp and x["same_leader"] == (by_count == by_exp)


def test_every_driver_separates_the_selection_rule_from_independent_evidence(sid):
    for d in _ins(sid)["drivers"]:
        assert d["selection_rule"].startswith("Selected because") and "not evidence of a systemic problem" in d["caveat"]
        assert d["corroboration"] and d["counter_evidence"] and d["evidence_strength"] in ("Strong", "Moderate", "Limited")
        for item in d["corroboration"] + d["counter_evidence"]:
            assert 0 <= item["n"] <= item["of"]


def test_commercial_driver_is_never_called_strong_because_it_rests_on_unverified_notes(sid):
    d = next(d for d in _ins(sid)["drivers"] if d["key"] == "commercial")
    assert d["evidence_strength"] == "Limited"


def test_segment_rates_carry_denominators(sid):
    s = client.get(f"/api/sessions/{sid}").json()["session"]
    for g in _ins(sid)["segments"]:
        assert sum(g["bands"][b]["n"] for b in ("high", "medium", "low")) == g["merchants"]
        assert all(g["bands"][b]["of"] == g["merchants"] for b in ("high", "medium", "low")), "every rate must carry its denominator (the UI prints 'n of N')"
        assert g["flagged_rate"]["of"] == g["merchants"]
        assert all(g["missing"][k]["of"] == g["merchants"] for k in ("incomplete", "csat", "note"))
    assert sum(g["merchants"] for g in _ins(sid)["segments"]) == len(s["merchants"])
    assert sum(g["tpv_share_pct"] for g in _ins(sid)["segments"]) == pytest.approx(100, abs=0.5)


def test_commercial_exposure_reports_concentration_and_renewal_windows(sid):
    c = _ins(sid)["commercial"]
    assert sum(w["merchants"] for w in c["renewal_windows"]) == c["of"]
    assert sum(w["exposure_inr"] for w in c["renewal_windows"]) == pytest.approx(c["flagged_exposure_inr"])
    assert sum(r["exposure_inr"] for r in c["segment_concentration"]) == pytest.approx(c["flagged_exposure_inr"])
    assert "Unverified" in c["commercial_evidence"]["status"]


def test_operational_leads_are_ranked_on_stated_criteria_and_claim_no_recovery(sid):
    x = _ins(sid)
    ops = x["operational"]
    assert ops and "No amount recoverable is claimed" in x["operational_order"]
    ranked = [o for o in ops if not o["informational"]]
    assert [o["exposure_inr"] for o in ranked] == sorted([o["exposure_inr"] for o in ranked], reverse=True)
    assert all(o["informational"] for o in ops[len(ranked):])
    for o in ops:
        assert {"evidence_strength", "effort", "scope", "urgent_renewals_60", "merchants"} <= set(o)
        assert not re.search(r"will (recover|save)|expected saving of|recover(s|ed)? Rs", json.dumps(o), re.I)


@pytest.fixture(scope="module")
def package(sid):
    real = weights.stability
    main.weights.stability = lambda *a, **k: real(*a[:5], 12, **{kk: v for kk, v in k.items() if kk != "n"}) if len(a) >= 6 else real(*a, **k)
    try:
        jid = client.post(f"/api/sessions/{sid}/evaluation-package").json()["job_id"]
        for _ in range(240):
            j = client.get(f"/api/jobs/{jid}").json()
            if j["status"] != "running":
                break
            time.sleep(0.5)
    finally:
        main.weights.stability = real
    assert j["status"] == "done", j
    r = client.get(f"/api/sessions/{sid}/evaluation-package")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    return zipfile.ZipFile(io.BytesIO(r.content))


def test_package_contains_every_required_part(package):
    names = set(package.namelist())
    assert {"README.md", "source_audit.md", "scoring_methodology.md", "configuration_snapshot.json", "merchant_register.csv", "top_outreach_list.csv", "playbook_mapping.csv",
            "weight_scenario_comparison.csv", "merchant_rank_stability.csv", "top15_overlap_matrix.csv", "weight_sensitivity_report.md", "manual_validation_log.csv",
            "failure_analysis.md", "limitations.md", "analysis_lineage.json", "evaluation_summary.md"} <= names


def test_package_lineage_records_source_config_and_runtime_ai(package):
    lin = json.loads(package.read("analysis_lineage.json"))
    assert len(lin["source_sha256"]) == 64 and lin["version"].startswith("EDGE") and lin["sheets_used"]["merchants"]
    assert lin["runtime_ai"]["claude_used_in_analysis"] is False and "not a runtime feature" in lin["runtime_ai"]["development"]
    assert "Scenario comparisons" in lin["scenario_vs_behaviour"]
    cfg = json.loads(package.read("configuration_snapshot.json"))
    assert cfg["scoring"]["weights"] and cfg["assumptions_in_force"]["net_revenue_rate"] == 0.01


def test_package_makes_no_accuracy_claims_and_leaks_no_secrets(package):
    text = "\n".join(package.read(n).decode("utf-8", "ignore") for n in package.namelist() if n.endswith((".md", ".json", ".csv")))
    assert "no churn labels" in text.lower()
    assert not re.search(r"\b\d+(\.\d+)?\s*%\s*(accura|precision|recall)", text, re.I) and "AUC of" not in text
    assert "sk-ant-" not in text and "ANTHROPIC_API_KEY" not in text
    assert package.read("playbook_mapping.csv").decode().count("PB-") >= 6
    assert "not a churn predictor" in package.read("evaluation_summary.md").decode()
