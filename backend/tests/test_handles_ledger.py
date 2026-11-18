"""Handles (I1) and ledger privacy (I8)."""
import json

from app import receipts, tools
from app.handles import HandleRegistry


def test_handles_stable_within_session_and_independent_across(shield):
    r1, r2 = HandleRegistry(shield.seed), HandleRegistry(shield.seed)
    a = r1.for_contact("c4")
    assert r1.for_contact("c4").handle == a.handle == "CONTACT_1"
    r2.for_contact("c1")
    assert r2.for_contact("c4").handle == "CONTACT_2"


def test_unknown_address_becomes_sender_without_address(shield):
    h = HandleRegistry(shield.seed).for_address("growth@quickcap-partners.io")
    assert h.kind == "SENDER" and "@" not in json.dumps(h.attrs)


def test_handle_attrs_never_hold_addresses_or_paths(shield):
    reg = HandleRegistry(shield.seed)
    hs = [reg.for_contact(c.id) for c in shield.seed.contacts] + [reg.for_file(f.id) for f in shield.seed.files]
    blob = json.dumps([h.attrs for h in hs])
    assert "@" not in blob and "files/" not in blob and ".pdf" not in blob


def test_resolve_rejects_non_handles(shield):
    reg = HandleRegistry(shield.seed)
    reg.for_contact("c1")
    assert reg.resolve("CONTACT_1") and reg.resolve("priya@northbeam.vc") is None and reg.resolve("CONTACT_9") is None


def test_ledger_holds_no_addresses_or_bodies(shield):
    s = "sess-l"
    res = tools.search(shield, s, "share_document", "investor")
    priya = next(i for i in res["items"] if (i["summary"] or "").startswith("Priya"))
    v3 = next(f for f in tools.list_files(shield, s, "projections")["files"] if f["latest"])
    a = shield.guard.actions[tools.propose_send_document(shield, s, priya["handle"], v3["handle"], "Ahead of Friday")["action_id"]]
    shield.guard.approve(a.id, "owner", a.payload_hash)
    receipts.answer(shield, "Did any AI see my cap table today?")
    blob = json.dumps(shield.ledger.all()) + (shield.settings.runtime_dir / "ledger.jsonl").read_text()
    for forbidden in ["priya@northbeam.vc", "founder@test.dev", "Please find", "Ahead of Friday", "40 Cr", "ABCPE1234F"]:
        assert forbidden not in blob, forbidden
    journal = (shield.settings.runtime_dir / "send_journal.jsonl").read_text()
    assert "%PDF" not in journal  # journal holds ids and seals, never attachment bytes
