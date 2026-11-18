"""Load seed JSON. `<<KEY>>` placeholders are filled from env vars so seed files hold no real addresses.
File sha256s are computed from bytes at startup, never trusted from JSON."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path

from .models import Contact, FileRecord, Item

_PLACEHOLDER = re.compile(r"<<([A-Z0-9_]+)>>")


def fill_placeholders(text: str, missing: set[str]) -> str:
    def sub(m: re.Match) -> str:
        val = os.getenv(m.group(1))
        if not val:
            missing.add(m.group(1))
            return m.group(0)
        return val

    return _PLACEHOLDER.sub(sub, text)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def norm_addr(a: str) -> str:
    a = a.strip().lower()
    if "<" in a and ">" in a:
        a = a[a.index("<") + 1:a.index(">")]
    local, _, domain = a.partition("@")
    if domain == "gmail.com":
        local = local.split("+", 1)[0]
    return f"{local}@{domain}"


class Seed:
    def __init__(self, data_dir: Path, files_dir: Path, runtime_dir: Path):
        self.missing_placeholders: set[str] = set()
        self.runtime_files = runtime_dir / "files"
        self.runtime_files.mkdir(parents=True, exist_ok=True)

        def load(name: str):
            return json.loads(fill_placeholders((data_dir / name).read_text(), self.missing_placeholders))

        self.contacts = [Contact(**c) for c in load("contacts.json")]
        self.files: list[FileRecord] = []
        for f in load("files.json"):
            rec = FileRecord(**f)
            src = files_dir / rec.path
            rec.filename = src.name
            shutil.copyfile(src, self.runtime_files / rec.filename)  # tamper target; committed files untouched
            rec.sha256 = sha256_bytes(src.read_bytes())
            self.files.append(rec)
        self.items: list[Item] = []
        for e in load("emails.json"):
            self.items.append(Item(id=e["id"], kind="email", thread_id=e["thread_id"], sender=e["from"], to=e["to"],
                                   subject=e["subject"], body_html=e["body_html"], ts=e["ts"],
                                   attachments=e.get("attachments", [])))
        for ev in load("events.json"):
            self.items.append(Item(id=ev["id"], kind="event", sender=ev["organizer"], to=ev["attendees"],
                                   subject=ev["title"], body_html=ev["description_html"], ts=ev["start"],
                                   start=ev["start"], end=ev["end"]))

    def contact(self, cid: str | None) -> Contact | None:
        return next((c for c in self.contacts if c.id == cid), None)

    def contact_by_addr(self, addr: str) -> Contact | None:
        n = norm_addr(addr)
        return next((c for c in self.contacts if norm_addr(c.email) == n), None)

    def file(self, fid: str | None) -> FileRecord | None:
        return next((f for f in self.files if f.id == fid), None)

    def latest(self, category: str) -> FileRecord | None:
        cands = [f for f in self.files if f.category == category]
        return max(cands, key=lambda f: f.version) if cands else None

    def read_file_once(self, rec: FileRecord) -> bytes:
        """The runtime copy is what LOCK and the executor read."""
        return (self.runtime_files / rec.filename).read_bytes()
