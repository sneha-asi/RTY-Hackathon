"""Executor adapters (LLD §6): send the exact sealed bytes; find the sent copy by Message-ID."""
from __future__ import annotations

import base64
import email
import email.policy
import hashlib
import threading
from dataclasses import dataclass, field
from email.utils import getaddresses


class DefinitelyNotSent(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class SentMessage:
    provider_id: str
    to: list[str]
    cc: list[str]
    bcc: list[str]
    subject: str
    message_id_header: str
    attachments: list[tuple[str, str]] = field(default_factory=list)  # (filename, sha256)
    body: str = ""


def parse_raw(raw: bytes, provider_id: str, envelope_bcc: list[str] | None = None) -> SentMessage:
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    addrs = lambda h: [a for _, a in getaddresses(msg.get_all(h, []))]
    atts = []
    for part in msg.iter_attachments():
        data = part.get_payload(decode=True) or b""
        atts.append((part.get_filename(), hashlib.sha256(data).hexdigest()))
    bcc = addrs("Bcc") or list(envelope_bcc or [])
    body_part = msg.get_body(preferencelist=("plain",))
    body = body_part.get_content() if body_part is not None else ""
    return SentMessage(body=body, provider_id=provider_id, to=addrs("To"), cc=addrs("Cc"), bcc=bcc,
                       subject=str(msg.get("Subject", "")), message_id_header=str(msg.get("Message-ID", "")).strip(),
                       attachments=atts)


class FakeMail:
    """In-memory outbox with fault injection for tests and the sandbox demo."""

    def __init__(self) -> None:
        self.outbox: list[dict] = []
        self.fail_mode: str | None = None  # timeout_after_send | timeout_before_send | reject | lag
        self.lag = 0
        self.send_calls = 0
        self._lock = threading.Lock()

    def send_raw(self, raw: bytes, envelope: list[str], bcc: list[str] | None = None) -> str | None:
        with self._lock:
            self.send_calls += 1
            mode, self.fail_mode = self.fail_mode, None
            if mode == "reject":
                raise DefinitelyNotSent("400 invalid")
            if mode == "timeout_before_send":
                raise TimeoutError("provider timeout")
            pid = f"fake-{len(self.outbox) + 1}"
            self.outbox.append({"id": pid, "raw": raw, "envelope": list(envelope), "bcc": list(bcc or [])})
            if mode == "timeout_after_send":
                raise TimeoutError("provider timeout after accept")
            return pid

    def find_sent(self, message_id_header: str, provider_id: str | None = None) -> SentMessage | None:
        with self._lock:
            if self.lag > 0:
                self.lag -= 1
                return None
            for m in self.outbox:
                s = parse_raw(m["raw"], m["id"], m["bcc"])
                if s.message_id_header == message_id_header:
                    return s
            return None


class GmailMail:
    """Gmail API adapter. token.json (gmail.send + gmail.readonly) stays out of git."""

    def __init__(self, token_path) -> None:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        creds = Credentials.from_authorized_user_file(str(token_path))
        self.svc = build("gmail", "v1", credentials=creds, cache_discovery=False)

    def send_raw(self, raw: bytes, envelope: list[str], bcc: list[str] | None = None) -> str | None:
        from googleapiclient.errors import HttpError
        try:
            res = self.svc.users().messages().send(
                userId="me", body={"raw": base64.urlsafe_b64encode(raw).decode()}).execute()
            return res.get("id")
        except HttpError as e:
            if e.resp.status in (400, 401, 403):
                raise DefinitelyNotSent(str(e.resp.status)) from e
            raise

    def find_sent(self, message_id_header: str, provider_id: str | None = None) -> SentMessage | None:
        """Read the Sent record: by Gmail's own id when we have it, else by our sealed Message-ID header
        (Gmail may replace a client-supplied Message-ID, so the provider id is tried first)."""
        from googleapiclient.errors import HttpError
        mid = provider_id
        if not mid:
            q = f"in:sent rfc822msgid:{message_id_header.strip('<>')}"
            msgs = self.svc.users().messages().list(userId="me", q=q).execute().get("messages", [])
            if not msgs:
                return None
            mid = msgs[0]["id"]
        try:
            msg = self.svc.users().messages().get(userId="me", id=mid, format="raw").execute()
        except HttpError as e:
            if e.resp.status == 404:
                return None
            raise
        if "SENT" not in msg.get("labelIds", ["SENT"]):
            return None
        return parse_raw(base64.urlsafe_b64decode(msg["raw"]), mid)
