"""Vercel mode: saved files go to a temp dir, and background work runs before the reply (a serverless function can be frozen once it responds).
Runs in a subprocess with VERCEL=1 so the main test process keeps its normal settings."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from src.config import ROOT

SAMPLE = ROOT / "data" / "source" / "Buildathon_Student_Data_Pack.xlsx"

SCRIPT = r"""
import sys, io, tempfile
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from fastapi.testclient import TestClient
from src.config import DATA_DIR, SERVERLESS
import api.main as main
assert SERVERLESS and str(DATA_DIR).startswith(tempfile.gettempdir()), DATA_DIR
c = TestClient(main.app)
r = c.post("/api/uploads", files={"file": ("book.xlsx", open(sys.argv[2], "rb"), "application/octet-stream")})
up = r.json(); assert r.status_code == 200, r.text
jid = c.post("/api/analyses", json={"upload_id": up["upload_id"], "mapping": up["mapping"], "config": {"capacity": 15}}).json()["job_id"]
j = c.get(f"/api/jobs/{jid}").json()
assert j["status"] == "done", j          # finished before the reply, no polling needed
sid = j["session_id"]
s = c.get(f"/api/sessions/{sid}").json()["session"]
assert s["kpis"]["selected"] == 15 and str(main.store.SESSIONS).startswith(tempfile.gettempdir())
j2 = c.get("/api/jobs/" + c.post(f"/api/sessions/{sid}/stability", json={"n": 100}).json()["job_id"]).json()
assert j2["status"] == "done", j2
assert c.get(f"/api/sessions/{sid}/export", params={"kind": "risk_register", "format": "csv"}).status_code == 200
print("SERVERLESS_OK")
"""


@pytest.mark.skipif(not SAMPLE.exists(), reason="sample workbook not present")
def test_analysis_and_robustness_run_inline_with_temp_storage():
    env = {**os.environ, "VERCEL": "1"}
    env.pop("EDGE_DATA_DIR", None)
    out = subprocess.run([sys.executable, "-c", SCRIPT, str(ROOT), str(SAMPLE)], env=env, capture_output=True, text=True, timeout=240)
    assert "SERVERLESS_OK" in out.stdout, out.stdout[-800:] + out.stderr[-1500:]


def test_vercel_config_is_valid_and_routes_api_before_the_spa():
    import json
    cfg = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert any(b["use"] == "@vercel/python" and b["src"] == "api/main.py" for b in cfg["builds"])
    assert any(b["use"] == "@vercel/static-build" for b in cfg["builds"])
    srcs = [r.get("src") for r in cfg["routes"] if "src" in r]
    assert srcs[0] == "/api/(.*)" and srcs[-1] == "/(.*)"
    # @vercel/static-build publishes web/package.json output under /web, so the UI routes must point there (a bare /index.html gives 404 NOT_FOUND)
    dests = {r["src"]: r["dest"] for r in cfg["routes"] if "src" in r}
    assert dests["/(.*)"] == "/web/index.html" and dests["/assets/(.*)"].startswith("/web/assets/")
    ignore = (ROOT / ".vercelignore").read_text(encoding="utf-8")
    assert ".env" in ignore and "data" in ignore.split() and "node_modules" in ignore


def test_runtime_requirements_are_lean_and_hold_no_test_tools():
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "pytest" not in req and "fastapi" in req and "pandas" in req
