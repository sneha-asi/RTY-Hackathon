"""Send-attempt journal (LLD §5.4). Written and fsynced BEFORE the provider call so no-resend survives restarts.
Separate from the content-free ledger. Holds only what recovery and verification need: action id, session, seal,
Message-ID, recipient, subject, file name and hashes (the body is stored as a hash, never in clear; no attachment
bytes). File mode 0600 in a 0700 runtime directory."""
from __future__ import annotations

import json
import os
from pathlib import Path

KEEP_PAYLOAD = ("type", "recipient_contact_ids", "to", "cc", "bcc", "sender", "subject", "file_id", "file_name",
                "attachment_sha256", "message_id", "date", "boundary", "message_sha256", "body_sha256")


def secure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass


def secure_append(path: Path, line: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, (line + "\n").encode())
        os.fsync(fd)
    finally:
        os.close(fd)


class SendJournal:
    def __init__(self, path: Path):
        self.path = path
        secure_dir(path.parent)

    def attempt(self, action) -> None:
        p = action.payload
        rec = {"id": action.id, "session_id": action.session_id, "type": action.type, "policy": action.policy,
               "request_handle": action.request_handle, "payload_hash": action.payload_hash,
               "display": action.display, "created_at": action.created_at,
               "payload": {**{k: getattr(p, k) for k in KEEP_PAYLOAD}, "body": ""}}
        secure_append(self.path, json.dumps({"event": "send_attempt", "action": rec}))

    def outcome(self, action_id: str, state: str) -> None:
        secure_append(self.path, json.dumps({"event": "outcome", "action_id": action_id, "state": state}))

    def _records(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text().splitlines() if l.strip()]

    def open_attempts(self) -> list[dict]:
        """Actions whose send was attempted but never reached a terminal outcome."""
        attempts, done = {}, set()
        for rec in self._records():
            if rec["event"] == "send_attempt":
                attempts[rec["action"]["id"]] = rec["action"]
            elif rec["event"] == "outcome":
                done.add(rec["action_id"])
        return [a for aid, a in attempts.items() if aid not in done]

    def attempted(self, action_id: str) -> bool:
        return any(r["event"] == "send_attempt" and r["action"]["id"] == action_id for r in self._records())
