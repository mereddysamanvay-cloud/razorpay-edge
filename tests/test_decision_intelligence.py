"""Decision Intelligence content, demo workspace, P2 sheet selection, Anthropic status masking and the related corrections.
No test here makes a paid API call: the Anthropic client is always a stub."""
import hashlib
import io
import json
import re
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import api.main as main
from api import ingest, intelligence, store
from src.config import ROOT, load_playbook_cfg, load_scoring
from tests.helpers import run_one

client = TestClient(main.app)
SECRET = "sk-ant-THIS-MUST-NEVER-APPEAR-1234567890"


@pytest.fixture(scope="module")
def demo():
    r = client.post("/api/demo")
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


# ---------------------------------------------------------------- content is generated from the real configuration
def test_intelligence_weights_bands_and_formula_constants_come_from_the_config(demo):
    d = client.get("/api/intelligence", params={"session": demo}).json()
    sc = load_scoring()
    assert d["weights"] == {k: sc["weights"][k] for k in ("performance", "relationship", "engagement", "commercial")}
    assert d["weights_sum"] == pytest.approx(1.0) and d["bands"] == sc["bands"]
    final = next(e for e in d["equations"] if e["key"] == "final")["formula"]
    assert f"{sc['aggregation']['weighted_share']:g} × WM" in final
    assert d["generated_from"]["scoring_version"] == sc["scoring_version"]


def test_every_equation_threshold_matches_the_scoring_config(demo):
    d = client.get("/api/intelligence", params={"session": demo}).json()
    sc = load_scoring()
    eq = {e["key"]: e for e in d["equations"]}
    assert f"{sc['tpv']['zero_at_pct']:g}%" in eq["lin"]["plain"] and f"{sc['tpv']['full_at_pct']:g}%" in eq["lin"]["plain"]
    assert f"{sc['success']['zero_at_pp']:g}pp" in eq["lin"]["plain"]
    assert f"High if Score ≥ {sc['bands']['high']:g}" in eq["bands"]["formula"] and f"Moderate if Score ≥ {sc['bands']['medium']:g}" in eq["bands"]["formula"]
    assert "min(100" in eq["final"]["formula"] and "Confidence factor" in eq["priority"]["formula"]
    assert "not min-max" in eq["lin"]["plain"].lower()


def test_worked_score_example_reconciles_with_the_stored_score(demo):
    w = client.get("/api/intelligence", params={"session": demo}).json()["worked"]["score"]
    total = min(100, w["share"] * w["weighted_mean"] + (1 - w["share"]) * w["strongest"] + w["bonus"])
    assert total == pytest.approx(w["total"], abs=0.06)
    assert sum(w["weighted_points"].values()) == pytest.approx(w["weighted_mean"], abs=0.02)


def test_priority_example_is_a_real_pair_where_lower_risk_ranks_higher(demo):
    p = client.get("/api/intelligence", params={"session": demo}).json()["worked"]["priority"]
    assert p and p["higher_priority"]["score"] < p["higher_risk"]["score"] and p["higher_priority"]["index"] > p["higher_risk"]["index"]
    s = client.get(f"/api/sessions/{demo}").json()["session"]
    ids = {m["id"] for m in s["merchants"]}
    assert p["higher_priority"]["id"] in ids and p["higher_risk"]["id"] in ids


def test_decision_tree_reflects_the_actual_playbook_rules_not_a_fixed_order(demo):
    d = client.get("/api/intelligence", params={"session": demo}).json()
    t = {n["id"]: n for n in d["tree"]}
    cfg = load_playbook_cfg()["triggers"]
    assert f"{abs(cfg['PB-1']['max_success_drop_pp']):g}pp" in t["n4"]["condition"] and f"{cfg['PB-3']['max_renewal_days']} days" in t["n4"]["condition"]
    assert "tested independently" in t["n4"]["question"].lower() and "highest fit" in t["n5"]["condition"].lower()
    assert load_playbook_cfg()["tie_break_order"][0] in t["n5"]["condition"]
    assert "NOT scored as worse" in t["n1"]["no_label"]
    ids = {m["id"] for m in client.get(f"/api/sessions/{demo}").json()["session"]["merchants"]}
    assert all(n["example"]["id"] in ids for n in d["tree"] if n["example"])


def test_playbook_explainer_lists_exactly_the_six_workbook_playbooks(demo):
    pb = client.get("/api/intelligence", params={"session": demo}).json()["playbooks"]
    assert [p["id"] for p in pb] == ["PB-1", "PB-2", "PB-3", "PB-4", "PB-5", "PB-6"]
    assert all(p["what_happens"] and p["rule"] and p["concern"] for p in pb)


def test_no_machine_learning_or_probability_claims_and_missing_data_is_unknown(demo):
    d = client.get("/api/intelligence", params={"session": demo}).json()
    text = json.dumps({k: d[k] for k in ("architecture", "equations", "glossary", "human", "validation", "tree")})
    assert not re.search(r"\b\d+\s*%\s*(chance|probability|likelihood)", text, re.I)
    assert {"Machine learning", "Logistic regression", "Random forests", "Gradient boosting", "Clustering", "Survival analysis"} <= set(d["not_used"])
    assert "rule-based early-warning and decision-support system" in d["human"]["statement"] and "cannot currently be established" in d["human"]["statement"]
    assert any("Missing CSAT ≠ Poor CSAT" == e["claim"] for e in d["validation"]["unknown_examples"])
    feats = json.dumps(d["features"])
    assert "no monthly success-rate trend" in feats.lower() or "TWO period averages" in feats
    assert "no history" in feats.lower() or "no adoption history" in feats.lower()


def test_pipeline_has_the_twelve_stages_in_the_required_order(demo):
    d = client.get("/api/intelligence", params={"session": demo}).json()
    assert [a["id"] for a in d["architecture"]] == ["source", "validate", "features", "context", "scoring", "classify", "rootcause", "priority", "playbook", "draft", "review", "outcome"]
    assert all(a["what"] and a["fields"] and a["rule"] and a["why"] and a["output"] for a in d["architecture"])


# ---------------------------------------------------------------- demo workspace
def test_demo_workspace_opens_with_problem2_data_only(demo):
    s = client.get(f"/api/sessions/{demo}").json()["session"]
    assert s["demo"] is True and s["merchant_count"] == 100 and s["kpis"]["selected"] == 15
    assert s["sheets"]["merchants"] == "P2_Merchants" and s["sheets"]["playbooks"] == "P2_Playbooks" and s["sheets"]["assumptions"] == "P2_Assumptions"
    assert sorted(p["playbook_id"] for p in s["playbooks"]) == ["PB-1", "PB-2", "PB-3", "PB-4", "PB-5", "PB-6"]
    assert s["assumptions"]["max_outreaches"] == 15 and s["assumptions"]["net_revenue_rate"] == 0.01


def test_demo_workbook_contains_only_the_three_problem2_sheets():
    import pandas as pd
    assert pd.ExcelFile(ROOT / "demo" / "Problem2_Demo_Workbook.xlsx").sheet_names == ["P2_Merchants", "P2_Playbooks", "P2_Assumptions"]


def test_uploading_a_workbook_never_overwrites_the_demo_and_the_demo_cannot_be_deleted(demo):
    path = store.SESSIONS / demo / "session.json"
    before = hashlib.md5(path.read_bytes()).hexdigest()
    up = client.post("/api/uploads/sample").json()
    jid = client.post("/api/analyses", json={"upload_id": up["upload_id"], "mapping": up["mapping"], "name": "My own upload"}).json()["job_id"]
    for _ in range(120):
        j = client.get(f"/api/jobs/{jid}").json()
        if j["status"] != "running":
            break
        time.sleep(0.5)
    assert j["status"] == "done" and j["session_id"] != demo
    assert hashlib.md5(path.read_bytes()).hexdigest() == before
    assert client.delete(f"/api/sessions/{demo}").status_code == 409
    assert store.load_session(demo) is not None


# ---------------------------------------------------------------- P2 worksheet identification
SAMPLE = ROOT / "data" / "source" / "Buildathon_Student_Data_Pack.xlsx"


@pytest.mark.skipif(not SAMPLE.exists(), reason="full data pack not present")
def test_combined_workbook_selects_p2_and_excludes_p1_and_p3_with_a_reason():
    sheets = ingest.classify_sheets(SAMPLE)
    by = {s["name"]: s for s in sheets}
    assert [by[n]["role"] for n in ("P2_Merchants", "P2_Playbooks", "P2_Assumptions")] == ["merchants", "playbooks", "assumptions"]
    for n in ("P1_Tickets", "P1_Merchants", "P1_KnowledgeBase", "P3_Applications", "P3_RejectionCatalog"):
        assert by[n]["role"] == "excluded" and "not part of the Problem 2 analysis" in by[n]["reason"]
    up = client.post("/api/uploads/sample").json()
    sel = up["sheet_selection"]
    assert {x["name"] for x in sel["selected"]} == {"P2_Merchants", "P2_Playbooks", "P2_Assumptions"}
    assert {x["name"] for x in sel["excluded"]} >= {"P1_Merchants", "P3_Applications"} and sel["overridden_into_other_problem"] == []


@pytest.mark.skipif(not SAMPLE.exists(), reason="full data pack not present")
def test_choosing_a_problem1_sheet_by_hand_is_flagged_not_silent():
    up = client.post("/api/uploads/sample").json()
    r = client.post(f"/api/uploads/{up['upload_id']}/inspect", json={"merchant_sheet": "P1_Merchants"}).json()
    assert "P1_Merchants" in r["sheet_selection"]["overridden_into_other_problem"]


def test_problem_tag_parser():
    assert [ingest.problem_of(n) for n in ("P1_Tickets", "P2_Merchants", "Problem 3 data", "Merchants", "README")] == [1, 2, 3, None, None]


# ---------------------------------------------------------------- pricing / MDR objection correction
def test_pricing_objection_alone_now_scores_in_the_commercial_dimension_and_triggers_pb3():
    r = run_one(account_manager_note="Merchant says the MDR is too expensive", days_to_contract_renewal=40.0)
    assert r["note_pricing_objection"] and r["dim_commercial"] >= 50
    assert "PB-3" in r["playbook_triggers"]


def test_supplied_workbook_results_are_unchanged_by_the_correction(demo):
    k = client.get(f"/api/sessions/{demo}").json()["session"]["kpis"]
    assert (k["high"], k["medium"], k["low"]) == (13, 11, 76)


# ---------------------------------------------------------------- Anthropic status: masked and honest
class StubClient:
    available = True
    model = "claude-test"
    _key = SECRET

    def __init__(self, exc=None):
        self.exc = exc
        self.messages = self

    def _sdk(self):
        return self

    def create(self, **_):
        if self.exc:
            raise self.exc
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="ready")])


def _use(monkeypatch, stub, tmp_path):
    monkeypatch.setattr(main, "llm", lambda: stub)
    monkeypatch.setattr(main, "LLM_STATE_FILE", tmp_path / "llm_status.json")


def test_status_without_a_key_says_unavailable_and_never_claims_success(monkeypatch, tmp_path):
    _use(monkeypatch, SimpleNamespace(available=False, model="claude-test"), tmp_path)
    s = client.get("/api/llm/status").json()
    assert s["key_configured"] is False and s["authentication_test"] == "Not run" and s["ai_assisted_analysis"].startswith("Unavailable")


def test_key_present_but_untested_is_not_reported_as_working(monkeypatch, tmp_path):
    _use(monkeypatch, StubClient(), tmp_path)
    s = client.get("/api/llm/status").json()
    assert s["key_configured"] is True and s["authentication_test"] == "Not run" and s["ai_assisted_analysis"].startswith("Unverified")


def test_successful_test_updates_the_status_and_the_secret_never_appears(monkeypatch, tmp_path):
    _use(monkeypatch, StubClient(), tmp_path)
    r = client.post("/api/llm/test").json()
    assert r["ok"] is True and r["status"]["authentication_test"] == "Successful" and r["status"]["ai_assisted_analysis"] == "Available"
    assert r["status"]["last_test"]["ok"] is True and r["status"]["key_displayed"] is False
    assert SECRET not in json.dumps(r) and SECRET not in json.dumps(client.get("/api/llm/status").json())
    assert SECRET not in (tmp_path / "llm_status.json").read_text()


@pytest.mark.parametrize("name,category", [("AuthenticationError", "authentication_failed"), ("NotFoundError", "model_not_found"), ("RateLimitError", "rate_limited"),
                                           ("APIConnectionError", "network_error"), ("BadRequestError", "bad_request"), ("Surprise", "unexpected_error")])
def test_failures_report_a_category_and_never_the_provider_text(monkeypatch, tmp_path, name, category):
    exc = type(name, (Exception,), {})(f"request failed with key {SECRET}")
    _use(monkeypatch, StubClient(exc), tmp_path)
    r = client.post("/api/llm/test").json()
    assert r["ok"] is False and r["category"] == category and r["status"]["authentication_test"] == "Failed"
    assert SECRET not in json.dumps(r) and r["status"]["ai_assisted_analysis"] != "Available"


def test_serverless_runtime_is_named_and_a_local_key_is_not_assumed_for_the_deployment(monkeypatch, tmp_path):
    _use(monkeypatch, StubClient(), tmp_path)
    monkeypatch.setattr(main, "SERVERLESS", True)
    s = client.get("/api/llm/status").json()
    assert s["runtime"].startswith("Vercel") and "Vercel" in s["key_source"] and "deployed server" in s["note"]


def test_env_file_and_secrets_are_not_tracked_by_git():
    ignore = (ROOT / ".gitignore").read_text()
    assert ".env" in ignore.splitlines()
    for p in (ROOT / "web" / "src").rglob("*.ts*"):
        assert "ANTHROPIC_API_KEY" not in p.read_text(encoding="utf-8", errors="ignore") or p.name == "Settings.tsx", p.name  # the name appears only as a label
    assert "VITE_ANTHROPIC" not in "".join(p.read_text(encoding="utf-8", errors="ignore") for p in (ROOT / "web").glob("*.*") if p.suffix in (".json", ".ts", ".js"))


# ---------------------------------------------------------------- reports, insights, robustness additions
def test_artifacts_distinguish_generated_from_not_yet_generated(demo):
    rows = {r["key"]: r for r in client.get(f"/api/sessions/{demo}/artifacts").json()["rows"]}
    assert rows["evaluation_package"]["primary"] is True and rows["validation"]["generated"] is True
    assert isinstance(rows["robustness"]["generated"], bool) and isinstance(rows["evaluation_package"]["generated"], bool)


def test_package_readme_explains_every_file(demo):
    jid = client.post(f"/api/sessions/{demo}/evaluation-package").json()["job_id"]
    for _ in range(240):
        j = client.get(f"/api/jobs/{jid}").json()
        if j["status"] != "running":
            break
        time.sleep(0.5)
    assert j["status"] == "done", j
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/api/sessions/{demo}/evaluation-package").content))
    readme = z.read("README.md").decode()
    for name in z.namelist():
        if name != "README.md":
            assert f"`{name}`" in readme and f"| `{name}` | Generated from the saved analysis. |" not in readme, name


def test_operational_leads_name_an_owner_and_an_implication_without_causal_claims(demo):
    for o in client.get(f"/api/sessions/{demo}/insights").json()["operational"]:
        assert o["owner"] and o["implication"]
        assert not re.search(r"\b(caused by|because of|due to)\b", o["implication"] + o["suggestion"], re.I)


def test_scenario_comparison_reports_rank_movement(demo):
    from api import weights
    s = store.load_session(demo)
    out = weights.stability(store.load_frame(demo), load_scoring(), s["assumptions"], weights.playbook_frame(s["playbooks"]), 15, n=10)
    base = out["scenarios"][0]
    assert base["avg_rank_movement"] == 0 and base["max_rank_movement"] == 0
    for sc in out["scenarios"][1:]:
        assert sc["avg_rank_movement"] >= 0 and sc["max_rank_movement"] >= sc["avg_rank_movement"] and len(sc["top_movers"]) <= 5
