"""Razorpay EDGE API. Run:  python -m uvicorn api.main:app --port 8000"""
from __future__ import annotations

import base64
import json
import os
import secrets
import shutil
import threading
import time
import uuid
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api import ai_disclosure as ai_mod
from api import evaluation, insights_ext, workflow
from api import ask as ask_mod
from api import exporter, ingest, runner, scenarios, store, validation, weights
from api.assumptions import KEYS, parse_assumptions
from src.agent.llm_client import LLMClient
from src.config import ROOT, load_scoring, load_settings

MAX_MB = 25
SAMPLE = ROOT / "data" / "source" / "Buildathon_Student_Data_Pack.xlsx"
app = FastAPI(title="Razorpay EDGE API")
JOBS: dict[str, dict] = {}


@app.middleware("http")
async def access_gate(request, call_next):
    """Optional shared login for public previews. Off unless EDGE_ACCESS_PASSWORD is set."""
    pw = os.environ.get("EDGE_ACCESS_PASSWORD")
    if not pw or request.url.path == "/api/health":
        return await call_next(request)
    try:
        user, _, given = base64.b64decode(request.headers.get("authorization", "")[6:]).decode().partition(":")
    except Exception:
        user, given = "", ""
    if secrets.compare_digest(given, pw) and secrets.compare_digest(user, os.environ.get("EDGE_ACCESS_USER", "edge")):
        return await call_next(request)
    return Response("Authentication required", status_code=401, headers={"WWW-Authenticate": 'Basic realm="Razorpay EDGE"'})
SETTINGS_FILE = ROOT / "data" / "app_settings.json"


def llm() -> LLMClient:
    return LLMClient(load_settings())


def app_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"default_capacity": None, "default_risk_focus": "revenue", "assumption_overrides": {}}


@app.get("/api/health")
def health():
    c = llm()
    return {"ok": True, "llm_available": c.available, "model": c.model, "sample_available": SAMPLE.exists()}


# ---------------------------------------------------------------- upload + inspection
def _find_upload(upload_id: str) -> Path:
    d = store.upload_dir(upload_id)
    files = [f for f in d.glob("*") if f.is_file()] if d.exists() else []
    if not files:
        raise HTTPException(404, "Upload not found. Please upload the workbook again.")
    return files[0]


def _load_sheet(path: Path, name: str, header_row: int | None = None) -> pd.DataFrame:
    raw = ingest.read_raw(path, name)
    return ingest.frame_from_raw(raw, ingest.detect_header(raw) if header_row is None else header_row)


def inspect(upload_id: str, body: dict | None = None) -> dict:
    body = body or {}
    path = _find_upload(upload_id)
    sheets = ingest.classify_sheets(path)
    role = lambda r: next((s["name"] for s in sheets if s["role"] == r), None)
    m_name = body.get("merchant_sheet") or role("merchants")
    pb_name = body.get("playbook_sheet") or role("playbooks")
    as_name = body.get("assumption_sheet") or role("assumptions")
    out = {"upload_id": upload_id, "file_name": path.name, "size_kb": round(path.stat().st_size / 1024, 1), "sheets": sheets,
           "merchant_sheet": m_name, "playbook_sheet": pb_name, "assumption_sheet": as_name}
    if not m_name:
        out["error"] = "No sheet that looks like merchant data was found. Select the sheet that holds one row per merchant."
        return out
    df = _load_sheet(path, m_name)
    auto = ingest.auto_map(list(df.columns))
    mapping = {k: (body.get("mapping") or {}).get(k, v["source"]) for k, v in auto.items()}
    mapping = {k: (v if v in df.columns else None) for k, v in mapping.items()}
    prep = ingest.prepare(df, mapping)
    out.update({
        "columns": ingest.column_profiles(df), "fields": [{**{k: f[k] for k in ("key", "label", "required", "kind")}, "source": mapping.get(f["key"]),
                    "status": ("mapped" if mapping.get(f["key"]) and auto[f["key"]]["source"] == mapping.get(f["key"]) and auto[f["key"]]["confidence"] == "exact"
                               else "confirm" if mapping.get(f["key"]) else "missing")} for f in ingest.FIELDS],
        "quality": prep["report"], "preview": ingest.df_preview(df), "mapping": mapping,
    })
    inds = sorted({v for v in prep["clean"]["industry"].dropna()}) if len(prep["clean"]) else []
    ass_df = _load_sheet(path, as_name) if as_name else None
    values, unresolved, prov = parse_assumptions(ass_df, inds)
    out["assumptions"] = {"values": values, "unresolved": unresolved, "provenance": prov, "labels": KEYS, "present": as_name is not None}
    out["playbooks"] = {"present": pb_name is not None, "rows": _load_sheet(path, pb_name).astype(str).to_dict("records") if pb_name else []}
    out["analysable"] = prep["report"]["analysable_records"]
    return out


@app.post("/api/uploads")
async def upload(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".xlsx", ".xls", ".csv"):
        raise HTTPException(400, f"Unsupported file type '{ext or 'unknown'}'. Upload .xlsx, .xls or .csv.")
    data = await file.read()
    if len(data) > MAX_MB * 1024 * 1024:
        raise HTTPException(413, f"File is larger than {MAX_MB} MB.")
    uid = uuid.uuid4().hex[:10]
    d = store.upload_dir(uid)
    d.mkdir(parents=True, exist_ok=True)
    (d / Path(file.filename).name).write_bytes(data)
    try:
        return inspect(uid)
    except Exception as exc:
        raise HTTPException(422, f"Could not read this workbook: {type(exc).__name__}: {exc}")


@app.post("/api/uploads/sample")
def upload_sample():
    if not SAMPLE.exists():
        raise HTTPException(404, "The bundled Problem 2 workbook is not present.")
    uid = uuid.uuid4().hex[:10]
    d = store.upload_dir(uid)
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(SAMPLE, d / SAMPLE.name)
    return inspect(uid)


class InspectBody(BaseModel):
    merchant_sheet: str | None = None
    playbook_sheet: str | None = None
    assumption_sheet: str | None = None
    mapping: dict[str, str | None] | None = None


@app.post("/api/uploads/{upload_id}/inspect")
def reinspect(upload_id: str, body: InspectBody):
    return inspect(upload_id, body.model_dump())


# ---------------------------------------------------------------- analysis jobs
class AnalyseBody(BaseModel):
    upload_id: str
    name: str | None = None
    merchant_sheet: str | None = None
    playbook_sheet: str | None = None
    assumption_sheet: str | None = None
    mapping: dict[str, str | None]
    config: dict = {}
    assumption_overrides: dict = {}
    use_reference_playbooks: bool = False
    use_llm: bool = False
    confirm_paid_calls: bool = False


STAGES = ["validate", "score", "queue", "recommend", "llm", "insights"]


def _job(job_id: str, b: AnalyseBody):
    job = JOBS[job_id]
    try:
        info = inspect(b.upload_id, b.model_dump())
        path = _find_upload(b.upload_id)
        df = _load_sheet(path, info["merchant_sheet"])
        prep = ingest.prepare(df, b.mapping)
        if prep["report"]["required_missing"]:
            raise ValueError("Required fields are not mapped: " + ", ".join(prep["report"]["required_missing"]))
        playbooks = _load_sheet(path, info["playbook_sheet"]) if info["playbook_sheet"] else None
        ass_df = _load_sheet(path, info["assumption_sheet"]) if info["assumption_sheet"] else None
        values, unresolved, prov = parse_assumptions(ass_df, sorted(prep["clean"]["industry"].dropna().unique()))
        ref_used = []
        if (playbooks is None or ass_df is None) and b.use_reference_playbooks and SAMPLE.exists():
            if playbooks is None:
                playbooks = _load_sheet(SAMPLE, "P2_Playbooks"); ref_used.append("playbooks")
            if ass_df is None:
                values, unresolved, prov = parse_assumptions(_load_sheet(SAMPLE, "P2_Assumptions"), sorted(prep["clean"]["industry"].dropna().unique()))
                ref_used.append("assumptions")
        if playbooks is None:
            raise ValueError("No playbook sheet was found. Select one or confirm use of the reference playbooks.")
        sheet_values = dict(values)
        values.update({k: v for k, v in {**app_settings().get("assumption_overrides", {}), **b.assumption_overrides}.items() if v not in (None, "", [])})
        overridden = sorted(k for k in values if k in sheet_values and values[k] != sheet_values[k])
        still = [k for k in KEYS if k not in values]
        if still:
            raise ValueError("These assumptions are required and were not found: " + ", ".join(KEYS[k] for k in still) + ". Supply them before running.")
        client = llm() if b.use_llm and b.confirm_paid_calls else None
        job["client"] = client
        cfg = dict(b.config)
        cfg.setdefault("capacity", values["max_outreaches"])

        def progress(stage, label, frac):
            job.update({"stage": stage, "label": label, "progress": frac})
            job["stages_done"] = [s for s in STAGES if STAGES.index(s) < STAGES.index(stage)]

        result = runner.run_analysis(prep["clean"], playbooks, values, cfg, progress, bool(client), client)
        sid = uuid.uuid4().hex[:10]
        qr = prep["report"]
        name = b.name or Path(info["file_name"]).stem
        result.update({
            "id": sid, "name": name, "source_file": info["file_name"], "upload_id": b.upload_id, "config": {**cfg, "use_llm": bool(client)}, "mapping": b.mapping,
            "sheets": {"merchants": info["merchant_sheet"], "playbooks": info["playbook_sheet"], "assumptions": info["assumption_sheet"], "reference_used": ref_used},
            "assumptions": {k: values[k] for k in KEYS}, "assumptions_provenance": prov, "assumptions_overridden": overridden, "quality": {k: v for k, v in qr.items() if k != "invalid_records"} | {"invalid_records": qr["invalid_records"][:50]},
            "excluded_records": qr["excluded_records"] + result.pop("extra_excluded", []),
            "period": "Six months of TPV (M1 to M6) as supplied; calendar dates are not included in the workbook.",
        })
        store.save_frame(sid, result.pop("_feats"))
        store.save_session(sid, result)
        store.save_state(sid, store.load_state(sid))
        job.update({"status": "done", "session_id": sid, "progress": 1.0, "label": "Analysis complete"})
    except Exception as exc:
        job.update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})


@app.post("/api/analyses")
def start_analysis(b: AnalyseBody):
    if b.use_llm and not b.confirm_paid_calls:
        raise HTTPException(400, "Claude analysis makes paid API calls. Confirm them explicitly to continue.")
    if b.use_llm and not llm().available:
        raise HTTPException(400, "No Anthropic API key is configured in .env. Add ANTHROPIC_API_KEY and restart the API.")
    jid = uuid.uuid4().hex[:8]
    JOBS[jid] = {"status": "running", "stage": "validate", "label": "Validating merchant records", "progress": 0.02, "stages_done": [], "use_llm": b.use_llm}
    threading.Thread(target=_job, args=(jid, b), daemon=True).start()
    return {"job_id": jid}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    j = JOBS.get(job_id)
    if not j:
        raise HTTPException(404, "Unknown job")
    out = {k: v for k, v in j.items() if k != "client"}
    c = j.get("client")
    if c and j.get("stage") == "llm" and j["status"] == "running":
        out["progress"] = min(0.65 + 0.3 * c.calls / max(c.max_calls * 0.9, 1), 0.92)
        out["label"] = f"Claude review in progress ({c.calls} calls made)"
    return out


# ---------------------------------------------------------------- sessions
def _session(sid: str) -> dict:
    s = store.load_session(sid)
    if not s:
        raise HTTPException(404, "Analysis not found")
    return s


def _frame(s: dict) -> pd.DataFrame:
    rows = []
    for m in s["merchants"]:
        rows.append({"merchant_id": m["id"], "business_name": m["name"], "segment": m["segment"], "industry": m["industry"], "risk_band": m["risk_band"],
                     "risk_score": m["risk_score"], "eligible_for_outreach": m["eligible"], "primary_dimension": m["primary_dimension"],
                     "success_drop_pp": m["success_drop_pp"] or 0.0, "renewal_days": m["renewal_days"], "dim_relationship": m["dims"]["relationship"],
                     "dim_engagement": m["dims"]["engagement"], "dim_performance": m["dims"]["performance"], "dim_commercial": m["dims"]["commercial"],
                     "is_seasonal_industry": m["seasonal_industry"], "completeness_score": m["completeness"],
                     "note_competitor_explicit": "competitor_explicit" in m["note_signals"], "annual_value_at_stake_inr": m["annual_value"],
                     "priority_value_inr": m["priority_value"]})
    return pd.DataFrame(rows)


@app.get("/api/sessions")
def sessions():
    return store.list_sessions()


@app.get("/api/sessions/{sid}")
def get_session(sid: str):
    return {"session": _session(sid), "state": store.load_state(sid)}


@app.delete("/api/sessions/{sid}")
def del_session(sid: str):
    store.delete_session(sid)
    return {"ok": True}


@app.post("/api/sessions/{sid}/state")
def patch_state(sid: str, patch: dict):
    _session(sid)
    st = store.load_state(sid)
    guarded = {"approved", "events", "outcomes"}
    if guarded & set(patch):
        raise HTTPException(400, "Approvals, events and outcomes are recorded through the workflow so each step is validated.")
    locked = {workflow.REVIEWED, workflow.APPROVED, workflow.CONTACTED, workflow.FOLLOW_UP, workflow.OUTCOME, workflow.CLOSED}
    if isinstance(patch.get("statuses"), dict) and locked & set(patch["statuses"].values()):
        raise HTTPException(400, "Review, approval, contact and outcome can only be recorded through the workflow.")
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(st.get(k), dict):
            for kk, vv in v.items():
                if vv is None:
                    st[k].pop(kk, None)
                else:
                    st[k][kk] = vv
        else:
            st[k] = v
    store.save_state(sid, st)
    return st


class WorkflowBody(BaseModel):
    merchant_id: str
    action: str
    payload: dict = {}


def _merchant(s: dict, mid: str) -> dict:
    m = next((x for x in s["merchants"] if x["id"] == mid), None)
    if not m:
        raise HTTPException(404, "Merchant not found in this analysis")
    return m


@app.post("/api/sessions/{sid}/workflow")
def workflow_action(sid: str, b: WorkflowBody):
    s = _session(sid)
    m = _merchant(s, b.merchant_id)
    st = store.load_state(sid)
    try:
        workflow.apply(st, m, b.action, b.payload)
    except workflow.WorkflowError as exc:
        raise HTTPException(exc.code, str(exc))
    store.save_state(sid, st)
    return st


class PackBody(BaseModel):
    merchant_id: str
    subject: str = ""
    body: str = ""


@app.post("/api/sessions/{sid}/review-pack")
def review_pack(sid: str, b: PackBody):
    s = _session(sid)
    m = _merchant(s, b.merchant_id)
    st = store.load_state(sid)
    draft = (st.get("drafts") or {}).get(m["id"]) or m.get("draft")
    return workflow.review_pack(m, s["playbooks"], b.subject, b.body, draft)


class ScnBody(BaseModel):
    spec: dict
    compare_to: str = "baseline"  # baseline | current


def _spec(s: dict, spec: dict) -> dict:
    return {**scenarios.default_scenario(spec.get("capacity", s["kpis"]["capacity"])), **spec}


def _weights_frame(sid: str, s: dict, spec: dict):
    """Engine re-run under the scenario's weights, or None when they equal the analysis' own weights."""
    w = spec.get("weights")
    if not w:
        return None
    try:
        weights.validate_weights(w)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    own = s.get("weights_pct") or weights.current_weights(load_scoring())
    if all(abs(float(w[d]) - float(own[d])) < 1e-6 for d in weights.DIMS):
        return None
    feats = store.load_frame(sid)
    if feats is None:
        raise HTTPException(409, "This analysis was created before weight scenarios existed. Run the analysis again to enable them.")
    ov = {"weights": w, "params": (s.get("scoring_overrides") or {}).get("params")}
    return weights.evaluate(feats, weights.apply_overrides(load_scoring(), ov), weights.engine_settings(s["assumptions"], spec["capacity"]), weights.playbook_frame(s["playbooks"]))


@app.post("/api/sessions/{sid}/scenario")
def run_scenario(sid: str, b: ScnBody):
    s = _session(sid)
    base_df = _frame(s)
    spec = _spec(s, b.spec)
    ref = s["scenario"] if b.compare_to == "current" else s["baseline_scenario"]
    new_df = _weights_frame(sid, s, spec)
    by_df = base_df if new_df is None else new_df
    base_rank, new_rank = scenarios.rank(base_df, ref), scenarios.rank(by_df, spec)
    res = scenarios.compare(by_df, base_rank, new_rank, spec)
    own = s.get("weights_pct") or weights.current_weights(load_scoring())
    nw = spec.get("weights") or own
    bi, ni = base_df.set_index("merchant_id"), by_df.set_index("merchant_id")
    movers = [x["merchant_id"] for x in res["moved_in"] + res["moved_out"]]
    res["weights"] = {
        "before": own, "after": nw, "changed": new_df is not None,
        "bands_before": weights.summarise(base_df, res["before"])["bands"], "bands_after": weights.summarise(by_df, res["after"])["bands"],
        "overlap": len(set(res["before"]) & set(res["after"])), "selected_after": len(res["after"]),
        "seasonal_selected_after": weights.summarise(by_df, res["after"])["seasonal_selected"], "incomplete_selected_after": weights.summarise(by_df, res["after"])["incomplete_selected"],
        "why": {m: weights.why_moved(m, bi, ni, own, nw) for m in movers if m in bi.index and m in ni.index} if new_df is not None else {},
    }
    byid = {m["id"]: m for m in s["merchants"]}
    new = new_rank.set_index("merchant_id")
    ranked = [{"merchant_id": mid, "rank": int(r.scn_rank), "selected": bool(r.scn_selected), "matched": r.matched, "forced": bool(r.forced),
               "name": byid[mid]["name"], "score": float(ni.loc[mid, "risk_score"]), "band": str(ni.loc[mid, "risk_band"])} for mid, r in new.iterrows()]
    return {"result": res, "ranking": ranked[:60], "spec": spec}


class ApplyWeightsBody(BaseModel):
    spec: dict
    name: str | None = None


@app.post("/api/sessions/{sid}/apply-weights")
def apply_weights(sid: str, b: ApplyWeightsBody):
    """Scores change when weights change, so applying them creates a new saved analysis (full lineage) instead of editing this one."""
    s = _session(sid)
    spec = _spec(s, b.spec)
    try:
        weights.validate_weights(spec.get("weights") or {})
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if not s.get("upload_id") or not store.upload_dir(s["upload_id"]).exists():
        raise HTTPException(409, "The original workbook is no longer stored, so a new analysis cannot be created from it.")
    keep = ("capacity", "priorities", "risk_focus", "segments", "prefer_segments", "exclude_industries", "renewal_window", "include_ids", "exclude_ids", "exclude_reasons")
    ov = {"weights": spec["weights"], "params": (s.get("scoring_overrides") or {}).get("params")}
    label = ", ".join(f"{weights.DIM_LABEL[d][:4]} {spec['weights'][d]:g}" for d in weights.DIMS)
    body = AnalyseBody(upload_id=s["upload_id"], name=b.name or f"{s['name']} (weights {label})", merchant_sheet=s["sheets"].get("merchants"), playbook_sheet=s["sheets"].get("playbooks"),
                       assumption_sheet=s["sheets"].get("assumptions"), mapping=s["mapping"], config={**{k: spec[k] for k in keep if k in spec}, "scoring_overrides": ov},
                       assumption_overrides=s["assumptions"], use_reference_playbooks=bool(s["sheets"].get("reference_used")), use_llm=False)
    return start_analysis(body)


@app.get("/api/sessions/{sid}/stability")
def get_stability(sid: str):
    _session(sid)
    d = store.load_extra(sid, "stability")
    return {"ready": bool(d), **(d or {})}


class StabilityBody(BaseModel):
    n: int = 300


@app.post("/api/sessions/{sid}/stability")
def run_stability(sid: str, b: StabilityBody):
    s = _session(sid)
    feats = store.load_frame(sid)
    if feats is None:
        raise HTTPException(409, "This analysis was created before robustness testing existed. Run the analysis again to enable it.")
    n = max(100, min(int(b.n), 500))
    jid = uuid.uuid4().hex[:8]
    JOBS[jid] = {"status": "running", "stage": "stability", "label": f"Re-scoring all merchants under {n + len(weights.PRESETS)} configurations", "progress": 0.02, "stages_done": []}

    def work():
        try:
            base = weights.apply_overrides(load_scoring(), s.get("scoring_overrides"))
            out = weights.stability(feats, base, s["assumptions"], weights.playbook_frame(s["playbooks"]), int(s["kpis"]["capacity"]), n,
                                    progress=lambda f: JOBS[jid].update({"progress": 0.02 + 0.96 * f}))
            store.save_extra(sid, "stability", out)
            JOBS[jid].update({"status": "done", "progress": 1.0, "label": "Robustness test complete", "session_id": sid})
        except Exception as exc:
            JOBS[jid].update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})

    threading.Thread(target=work, daemon=True).start()
    return {"job_id": jid}


@app.post("/api/sessions/{sid}/apply-scenario")
def apply_scenario(sid: str, b: ScnBody):
    """Make a scenario the current shortlist. The previous baseline stays available for comparison."""
    s = _session(sid)
    df = _frame(s)
    spec = _spec(s, b.spec)
    spec["name"] = b.spec.get("name") or "Current selection"
    rk = scenarios.rank(df, spec).set_index("merchant_id")
    cap = int(spec["capacity"])
    for m in s["merchants"]:
        if m["id"] in rk.index:
            r = rk.loc[m["id"]]
            m["rank"], m["selected"] = int(r.scn_rank), bool(r.scn_selected)
            if m["selected"]:
                m["selection_reason"] = f"Priority #{m['rank']} of {cap}. {m['why_priority']}"
                if not m["draft"]:
                    m["draft"] = None
        else:
            m["rank"], m["selected"] = None, False
    s["scenario"] = spec
    s["kpis"]["capacity"], s["kpis"]["selected"] = cap, sum(m["selected"] for m in s["merchants"])
    s["kpis"]["remaining_capacity"] = max(cap - s["kpis"]["selected"], 0)
    s["config"] = {**s["config"], "capacity": cap, "priorities": spec["priorities"], "risk_focus": spec["risk_focus"]}
    store.save_session(sid, s)
    return {"session": s}


class AskBody(BaseModel):
    question: str
    context: dict = {}
    history: list[dict] = []


@app.post("/api/sessions/{sid}/ask")
def ask(sid: str, b: AskBody):
    s = _session(sid)
    c = llm()
    r = ask_mod.deterministic(b.question, s, b.context, {"stability": store.load_extra(sid, "stability")})
    if r and r.get("scenario"):
        r = {**ask_mod.scenario_answer(_frame(s), s, r["scenario"]), "source": "computed"}
    elif r:
        r["source"] = "computed"
    if not r:
        r = ask_mod.claude_answer(b.question, s, b.context, c, b.history)
    if not r:
        r = {"answer": "I can't answer that from the analysis without a language model, and no Anthropic API key is configured, so open-ended questions are unavailable. "
                       "Calculated answers still work: who to contact first, why a merchant ranks above another, payment deterioration, renewals within N days, "
                       "merchants outside the shortlist, seasonal merchants, missing CSAT, contradictory evidence, driver exposure, weight-sensitive merchants, "
                       "playbook choices, what to verify before contact, and capacity or priority what-ifs.", "merchants": [], "fields": [],
             "limits": ["Runtime AI is not configured."], "source": "unavailable"}
    r["runtime_ai_used"] = r.get("source") == "claude"
    r["runtime_ai_configured"] = c.available
    log = store.load_extra(sid, "ask_log") or []
    log.append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "method": r["source"]})
    store.save_extra(sid, "ask_log", log[-500:])
    return r


@app.get("/api/sessions/{sid}/insights")
def insights_ext_view(sid: str):
    return insights_ext.build(_session(sid))


@app.post("/api/sessions/{sid}/evaluation-package")
def start_package(sid: str):
    s = _session(sid)
    jid = uuid.uuid4().hex[:8]
    JOBS[jid] = {"status": "running", "stage": "package", "label": "Preparing the evaluation package", "progress": 0.03, "stages_done": []}

    def work():
        try:
            stab = store.load_extra(sid, "stability")
            feats = store.load_frame(sid)
            if not stab and feats is not None:
                JOBS[jid].update({"label": "Running the robustness test (about 30 seconds)"})
                base = weights.apply_overrides(load_scoring(), s.get("scoring_overrides"))
                stab = weights.stability(feats, base, s["assumptions"], weights.playbook_frame(s["playbooks"]), int(s["kpis"]["capacity"]), 300,
                                         progress=lambda f: JOBS[jid].update({"progress": 0.03 + 0.8 * f}))
                store.save_extra(sid, "stability", stab)
            JOBS[jid].update({"label": "Assembling files", "progress": 0.9})
            st = store.load_state(sid)
            c = llm()
            val = validation.build(s, stab, st.get("validation"))
            ai = ai_mod.build(s, store.load_extra(sid, "ask_log") or [], c.available, c.model)
            data = evaluation.build_package(s, st, stab, val, ai, store.upload_dir(s["upload_id"]) if s.get("upload_id") else None)
            (store.SESSIONS / sid / "evaluation_package.zip").write_bytes(data)
            JOBS[jid].update({"status": "done", "progress": 1.0, "label": "Package ready", "session_id": sid})
        except Exception as exc:
            JOBS[jid].update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})

    threading.Thread(target=work, daemon=True).start()
    return {"job_id": jid}


@app.get("/api/sessions/{sid}/evaluation-package")
def get_package(sid: str):
    s = _session(sid)
    p = store.SESSIONS / sid / "evaluation_package.zip"
    if not p.exists():
        raise HTTPException(404, "No evaluation package has been built for this analysis yet.")
    return Response(p.read_bytes(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="edge_evaluation_package_{s["name"].replace(" ", "_")}.zip"'})


@app.get("/api/sessions/{sid}/ai-disclosure")
def ai_disclosure(sid: str):
    s = _session(sid)
    c = llm()
    return ai_mod.build(s, store.load_extra(sid, "ask_log") or [], c.available, c.model)


def _validation(sid: str, s: dict, st: dict) -> dict:
    return validation.build(s, store.load_extra(sid, "stability"), st.get("validation"))


@app.get("/api/sessions/{sid}/validation")
def get_validation(sid: str):
    s, st = _session(sid), store.load_state(sid)
    return _validation(sid, s, st)


@app.get("/api/sessions/{sid}/export")
def export(sid: str, kind: str = "risk_register", format: str = "csv"):
    s, st = _session(sid), store.load_state(sid)
    extra = {"stability": store.load_extra(sid, "stability"), "validation": _validation(sid, s, st)}
    tag = f"edge_{s['name'].replace(' ', '_')}_{kind if format == 'csv' else (kind if kind != 'all' else 'full')}"
    if format == "xlsx":
        data = exporter.to_xlsx(None if kind == "all" else kind, s, st, extra)
        return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{tag}.xlsx"'})
    if kind not in exporter.KINDS and kind not in exporter.EXTRA_KINDS:
        raise HTTPException(400, "Unknown export")
    try:
        body = exporter.to_csv(kind, s, st, extra)
    except KeyError as exc:
        raise HTTPException(409, str(exc).strip("'\""))
    return Response(body, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{tag}.csv"'})


@app.get("/api/compare")
def compare_sessions(a: str, b: str):
    sa, sb = _session(a), _session(b)
    ia, ib = {m["id"]: m for m in sa["merchants"]}, {m["id"]: m for m in sb["merchants"]}
    common = sorted(set(ia) & set(ib))
    rows = [{"id": i, "name": ib[i]["name"], "score_a": ia[i]["risk_score"], "score_b": ib[i]["risk_score"], "delta": ib[i]["risk_score"] - ia[i]["risk_score"],
             "band_a": ia[i]["risk_label"], "band_b": ib[i]["risk_label"], "selected_a": ia[i]["selected"], "selected_b": ib[i]["selected"]} for i in common]
    return {"a": {"name": sa["name"], "source": sa["source_file"], "created_at": sa["created_at"], "kpis": sa["kpis"]},
            "b": {"name": sb["name"], "source": sb["source_file"], "created_at": sb["created_at"], "kpis": sb["kpis"]},
            "common": len(common), "only_a": len(set(ia) - set(ib)), "only_b": len(set(ib) - set(ia)),
            "comparable": len(common) >= 0.5 * min(len(ia), len(ib)), "rows": sorted(rows, key=lambda r: -abs(r["delta"]))[:40],
            "caveat": "Different workbooks are not a continuous time series. Score changes reflect different input data, not necessarily a change in the merchant."}


@app.get("/api/config/model")
def config_model():
    """Scoring and playbook-trigger configuration, for the Settings page. Read-only: changing it changes the methodology."""
    from src.config import load_playbook_cfg
    sc, pb = load_scoring(), load_playbook_cfg()
    return {"scoring": {k: sc[k] for k in ("scoring_version", "weights", "bands", "aggregation", "driver_min_score", "tpv", "success", "seasonal", "performance", "service", "engagement", "commercial", "critical_triggers", "confidence")},
            "playbook_triggers": pb["triggers"], "tie_break_order": pb["tie_break_order"], "eligible_playbooks": load_settings()["selection"]["eligible_playbooks"],
            "selection": {k: load_settings()["selection"][k] for k in ("min_band", "confidence_factor", "urgency_multiplier")}, "config_files": ["config/scoring.yaml", "config/playbook_mapping.yaml", "config/settings.yaml", "config/note_signals.yaml"]}


@app.get("/api/settings")
def get_settings():
    return {**app_settings(), "llm_available": llm().available, "model": llm().model, "key_hint": "ANTHROPIC_API_KEY is read from .env on the server and never sent to the browser.",
            "assumption_labels": KEYS}


@app.put("/api/settings")
def put_settings(body: dict):
    cur = {**app_settings(), **{k: v for k, v in body.items() if k in ("default_capacity", "default_risk_focus", "assumption_overrides")}}
    SETTINGS_FILE.parent.mkdir(exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(cur), encoding="utf-8")
    return cur


@app.post("/api/llm/test")
def test_llm():
    c = llm()
    if not c.available:
        return {"ok": False, "message": "No ANTHROPIC_API_KEY found in .env."}
    t = time.time()
    try:
        r = c._sdk().messages.create(model=c.model, max_tokens=16, messages=[{"role": "user", "content": "Reply with the single word: ready"}])
        return {"ok": True, "message": f"Connected to {c.model} in {time.time() - t:.1f}s.", "reply": "".join(b.text for b in r.content if getattr(b, "type", "") == "text")[:40]}
    except Exception as exc:
        return {"ok": False, "message": f"Call failed ({type(exc).__name__}). Check the key and model name in .env."}


DIST = ROOT / "web" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = DIST / path
        return FileResponse(f if path and f.is_file() else DIST / "index.html")
