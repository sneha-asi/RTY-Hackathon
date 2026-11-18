"""Write path (LLD §5): proposals, checks, exact-message seal, owner approval, at-most-once send, verification."""
from __future__ import annotations

import email.policy
import hashlib
import json
import re
import threading
import uuid
from email.message import EmailMessage
from email.utils import format_datetime
from datetime import datetime
from typing import Callable

from . import labels
from .config import TZ
from .handles import HandleRegistry
from .ledger import Ledger, now_iso
from .mail import DefinitelyNotSent
from .models import TERMINAL, TRANSITIONS, Action, IllegalTransition, Payload, State
from .seed import Seed, norm_addr, sha256_bytes

URL_RX = re.compile(r"https?://|www\.|\b[\w-]+\.(com|io|net|co|ai|in|org)\b/?", re.I)
IMG_RX = re.compile(r"!\[|<img", re.I)
HANDLE_IN_TEXT = re.compile(r"\b(CONTACT|SENDER|FILE|THREAD|EVENT)_\d+\b")
MAX_NOTE = 1000
NEVER_SHARE = {"secrets", "hr"}


def build_mime(p: Payload, attachment: bytes | None) -> bytes:
    m = EmailMessage(policy=email.policy.SMTP)
    m["From"] = p.sender
    m["To"] = ", ".join(p.to)
    if p.cc:
        m["Cc"] = ", ".join(p.cc)
    m["Subject"] = p.subject
    m["Date"] = p.date
    m["Message-ID"] = p.message_id
    m["MIME-Version"] = "1.0"
    m.set_content(p.body)
    if attachment is not None:
        sub = "pdf" if (p.file_name or "").lower().endswith(".pdf") else "octet-stream"
        m.add_attachment(attachment, maintype="application", subtype=sub, filename=p.file_name)
        m.set_boundary(p.boundary)
    return m.as_bytes()


def seal(p: Payload) -> str:
    canon = json.dumps({
        "type": p.type,
        "to": sorted(norm_addr(a) for a in p.to),
        "cc": sorted(norm_addr(a) for a in p.cc),
        "bcc": sorted(norm_addr(a) for a in p.bcc),
        "subject": p.subject,
        "message_sha256": p.message_sha256,
        "attachment_sha256": p.attachment_sha256,
    }, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


class Unauthorized(Exception):
    pass


class Conflict(Exception):
    pass


class Guard:
    def __init__(self, seed: Seed, ledger: Ledger, mail, founder_name: str, sender_addr: str,
                 backoff: tuple[float, ...] = (1, 2, 4, 8, 15, 30, 60),
                 scheduler: Callable[[Callable[[], None]], None] | None = None):
        self.seed, self.ledger, self.mail = seed, ledger, mail
        self.founder_name, self.sender_addr = founder_name, sender_addr
        self.backoff = backoff
        self.actions: dict[str, Action] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._scheduler = scheduler or (lambda fn: threading.Thread(target=fn, daemon=True).start())

    # ---------- state ----------
    def _to(self, a: Action, new: State, reason: str = "") -> Action:
        if new not in TRANSITIONS.get(a.state, set()):
            raise IllegalTransition(f"{a.state} -> {new}")
        old, a.state, a.updated_at = a.state, new, now_iso()
        if reason:
            a.reason = reason
        self.ledger.emit("transition", session_id=a.session_id, action_id=a.id, frm=old.value, to=new.value, reason=reason)
        return a

    def _lock(self, aid: str) -> threading.Lock:
        return self._locks.setdefault(aid, threading.Lock())

    # ---------- propose ----------
    def propose_send_document(self, session_id: str, reg: HandleRegistry, recipient: str, file: str, note: str = "") -> Action:
        a = Action(id="act_" + uuid.uuid4().hex[:8], session_id=session_id, type="send_document",
                   args={"recipient": recipient, "file": file, "note": note}, created_at=now_iso(), updated_at=now_iso())
        self.actions[a.id] = a
        self.ledger.emit("transition", session_id=session_id, action_id=a.id, frm=None, to=State.PROPOSED.value, reason="")
        try:
            return self._run_checks(a, reg, recipient, file, note or "")
        except Exception as e:  # fail closed (I9)
            for c in a.checks:
                if c.status == "pending":
                    c.status, c.detail = "fail", "not evaluated"
            return self._to(a, State.BLOCKED, f"internal: {type(e).__name__}")

    def _run_checks(self, a: Action, reg: HandleRegistry, recipient: str, file: str, note: str) -> Action:
        who, what, policy, content, lock = (a.check(n) for n in ("WHO", "WHAT", "POLICY", "CONTENT", "LOCK"))
        contact = None
        # argument gate + WHO (I4)
        if any(isinstance(v, str) and ("@" in v or "://" in v) for v in (recipient, file)):
            who.status, who.detail = "fail", "raw address not accepted; use a handle"
        else:
            h = reg.resolve(recipient)
            if h is None:
                who.status, who.detail = "fail", "unknown handle"
            elif h.kind == "SENDER":
                who.status, who.detail = "fail", "unknown recipient: add them as a contact first"
            elif h.kind != "CONTACT":
                who.status, who.detail = "fail", f"{h.kind} is not a recipient"
            else:
                contact = self.seed.contact(h.ref)
                who.status, who.detail = "pass", f"{contact.name} · {contact.org}"
        # WHAT
        frec = None
        fh = reg.resolve(file)
        if fh is None or fh.kind != "FILE":
            what.status, what.detail = "fail", "unknown file handle"
        else:
            frec = self.seed.file(fh.ref)
            if not frec.shareable:
                what.status, what.detail = "fail", "file is not shareable"
            else:
                latest = self.seed.latest(frec.category)
                if latest and latest.id != frec.id:
                    a.warnings.append(f"{frec.label} requested; using latest {latest.label}")
                    frec = latest
                if contact and frec.requires_nda and not contact.nda:
                    teaser = self.seed.file("teaser")
                    a.warnings.append(f"{contact.first_name} has no NDA: sending {teaser.label} instead of {frec.label}")
                    frec = teaser
                what.status = "warn" if a.warnings else "pass"
                what.detail = f"{frec.label} · {frec.filename}" + (f" ({'; '.join(a.warnings)})" if a.warnings else "")
        # POLICY
        if frec is None:
            policy.status, policy.detail = "fail", "no file"
        elif set(frec.sensitivity) & NEVER_SHARE:
            policy.status, policy.detail = "fail", f"{', '.join(sorted(set(frec.sensitivity) & NEVER_SHARE))} is never shared"
        elif "financial" in frec.sensitivity and not (contact and contact.nda):
            policy.status, policy.detail = "fail", "financial file needs a known contact with an NDA"
        else:
            policy.status = "pass"
            policy.detail = ("financial · NDA on file" if "financial" in frec.sensitivity else "no restriction")
        # CONTENT (I5)
        problems = []
        if URL_RX.search(note):
            problems.append("external link in outgoing text")
        if IMG_RX.search(note):
            problems.append("image in outgoing text")
        if HANDLE_IN_TEXT.search(note):
            problems.append("handle leaked into text")
        spans = labels.detect(note)
        if any(s.detector == "email" for s in spans):
            problems.append("raw address in text")
        sens = sorted({s.detector.upper() for s in spans if s.detector != "email"})
        if sens:
            problems.append(f"sensitive value in text: {', '.join(sens)}")
        if len(note) > MAX_NOTE:
            problems.append("too long")
        content.status, content.detail = ("fail", "; ".join(problems)) if problems else ("pass", "clean")

        failed = [c for c in a.checks if c.status == "fail"]
        if failed:
            lock.status, lock.detail = "fail", "not sealed"
            return self._to(a, State.BLOCKED, f"{failed[0].name}: {failed[0].detail}")

        # LOCK: build the exact message and seal it (I6)
        body = f"Hi {contact.first_name},\n\nPlease find {frec.label} attached.\n"
        if note.strip():
            body += f"\n{note.strip()}\n"
        body += f"\n— {self.founder_name}\n"
        p = Payload(recipient_contact_ids=[contact.id], to=[contact.email], sender=self.sender_addr,
                    subject=frec.label, body=body, file_id=frec.id, file_name=frec.filename,
                    message_id=f"<{a.id}.{uuid.uuid4().hex[:6]}@shield.local>",
                    date=format_datetime(datetime.now(TZ)), boundary=f"shield-{a.id}")
        data = self.seed.read_file_once(frec)
        p.attachment_sha256 = sha256_bytes(data)
        p.message_sha256 = sha256_bytes(build_mime(p, data))
        a.payload, a.payload_hash = p, seal(p)
        a.display = {"recipient": contact.name, "file": frec.label}
        lock.status, lock.detail = "pass", f"sealed {a.payload_hash[:12]}"
        return self._to(a, State.AWAITING_APPROVAL)

    # ---------- approve / reject ----------
    def reject(self, aid: str, user: str | None) -> Action:
        if user != "owner":
            raise Unauthorized()
        with self._lock(aid):
            a = self.actions[aid]
            if a.state == State.AWAITING_APPROVAL:
                self._to(a, State.REJECTED, "rejected by user")
            return a

    def approve(self, aid: str, user: str | None, seal_from_screen: str) -> Action:
        if user != "owner":
            raise Unauthorized()
        with self._lock(aid):
            a = self.actions[aid]
            if a.state != State.AWAITING_APPROVAL:
                return a  # idempotent: never a second send
            if seal_from_screen != a.payload_hash:
                raise Conflict("seal mismatch")
            a.approved_by = user
            self._to(a, State.APPROVED)
            p = a.payload
            frec = self.seed.file(p.file_id)
            data = self.seed.read_file_once(frec)  # read ONCE; these bytes are checked and sent
            if sha256_bytes(data) != p.attachment_sha256:
                return self._to(a, State.FAILED, "changed after approval: attachment")
            raw = build_mime(p, data)
            if sha256_bytes(raw) != p.message_sha256 or seal(p) != a.payload_hash:
                return self._to(a, State.FAILED, "changed after approval: message")
            self._to(a, State.EXECUTING)
            a.send_attempted = True  # before the provider call: at most once (I7)
            try:
                a.sent_message_id = self.mail.send_raw(raw, envelope=p.to + p.cc + p.bcc, bcc=p.bcc)
            except DefinitelyNotSent as e:
                return self._to(a, State.FAILED, f"not sent: {e.code}")
            except Exception as e:
                self._to(a, State.VERIFICATION_PENDING, f"provider: {type(e).__name__}")
                self._scheduler(lambda: self._verify_loop(a.id))
                return a
            verdict = self.verify_once(a)
            if verdict == "ok":
                return self._to(a, State.VERIFIED, "recipients, subject and attachment fingerprint match")
            if verdict == "mismatch":
                return self._to(a, State.FAILED, f"sent but does not match approval: {self._first_mismatch(a)}")
            self._to(a, State.VERIFICATION_PENDING, "sent; read-back not visible yet")
            self._scheduler(lambda: self._verify_loop(a.id))
            return a

    # ---------- verify (I7) ----------
    def verify_once(self, a: Action) -> str:
        p = a.payload
        a.verify_attempts += 1
        s = self.mail.find_sent(p.message_id)
        if s is None:
            return "not_found"
        n = lambda xs: sorted(norm_addr(x) for x in xs)
        checks = {
            "recipients": n(s.to + s.cc + s.bcc) == n(p.to + p.cc + p.bcc),
            "subject": s.subject == p.subject,
            "attachment": s.attachments == [(p.file_name, p.attachment_sha256)],
        }
        a.verification = checks
        self.ledger.emit("verify", action_id=a.id, ok=all(checks.values()), detail=checks)
        return "ok" if all(checks.values()) else "mismatch"

    def _first_mismatch(self, a: Action) -> str:
        return next((k for k, v in (a.verification or {}).items() if not v), "unknown")

    def _verify_loop(self, aid: str, sleep: Callable[[float], None] | None = None) -> None:
        import time
        sleep = sleep or time.sleep
        a = self.actions[aid]
        for delay in self.backoff:
            sleep(delay)
            with self._lock(aid):
                if a.state != State.VERIFICATION_PENDING:
                    return
                v = self.verify_once(a)  # read only — never send_raw here
                if v == "ok":
                    self._to(a, State.VERIFIED, "found in Sent; matches approval")
                    return
                if v == "mismatch":
                    self._to(a, State.FAILED, f"sent but does not match approval: {self._first_mismatch(a)}")
                    return
        with self._lock(aid):
            if a.state == State.VERIFICATION_PENDING:
                self._to(a, State.UNVERIFIED, "could not confirm within the retry window")

    # ---------- status text (code-written, no addresses) ----------
    def status_text(self, a: Action) -> str:
        r, f = a.display.get("recipient", "the recipient"), a.display.get("file", "the file")
        return {
            State.PROPOSED: "Proposed.",
            State.BLOCKED: f"Blocked: {a.reason}.",
            State.AWAITING_APPROVAL: f"Waiting for your approval in Shield: {f} to {r}.",
            State.REJECTED: "You rejected this. Nothing was sent.",
            State.APPROVED: "Approved; sending.",
            State.EXECUTING: "Sending now.",
            State.VERIFICATION_PENDING: "The email may have been sent. Shield is checking your Sent folder and will not send it again.",
            State.VERIFIED: f"Sent and verified: {r} received {f} (fingerprint matched).",
            State.FAILED: f"Not done: {a.reason}.",
            State.UNVERIFIED: "May have been sent, but Shield could not confirm it. Check your Sent folder. Not counted as done.",
        }[a.state]

    def view_for_model(self, a: Action) -> dict:
        return {"action_id": a.id, "state": a.state.value, "status_text": self.status_text(a),
                "checks": [{"name": c.name, "status": c.status, "detail": c.detail} for c in a.checks],
                "warnings": a.warnings}
