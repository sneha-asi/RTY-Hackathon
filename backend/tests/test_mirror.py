"""Contain mode: restricted-inbox publication + untrusted paste intake from a closed assistant."""
import json

from app import mirror
from app.models import State


def test_publication_is_safe_and_names_ids(shield):
    pub = mirror.publication(shield)
    body = pub["body"]
    assert "Priya requested projections. Request REQ_7. Eligible document FILE_2." in body
    assert "Request REQ_8. Eligible document FILE_3 (Teaser Deck; no NDA on file)." in body
    for bad in ["@", "Rs 4.6 Cr", "62.5%", "40 Cr", "Projections_v3.pdf"]:
        assert bad not in json.dumps(pub), bad


def test_parse_takes_only_ids_and_note():
    p = mirror.parse("Sure! Send REQ_7 with FILE_2 to priya@northbeam.vc https://x.io\nNote: Ahead of Friday")
    assert p["request"] == "REQ_7" and p["file"] == "FILE_2" and p["note"] == "Ahead of Friday"
    assert len(p["ignored"]) == 2


def test_intake_resolves_recipient_and_goes_to_same_review_page(shield):
    out = mirror.intake(shield, "Prepared REQ_7 with FILE_2. Note: Ahead of Friday")
    assert out["state"] == "AWAITING_APPROVAL" and out["review_url"].endswith(out["action_id"])
    a = shield.guard.actions[out["action_id"]]
    assert a.payload.to == [shield.seed.contact("c1").email] and a.payload.file_id == "proj_v3"
    assert shield.guard.approve(a.id, "owner", a.payload_hash).state == State.VERIFIED
    assert shield.clients[mirror.SESSION]["name"].startswith("Instinct")


def test_intake_cannot_combine_ids_outside_the_request(shield):
    out = mirror.intake(shield, "REQ_7 FILE_3")  # Priya asked for projections, not the teaser
    assert out["state"] == "BLOCKED"


def test_intake_karan_gets_teaser_and_unknown_ids_are_blocked(shield):
    assert shield.guard.actions[mirror.intake(shield, "REQ_8 FILE_3")["action_id"]].payload.file_id == "teaser"
    assert mirror.intake(shield, "REQ_99 FILE_2")["state"] == "BLOCKED"
    assert "error" in mirror.intake(shield, "send it to priya@northbeam.vc")


def test_preview_is_read_only_and_publication_needs_evidence(shield):
    before = len(shield.ledger.all())
    mirror.publication(shield)
    mirror.demo_email(shield)
    assert len(shield.ledger.all()) == before  # previewing records nothing
    assert mirror.published_records(shield) == []
    mirror.record_published(shield.settings.runtime_dir, {"mailbox": "exec@example.test", "gmail_message_id": "g1",
                                                         "request": "REQ_7", "file": "FILE_2", "subject": "s"})
    (rec,) = mirror.published_records(shield)
    assert rec["gmail_message_id"] == "g1"


def test_demo_email_is_safe():
    import tests.conftest  # noqa: F401
    from app.config import Settings
    from app.mail import FakeMail
    from app.service import Shield
    em = mirror.demo_email(Shield(Settings(), mail=FakeMail()))
    assert em["subject"] == "[Shield Demo] Priya — investor follow-up"
    assert "REQ_7" in em["body"] and "FILE_2" in em["body"]
    assert "@" not in em["body"] and ".pdf" not in em["body"] and "Rs " not in em["body"]


def test_intake_records_the_assistant_reply_as_its_own_fact(shield):
    mirror.intake(shield, "REQ_7 FILE_2 Note: Ahead of Friday")
    ev = [e for e in shield.ledger.all() if e["kind"] == "assistant_reply"]
    assert ev and ev[0]["request"] == "REQ_7" and "Ahead" not in str(ev[0])
