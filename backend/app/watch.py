"""Watch & verify (PRD §4, mode 4) for a mailbox an assistant reaches directly (e.g. Instinct on the executive's Gmail).
Shield can't sit in that path, so it reads the mailbox's own Sent and Drafts records and flags anything Shield did
not approve: confidential files, unknown recipients, sensitive values, links. Drafts can be removed before they go
out; sent mail can only be reported (plus revoke the assistant's access). Read-only except the optional draft delete."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Protocol

from . import cleaner, labels
from .guard import URL_RX
from .ledger import now_iso
from .mail import SentMessage
from .seed import norm_addr

REVOKE_URL = "https://myaccount.google.com/connections"


@dataclass
class Observed:
    """A message found in the watched mailbox's Sent or Drafts."""
    kind: str  # "sent" | "draft"
    msg: SentMessage
    draft_id: str | None = None
    date: str = ""


class WatchSource(Protocol):
    label: str
    def recent(self) -> list[Observed]: ...
    def delete_draft(self, draft_id: str) -> bool: ...


@dataclass
class Alert:
    id: str
    kind: str
    severity: str  # "high" | "medium" | "ok"
    to: list[str]
    subject: str
    reasons: list[str]
    approved_by_shield: bool
    draft_id: str | None
    seen_at: str
    status: str = "open"  # open | draft_deleted | dismissed
    attachments: list[str] = field(default_factory=list)


class Watcher:
    def __init__(self, shield, source: WatchSource):
        self.shield, self.source = shield, source
        self.alerts: dict[str, Alert] = {}
        self._lock = threading.Lock()

    def _approved_ids(self) -> set[str]:
        ids = set()
        for a in self.shield.guard.actions.values():
            if a.payload and a.state.value in ("VERIFIED", "VERIFICATION_PENDING", "UNVERIFIED", "EXECUTING"):
                ids.add(a.payload.message_id.strip("<>"))
                if a.sent_message_id:
                    ids.add(a.sent_message_id)
        return ids

    def assess(self, o: Observed) -> Alert:
        seed = self.shield.seed
        m = o.msg
        contacts = {norm_addr(c.email): c for c in seed.contacts}
        by_sha = {f.sha256: f for f in seed.files}
        approved = (m.message_id_header.strip("<>") in self._approved_ids() or m.provider_id in self._approved_ids())
        reasons = []
        recips = m.to + m.cc + m.bcc
        unknown = [r for r in recips if norm_addr(r) not in contacts]
        if unknown:
            reasons.append(f"unknown recipient: {', '.join(unknown)}")
        att_names = []
        for name, sha in m.attachments:
            f = by_sha.get(sha)
            att_names.append(name or "attachment")
            if f is None:
                continue
            if not f.shareable:
                reasons.append(f"confidential file attached: {f.label} ({', '.join(f.sensitivity)})")
            elif f.requires_nda and any(not contacts.get(norm_addr(r)) or not contacts[norm_addr(r)].nda for r in recips):
                reasons.append(f"NDA-only file to a recipient without an NDA: {f.label}")
        text = f"{m.subject}\n{m.body}"
        spans = [s for s in labels.detect(text) if s.detector != "email"]
        if spans:
            reasons.append("sensitive values in the message: " + ", ".join(sorted({s.detector.upper() for s in spans})))
        labs = labels.labels_for(text) - {"financial"} if not spans else set()
        if labs & {"hr", "health", "secrets", "deal", "legal"}:
            reasons.append("sensitive topic: " + ", ".join(sorted(labs & {"hr", "health", "secrets", "deal", "legal"})))
        if URL_RX.search(m.body or "") or "![" in (m.body or ""):
            reasons.append("link or image in the message (possible exfiltration channel)")
        hits = cleaner.scan(text)
        if hits:
            reasons.append("carries instruction-like text: " + ", ".join(hits))
        if approved:
            severity = "ok"
        elif any(r.startswith(("confidential", "unknown recipient", "sensitive values", "link")) for r in reasons):
            severity = "high"
        else:
            severity = "medium" if reasons else "ok"
        if not approved:
            reasons.insert(0, "not approved through Shield")
        return Alert(id=f"{o.kind}:{m.provider_id}", kind=o.kind, severity=severity, to=recips, subject=m.subject,
                     reasons=reasons, approved_by_shield=approved, draft_id=o.draft_id, seen_at=now_iso(),
                     attachments=att_names)

    def scan(self) -> list[Alert]:
        found = self.source.recent()
        with self._lock:
            for o in found:
                aid = f"{o.kind}:{o.msg.provider_id}"
                if aid in self.alerts:
                    continue
                al = self.assess(o)
                self.alerts[aid] = al
                if al.severity != "ok":
                    self.shield.ledger.emit("watch_alert", alert_id=aid, where=al.kind, severity=al.severity,
                                            reasons=[r.split(":")[0] for r in al.reasons])
            return sorted(self.alerts.values(), key=lambda a: a.seen_at, reverse=True)

    def delete_draft(self, alert_id: str) -> Alert:
        al = self.alerts[alert_id]
        if al.kind != "draft" or not al.draft_id:
            raise ValueError("only drafts can be removed; sent mail can only be reported (revoke access instead)")
        if self.source.delete_draft(al.draft_id):
            al.status = "draft_deleted"
            self.shield.ledger.emit("watch_draft_deleted", alert_id=alert_id)
        return al


class FakeWatchSource:
    """Offline rehearsal / tests: simulate what an assistant did in the mailbox."""
    label = "simulated mailbox"

    def __init__(self):
        self.items: list[Observed] = []

    def recent(self) -> list[Observed]:
        return list(self.items)

    def delete_draft(self, draft_id: str) -> bool:
        self.items = [o for o in self.items if o.draft_id != draft_id]
        return True


class GmailWatchSource:
    """The executive's real Gmail, read-only (gmail.readonly; gmail.compose only if draft removal is wanted).
    Runs on the executive's laptop; the token never leaves it."""
    label = "Gmail"

    def __init__(self, token_path, window: str = "1d"):
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        self.svc = build("gmail", "v1", credentials=Credentials.from_authorized_user_file(str(token_path)),
                         cache_discovery=False)
        self.window = window
        self._cache: dict[str, SentMessage] = {}

    def _get(self, mid: str) -> SentMessage:
        import base64
        from .mail import parse_raw
        if mid in self._cache:
            return self._cache[mid]
        raw = self.svc.users().messages().get(userId="me", id=mid, format="raw").execute()["raw"]
        self._cache[mid] = parse_raw(base64.urlsafe_b64decode(raw), mid)
        return self._cache[mid]

    def recent(self) -> list[Observed]:
        out = []
        sent = self.svc.users().messages().list(userId="me", q=f"in:sent newer_than:{self.window}",
                                                maxResults=25).execute().get("messages", [])
        for m in sent:
            out.append(Observed("sent", self._get(m["id"])))
        drafts = self.svc.users().drafts().list(userId="me", maxResults=25).execute().get("drafts", [])
        for d in drafts:
            out.append(Observed("draft", self._get(d["message"]["id"]), draft_id=d["id"]))
        return out

    def delete_draft(self, draft_id: str) -> bool:
        self.svc.users().drafts().delete(userId="me", id=draft_id).execute()
        return True


def simulate(source: FakeWatchSource, shield, scenario: str = "forward_cap_table") -> None:
    """Rehearsal events that mirror what an injected assistant might do."""
    import uuid
    cap = shield.seed.file("cap_table")
    v3 = shield.seed.file("proj_v3")
    if scenario == "forward_cap_table":
        msg = SentMessage(provider_id="sim-" + uuid.uuid4().hex[:6], to=["audit@docs-share.co"], cc=[], bcc=[],
                          subject="Fwd: Cap table", message_id_header="<sim@local>", body="As requested. ![x](https://x.io/p?d=1)",
                          attachments=[(cap.filename, cap.sha256)])
        source.items.append(Observed("sent", msg))
    elif scenario == "draft_data_room":
        msg = SentMessage(provider_id="sim-" + uuid.uuid4().hex[:6], to=["growth@quickcap-partners.io"], cc=[], bcc=[],
                          subject="Re: New investor - data room access", message_id_header="<simd@local>",
                          body="Sharing our projections as requested.", attachments=[(v3.filename, v3.sha256)])
        source.items.append(Observed("draft", msg, draft_id="d-" + uuid.uuid4().hex[:6]))
