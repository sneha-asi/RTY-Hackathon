"""The Shielded tool surface (LLD §9). Shared by the MCP server and tests.
There is deliberately no send tool and no approve tool (I3)."""
from __future__ import annotations

from . import labels
from .service import Shield


def _public(d: dict) -> dict:
    return {k: v for k, v in d.items() if not k.startswith("_")}


def _record(shield: Shield, session_id: str, tool: str, result: dict) -> dict:
    import json
    spans = labels.detect(json.dumps(result))
    shield.ledger.emit("exposure", session_id=session_id, tool=tool,
                       sensitive_values=len({s.value_hash for s in spans}))
    return result


def search(shield: Shield, session_id: str, purpose: str, query: str = "") -> dict:
    reg = shield.registry(session_id)
    out = shield.broker.release(reg, purpose, query)
    shield.ledger.emit("release", session_id=session_id, purpose=purpose, released_ids=out["_released_ids"],
                       quarantined_ids=out["_quarantined_ids"], withheld_ids=out["_withheld_ids"],
                       withheld=out["withheld"])
    for qid in out["_quarantined_ids"]:
        shield.ledger.emit("quarantine", session_id=session_id, item_id=qid)
    return _record(shield, session_id, "search", _public(out))


def list_files(shield: Shield, session_id: str, category: str = "") -> dict:
    out = shield.broker.list_files(shield.registry(session_id), category)
    shield.ledger.emit("release", session_id=session_id, purpose="list_files",
                       released_ids=[f["handle"] for f in out["files"]], quarantined_ids=[], withheld_ids=[],
                       withheld=out["withheld"],
                       withheld_files=[f.id for f in shield.seed.files if not f.shareable and (not category or f.category == category)])
    return _record(shield, session_id, "list_files", out)


def free_slots(shield: Shield, session_id: str, start: str, end: str) -> dict:
    return _record(shield, session_id, "free_slots", shield.broker.free_slots(start, end))


def propose_send_document(shield: Shield, session_id: str, recipient: str, file: str, note: str = "") -> dict:
    a = shield.guard.propose_send_document(session_id, shield.registry(session_id), recipient, file, note)
    return _record(shield, session_id, "propose_send_document", shield.guard.view_for_model(a))


def action_status(shield: Shield, session_id: str, action_id: str) -> dict:
    a = shield.guard.actions.get(action_id)
    if a is None or a.session_id != session_id:
        return {"action_id": action_id, "state": "UNKNOWN", "status_text": "No such action in this session."}
    return {"action_id": a.id, "state": a.state.value, "status_text": shield.guard.status_text(a)}
