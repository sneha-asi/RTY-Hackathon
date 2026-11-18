"""Append-only ledger (LLD §8). IDs, labels, hashes and reasons only — never bodies or addresses (I8)."""
from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import TZ


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="milliseconds")


class Ledger:
    def __init__(self, path: Path | None = None) -> None:
        self._events: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self.epoch = 0
        self.path = path

    def emit(self, kind: str, **fields: Any) -> dict:
        with self._lock:
            ev = {"seq": len(self._events), "ts": now_iso(), "kind": kind, **fields}
            self._events.append(ev)
            if self.path:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a") as f:
                    f.write(json.dumps(ev) + "\n")
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
