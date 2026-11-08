"""API and ingestion tests against the supplied Problem 2 workbook (deterministic mode, no API key needed)."""
import time

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api import ingest, scenarios
from api.main import SAMPLE, app
from src.pipeline import build_frame

client = TestClient(app)


@pytest.fixture(scope="module")
def session_id():
    up = client.post("/api/uploads/sample").json()
    cfg = {"capacity": 15, "priorities": [], "risk_focus": "revenue"}
    jid = client.post("/api/analyses", json={"upload_id": up["upload_id"], "mapping": up["mapping"], "config": cfg}).json()["job_id"]
    for _ in range(120):
        j = client.get(f"/api/jobs/{jid}").json()
        if j["status"] != "running":
            break
        time.sleep(0.5)
    assert j["status"] == "done", j
    return j["session_id"]


def test_sheets_detected_and_fully_mapped():
    up = client.post("/api/uploads/sample").json()
    roles = {s["role"]: s["name"] for s in up["sheets"]}
    assert roles["merchants"] == "P2_Merchants" and roles["playbooks"] == "P2_Playbooks" and roles["assumptions"] == "P2_Assumptions"
    assert up["quality"]["total_records"] == 100 and up["quality"]["unique_ids"] == 100 and not up["quality"]["duplicate_ids"]
    assert not up["quality"]["required_missing"]
    assert up["assumptions"]["unresolved"] == []
    v = up["assumptions"]["values"]
    assert v["net_revenue_rate"] == 0.01 and v["max_outreaches"] == 15 and v["tpv_unit_inr"] == 100000
    assert sorted(v["seasonal_industries"]) == ["Education / Coaching", "Gifting & Festive", "Travel & Hospitality"]


def test_missing_values_identified():
    up = client.post("/api/uploads/sample").json()
    miss = {m["field"]: m["missing"] for m in up["quality"]["missing_by_field"]}
    assert miss["last_csat_1_to_5"] > 0 and miss["account_manager_note"] > 0


def test_renamed_columns_are_mapped_and_unmapped_reported():
    df = pd.DataFrame({"Merchant ID": ["A", "A", "B"], "Name": ["x", "y", "z"], "Monthly TPV M1": [1, 2, "abc"], "CSAT": [4, 9, None]})
    m = ingest.auto_map(list(df.columns))
    assert m["merchant_id"]["source"] == "Merchant ID" and m["last_csat_1_to_5"]["source"] == "CSAT"
    rep = ingest.prepare(df, {k: v["source"] for k, v in m.items()})["report"]
    assert rep["duplicate_ids"] == ["A"] and rep["required_missing"]
    assert any(i["issue"] == "outside 1-5" for i in rep["invalid_records"])


def test_every_merchant_assessed_and_cap_respected(session_id):
    s = client.get(f"/api/sessions/{session_id}").json()["session"]
    assert len(s["merchants"]) == 100
    assert sum(m["selected"] for m in s["merchants"]) <= 15
    assert {m["assessment"]["primary_playbook_id"] for m in s["merchants"]} <= {p["playbook_id"] for p in s["playbooks"]}
    assert all("probability" not in (m["assessment"]["plain_language_reason"] or "").lower() for m in s["merchants"])


def test_baseline_selection_matches_original_engine(session_id):
    s = client.get(f"/api/sessions/{session_id}").json()["session"]
    _, _, df = build_frame()
    want = set(df[df["selected_for_outreach"]]["merchant_id"])
    assert {m["id"] for m in s["merchants"] if m["selected"]} == want


def test_revenue_uses_workbook_assumptions(session_id):
    s = client.get(f"/api/sessions/{session_id}").json()["session"]
    m = s["merchants"][0]
    assert m["annual_value"] == pytest.approx(m["tpv_m6"] * 100000 * 0.01 * 12)
    assert s["commercial"]["lost_inr"] is None


def test_seasonal_and_low_volume_not_high(session_id):
    s = client.get(f"/api/sessions/{session_id}").json()["session"]
    assert all(m["risk_band"] != "high" for m in s["merchants"] if m["seasonal_adjusted"])


def test_scenario_explains_changes(session_id):
    r = client.post(f"/api/sessions/{session_id}/scenario", json={"spec": {"capacity": 15, "priorities": ["renewals"]}}).json()["result"]
    assert set(r["before"]) != set(r["after"]) or r["summary"].startswith("The selection is unchanged")
    assert all(x["reason"] for x in r["moved_in"] + r["moved_out"])


def test_exports_and_state(session_id):
    for kind in ("risk_register", "outreach", "analysis", "insights", "scenarios"):
        assert client.get(f"/api/sessions/{session_id}/export", params={"kind": kind, "format": "csv"}).status_code == 200
    x = client.get(f"/api/sessions/{session_id}/export", params={"kind": "all", "format": "xlsx"})
    assert x.status_code == 200 and x.content[:2] == b"PK"
    st = client.post(f"/api/sessions/{session_id}/state", json={"statuses": {"C2001": "contacted"}}).json()
    assert st["statuses"]["C2001"] == "contacted"


def test_ask_is_grounded(session_id):
    r = client.post(f"/api/sessions/{session_id}/ask", json={"question": "Which 5 merchants should I contact first and why?"}).json()
    assert len(r["merchants"]) == 5 and r["source"] == "computed"


def test_llm_requires_confirmation():
    up = client.post("/api/uploads/sample").json()
    r = client.post("/api/analyses", json={"upload_id": up["upload_id"], "mapping": up["mapping"], "use_llm": True})
    assert r.status_code == 400
