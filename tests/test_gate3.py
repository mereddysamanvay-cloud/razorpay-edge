"""Gate 3: weight scenarios, ranking robustness and the Validation Lab (deterministic, no API key)."""
import hashlib
import time

import pytest
from fastapi.testclient import TestClient

from api import store, validation, weights
from api.main import app
from src.config import load_scoring

client = TestClient(app)


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


def _session_hash(sid):
    return hashlib.md5(open(store.SESSIONS / sid / "session.json", "rb").read()).hexdigest()


def test_preset_weights_all_sum_to_100():
    for name, vals in weights.PRESETS.items():
        assert sum(vals) == 100, name


@pytest.mark.parametrize("w,msg", [
    ({"performance": 30, "relationship": 40, "engagement": 15, "commercial": 20}, "100%"),
    ({"performance": -5, "relationship": 45, "engagement": 30, "commercial": 30}, "negative"),
    ({"performance": 100, "relationship": 0}, "Provide"),
])
def test_invalid_weights_are_rejected(w, msg):
    with pytest.raises(ValueError, match=msg):
        weights.validate_weights(w)


def test_grid_is_deterministic_bounded_and_sums_to_100():
    a, b = weights.grid(120), weights.grid(120)
    assert a == b
    assert weights.grid(120, seed=1) != a
    lo, hi = weights.WEIGHT_BOUNDS
    for c in a:
        assert abs(sum(c["weights"].values()) - 100) < 0.11 and all(lo <= v <= hi for v in c["weights"].values())
        for k, (plo, phi) in weights.PARAM_BOUNDS.items():
            assert plo <= c["params"][k] <= phi


def test_baseline_weights_reproduce_the_live_shortlist(sid):
    s = client.get(f"/api/sessions/{sid}").json()["session"]
    live = {m["id"] for m in s["merchants"] if m["selected"]}
    r = client.post(f"/api/sessions/{sid}/scenario", json={"spec": {"weights": weights.preset_weights("Baseline")}, "compare_to": "current"}).json()["result"]
    assert set(r["after"]) == live and r["moved_in"] == [] and r["moved_out"] == [] and r["weights"]["changed"] is False


def test_weight_preview_does_not_change_the_live_shortlist(sid):
    before = _session_hash(sid)
    r = client.post(f"/api/sessions/{sid}/scenario", json={"spec": {"weights": weights.preset_weights("Commercial-led")}, "compare_to": "current"})
    assert r.status_code == 200 and r.json()["result"]["weights"]["changed"] is True
    assert _session_hash(sid) == before


def test_moving_in_and_out_match_set_differences_and_capacity(sid):
    r = client.post(f"/api/sessions/{sid}/scenario", json={"spec": {"weights": weights.preset_weights("Equal"), "capacity": 10}, "compare_to": "current"}).json()["result"]
    assert len(r["after"]) <= 10
    assert {x["merchant_id"] for x in r["moved_in"]} == set(r["after"]) - set(r["before"])
    assert {x["merchant_id"] for x in r["moved_out"]} == set(r["before"]) - set(r["after"])
    assert r["weights"]["overlap"] == len(set(r["after"]) & set(r["before"]))


def test_api_rejects_weights_not_summing_to_100(sid):
    r = client.post(f"/api/sessions/{sid}/scenario", json={"spec": {"weights": {"performance": 30, "relationship": 40, "engagement": 15, "commercial": 20}}})
    assert r.status_code == 400 and "100%" in r.json()["detail"]


def test_scenario_scores_are_deterministic(sid):
    spec = {"spec": {"weights": weights.preset_weights("Relationship-led")}, "compare_to": "current"}
    a, b = (client.post(f"/api/sessions/{sid}/scenario", json=spec).json() for _ in range(2))
    assert a["ranking"] == b["ranking"]


def test_stability_metrics_and_classes(sid):
    s = store.load_session(sid)
    out = weights.stability(store.load_frame(sid), load_scoring(), s["assumptions"], weights.playbook_frame(s["playbooks"]), 15, n=12)
    k = out["configurations"]
    assert k == 12 + len(weights.PRESETS)
    for r in out["merchants"]:
        assert r["selection_frequency"] == pytest.approx(r["times_selected"] / k, abs=1e-3)
        if r["classification"] == "Robust priority":
            assert r["selection_frequency"] >= weights.ROBUST_AT
        if r["classification"] == "Low priority":
            assert r["selection_frequency"] <= weights.LOW_AT and not r["baseline_selected"]
        if r["best_rank"]:
            assert r["best_rank"] <= r["avg_rank"] <= r["worst_rank"]
    for sc in out["scenarios"]:
        assert len(sc["top_n"]) <= 15
        assert sc["overlap_with_baseline"] == len(set(sc["top_n"]) & set(out["baseline_top"]))
        assert set(sc["moved_in"]) == set(sc["top_n"]) - set(out["baseline_top"])
    assert all(out["overlap_matrix"][a][a] == len(next(x for x in out["scenarios"] if x["scenario"] == a)["top_n"]) for a in out["overlap_matrix"])
    again = weights.stability(store.load_frame(sid), load_scoring(), s["assumptions"], weights.playbook_frame(s["playbooks"]), 15, n=12)
    assert again == out


def test_apply_weights_creates_a_new_analysis_and_leaves_the_original(sid):
    before = _session_hash(sid)
    jid = client.post(f"/api/sessions/{sid}/apply-weights", json={"spec": {"weights": weights.preset_weights("Performance-led")}}).json()["job_id"]
    for _ in range(120):
        j = client.get(f"/api/jobs/{jid}").json()
        if j["status"] != "running":
            break
        time.sleep(0.5)
    assert j["status"] == "done" and j["session_id"] != sid
    new = store.load_session(j["session_id"])
    assert new["weights_pct"] == {"performance": 45.0, "relationship": 20.0, "engagement": 15.0, "commercial": 20.0}
    assert _session_hash(sid) == before


def test_validation_lab_has_20_documented_cases_in_four_categories(sid):
    v = client.get(f"/api/sessions/{sid}/validation").json()
    done = [c for c in v["cases"] if c.get("merchant_id")]
    assert len(done) >= 20
    cats = {c["category"] for c in done}
    assert cats == {"Likely high concern", "Decoy", "Conflicting signals", "Borderline / missing data"}
    for cat in cats:
        assert sum(c["category"] == cat for c in done) == 5
    for c in done:
        assert c["expectation"] and c["checks"] is not None and c["status"] in ("Pass", "Fail", "Needs review")
        assert "ground truth" in c["expectation_basis"].lower()
    assert {t["test"] for t in v["coverage"]} >= {"Seasonal TPV decline", "Contact-person change", "Missing CSAT", "TPV rebound"}
    assert "accuracy" in v["claims"].lower() and "no churn labels" in v["claims"].lower()


def test_validation_failures_carry_stage_and_corrective_action():
    m = {"id": "X", "name": "X", "segment": "Small", "industry": "I", "risk_band": "high", "risk_label": "High risk", "risk_score": 70.0, "eligible": True, "selected": True, "rank": 1,
         "dims": {"performance": 90, "relationship": 0, "engagement": 0, "commercial": 0}, "completeness": 100, "missing_fields": [], "csat_missing": False, "note": "n", "note_signals": [], "tpv": [10, 10, 10, 7, 6, 5],
         "tpv_change_pct": -30, "m6_vs_m5_pct": -10, "success_drop_pp": 0, "seasonal_industry": True, "dip_and_rebound": True, "logins": 20, "csat": 4, "unresolved": 0, "tickets": 1,
         "consecutive_declines": 3, "primary_dimension": "performance", "playbooks_not_selected": [],
         "assessment": {"supporting_evidence": [], "mitigating_signals": [], "contradictory_signals": [], "additional_checks_for_csm": [], "primary_playbook_id": "PB-1",
                        "primary_playbook_name": "Performance deep-dive", "primary_risk_driver": "Performance", "secondary_playbook_id": None}}
    v = validation.build({"merchants": [m]})
    b1 = next(c for c in v["cases"] if c["case_id"] == "B1")
    assert b1["status"] == "Fail" and b1["failure_stage"] and b1["corrective_action"]
