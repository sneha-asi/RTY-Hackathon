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
from .handles import HANDLE_RX, HandleRegistry
from .ledger import Ledger, now_iso
from .mail import DefinitelyNotSent
from .models import TERMINAL, TRANSITIONS, Action, IllegalTransition, Payload, State
from .seed import Seed, norm_addr, sha256_bytes

URL_RX = re.compile(
    r"https?://|www\.|\b(?:[a-z0-9-]+\.)+[a-z]{2,24}/"  # any scheme, www., or domain followed by a path
    r"|\b(?:[a-z0-9-]+\.)+(?:com|io|net|co|ai|in|org|app|dev|me|xyz|link|ly|gl|to|so|sh|site|page|cloud|biz|info|us|uk)\b",
    re.I)
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


def content_problems(text: str, max_len: int) -> list[str]:
    """CONTENT check (I5): model-written text may not carry an outbound channel or sensitive values."""
    problems = []
    if URL_RX.search(text):
        problems.append("external link in outgoing text")
    if IMG_RX.search(text):
        problems.append("image in outgoing text")
    if HANDLE_IN_TEXT.search(text):
        problems.append("handle leaked into text")
    spans = labels.detect(text)
    if any(sp.detector == "email" for sp in spans):
        problems.append("raw address in text")
    sens = sorted({sp.detector.upper() for sp in spans if sp.detector != "email"})
    if sens:
        problems.append(f"sensitive value in text: {', '.join(sens)}")
    if len(text) > max_len:
        problems.append("too long")
    return problems


def _norm_body(b: str) -> str:
    return re.sub(r"\s+", " ", (b or "").replace("\r\n", "\n")).strip()


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
                 scheduler: Callable[[Callable[[], None]], None] | None = None, journal=None,
                 sent_label: str = "Sent (sandbox)"):
        self.seed, self.ledger, self.mail = seed, ledger, mail
        self.journal = journal
        self.sent_label = sent_label
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
        if self.journal and a.send_attempted and new in TERMINAL:
            self.journal.outcome(a.id, new.value)
        return a

    def _lock(self, aid: str) -> threading.Lock:
        return self._locks.setdefault(aid, threading.Lock())

    # ---------- propose ----------
    def propose_send_document(self, session_id: str, reg: HandleRegistry, request: str, file: str, note: str = "") -> Action:
        """Bound to a request released in THIS session under the session's standing policy."""
        a = Action(id="act_" + uuid.uuid4().hex[:8], session_id=session_id, type="send_document", policy=reg.policy_name,
                   request_handle=request if isinstance(request, str) else None,
                   args={"request": request, "file": file, "note": note}, created_at=now_iso(), updated_at=now_iso())
        self.actions[a.id] = a
        self.ledger.emit("transition", session_id=session_id, action_id=a.id, frm=None, to=State.PROPOSED.value, reason="")
        try:
            return self._run_checks(a, reg, request, file, note or "")
        except Exception as e:  # fail closed (I9)
            for c in a.checks:
                if c.status == "pending":
                    c.status, c.detail = "fail", "not evaluated"
            return self._to(a, State.BLOCKED, f"internal: {type(e).__name__}")

    def _run_checks(self, a: Action, reg: HandleRegistry, request: str, file: str, note: str) -> Action:
        who, what, policy, content, lock = (a.check(n) for n in ("WHO", "WHAT", "POLICY", "CONTENT", "LOCK"))
        pol = reg.policy
        contact, req = None, None
        # argument gate + WHO: the recipient comes from the request, never from the model (I4)
        if any(isinstance(v, str) and ("@" in v or "://" in v) for v in (request, file)):
            who.status, who.detail = "fail", "raw address not accepted; use a handle"
        elif not pol.get("enabled"):
            who.status, who.detail = "fail", "no standing policy enabled for this session"
        else:
            req = reg.requests.get(request)
            if req is None:
                who.status, who.detail = "fail", "not a request released in this session"
            else:
                sh = reg.resolve(req["sender"])
                if sh is None or sh.kind == "SENDER":
                    who.status, who.detail = "fail", "unknown recipient: add them as a contact first"
                else:
                    contact = self.seed.contact(sh.ref)
                    if contact.role not in pol.get("recipient_roles", []):
                        who.status, who.detail = "fail", f"{contact.role} is outside policy '{reg.policy_name}'"
                        contact = None
                    else:
                        who.status, who.detail = "pass", f"{contact.name} · {contact.org} (from {request})"
        # WHAT: the file must match what the request asked for (teaser fallback is the only exception)
        frec = None
        fh = reg.resolve(file)
        if fh is None or fh.kind != "FILE":
            what.status, what.detail = "fail", "unknown file handle"
        else:
            frec = self.seed.file(fh.ref)
            asked = req["category"] if req else None
            if not frec.shareable:
                what.status, what.detail = "fail", "file is not shareable"
                frec = None
            elif asked is not None and asked not in pol.get("categories", []):
                what.status, what.detail = "fail", f"request asks for {asked.replace('_', ' ')}, which policy '{reg.policy_name}' does not cover"
                frec = None
            elif asked is not None and frec.category != asked:
                what.status, what.detail = "fail", f"request asked for {asked}, not {frec.category}"
                frec = None
            else:
                latest = self.seed.latest(frec.category)
                if latest and latest.id != frec.id:
                    a.warnings.append(f"{frec.label} requested; using latest {latest.label}")
                    frec = latest
                if contact and frec.requires_nda and not contact.nda and pol.get("nda_fallback"):
                    fb = self.seed.file(pol["nda_fallback"])
                    a.warnings.append(f"{contact.first_name} has no NDA: sending {fb.label} instead of {frec.label}")
                    frec = fb
                if what.status == "pending":
                    what.status = "warn" if a.warnings else "pass"
                    what.detail = f"{frec.label} · {frec.filename}" + (f" ({'; '.join(a.warnings)})" if a.warnings else "")
        # POLICY
        if frec is None:
            policy.status, policy.detail = "fail", "no file to check"
        elif set(frec.sensitivity) & set(pol.get("never_share", [])):
            policy.status, policy.detail = "fail", f"{', '.join(sorted(set(frec.sensitivity) & set(pol['never_share'])))} is never shared"
        elif "financial" in frec.sensitivity and not (contact and contact.nda):
            policy.status, policy.detail = "fail", "financial file needs a known contact with an NDA"
        else:
            policy.status = "pass"
            policy.detail = f"{reg.policy_name} · " + ("financial, NDA on file" if "financial" in frec.sensitivity else "no restriction")
        # CONTENT (I5)
        problems = content_problems(note, MAX_NOTE)
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
        return self._seal_and_queue(a, "send_document", contact, frec.label, body, frec, {"file": frec.label})

    def _seal_and_queue(self, a: Action, kind: str, contact, subject: str, body: str, frec, display: dict) -> Action:
        """Build the exact outgoing MIME once, seal recipient + bytes + attachment hash, queue for approval (I6)."""
        lock = a.check("LOCK")
        p = Payload(type=kind, recipient_contact_ids=[contact.id], to=[contact.email], sender=self.sender_addr,
                    subject=subject, body=body, file_id=frec.id if frec else None,
                    file_name=frec.filename if frec else None,
                    message_id=f"<{a.id}.{uuid.uuid4().hex[:6]}@shield.local>",
                    date=format_datetime(datetime.now(TZ)), boundary=f"shield-{a.id}")
        data = self.seed.read_file_once(frec) if frec else None
        p.attachment_sha256 = sha256_bytes(data) if data is not None else None
        p.message_sha256 = sha256_bytes(build_mime(p, data))
        if p.cc or p.bcc or len(p.to) != 1:  # M0 contract: exactly one To recipient
            lock.status, lock.detail = "fail", "M0 supports exactly one To recipient"
            return self._to(a, State.BLOCKED, "LOCK: M0 supports exactly one To recipient")
        a.payload, a.payload_hash = p, seal(p)
        a.display = {"recipient": contact.name, **display}
        lock.status, lock.detail = "pass", f"sealed {a.payload_hash[:12]}"
        return self._to(a, State.AWAITING_APPROVAL)

    # ---------- propose_reply (PRD §10.3) ----------
    def propose_reply(self, session_id: str, reg: HandleRegistry, thread: str, text: str) -> Action:
        """Reply to a thread released in this session. Recipient comes from the thread; text is model-written,
        so CONTENT is the main gate (the EchoLeak channel). No attachment."""
        a = Action(id="act_" + uuid.uuid4().hex[:8], session_id=session_id, type="reply", policy=reg.policy_name,
                   request_handle=thread if isinstance(thread, str) else None,
                   args={"thread": thread, "text": text}, created_at=now_iso(), updated_at=now_iso())
        self.actions[a.id] = a
        self.ledger.emit("transition", session_id=session_id, action_id=a.id, frm=None, to=State.PROPOSED.value, reason="")
        try:
            who, what, policy, content = (a.check(n) for n in ("WHO", "WHAT", "POLICY", "CONTENT"))
            pol, contact = reg.policy, None
            t = reg.threads.get(thread) if isinstance(thread, str) else None
            if isinstance(thread, str) and ("@" in thread or "://" in thread):
                who.status, who.detail = "fail", "raw address not accepted; use a handle"
            elif t is None:
                who.status, who.detail = "fail", "not a thread released in this session"
            else:
                sh = reg.resolve(t["sender"])
                if sh is None or sh.kind == "SENDER":
                    who.status, who.detail = "fail", "unknown recipient: add them as a contact first"
                else:
                    contact = self.seed.contact(sh.ref)
                    if contact.role not in pol.get("recipient_roles", []):
                        who.status, who.detail = "fail", f"{contact.role} is outside policy '{reg.policy_name}'"
                        contact = None
                    else:
                        who.status, who.detail = "pass", f"{contact.name} · {contact.org} (from {thread})"
            what.status, what.detail = "pass", "text reply, no attachment"
            if "reply" not in pol.get("actions", []):
                policy.status, policy.detail = "fail", f"replies are outside policy '{reg.policy_name}'"
            else:
                policy.status, policy.detail = "pass", f"{reg.policy_name} · reply"
            text = text or ""
            problems = content_problems(text, MAX_NOTE) or ([] if text.strip() else ["empty reply"])
            content.status, content.detail = ("fail", "; ".join(problems)) if problems else ("pass", "clean")
            failed = [c for c in a.checks if c.status == "fail"]
            if failed:
                a.check("LOCK").status, a.check("LOCK").detail = "fail", "not sealed"
                return self._to(a, State.BLOCKED, f"{failed[0].name}: {failed[0].detail}")
            item = next(i for i in self.seed.items if i.id == t["item_id"])
            subject = item.subject if item.subject.lower().startswith("re:") else f"Re: {item.subject}"
            body = f"Hi {contact.first_name},\n\n{text.strip()}\n\n— {self.founder_name}\n"
            return self._seal_and_queue(a, "reply", contact, subject, body, None, {"file": "your reply"})
        except Exception as e:  # fail closed (I9)
            for c in a.checks:
                if c.status == "pending":
                    c.status, c.detail = "fail", "not evaluated"
            return self._to(a, State.BLOCKED, f"internal: {type(e).__name__}")

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
            frec = self.seed.file(p.file_id) if p.file_id else None
            data = self.seed.read_file_once(frec) if frec else None  # read ONCE; these bytes are checked and sent
            if (sha256_bytes(data) if data is not None else None) != p.attachment_sha256:
                return self._to(a, State.FAILED, "changed after approval: attachment")
            raw = build_mime(p, data)
            if sha256_bytes(raw) != p.message_sha256 or seal(p) != a.payload_hash:
                return self._to(a, State.FAILED, "changed after approval: message")
            if self.journal and self.journal.attempted(a.id):  # survived a restart: verify only, never resend
                self._to(a, State.EXECUTING)
                a.send_attempted = True
                self._to(a, State.VERIFICATION_PENDING, "send already attempted before restart")
                self._scheduler(lambda: self._verify_loop(a.id))
                return a
            self._to(a, State.EXECUTING)
            a.send_attempted = True  # before the provider call: at most once (I7)
            if self.journal:
                self.journal.attempt(a.model_dump(mode="json"))  # durable marker, fsynced before sending
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
                return self._to(a, State.VERIFIED, f"found in {self.sent_label}; recipient, subject, body and attachment match")
            if verdict == "mismatch":
                return self._to(a, State.UNVERIFIED, f"sent record differs from approval: {self._first_mismatch(a)}")
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
            "body": _norm_body(s.body) == _norm_body(p.body),
            "attachment": s.attachments == ([(p.file_name, p.attachment_sha256)] if p.file_id else []),
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
                    self._to(a, State.VERIFIED, f"found in {self.sent_label}; matches approval")
                    return
                if v == "mismatch":
                    self._to(a, State.UNVERIFIED, f"sent record differs from approval: {self._first_mismatch(a)}")
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
            State.VERIFIED: f"Verified in {self.sent_label}: {f} to {r}; recipient, message and attachment fingerprint match what you approved.",
            State.FAILED: f"Not sent: {a.reason}.",
            State.UNVERIFIED: (f"Sent, but the {self.sent_label} record differs from what you approved ({a.reason.split(': ')[-1]}). Not counted as done."
                               if "differs" in a.reason else
                               f"May have been sent, but Shield could not confirm it in {self.sent_label}. It will not be resent. Not counted as done."),
        }[a.state]

    def view_for_model(self, a: Action) -> dict:
        return {"action_id": a.id, "state": a.state.value, "status_text": self.status_text(a),
                "request": a.request_handle if a.request_handle and HANDLE_RX.match(a.request_handle) else None,
                "checks": [{"name": c.name, "status": c.status, "detail": c.detail} for c in a.checks],
                "warnings": a.warnings}

    # ---------- restart recovery ----------
    def recover(self) -> list[str]:
        """Actions with a durable send-attempt marker and no outcome: verify only, never send."""
        recovered = []
        if not self.journal:
            return recovered
        for d in self.journal.open_attempts():
            a = Action.model_validate(d)
            a.state, a.send_attempted = State.VERIFICATION_PENDING, True
            a.reason = "recovered after restart: send was attempted; verifying only"
            self.actions[a.id] = a
            self.ledger.emit("transition", session_id=a.session_id, action_id=a.id, frm="EXECUTING",
                             to=State.VERIFICATION_PENDING.value, reason=a.reason)
            self._scheduler(lambda aid=a.id: self._verify_loop(aid))
            recovered.append(a.id)
        return recovered
