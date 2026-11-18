"""Per-session handle registry (LLD §4.3). The ref never leaves the server."""
from __future__ import annotations

import re
import threading

from .models import Handle
from .seed import Seed, norm_addr

HANDLE_RX = re.compile(r"^(CONTACT|SENDER|FILE|THREAD|EVENT)_\d+$")


class HandleRegistry:
    def __init__(self, seed: Seed, policy_name: str = "", policy: dict | None = None):
        self.seed = seed
        self.policy_name = policy_name
        self.policy = policy or {}
        self.requests: dict[str, dict] = {}  # THREAD handle -> {item_id, category, sender}, released in THIS session
        self._by_key: dict[tuple[str, str], Handle] = {}
        self._by_handle: dict[str, Handle] = {}
        self._counters: dict[str, int] = {}
        self._lock = threading.Lock()

    def _get(self, kind: str, ref: str, attrs: dict) -> Handle:
        with self._lock:
            key = (kind, ref)
            if key not in self._by_key:
                n = self._counters.get(kind, 0) + 1
                self._counters[kind] = n
                h = Handle(handle=f"{kind}_{n}", kind=kind, ref=ref, attrs=attrs)
                self._by_key[key] = h
                self._by_handle[h.handle] = h
            return self._by_key[key]

    def for_contact(self, contact_id: str) -> Handle:
        c = self.seed.contact(contact_id)
        return self._get("CONTACT", c.id, {"name": c.name, "org": c.org, "role": c.role, "nda": c.nda})

    def for_address(self, raw: str) -> Handle:
        c = self.seed.contact_by_addr(raw)
        if c:
            return self.for_contact(c.id)
        return self._get("SENDER", norm_addr(raw), {"role": "unknown sender"})

    def for_file(self, file_id: str) -> Handle:
        f = self.seed.file(file_id)
        latest = self.seed.latest(f.category)
        return self._get("FILE", f.id, {"category": f.category, "version": f.version,
                                        "latest": latest is not None and latest.id == f.id,
                                        "requires_nda": f.requires_nda})

    def for_thread(self, thread_id: str) -> Handle:
        return self._get("THREAD", thread_id, {})

    def for_event(self, event_id: str) -> Handle:
        return self._get("EVENT", event_id, {})

    def note_request(self, thread_handle: str, item_id: str, category: str | None, sender_handle: str) -> None:
        self.requests[thread_handle] = {"item_id": item_id, "category": category, "sender": sender_handle}

    def resolve(self, handle: str) -> Handle | None:
        if not isinstance(handle, str) or not HANDLE_RX.match(handle):
            return None
        return self._by_handle.get(handle)
