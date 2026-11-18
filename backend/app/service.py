"""Wires the pieces together. One process-wide Shield; per-session handle registries."""
from __future__ import annotations

import os

from .broker import Broker
from .config import Settings
from .guard import Guard
import json

from .handles import HandleRegistry
from .journal import SendJournal
from .ledger import Ledger
from .mail import FakeMail, GmailMail
from .seed import Seed


class Shield:
    def __init__(self, settings: Settings | None = None, mail=None, scheduler=None):
        self.settings = settings or Settings()
        self._mail_override = mail
        self.scheduler = scheduler
        self.reset()

    def reset(self, wipe_journal: bool = False) -> None:
        s = self.settings
        if wipe_journal:
            (s.runtime_dir / "send_journal.jsonl").unlink(missing_ok=True)
            (s.runtime_dir / "ledger.jsonl").unlink(missing_ok=True)
        self.seed = Seed(s.data_dir, s.files_dir, s.runtime_dir)
        if self._mail_override is not None:
            self.mail = self._mail_override
        else:
            self.mail = GmailMail(s.gmail_token) if s.mail_backend == "gmail" else FakeMail()
        self.ledger = Ledger(s.runtime_dir / "ledger.jsonl")
        self.broker = Broker(self.seed, s.today())
        sender = os.getenv("FOUNDER_TEST_GMAIL", "founder@shield.local")
        self.journal = SendJournal(s.runtime_dir / "send_journal.jsonl")
        self.guard = Guard(self.seed, self.ledger, self.mail, s.founder_name, sender, s.verify_backoff, self.scheduler,
                           journal=self.journal,
                           sent_label="Gmail Sent" if s.mail_backend == "gmail" else "Sent (sandbox)")
        self.policies: dict = json.loads((s.data_dir / "policy.json").read_text())
        self.sessions: dict[str, HandleRegistry] = {}
        self.guard.recover()
        self.model_view: list[dict] = []  # exactly what the model received, for the dashboard

    def registry(self, session_id: str) -> HandleRegistry:
        if session_id not in self.sessions:
            # bind the session to the founder's enabled standing policy (M0: investor_followups)
            name, pol = next(((k, v) for k, v in self.policies.items() if v.get("enabled")), ("", {}))
            self.sessions[session_id] = HandleRegistry(self.seed, name, pol)
        return self.sessions[session_id]
