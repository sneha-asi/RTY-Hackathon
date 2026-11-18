"""Send-state hardening: before the provider call → FAILED (nothing sent); after it → read-back retries only."""
import json
import os
import stat

from app import tools
from app.models import State
from tests.conftest import run_pending

S = "sess-states"


def _proposal(sh):
    res = tools.search(sh, S, "share_document", "investor")
    priya = next(i for i in res["items"] if (i["summary"] or "").startswith("Priya"))
    v3 = next(f["handle"] for f in tools.list_files(sh, S, "projections")["files"] if f["latest"])
    return sh.guard.actions[tools.propose_send_document(sh, S, priya["handle"], v3, "Ahead of Friday")["action_id"]]


def test_file_read_failure_before_send_is_failed_and_unsent(shield, monkeypatch):
    a = _proposal(shield)
    monkeypatch.setattr(shield.seed, "read_file_once", lambda rec: (_ for _ in ()).throw(OSError("disk")))
    out = shield.guard.approve(a.id, "owner", a.payload_hash)
    assert out.state == State.FAILED and "before the provider call" in out.reason
    assert shield.mail.send_calls == 0


def test_journal_write_failure_is_failed_and_unsent(shield, monkeypatch):
    a = _proposal(shield)
    monkeypatch.setattr(shield.guard.journal, "attempt", lambda action: (_ for _ in ()).throw(OSError("disk full")))
    out = shield.guard.approve(a.id, "owner", a.payload_hash)
    assert out.state == State.FAILED and shield.mail.send_calls == 0 and not out.send_attempted


def test_accepted_then_readback_throws_then_verifies_with_one_send(shield, monkeypatch):
    a = _proposal(shield)
    real, calls = shield.mail.find_sent, {"n": 0}

    def flaky(mid, provider_id=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("read-back reset")
        return real(mid, provider_id=provider_id)
    monkeypatch.setattr(shield.mail, "find_sent", flaky)
    out = shield.guard.approve(a.id, "owner", a.payload_hash)
    assert out.state == State.VERIFICATION_PENDING
    run_pending(shield)
    assert a.state == State.VERIFIED and shield.mail.send_calls == 1 and len(shield.mail.outbox) == 1


def test_readback_errors_until_window_closes_end_unverified(shield, monkeypatch):
    a = _proposal(shield)
    monkeypatch.setattr(shield.mail, "find_sent", lambda mid, provider_id=None: (_ for _ in ()).throw(TimeoutError()))
    shield.guard.approve(a.id, "owner", a.payload_hash)
    run_pending(shield)
    assert a.state == State.UNVERIFIED and shield.mail.send_calls == 1


def test_journal_is_minimal_and_private(shield):
    a = _proposal(shield)
    shield.guard.approve(a.id, "owner", a.payload_hash)
    j = shield.settings.runtime_dir / "send_journal.jsonl"
    text = j.read_text()
    assert "Please find" not in text and "Ahead of Friday" not in text and "%PDF" not in text
    rec = json.loads(text.splitlines()[0])["action"]
    assert rec["payload"]["body_sha256"] and rec["payload"]["body"] == ""
    if os.name == "posix":
        assert stat.S_IMODE(os.stat(j).st_mode) == 0o600
        assert stat.S_IMODE(os.stat(j.parent).st_mode) == 0o700
