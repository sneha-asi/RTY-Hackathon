"""Receipt queries from ledger counts only (LLD §8). States what Shield did, not what any assistant did elsewhere."""
from __future__ import annotations

import re

from .service import Shield

TOPICS = {
    "cap table": {"phrases": ["cap table"], "files": ["cap_table"]},
    "layoff plan": {"phrases": ["layoff"], "files": ["layoff_plan"]},
    "term sheet": {"phrases": ["term sheet"], "files": []},
    "medical note": {"phrases": ["medical", "diagnosis", "doctor"], "files": []},
    "api keys": {"phrases": ["api key", "sk-"], "files": ["eng_onboarding"]},
    "projections": {"phrases": ["projections"], "files": ["proj_v2", "proj_v3"]},
}


def _items_for(shield: Shield, phrases: list[str]) -> set[str]:
    out = set()
    for it in shield.seed.items:
        r, _ = shield.broker.analyse(it)
        text = f"{it.subject} {r.text} {r.hidden_text}".lower()
        if any(p in text for p in phrases):
            out.add(it.id)
    return out


def answer(shield: Shield, question: str) -> dict:
    q = question.lower()
    if re.search(r"\b(sent|send)\b", q) and not re.search(r"\bsee|seen\b", q):
        verified = [a for a in shield.guard.actions.values() if a.state.value == "VERIFIED"]
        other = [a for a in shield.guard.actions.values() if a.state.value in ("VERIFICATION_PENDING", "UNVERIFIED")]
        lines = [f"{a.display.get('file')} to {a.display.get('recipient')} (verified)" for a in verified]
        text = f"Shield sent and verified {len(verified)} message(s) today" + (": " + "; ".join(lines) if lines else ".")
        if other:
            text += f" {len(other)} more may have been sent but are not confirmed."
        return {"intent": "what_sent", "answer": text}
    if "block" in q or "stop" in q:
        blocked = [a for a in shield.guard.actions.values() if a.state.value == "BLOCKED"]
        quarantined = {e["item_id"] for e in shield.ledger.all() if e["kind"] == "quarantine"}
        return {"intent": "what_blocked", "answer":
                f"Shield blocked {len(blocked)} proposed action(s) and quarantined {len(quarantined)} item(s) today."}
    topic = next((t for t in TOPICS if t in q or t.rstrip("s") in q), None)
    if topic is None:
        return {"intent": "unknown", "answer": "Try: 'Did any AI see my cap table today?', 'What was sent today?', 'What was blocked?'"}
    spec = TOPICS[topic]
    ids = _items_for(shield, spec["phrases"])
    released = withheld = 0
    evidence = []
    for e in shield.ledger.all():
        if e["kind"] != "release":
            continue
        rel = set(e.get("released_ids", [])) & ids
        held = (set(e.get("withheld_ids", [])) | set(e.get("quarantined_ids", []))) & ids
        held |= set(e.get("withheld_files", [])) & set(spec["files"])
        if rel:
            released += 1
            evidence.append(e["seq"])
        elif held:
            withheld += 1
            evidence.append(e["seq"])
    times = lambda n: "once" if n == 1 else ("twice" if n == 2 else f"{n} times")
    return {"intent": "did_ai_see", "topic": topic,
            "answer": f"Shield released the {topic} {times(released)} and withheld it {times(withheld)} today.",
            "released": released, "withheld": withheld, "evidence_events": evidence}
