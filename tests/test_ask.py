"""Gate 4: Ask EDGE grounding, runtime-AI disclosure and the fallback when no language model is configured. No paid API calls are made."""
import hashlib
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import api.main as main
from api import ai_disclosure, ask as ask_mod, store
from src.agent.safety import check_analysis_text

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


@pytest.fixture()
def no_llm(monkeypatch):
    """Server with no runtime AI configured, so a test can never reach the paid API."""
    monkeypatch.setattr(main, "llm", lambda: SimpleNamespace(available=False, model="none", calls=0))


class Stub:
    available, model, calls = True, "stub", 0

    def __init__(self, text):
        self.text = text
        self.messages = self

    def _sdk(self):
        return self

    def create(self, **_):
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.text)])


def _s(sid):
    return client.get(f"/api/sessions/{sid}").json()["session"]


def _ask(sid, q, **ctx):
    return client.post(f"/api/sessions/{sid}/ask", json={"question": q, "context": ctx}).json()


def _questions(sid):
    s = _s(sid)
    sel = sorted([m for m in s["merchants"] if m["selected"]], key=lambda m: m["rank"])
    a, b = sel[0], sel[1]
    return [f"Why is {a['name']} ranked above {b['name']}?", "Which merchants show the strongest payment deterioration?", "Which seasonal merchants were not escalated?",
            "What changes if capacity becomes 20?", "Which shortlisted merchants lack CSAT?", "Which merchants have contradictory signals?",
            f"Why was this playbook selected for {a['name']}?", "Which driver has the highest annual run-rate exposure?", f"What must the CSM verify before contacting {a['name']}?"]


def test_brief_questions_are_calculated_grounded_and_disclose_their_fields(sid, no_llm):
    ids = {m["id"] for m in _s(sid)["merchants"]}
    for q in _questions(sid):
        r = _ask(sid, q)
        assert r["source"] == "computed", q
        assert r["runtime_ai_used"] is False
        assert r["fields"], f"no source fields listed for: {q}"
        assert set(r["merchants"]) <= ids
        assert not check_analysis_text(r["answer"]), q
        assert "probability" not in r["answer"].lower().replace("not a probability", "").replace("not churn probabilities", "")


def test_why_a_above_b_names_both_and_shows_priority_components(sid, no_llm):
    s = _s(sid)
    sel = sorted([m for m in s["merchants"] if m["selected"]], key=lambda m: m["rank"])
    r = _ask(sid, f"Why is {sel[0]['name']} ranked above {sel[1]['name']}?")
    assert set(r["merchants"]) == {sel[0]["id"], sel[1]["id"]}
    assert "priority index" in r["answer"] and "risk weight" in r["answer"] and "not an expected saving" in " ".join(r["limits"])


def test_capacity_question_is_a_preview_and_changes_nothing(sid, no_llm):
    path = store.SESSIONS / sid / "session.json"
    before = hashlib.md5(path.read_bytes()).hexdigest()
    r = _ask(sid, "What changes if capacity becomes 20?")
    assert "capacity 20" in r["answer"] and "Nothing in the analysis" in r["answer"]
    assert hashlib.md5(path.read_bytes()).hexdigest() == before


def test_verify_before_contact_marks_notes_unverified(sid, no_llm):
    s = _s(sid)
    m = next(m for m in s["merchants"] if m["selected"] and m["note"])
    r = _ask(sid, f"What must the CSM verify before contacting {m['name']}?")
    assert "unverified" in r["answer"].lower() and "never sent automatically" in r["answer"]


def test_weight_sensitive_question_says_when_data_is_missing(sid, no_llm):
    path = store.SESSIONS / sid / "stability.json"
    if path.exists():
        path.unlink()
    r = _ask(sid, "Which merchants are most weight-sensitive?")
    assert "Not available" in r["answer"] and r["source"] == "computed"


def test_open_question_without_runtime_ai_says_it_cannot_answer(sid, no_llm):
    r = _ask(sid, "Tell me a story about merchant feelings")
    assert r["source"] == "unavailable" and "no Anthropic API key" in r["answer"] and r["runtime_ai_used"] is False and r["runtime_ai_configured"] is False


def test_claude_reply_with_unknown_merchant_or_probability_is_withheld(sid):
    s = _s(sid)
    bad_id = ask_mod.claude_answer("q", s, {}, Stub("Merchant C9999 is at risk."), [])
    assert bad_id["source"] == "unavailable" and "C9999" in bad_id["answer"]
    prob = ask_mod.claude_answer("q", s, {}, Stub(f"{s['merchants'][0]['id']} has a 70% chance of churn."), [])
    assert prob["source"] == "unavailable"
    claim = ask_mod.claude_answer("q", s, {}, Stub("I have approved the outreach for you."), [])
    assert claim["source"] == "unavailable" and "changed" in claim["answer"]


def test_grounded_claude_reply_is_shown_with_known_merchants_only(sid):
    s = _s(sid)
    mid = s["merchants"][0]["id"]
    r = ask_mod.claude_answer("q", s, {}, Stub(f"**Observed.** {mid} has an unresolved ticket."), [])
    assert r["source"] == "claude" and r["merchants"] == [mid] and r["limits"]


def test_ai_disclosure_for_a_deterministic_analysis(sid, no_llm):
    _ask(sid, "Which 5 merchants should I contact first and why?")
    d = client.get(f"/api/sessions/{sid}/ai-disclosure").json()
    assert d["claude_used_in_analysis"] is False and not any(r["runtime_ai"] for r in d["rows"])
    assert "not a runtime feature" in d["development"]
    assert any("not requested" in n for n in d["notes"]) and any("No Anthropic API key" in n for n in d["notes"])
    ask_row = next(r for r in d["rows"] if r["task"].startswith("Ask EDGE"))
    assert "calculated" in ask_row["detail"] and ask_row["runtime_ai"] is False


def test_ai_disclosure_reports_claude_only_when_recorded():
    s = {"merchants": [{"draft": {"source": "llm"}}, {"draft": {"source": "template"}}], "config": {"use_llm": True},
         "llm_stats": {"review_attempted": 2, "review_accepted": 1, "review_rejected_unsafe": 0, "review_failed": 1, "outreach_fallback_to_template": 1, "note_flag_disagreements": []}}
    d = ai_disclosure.build(s, [{"method": "claude"}, {"method": "computed"}], True, "m")
    by = {r["task"].split(" (")[0].split(",")[0]: r for r in d["rows"]}
    assert d["claude_used_in_analysis"] is True
    assert next(r for r in d["rows"] if r["task"] == "Outreach drafts")["runtime_ai"] is True
    assert any("failed or were rejected" in n for n in d["notes"])
    assert next(r for r in d["rows"] if r["task"].startswith("Ask EDGE"))["runtime_ai"] is True
    assert next(r for r in d["rows"] if r["task"].startswith("Scores"))["runtime_ai"] is False and by
