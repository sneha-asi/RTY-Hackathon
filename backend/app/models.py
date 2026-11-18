"""Shield data shapes (LLD §3). Every model-facing type is built by Shield (I1)."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

Label = Literal["financial", "legal", "hr", "health", "identity_ids", "secrets", "deal"]


# ---------- seed ----------
class Contact(BaseModel):
    id: str
    name: str
    org: str
    email: str
    role: str
    nda: bool
    trusted: bool = False

    @property
    def first_name(self) -> str:
        return self.name.split()[0]


class FileRecord(BaseModel):
    id: str
    category: str
    version: int
    path: str
    requires_nda: bool
    sensitivity: list[str] = Field(default_factory=list)
    shareable: bool = True
    sha256: str = ""
    filename: str = ""

    @property
    def label(self) -> str:
        if self.category == "teaser":
            return "Teaser Deck"
        return f"{self.category.replace('_', ' ').title()} v{self.version}"


class Item(BaseModel):
    """A normalised source item (email or event)."""
    id: str
    kind: Literal["email", "event"]
    thread_id: str | None = None
    sender: str
    to: list[str] = Field(default_factory=list)
    subject: str = ""
    body_html: str = ""
    ts: str = ""
    attachments: list[str] = Field(default_factory=list)
    start: str | None = None
    end: str | None = None


# ---------- read path ----------
class Handle(BaseModel):
    handle: str
    kind: Literal["CONTACT", "SENDER", "FILE", "THREAD", "EVENT"]
    ref: str  # SERVER ONLY: contact id / raw address / file id / thread id
    attrs: dict[str, Any] = Field(default_factory=dict)


class ReleasedItem(BaseModel):
    handle: str
    kind: str
    sender: str  # handle
    intent: str
    requested_category: str | None = None
    due: str | None = None
    summary: str | None = None
    status: Literal["released", "quarantined"] = "released"
    reason: str | None = None


# ---------- write path ----------
class State(str, Enum):
    PROPOSED = "PROPOSED"
    BLOCKED = "BLOCKED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    REJECTED = "REJECTED"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    UNVERIFIED = "UNVERIFIED"


TRANSITIONS: dict[State, set[State]] = {
    State.PROPOSED: {State.BLOCKED, State.AWAITING_APPROVAL},
    State.AWAITING_APPROVAL: {State.APPROVED, State.REJECTED},
    State.APPROVED: {State.EXECUTING, State.FAILED},  # FAILED = definitely not sent
    State.EXECUTING: {State.VERIFIED, State.FAILED, State.VERIFICATION_PENDING, State.UNVERIFIED},
    State.VERIFICATION_PENDING: {State.VERIFIED, State.UNVERIFIED},
}
TERMINAL = {State.BLOCKED, State.REJECTED, State.VERIFIED, State.FAILED, State.UNVERIFIED}
SUCCESS = {State.VERIFIED}
CHECKS = ["WHO", "WHAT", "POLICY", "CONTENT", "LOCK"]


class IllegalTransition(Exception):
    pass


class Check(BaseModel):
    name: str
    status: Literal["pending", "pass", "warn", "fail"] = "pending"
    detail: str = ""


class Payload(BaseModel):
    """Exactly what the user approves (LLD §5.3)."""
    type: Literal["send_document"] = "send_document"
    recipient_contact_ids: list[str]
    to: list[str]
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)
    sender: str
    subject: str
    body: str
    file_id: str | None = None
    file_name: str | None = None
    attachment_sha256: str | None = None
    message_id: str
    date: str
    boundary: str
    message_sha256: str = ""


class Action(BaseModel):
    id: str
    policy: str = ""
    request_handle: str | None = None
    session_id: str
    type: str
    state: State = State.PROPOSED
    args: dict[str, Any] = Field(default_factory=dict)
    payload: Payload | None = None
    payload_hash: str | None = None
    checks: list[Check] = Field(default_factory=lambda: [Check(name=c) for c in CHECKS])
    warnings: list[str] = Field(default_factory=list)
    reason: str = ""
    display: dict[str, str] = Field(default_factory=dict)  # names/labels for status text (no addresses)
    send_attempted: bool = False
    sent_message_id: str | None = None
    verification: dict[str, Any] | None = None
    verify_attempts: int = 0
    approved_by: str | None = None
    created_at: str = ""
    updated_at: str = ""

    def check(self, name: str) -> Check:
        return next(c for c in self.checks if c.name == name)
