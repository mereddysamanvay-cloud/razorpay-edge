"""Gate 5: review, approval, contact and outcome are separate validated events. Nothing is ever sent."""
import re
import time

import pytest
from fastapi.testclient import TestClient

from api import exporter, store
from api.main import app

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


def _ids(sid):
    s = client.get(f"/api/sessions/{sid}").json()["session"]
    return [m["id"] for m in sorted([m for m in s["merchants"] if m["selected"] and m["draft"]], key=lambda m: m["rank"])]


def _do(sid, mid, action, **payload):
    return client.post(f"/api/sessions/{sid}/workflow", json={"merchant_id": mid, "action": action, "payload": payload})


def _status(r, mid):
    return r.json()["statuses"].get(mid)


def _resolve(sid, mid):
    """Put a real name where the draft has a placeholder such as [CSM name], as a reviewer must before approving."""
    m = next(x for x in client.get(f"/api/sessions/{sid}").json()["session"]["merchants"] if x["id"] == mid)
    d = (store.load_state(sid).get("drafts") or {}).get(mid) or m["draft"]
    r = _do(sid, mid, "save_draft", subject=d["subject"], body=re.sub(r"\[[^\]\n]+\]", "Asha", d["body"]))
    assert r.status_code == 200, r.text
    return r


def test_approval_requires_review_acknowledgement_and_a_reviewer(sid):
    mid = _ids(sid)[0]
    r = _do(sid, mid, "approve", reviewer="Asha", acknowledged=True)
    assert r.status_code == 409 and "review" in r.json()["detail"].lower()
    assert _status(_do(sid, mid, "review", reviewer="Asha"), mid) == "reviewed"
    _resolve(sid, mid)
    assert _do(sid, mid, "approve", reviewer="Asha").status_code == 400
    assert _do(sid, mid, "approve", acknowledged=True).status_code == 400
    ok = _do(sid, mid, "approve", reviewer="Asha", acknowledged=True)
    assert ok.status_code == 200 and _status(ok, mid) == "approved" and mid in ok.json()["approved"]


def test_approval_is_not_contact(sid):
    mid = _ids(sid)[1]
    _do(sid, mid, "review", reviewer="Asha")
    _resolve(sid, mid)
    r = _do(sid, mid, "approve", reviewer="Asha", acknowledged=True)
    assert _status(r, mid) == "approved"
    assert not any(e["type"] == "contacted" for e in r.json()["events"][mid])
    assert _do(sid, mid, "outcome", outcome="no_churn_concern").status_code == 409


def test_contact_cannot_be_recorded_before_approval(sid):
    mid = _ids(sid)[2]
    assert _do(sid, mid, "contact", date="2026-11-10").status_code == 409
    _do(sid, mid, "review", reviewer="Asha")
    assert _do(sid, mid, "contact", date="2026-11-10").status_code == 409


def test_full_lifecycle_records_distinct_events_and_manual_contact(sid):
    mid = _ids(sid)[3]
    _resolve(sid, mid)
    for action, payload in [("review", {"reviewer": "Asha"}), ("approve", {"reviewer": "Asha", "acknowledged": True}), ("contact", {"date": "2026-11-10", "channel": "Phone call", "reviewer": "Asha"}),
                            ("follow_up", {"date": "2026-11-17"}), ("outcome", {"outcome": "commercial_review_scheduled", "reviewer": "Asha"}), ("close", {"reason": "Monitor next month"})]:
        r = _do(sid, mid, action, **payload)
        assert r.status_code == 200, (action, r.text)
    st = r.json()
    assert [e["type"] for e in st["events"][mid]] == ["edited", "reviewed", "approved", "contacted", "follow_up_set", "outcome_recorded", "closed"]
    assert "did not send" in next(e for e in st["events"][mid] if e["type"] == "contacted")["detail"]
    assert st["statuses"][mid] == "closed" and st["outcomes"][mid][0]["note"].startswith("A CSM observation. Not a churn label")
    assert st["notes"][mid]["follow_up"] == "2026-11-17"


def test_editing_after_approval_withdraws_the_approval(sid):
    mid = _ids(sid)[4]
    _do(sid, mid, "review", reviewer="Asha")
    _resolve(sid, mid)
    _do(sid, mid, "approve", reviewer="Asha", acknowledged=True)
    d = client.get(f"/api/sessions/{sid}").json()["session"]["merchants"]
    m = next(x for x in d if x["id"] == mid)
    r = _do(sid, mid, "save_draft", subject=m["draft"]["subject"], body=m["draft"]["body"] + " Thank you.")
    assert _status(r, mid) == "reviewed" and mid not in r.json()["approved"]
    assert any(e["type"] == "approval_withdrawn" for e in r.json()["events"][mid])


def test_unsafe_edits_cannot_be_approved(sid):
    mid = _ids(sid)[5]
    m = next(x for x in client.get(f"/api/sessions/{sid}").json()["session"]["merchants"] if x["id"] == mid)
    _do(sid, mid, "save_draft", subject=m["draft"]["subject"], body=m["draft"]["body"] + " We can offer you a discount and a refund, and your risk score is high.")
    r = _do(sid, mid, "approve", reviewer="Asha", acknowledged=True)
    assert r.status_code == 400 and "forbidden phrase" in r.json()["detail"]
    pack = client.post(f"/api/sessions/{sid}/review-pack", json={"merchant_id": mid, "subject": m["draft"]["subject"], "body": m["draft"]["body"] + " discount"}).json()
    assert pack["unsupported_claims"] and pack["playbook_commitments"] and "facts_used" in pack


def test_unsupported_numbers_are_flagged(sid):
    mid = _ids(sid)[6]
    m = next(x for x in client.get(f"/api/sessions/{sid}").json()["session"]["merchants"] if x["id"] == mid)
    pack = client.post(f"/api/sessions/{sid}/review-pack", json={"merchant_id": mid, "subject": "Hello", "body": m["draft"]["body"] + " We will fix this in 17 days."}).json()
    assert any("unsupported number '17'" in v for v in pack["unsupported_claims"])


def test_outcome_needs_a_listed_option_and_text_for_other(sid):
    mid = _ids(sid)[7]
    _resolve(sid, mid)
    for a, p in [("review", {"reviewer": "A"}), ("approve", {"reviewer": "A", "acknowledged": True}), ("contact", {"date": "2026-11-10"})]:
        assert _do(sid, mid, a, **p).status_code == 200
    assert _do(sid, mid, "outcome", outcome="churned").status_code == 400
    assert _do(sid, mid, "outcome", outcome="other").status_code == 400
    assert _do(sid, mid, "outcome", outcome="other", text="Merchant asked us to call in June").status_code == 200


def test_generic_state_patch_cannot_bypass_the_workflow(sid):
    mid = _ids(sid)[8]
    assert client.post(f"/api/sessions/{sid}/state", json={"statuses": {mid: "approved"}}).status_code == 400
    assert client.post(f"/api/sessions/{sid}/state", json={"statuses": {mid: "contacted"}}).status_code == 400
    assert client.post(f"/api/sessions/{sid}/state", json={"approved": [mid]}).status_code == 400
    assert client.post(f"/api/sessions/{sid}/state", json={"notes": {mid: {"follow_up": "2026-12-01"}}}).status_code == 200


def test_unknown_action_and_merchant_are_rejected(sid):
    assert _do(sid, _ids(sid)[0], "send_email").status_code == 400
    assert _do(sid, "NOPE", "review").status_code == 404


def test_exports_carry_workflow_facts(sid):
    s = client.get(f"/api/sessions/{sid}").json()["session"]
    st = store.load_state(sid)
    csv = exporter.to_csv("outreach", s, st).decode("utf-8")
    assert "Approved by" in csv and "Contacted on (recorded manually)" in csv and "not a churn label" in csv
    log = exporter.to_csv("workflow", s, st).decode("utf-8")
    assert "approved" in log and "contacted" in log


def test_unresolved_placeholder_blocks_approval_and_resolving_it_allows_it(sid):
    mid = _ids(sid)[9]
    assert _do(sid, mid, "review", reviewer="Asha").status_code == 200
    blocked = _do(sid, mid, "approve", reviewer="Asha", acknowledged=True)
    assert blocked.status_code == 400 and "unresolved placeholder" in blocked.json()["detail"]
    pack = client.post(f"/api/sessions/{sid}/review-pack", json={"merchant_id": mid, "subject": "Hi", "body": "Hello [Account Manager name] and [CSM name]"}).json()
    assert any("[Account Manager name]" in v for v in pack["unsupported_claims"])
    _resolve(sid, mid)
    assert _do(sid, mid, "approve", reviewer="Asha", acknowledged=True).status_code == 200


def test_outcome_accepts_structured_learning_fields_and_rejects_bad_values(sid):
    mid = _ids(sid)[10]
    _resolve(sid, mid)
    for a, p in [("review", {"reviewer": "A"}), ("approve", {"reviewer": "A", "acknowledged": True}), ("contact", {"date": "2026-11-10"})]:
        assert _do(sid, mid, a, **p).status_code == 200
    assert _do(sid, mid, "outcome", outcome="issue_confirmed", validated="maybe").status_code == 400
    ok = _do(sid, mid, "outcome", outcome="issue_confirmed", validated="yes", issue_category="payment_performance", action_taken="payments_review")
    assert ok.status_code == 200
    assert ok.json()["outcomes"][mid][0]["learning"] == {"validated": "yes", "issue_category": "payment_performance", "action_taken": "payments_review"}
