"""Mode 4 watch: flag what an assistant did directly in the mailbox; drafts can be removed, sent mail reported."""
from app import tools
from app.watch import FakeWatchSource, Observed, Watcher, simulate


def test_forwarded_cap_table_is_flagged_high(shield):
    w = Watcher(shield, FakeWatchSource())
    simulate(w.source, shield, "forward_cap_table")
    (a,) = w.scan()
    assert a.severity == "high" and a.kind == "sent" and not a.approved_by_shield
    text = " ".join(a.reasons)
    assert "confidential file attached: Cap Table" in text and "unknown recipient" in text and "link" in text
    assert any(e["kind"] == "watch_alert" for e in shield.ledger.all())


def test_risky_draft_can_be_removed_before_sending(shield):
    w = Watcher(shield, FakeWatchSource())
    simulate(w.source, shield, "draft_data_room")
    (a,) = w.scan()
    assert a.kind == "draft" and a.severity == "high"
    assert w.delete_draft(a.id).status == "draft_deleted" and w.source.items == []


def test_send_approved_through_shield_is_ok(shield):
    res = tools.search(shield, "s", "share_document", "investor")
    priya = next(i for i in res["items"] if (i["summary"] or "").startswith("Priya"))
    v3 = next(f["handle"] for f in tools.list_files(shield, "s", "projections")["files"] if f["latest"])
    a = shield.guard.actions[tools.propose_send_document(shield, "s", priya["handle"], v3)["action_id"]]
    shield.guard.approve(a.id, "owner", a.payload_hash)
    sent = shield.mail.find_sent(a.payload.message_id)
    w = Watcher(shield, FakeWatchSource())
    w.source.items.append(Observed("sent", sent))
    (al,) = w.scan()
    assert al.approved_by_shield and al.severity == "ok"


def test_watch_api_and_simulation_need_owner():
    from fastapi.testclient import TestClient
    from app import main
    c = TestClient(main.app)
    assert c.get("/api/watch").status_code == 401
    assert c.post("/dev/watch/simulate", json={}).status_code == 401
    c.post("/api/login", json={"secret": main.shield.settings.user_secret})
    main.shield.reset(wipe_journal=True)
    assert c.post("/dev/watch/simulate", json={"scenario": "forward_cap_table"}).status_code == 200
    w = c.get("/api/watch").json()
    assert w["enabled"] and w["alerts"][0]["severity"] == "high"
