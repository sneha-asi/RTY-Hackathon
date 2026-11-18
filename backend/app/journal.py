"""Send-attempt journal (LLD §5.4). Written and fsynced BEFORE the provider call so no-resend survives restarts.
Holds action ids, Message-IDs, seals and states only — no bodies or attachments (I8)."""
from __future__ import annotations

import json
import os
from pathlib import Path


class SendJournal:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, rec: dict) -> None:
        with self.path.open("a") as f:
            f.write(json.dumps(rec) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def attempt(self, action_json: dict) -> None:
        self._append({"event": "send_attempt", "action": action_json})

    def outcome(self, action_id: str, state: str) -> None:
        self._append({"event": "outcome", "action_id": action_id, "state": state})

    def open_attempts(self) -> list[dict]:
        """Actions whose send was attempted but never reached a terminal outcome."""
        if not self.path.exists():
            return []
        attempts, done = {}, set()
        for line in self.path.read_text().splitlines():
            rec = json.loads(line)
            if rec["event"] == "send_attempt":
                attempts[rec["action"]["id"]] = rec["action"]
            elif rec["event"] == "outcome":
                done.add(rec["action_id"])
        return [a for aid, a in attempts.items() if aid not in done]

    def attempted(self, action_id: str) -> bool:
        if not self.path.exists():
            return False
        return any(json.loads(l).get("action", {}).get("id") == action_id
                   for l in self.path.read_text().splitlines() if '"send_attempt"' in l)
