"""Load founder/contacts/files JSON. `<<KEY>>` placeholders are filled from env vars,
so the seed files can be committed without real addresses."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from .models import Contact, FileRecord, Founder

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


class Seed:
    def __init__(self, data_dir: Path, files_dir: Path):
        self.missing_placeholders: set[str] = set()
        self.files_dir = files_dir

        def load(name: str):
            return json.loads(fill_placeholders((data_dir / name).read_text(), self.missing_placeholders))

        self.founder = Founder(**load("founder.json"))
        self.contacts = [Contact(**c) for c in load("contacts.json")]
        self.files: list[FileRecord] = []
        for f in load("files.json"):
            rec = FileRecord(**f)
            p = files_dir / rec.path
            rec.sha256 = sha256_bytes(p.read_bytes())  # computed at startup, never trusted from JSON
            rec.filename = p.name
            self.files.append(rec)

    def contact(self, cid: str | None) -> Contact | None:
        return next((c for c in self.contacts if c.id == cid), None)

    def file(self, fid: str | None) -> FileRecord | None:
        return next((f for f in self.files if f.id == fid), None)

    def file_bytes(self, rec: FileRecord) -> bytes:
        return (self.files_dir / rec.path).read_bytes()
