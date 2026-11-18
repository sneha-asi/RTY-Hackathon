"""Read path (LLD §4): clean → label → purpose rule → handles + template summaries.
The model only ever receives what this module builds (I1)."""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, timedelta

from . import cleaner, labels
from .handles import HandleRegistry
from .models import Item, ReleasedItem
from .seed import Seed

PURPOSES = {"share_document", "schedule", "reply", "triage"}
CATEGORY_SYNONYMS = {"data room": "data_room", "projections": "projections", "forecast": "projections",
                     "financial model": "projections", "teaser": "teaser", "deck": "teaser"}
TOPICS = {"pricing": ["pricing", "price", "plan"], "integration": ["integration", "pilot", "rollout"],
          "meeting": ["meet", "call", "sync"], "projections": ["projections"], "invoice": ["invoice"]}
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
SENSITIVE_RELEASE_BLOCK = {"secrets", "identity_ids"}


def _intent(text: str) -> tuple[str, str | None]:
    low = text.lower()
    for word, cat in CATEGORY_SYNONYMS.items():
        if re.search(rf"\b(send|share|forward|could you|can you|please|see|access)\b.{{0,60}}\b{word}\b", low):
            return "document_request", cat
    if re.search(r"\b(meet|call|catch up|schedule|slot)\b", low):
        return "meeting_request", None
    if "?" in text:
        return "question", None
    return "fyi", None


def _due(text: str, today: date) -> str | None:
    m = re.search(r"\b(by|before)\s+(" + "|".join(WEEKDAYS) + r")\b", text.lower())
    if m:
        target = WEEKDAYS.index(m.group(2))
        d = today + timedelta(days=(target - today.weekday()) % 7 or 7)
        return d.isoformat()
    if re.search(r"\btoday\b", text.lower()):
        return today.isoformat()
    return None


def _topic(text: str) -> str:
    low = text.lower()
    for t, words in TOPICS.items():
        if any(w in low for w in words):
            return t
    return "general"


class Broker:
    def __init__(self, seed: Seed, today: date):
        self.seed = seed
        self.today = today
        self._cache: dict[str, tuple[cleaner.CleanResult, set[str]]] = {}

    def analyse(self, item: Item) -> tuple[cleaner.CleanResult, set[str]]:
        if item.id not in self._cache:
            c = self.seed.contact_by_addr(item.sender)
            r = cleaner.clean(item.body_html, sender_trusted=bool(c and c.trusted))
            labs = labels.labels_for(item.subject + " " + r.text)
            for fid in item.attachments:
                f = self.seed.file(fid)
                if f:
                    labs |= set(f.sensitivity)
            self._cache[item.id] = (r, labs)
        return self._cache[item.id]

    def _released(self, reg: HandleRegistry, item: Item, r: cleaner.CleanResult) -> ReleasedItem | None:
        sender = reg.for_address(item.sender)
        h = reg.for_thread(item.thread_id) if item.kind == "email" else reg.for_event(item.id)
        if r.quarantined:
            return ReleasedItem(handle=h.handle, kind=item.kind, sender=sender.handle, intent="unknown",
                                status="quarantined", reason=f"hidden or instruction-like content ({', '.join(r.hits)})")
        text = item.subject + ". " + r.text
        intent, cat = _intent(text)
        due = _due(text, self.today)
        if sender.kind == "CONTACT":
            who = f"{sender.attrs['name']} ({sender.attrs['role']}{', NDA on file' if sender.attrs['nda'] else ', no NDA'})"
        else:
            who = f"{sender.handle} (unknown sender)"
        if intent == "document_request":
            summary = f"{who} asked for {cat.replace('_', ' ')}" + (f", due {due}" if due else "") + "."
        elif intent == "meeting_request":
            summary = f"{who} wants to meet."
        elif intent == "question":
            summary = f"{who} asked a question about {_topic(text)}."
        else:
            summary = f"{who} sent an update about {_topic(text)}."
        if labels.detect(summary):  # fail closed: a template slot carried a sensitive value (I1, I9)
            return None
        if item.kind == "email":
            reg.note_thread(h.handle, item.id, sender.handle)
            if intent == "document_request":
                reg.note_request(h.handle, item.id, cat, sender.handle)
        return ReleasedItem(handle=h.handle, kind=item.kind, sender=sender.handle, intent=intent,
                            requested_category=cat, due=due, summary=summary)

    @staticmethod
    def _check_purpose(reg: HandleRegistry, purpose: str) -> None:
        if purpose not in PURPOSES:
            raise ValueError(f"unknown purpose: {purpose}")
        allowed = reg.policy.get("purposes", [])
        if purpose not in allowed:
            raise PermissionError(f"purpose '{purpose}' is outside the enabled policy '{reg.policy_name}' (allowed: {', '.join(allowed)})")

    def read(self, reg: HandleRegistry, purpose: str, thread: str) -> dict:
        """One thread, as a summary. Only threads already released in this session under the policy."""
        self._check_purpose(reg, purpose)
        t = reg.threads.get(thread)
        if t is None:
            raise PermissionError("not a thread released in this session")
        item = next(i for i in self.seed.items if i.id == t["item_id"])
        r, _ = self.analyse(item)
        ri = self._released(reg, item, r)
        if ri is None:
            raise PermissionError("withheld")
        return {"purpose": purpose, "items": [ri.model_dump()], "withheld": {}, "_released_ids": [item.id],
                "_quarantined_ids": [], "_withheld_ids": []}

    def release(self, reg: HandleRegistry, purpose: str, query: str = "") -> dict:
        self._check_purpose(reg, purpose)
        if purpose == "reply":
            raise ValueError("purpose 'reply' works on one thread: call read(purpose='reply', thread=THREAD_n)")
        items: list[ReleasedItem] = []
        withheld: Counter = Counter()
        released_ids, quarantined_ids, withheld_ids = [], [], []
        q = query.lower().strip()
        for item in self.seed.items:
            r, labs = self.analyse(item)
            if r.quarantined:
                if purpose in ("triage", "share_document"):
                    items.append(self._released(reg, item, r))
                    quarantined_ids.append(item.id)
                continue
            text = item.subject + ". " + r.text
            intent, cat = _intent(text)
            sender_c = self.seed.contact_by_addr(item.sender)
            keep = False
            if purpose == "share_document":
                keep = item.kind == "email" and intent == "document_request" and cat is not None
                roles = reg.policy.get("recipient_roles", [])
                if keep:  # policy scope: requests from the policy's recipient roles, plus unknown senders (so Shield can show the block)
                    keep = sender_c is None or sender_c.role in roles
                if keep and q and not q.startswith("investor"):
                    keep = q in text.lower()
            elif purpose == "schedule":
                keep = item.kind == "event" or (intent == "meeting_request" and not labs)
            elif purpose == "triage":
                keep = not labs
            ri = self._released(reg, item, r) if keep else None
            if keep and ri is None:
                keep = False
                withheld["summary_withheld"] += 1
            if keep:
                if purpose == "schedule" and item.kind == "event":
                    ri.summary = f"Busy {item.start[11:16]}–{item.end[11:16]} on {item.start[:10]}."
                    ri.intent = "busy"
                items.append(ri)
                released_ids.append(item.id)
            else:
                withheld_ids.append(item.id)
                if labs:
                    for lab in sorted(labs):
                        withheld[lab] += 1
                else:
                    withheld["out_of_purpose"] += 1
        return {"purpose": purpose, "items": [i.model_dump() for i in items], "withheld": dict(withheld),
                "_released_ids": released_ids, "_quarantined_ids": quarantined_ids, "_withheld_ids": withheld_ids}

    def list_files(self, reg: HandleRegistry, category: str = "") -> dict:
        """Only shareable files in the policy's categories (the same policy that governs proposals)."""
        files, withheld = [], Counter()
        allowed = set(reg.policy.get("categories", []))
        for f in self.seed.files:
            if category and f.category != category:
                continue
            if not f.shareable or f.category not in allowed:
                for lab in f.sensitivity:
                    withheld[lab] += 1
                continue
            h = reg.for_file(f.id)
            files.append({"handle": h.handle, **h.attrs})
        return {"files": files, "withheld": dict(withheld)}

    def free_slots(self, reg: HandleRegistry, start: str, end: str) -> dict:
        self._check_purpose(reg, "schedule")
        busy = sorted((i.start, i.end) for i in self.seed.items if i.kind == "event" and i.start and start <= i.start[:10] <= end)
        return {"busy": [{"start": s, "end": e} for s, e in busy],
                "note": "Free/busy only. Titles and descriptions are withheld."}
