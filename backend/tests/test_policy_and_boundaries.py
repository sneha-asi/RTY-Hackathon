"""Standing policy binds reads and proposals; MCP is isolated from owner endpoints; no-resend survives restart."""
import json

from app import tools
from app.models import State
from app.service import Shield
from tests.conftest import run_pending

S = "sess-p"


def _setup(sh):
    res = tools.search(sh, S, "share_document", "investor")
    priya = next(i for i in res["items"] if (i["summary"] or "").startswith("Priya"))
    files = {(f["category"], f["version"]): f["handle"] for f in tools.list_files(sh, S)["files"]}
    return priya, files


def test_purpose_outside_policy_is_refused(shield):
    out = tools.search(shield, S, "triage")
    assert "outside the enabled policy" in out["error"]


def test_request_must_be_released_in_this_session(shield):
    priya, files = _setup(shield)
    other = tools.propose_send_document(shield, "another-session", priya["handle"], files[("projections", 3)])
    assert other["state"] == "BLOCKED"


def test_two_valid_handles_cannot_be_combined_outside_the_request(shield):
    priya, files = _setup(shield)
    view = tools.propose_send_document(shield, S, priya["handle"], files[("teaser", 1)])  # Priya asked for projections
    assert view["state"] == "BLOCKED"
    assert "asked for projections" in next(c for c in view["checks"] if c["name"] == "WHAT")["detail"]


def test_contact_handle_is_not_a_request(shield):
    priya, files = _setup(shield)
    view = tools.propose_send_document(shield, S, priya["sender"], files[("projections", 3)])
    assert view["state"] == "BLOCKED"


def test_sent_record_mismatch_is_unverified_not_failed(shield, monkeypatch):
    priya, files = _setup(shield)
    a = shield.guard.actions[tools.propose_send_document(shield, S, priya["handle"], files[("projections", 3)])["action_id"]]
    real = shield.mail.find_sent

    def tampered(mid):
        s = real(mid)
        s.attachments = [(s.attachments[0][0], "0" * 64)]
        return s
    monkeypatch.setattr(shield.mail, "find_sent", tampered)
    out = shield.guard.approve(a.id, "owner", a.payload_hash)
    assert out.state == State.UNVERIFIED and "attachment" in out.reason
    assert "differs" in shield.guard.status_text(out)


def test_no_resend_after_restart(tmp_path):
    from app.config import Settings
    from app.mail import FakeMail
    s = Settings()
    s.runtime_dir = tmp_path / "rt"
    s.verify_backoff = (0,)
    mail, pending = FakeMail(), []
    sh = Shield(s, mail=mail, scheduler=pending.append)
    sh.pending = pending
    priya, files = _setup(sh)
    a = sh.guard.actions[tools.propose_send_document(sh, S, priya["handle"], files[("projections", 3)])["action_id"]]
    mail.fail_mode = "timeout_after_send"
    sh.guard.approve(a.id, "owner", a.payload_hash)
    assert a.state == State.VERIFICATION_PENDING and mail.send_calls == 1
    # process restarts before verification: same runtime dir, same mailbox
    pending2 = []
    sh2 = Shield(s, mail=mail, scheduler=pending2.append)
    sh2.pending = pending2
    assert sh2.guard.actions[a.id].state == State.VERIFICATION_PENDING
    run_pending(sh2)
    assert sh2.guard.actions[a.id].state == State.VERIFIED and mail.send_calls == 1


def test_mcp_listener_has_no_owner_endpoints():
    from starlette.testclient import TestClient
    from app.main import mcp_app
    c = TestClient(mcp_app)
    for path in ("/api/state", "/api/actions/x/approve", "/dev/reset", "/api/events", "/"):
        assert c.get(path).status_code == 404


def test_mcp_has_no_send_or_approve_tool():
    import asyncio
    from app.main import mcp
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert names == {"search", "read", "list_files", "free_slots", "propose_send_document", "propose_reply", "action_status"}


def test_owner_data_requires_login():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    assert c.get("/api/state").json() == {"authed": False}
    assert c.get("/api/events").status_code == 401
    assert c.post("/api/actions/x/approve", json={"seal": "x"}).status_code in (401, 404)
    assert c.post("/api/login", json={"secret": "wrong"}).status_code == 401


def test_model_never_sees_fixture_sensitive_values(shield):
    planted = ["29ABCPE1234F1Z5", "ABCPE1234F", "HDFC0001234", "vikram.joshi@okhdfcbank", "4111 1111 1111 1111",
               "sk-demoX9fK2mQ7rT4vB8nL3pZ6wY1cH5jD0aEe", "40 Cr", "Rahul Verma", "Meera Nair", "slipped disc",
               "priya@northbeam.vc", "karan@angel.test", "growth@quickcap-partners.io", "audit@docs-share.co",
               "finance-review@vendor-mail.net", "x@evil.io", "14 months", "62.5%"]
    priya, files = _setup(shield)
    tools.search(shield, S, "schedule")
    tools.free_slots(shield, S, "2026-11-18", "2026-11-25")
    tools.propose_send_document(shield, S, priya["handle"], files[("projections", 3)])
    blob = json.dumps([v["result"] for v in shield.model_view]).lower()
    leaked = [p for p in planted if p.lower() in blob]
    assert leaked == []


def test_receipt_cap_table_counts_from_ledger(shield):
    from app import receipts
    _setup(shield)
    out = receipts.answer(shield, "Did any AI see my cap table today?")
    assert out["released"] == 0 and out["withheld"] >= 1
    assert out["answer"].startswith("Shield released the cap table 0 times and withheld it")


def test_dev_endpoints_need_owner():
    from fastapi.testclient import TestClient
    from app.main import app, shield as live
    c = TestClient(app)
    assert c.post("/dev/reset").status_code == 401
    assert c.post("/dev/tamper/proj_v3").status_code == 401
    assert c.post("/dev/reset", headers={"X-Shield-Secret": live.settings.user_secret}).status_code == 200


def test_list_files_and_free_slots_follow_policy(shield):
    files = tools.list_files(shield, S)["files"]
    assert {f["category"] for f in files} <= {"projections", "teaser"}
    shield.registry("p2").policy["purposes"] = ["share_document"]
    assert "error" in tools.free_slots(shield, "p2", "2026-11-18", "2026-11-25")


def test_assistants_list_shows_connected_client_and_roadmap(shield):
    from fastapi.testclient import TestClient
    from app import main
    main.shield.note_client("mcp:abc", "claude-code", "2.1")
    c = TestClient(main.app)
    c.post("/api/login", json={"secret": main.shield.settings.user_secret})
    names = {a["name"]: a for a in c.get("/api/state").json()["assistants"]}
    assert names["claude-code"]["status"] == "enforced"
    assert names["Instinct"]["status"].startswith("roadmap")
