"""Wires the pieces together. One process-wide Shield; per-session handle registries."""
from __future__ import annotations

import os

from .broker import Broker
from .config import Settings
from .guard import Guard
from .handles import HandleRegistry
from .ledger import Ledger
from .mail import FakeMail, GmailMail
from .seed import Seed


class Shield:
    def __init__(self, settings: Settings | None = None, mail=None, scheduler=None):
        self.settings = settings or Settings()
        self._mail_override = mail
        self.scheduler = scheduler
        self.reset()

    def reset(self) -> None:
        s = self.settings
        self.seed = Seed(s.data_dir, s.files_dir, s.runtime_dir)
        if self._mail_override is not None:
            self.mail = self._mail_override
        else:
            self.mail = GmailMail(s.gmail_token) if s.mail_backend == "gmail" else FakeMail()
        self.ledger = Ledger(s.runtime_dir / "ledger.jsonl")
        self.broker = Broker(self.seed, s.today())
        sender = os.getenv("FOUNDER_TEST_GMAIL", "founder@shield.local")
        self.guard = Guard(self.seed, self.ledger, self.mail, s.founder_name, sender, s.verify_backoff, self.scheduler)
        self.sessions: dict[str, HandleRegistry] = {}

    def registry(self, session_id: str) -> HandleRegistry:
        if session_id not in self.sessions:
            self.sessions[session_id] = HandleRegistry(self.seed)
        return self.sessions[session_id]
