"""Append-only event log. IDs and short reasons only, never email bodies or file bytes.
The SSE endpoint tails it by sequence number."""
from __future__ import annotations

import threading
from datetime import datetime
from typing import Any

from .config import TZ


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="milliseconds")


class EventLog:
    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self.epoch = 0  # bumped on reset so SSE clients know to start over

    def emit(self, kind: str, call_id: str | None = None, action_id: str | None = None, **fields: Any) -> dict:
        with self._lock:
            ev = {"seq": len(self._events), "ts": now_iso(), "kind": kind,
                  "call_id": call_id, "action_id": action_id, **fields}
            self._events.append(ev)
            return ev

    def since(self, seq: int) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events[seq:])

    def all(self) -> list[dict[str, Any]]:
        return self.since(0)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
            self.epoch += 1
