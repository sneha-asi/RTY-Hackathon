"""Internal models. Stable regardless of what the voice platform sends."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ---------- seed data ----------
class Contact(BaseModel):
    id: str
    name: str
    org: str
    email: str
    role: str
    nda: bool

    @property
    def first_name(self) -> str:
        return self.name.split()[0]


class FileRecord(BaseModel):
    id: str
    category: str
    version: int
    path: str
    requires_nda: bool
    sha256: str = ""
    filename: str = ""

    @property
    def label(self) -> str:
        if self.category == "teaser":
            return "the Teaser Deck"
        return f"{self.category.replace('_', ' ').title()} v{self.version}"


class Founder(BaseModel):
    name: str
    company: str
    registered_numbers: list[str]
    pin: str
    sender_email: str
    policies: dict[str, dict[str, bool]]


# ---------- extraction: a proposal, untrusted ----------
CommitmentType = Literal["send_document", "follow_up", "intro", "other"]


class Commitment(BaseModel):
    type: CommitmentType
    person_name: str = ""
    person_org: str | None = None
    doc_category: str | None = None
    second_person_name: str | None = None
    due_phrase: str | None = None
    due_iso: str | None = None
    note: str = ""


class Extraction(BaseModel):
    commitments: list[Commitment] = Field(default_factory=list)
    unclear: list[str] = Field(default_factory=list)
    suspicious: list[str] = Field(default_factory=list)


# ---------- actions ----------
class State(str, Enum):
    PROPOSED = "PROPOSED"
    BLOCKED = "BLOCKED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    DISCARDED = "DISCARDED"
    READ_BACK = "READ_BACK"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    EXECUTING = "EXECUTING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"


TERMINAL = {State.BLOCKED, State.DISCARDED, State.CANCELLED, State.VERIFIED, State.FAILED}

# The only legal transitions. Anything else raises: a bug must never look like progress.
TRANSITIONS: dict[State, set[State]] = {
    State.PROPOSED: {State.BLOCKED, State.NEEDS_CLARIFICATION, State.READ_BACK},
    State.NEEDS_CLARIFICATION: {State.DISCARDED},
    State.READ_BACK: {State.CONFIRMED, State.CANCELLED, State.FAILED, State.BLOCKED, State.DISCARDED},
    State.CONFIRMED: {State.EXECUTING, State.FAILED},
    State.EXECUTING: {State.VERIFIED, State.FAILED},
}

CHECK_ORDER: list[str] = ["CALLER", "WHO", "WHAT", "POLICY", "LOCK", "VERIFIED"]


class Check(BaseModel):
    status: Literal["pending", "pass", "fail", "warn", "na"] = "pending"
    reason: str = ""


class Payload(BaseModel):
    """Exactly what the founder approves. Hashed into payload_hash."""
    type: str
    recipient_contact_id: str | None = None
    recipient_email: str | None = None
    subject: str = ""
    body: str = ""
    file_id: str | None = None
    file_sha256: str | None = None
    due_date: str | None = None


class Action(BaseModel):
    id: str
    call_id: str
    type: str
    state: State = State.PROPOSED
    payload: Payload | None = None
    payload_hash: str | None = None
    readback: str = ""
    readback_delivered_at: str | None = None
    clarification: str | None = None
    clarification_candidates: list[str] = Field(default_factory=list)
    commitment: Commitment | None = None
    checks: dict[str, Check] = Field(default_factory=lambda: {c: Check() for c in CHECK_ORDER})
    reason: str = ""
    result_message: str = ""
    sent_message_id: str | None = None
    display: dict[str, str] = Field(default_factory=dict)
    created_at: str = ""


class CallSession(BaseModel):
    call_id: str
    caller_number: str | None = None
    direction: Literal["inbound", "outbound"] = "inbound"
    number_registered: bool = False
    verified: bool = False
    pin_attempts: int = 0
    locked: bool = False
    transcript: list[dict[str, str]] = Field(default_factory=list)
    created_at: str = ""


class Reminder(BaseModel):
    id: str
    action_id: str
    contact_id: str | None
    due_date: str
    text: str
