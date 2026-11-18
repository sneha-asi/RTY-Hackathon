"""Direct baseline (comparison only, sandbox only, never exposed over MCP): the raw tools an assistant gets
when it connects to the mailbox directly (PRD §10.3). Same sandbox and seed as Shield."""
from __future__ import annotations

import email.policy
import uuid
from email.message import EmailMessage

from bs4 import BeautifulSoup

from .pdftext import pdf_text
from .service import Shield


def _raw_text(html: str) -> str:
    # what a raw connector hands the model: all text, including hidden spans
    return BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)


class DirectTools:
    def __init__(self, shield: Shield):
        self.shield = shield

    def list_emails(self) -> dict:
        return {"emails": [{"id": i.id, "from": i.sender, "subject": i.subject, "snippet": _raw_text(i.body_html)[:160]}
                           for i in self.shield.seed.items if i.kind == "email"]}

    def read_email(self, id: str) -> dict:
        i = next((x for x in self.shield.seed.items if x.id == id), None)
        if i is None:
            return {"error": "no such email"}
        return {"id": i.id, "from": i.sender, "to": i.to, "subject": i.subject, "body": _raw_text(i.body_html),
                "attachments": i.attachments}

    def list_events(self) -> dict:
        return {"events": [{"id": i.id, "title": i.subject, "start": i.start, "end": i.end, "organizer": i.sender,
                            "description": _raw_text(i.body_html)} for i in self.shield.seed.items if i.kind == "event"]}

    def list_files(self) -> dict:
        return {"files": [{"id": f.id, "name": f.filename, "category": f.category, "version": f.version}
                          for f in self.shield.seed.files]}

    def read_file(self, id: str) -> dict:
        f = self.shield.seed.file(id)
        if f is None:
            return {"error": "no such file"}
        data = self.shield.seed.read_file_once(f)
        text = pdf_text(data) if f.filename.endswith(".pdf") else data.decode("utf-8", "replace")
        return {"id": f.id, "name": f.filename, "content": text}

    def send_email(self, to: str, subject: str, body: str, attachment_file_id: str = "", cc: list[str] | None = None) -> dict:
        m = EmailMessage(policy=email.policy.SMTP)
        m["From"] = self.shield.guard.sender_addr
        m["To"] = to
        if cc:
            m["Cc"] = ", ".join(cc)
        m["Subject"] = subject
        m["Message-ID"] = f"<direct-{uuid.uuid4().hex[:8]}@baseline.local>"
        m.set_content(body)
        if attachment_file_id:
            f = self.shield.seed.file(attachment_file_id)
            if f:
                m.add_attachment(self.shield.seed.read_file_once(f), maintype="application", subtype="octet-stream",
                                 filename=f.filename)
        pid = self.shield.mail.send_raw(m.as_bytes(), envelope=[to] + list(cc or []))
        return {"sent": True, "id": pid}

    def call(self, name: str, args: dict) -> dict:
        return getattr(self, name)(**args)


DIRECT_SCHEMAS = [
    {"name": "list_emails", "description": "List emails in the user's inbox.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "read_email", "description": "Read one email by id.", "input_schema": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}},
    {"name": "list_events", "description": "List calendar events.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "list_files", "description": "List files in the user's drive.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "read_file", "description": "Read a file's contents by id.", "input_schema": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}},
    {"name": "send_email", "description": "Send an email, optionally with a drive file attached.",
     "input_schema": {"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"},
                      "attachment_file_id": {"type": "string"}, "cc": {"type": "array", "items": {"type": "string"}}},
                      "required": ["to", "subject", "body"]}},
]
