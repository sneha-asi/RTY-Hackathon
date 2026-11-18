"""Vertical slice: search → propose → approve (owner + seal) → FakeMail → read-back → VERIFIED."""
import json

import pytest

from app import tools
from app.guard import Conflict, Unauthorized, build_mime, seal
from app.models import IllegalTransition, State
from app.seed import sha256_bytes
from tests.conftest import run_pending

S = "sess-1"


def _priya_flow(sh):
    res = tools.search(sh, S, "share_document", "investor")
    by_summary = {i["summary"]: i for i in res["items"] if i["status"] == "released"}
    priya = next(i for s, i in by_summary.items() if s.startswith("Priya Rao"))
    files = tools.list_files(sh, S, "projections")["files"]
    v3 = next(f for f in files if f["version"] == 3)
    return res, priya, v3


def test_search_returns_handles_and_summaries_only(shield):
    res, priya, v3 = _priya_flow(shield)
    assert priya["sender"].startswith("CONTACT_") and priya["handle"].startswith("THREAD_") and priya["requested_category"] == "projections"
    assert v3["latest"] is True and v3["handle"].startswith("FILE_")
    blob = json.dumps(res)
    assert "@" not in blob and "priya@northbeam.vc" not in blob
    assert res["withheld"]  # unrelated sensitive items only as counts


def test_priya_end_to_end_verified(shield):
    _, priya, v3 = _priya_flow(shield)
    view = tools.propose_send_document(shield, S, priya["handle"], v3["handle"], "Ahead of Friday")
    assert view["request"] == priya["handle"]
    assert view["state"] == "AWAITING_APPROVAL", view
    assert [c["status"] for c in view["checks"]] == ["pass"] * 5
    a = shield.guard.actions[view["action_id"]]
    out = shield.guard.approve(a.id, "owner", a.payload_hash)
    assert out.state == State.VERIFIED
    assert len(shield.mail.outbox) == 1
    sent = shield.mail.outbox[0]
    assert sha256_bytes(sent["raw"]) == a.payload.message_sha256  # the exact sealed bytes were sent
    assert tools.action_status(shield, S, a.id)["status_text"].startswith("Verified in Sent (sandbox): Projections v3 to Priya Rao")


def test_unknown_sender_blocked(shield):
    res = tools.search(shield, S, "share_document", "investor")
    stranger = next(i for i in res["items"] if i["status"] == "released" and i["sender"].startswith("SENDER_"))
    assert stranger["requested_category"] == "data_room"
    v3 = next(f for f in tools.list_files(shield, S, "projections")["files"] if f["version"] == 3)
    view = tools.propose_send_document(shield, S, stranger["handle"], v3["handle"])
    assert view["state"] == "BLOCKED" and "unknown recipient" in view["status_text"]
    what = next(c for c in view["checks"] if c["name"] == "WHAT")
    assert what["status"] == "fail" and "data room" in what["detail"]  # not covered by the policy either
    assert shield.mail.outbox == []


def test_raw_address_blocked(shield):
    _, _, v3 = _priya_flow(shield)
    view = tools.propose_send_document(shield, S, "finance-review@vendor-mail.net", v3["handle"])
    assert view["state"] == "BLOCKED" and "raw address" in view["status_text"]


def test_content_url_and_image_blocked(shield):
    _, priya, v3 = _priya_flow(shield)
    view = tools.propose_send_document(shield, S, priya["handle"], v3["handle"], "see ![x](https://x.io/p?d=1)")
    assert view["state"] == "BLOCKED"
    content = next(c for c in view["checks"] if c["name"] == "CONTENT")
    assert content["status"] == "fail" and "link" in content["detail"]


def test_karan_downgraded_to_teaser(shield):
    res = tools.search(shield, S, "share_document", "investor")
    karan = next(i for i in res["items"] if (i["summary"] or "").startswith("Karan"))
    v3 = next(f for f in tools.list_files(shield, S, "projections")["files"] if f["version"] == 3)
    view = tools.propose_send_document(shield, S, karan["handle"], v3["handle"])
    assert view["state"] == "AWAITING_APPROVAL"
    a = shield.guard.actions[view["action_id"]]
    assert a.payload.file_id == "teaser" and a.warnings


def test_v2_upgraded_to_latest(shield):
    _, priya, _ = _priya_flow(shield)
    v2 = next(f for f in tools.list_files(shield, S, "projections")["files"] if f["version"] == 2)
    view = tools.propose_send_document(shield, S, priya["handle"], v2["handle"])
    a = shield.guard.actions[view["action_id"]]
    assert a.payload.file_id == "proj_v3"


def test_approval_requires_owner_and_matching_seal(shield):
    _, priya, v3 = _priya_flow(shield)
    a = shield.guard.actions[tools.propose_send_document(shield, S, priya["handle"], v3["handle"])["action_id"]]
    with pytest.raises(Unauthorized):
        shield.guard.approve(a.id, None, a.payload_hash)
    with pytest.raises(Conflict):
        shield.guard.approve(a.id, "owner", "0" * 64)
    assert a.state == State.AWAITING_APPROVAL and shield.mail.outbox == []


def test_double_approve_sends_once_and_reject_after_is_noop(shield):
    _, priya, v3 = _priya_flow(shield)
    a = shield.guard.actions[tools.propose_send_document(shield, S, priya["handle"], v3["handle"])["action_id"]]
    shield.guard.approve(a.id, "owner", a.payload_hash)
    shield.guard.approve(a.id, "owner", a.payload_hash)
    shield.guard.reject(a.id, "owner")
    assert len(shield.mail.outbox) == 1 and a.state == State.VERIFIED


def test_illegal_transition_raises(shield):
    _, priya, v3 = _priya_flow(shield)
    a = shield.guard.actions[tools.propose_send_document(shield, S, priya["handle"], v3["handle"])["action_id"]]
    with pytest.raises(IllegalTransition):
        shield.guard._to(a, State.VERIFIED)


def test_build_mime_is_deterministic(shield):
    _, priya, v3 = _priya_flow(shield)
    a = shield.guard.actions[tools.propose_send_document(shield, S, priya["handle"], v3["handle"])["action_id"]]
    data = shield.seed.read_file_once(shield.seed.file("proj_v3"))
    assert build_mime(a.payload, data) == build_mime(a.payload, data)
    assert seal(a.payload) == a.payload_hash


def test_tamper_after_approval_screen_fails(shield):
    _, priya, v3 = _priya_flow(shield)
    a = shield.guard.actions[tools.propose_send_document(shield, S, priya["handle"], v3["handle"])["action_id"]]
    p = shield.seed.runtime_files / "Projections_v3.pdf"
    p.write_bytes(p.read_bytes() + b"tampered")
    out = shield.guard.approve(a.id, "owner", a.payload_hash)
    assert out.state == State.FAILED and "changed after approval" in out.reason
    assert shield.mail.outbox == []


def test_added_bcc_after_seal_fails(shield):
    _, priya, v3 = _priya_flow(shield)
    a = shield.guard.actions[tools.propose_send_document(shield, S, priya["handle"], v3["handle"])["action_id"]]
    a.payload.bcc = ["attacker@evil.io"]
    out = shield.guard.approve(a.id, "owner", a.payload_hash)
    assert out.state == State.FAILED and shield.mail.outbox == []


def test_timeout_after_send_pending_then_verified_sent_once(shield):
    _, priya, v3 = _priya_flow(shield)
    a = shield.guard.actions[tools.propose_send_document(shield, S, priya["handle"], v3["handle"])["action_id"]]
    shield.mail.fail_mode = "timeout_after_send"
    out = shield.guard.approve(a.id, "owner", a.payload_hash)
    assert out.state == State.VERIFICATION_PENDING
    assert "will not send it again" in shield.guard.status_text(out)
    run_pending(shield)
    assert a.state == State.VERIFIED and shield.mail.send_calls == 1 and len(shield.mail.outbox) == 1


def test_timeout_before_send_ends_unverified_never_resent(shield):
    _, priya, v3 = _priya_flow(shield)
    a = shield.guard.actions[tools.propose_send_document(shield, S, priya["handle"], v3["handle"])["action_id"]]
    shield.mail.fail_mode = "timeout_before_send"
    shield.guard.approve(a.id, "owner", a.payload_hash)
    run_pending(shield)
    assert a.state == State.UNVERIFIED and shield.mail.send_calls == 1 and shield.mail.outbox == []


def test_provider_reject_is_failed(shield):
    _, priya, v3 = _priya_flow(shield)
    a = shield.guard.actions[tools.propose_send_document(shield, S, priya["handle"], v3["handle"])["action_id"]]
    shield.mail.fail_mode = "reject"
    assert shield.guard.approve(a.id, "owner", a.payload_hash).state == State.FAILED


def test_lagging_readback_verifies_after_retries(shield):
    _, priya, v3 = _priya_flow(shield)
    a = shield.guard.actions[tools.propose_send_document(shield, S, priya["handle"], v3["handle"])["action_id"]]
    shield.mail.lag = 2
    assert shield.guard.approve(a.id, "owner", a.payload_hash).state == State.VERIFICATION_PENDING
    run_pending(shield)
    assert a.state == State.VERIFIED and shield.mail.send_calls == 1


def test_fail_closed_on_internal_error(shield, monkeypatch):
    _, priya, v3 = _priya_flow(shield)
    monkeypatch.setattr(shield.seed, "read_file_once", lambda rec: (_ for _ in ()).throw(OSError("disk")))
    view = tools.propose_send_document(shield, S, priya["handle"], v3["handle"])
    assert view["state"] == "BLOCKED" and "internal" in view["status_text"]
