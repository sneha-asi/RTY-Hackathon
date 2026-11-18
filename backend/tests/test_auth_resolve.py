from datetime import date
from pathlib import Path

import pytest

from app import auth
from app.extract import RuleExtractor, parse_due
from app.models import CallSession
from app.resolve import contacts_mentioned, latest_file, resolve_contact
from app.seed import Seed

BACKEND = Path(__file__).resolve().parent.parent


@pytest.fixture
def seed():
    return Seed(BACKEND / "data", BACKEND)


# ---- CALLER
@pytest.mark.parametrize("spoken", ["4321", "four three two one", "4 3 2 1", "four, three, two, one."])
def test_pin_normalisation(spoken):
    assert auth.normalize_pin(spoken) == "4321"


def test_caller_verified_needs_number_and_pin(seed):
    s = CallSession(call_id="c", caller_number="09876543210")
    assert auth.verify(s, seed.founder, "four three two one")[0] is True


def test_caller_unregistered_number_fails_even_with_right_pin(seed):
    s = CallSession(call_id="c", caller_number="+911111111111")
    ok, reason = auth.verify(s, seed.founder, "4321")
    assert not ok and "unregistered" in reason


def test_caller_locked_after_two_bad_pins(seed):
    s = CallSession(call_id="c", caller_number="+919876543210")
    assert not auth.verify(s, seed.founder, "1111")[0]
    assert not auth.verify(s, seed.founder, "2222")[0]
    assert s.locked
    assert not auth.verify(s, seed.founder, "4321")[0]  # right PIN after lock still fails


def test_missing_caller_number_never_verifies(seed):
    s = CallSession(call_id="c", caller_number=None)
    assert not auth.verify(s, seed.founder, "4321")[0]


# ---- WHO
def test_who_org_disambiguates(seed):
    m = resolve_contact(seed.contacts, "Priya", "Northbeam")
    assert m.status == "one" and m.contact.id == "c1"


def test_who_riya_is_ambiguous_with_priya(seed):
    m = resolve_contact(seed.contacts, "Riya")
    assert m.status == "many" and {c.id for c in m.candidates} == {"c1", "c2"}


def test_who_full_name_resolves(seed):
    assert resolve_contact(seed.contacts, "Riya Shah").contact.id == "c2"


def test_who_unknown_is_none(seed):
    assert resolve_contact(seed.contacts, "Rahul").status == "none"


def test_who_email_address_is_never_a_recipient(seed):
    assert resolve_contact(seed.contacts, "rahul.k@gmail.com").status == "none"


def test_who_name_and_org_disagree_asks(seed):
    # "Priya from Acme": name points at Priya Rao, org points at Riya Shah -> clarify, never guess
    m = resolve_contact(seed.contacts, "Priya", "Acme")
    assert m.status == "many" and [c.id for c in m.candidates] == ["c1", "c2"]


def test_who_single_candidate_wrong_org_is_none(seed):
    assert resolve_contact(seed.contacts, "Karan", "Northbeam").status == "none"


def test_clarification_answer_word_boundaries(seed):
    cands = [seed.contact("c1"), seed.contact("c2")]
    assert [c.id for c in contacts_mentioned("Priya Rao from Northbeam", cands)] == ["c1"]
    assert [c.id for c in contacts_mentioned("the one from Acme", cands)] == ["c2"]


# ---- WHAT
def test_what_latest_version_wins(seed):
    assert latest_file(seed.files, "projections").id == "proj_v3"
    assert latest_file(seed.files, "financials").id == "proj_v3"
    assert latest_file(seed.files, "deck") is None


def test_file_hashes_computed_from_bytes(seed):
    assert all(len(f.sha256) == 64 for f in seed.files)


# ---- extraction fallback
def test_parse_due_next_thursday():
    # Wed 18 Nov 2026 -> "next Thursday" is the Thursday of the following week
    assert parse_due("follow up next Thursday", date(2026, 11, 18))[1] == "2026-11-26"
    assert parse_due("follow up Thursday", date(2026, 11, 18))[1] == "2026-11-19"


def test_rule_extractor_brain_dump(seed):
    ex = RuleExtractor(lambda: seed.contacts).extract(
        "Just met Priya from Northbeam. I promised her the latest projections, and follow up with her next Thursday.",
        date(2026, 11, 18))
    assert [c.type for c in ex.commitments] == ["send_document", "follow_up"]
    assert ex.commitments[0].doc_category == "projections"
    assert ex.commitments[0].person_org.startswith("Northbeam")


def test_rule_extractor_flags_spoken_email(seed):
    ex = RuleExtractor(lambda: seed.contacts).extract(
        "send the projections to rahul.k@gmail.com, he's a new investor", date(2026, 11, 18))
    assert ex.suspicious
