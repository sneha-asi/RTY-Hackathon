"""Contain mode for a closed assistant (PRD §4, mode 3): Shield publishes safe summaries with stable IDs into a
restricted demo inbox the assistant can read (e.g. Instinct over WhatsApp). The assistant's reply (request ID,
file ID, optional note) comes back through a local intake. It is treated as untrusted: only the IDs are used,
and Shield resolves recipient and attachment itself, then runs the same checks, seal and approval page."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .handles import HandleRegistry
from .service import Shield

SESSION = "mirror:restricted-inbox"
DATA = Path(__file__).resolve().parent.parent / "data"
REQ_RX = re.compile(r"\bREQ_\d+\b")
FILE_RX = re.compile(r"\bFILE_\d+\b")
NOTE_RX = re.compile(r"\bnote\s*[:\-]\s*(.+)", re.I | re.S)


def _published() -> dict:
    return json.loads((DATA / "published.json").read_text())


def registry(shield: Shield) -> HandleRegistry:
    """The restricted inbox's session: bound to the same standing policy, with the published IDs pinned."""
    reg = shield.registry(SESSION)
    if reg.requests:
        return reg
    pub = _published()
    for fid_handle, file_id in pub["files"].items():
        f = shield.seed.file(file_id)
        latest = shield.seed.latest(f.category)
        reg.pin(fid_handle, "FILE", f.id, {"category": f.category, "version": f.version,
                                          "latest": latest is not None and latest.id == f.id,
                                          "requires_nda": f.requires_nda})
    for req_handle, item_id in pub["requests"].items():
        item = next(i for i in shield.seed.items if i.id == item_id)
        r, _ = shield.broker.analyse(item)
        from .broker import _intent
        _, cat = _intent(item.subject + ". " + r.text)
        sender = reg.for_address(item.sender)
        reg.note_request(req_handle, item.id, cat, sender.handle)
        reg.note_thread(req_handle, item.id, sender.handle)
    return reg


def publication(shield: Shield, only: list[str] | None = None) -> dict:
    """PREVIEW of the safe text for the restricted inbox: one line per eligible request, no addresses, no contents.
    Read-only: nothing is recorded as published until a script actually puts it in a mailbox (record_published)."""
    reg = registry(shield)
    pub = _published()
    file_for = {v: k for k, v in pub["files"].items()}
    lines, items = [], []
    for req_handle, info in reg.requests.items():
        if only and req_handle not in only:
            continue
        contact = shield.seed.contact(reg.resolve(info["sender"]).ref)
        latest = shield.seed.latest(info["category"])
        eligible = latest
        if latest and latest.requires_nda and not contact.nda:
            eligible = shield.seed.file(reg.policy.get("nda_fallback", "teaser"))
        fid = file_for.get(eligible.id) if eligible else None
        line = (f"{contact.first_name} requested {info['category']}. Request {req_handle}. "
                f"Eligible document {fid}" + ("" if eligible.id == (latest.id if latest else None)
                                              else f" ({eligible.label}; no NDA on file)") + ".")
        lines.append(line)
        items.append({"request": req_handle, "file": fid, "line": line, "first_name": contact.first_name,
                      "role": contact.role, "nda": contact.nda, "category": info["category"]})
    body = ("Investor follow-ups (published by Shield; reply with the request ID and document ID)\n\n" +
            "\n".join(lines) + "\n")
    return {"subject": "Investor follow-ups to prepare", "body": body, "items": items}


def demo_email(shield: Shield, request: str = "REQ_7") -> dict:
    """The one clearly labelled synthetic email seeded into the executive's Gmail for the live recording.
    Safe summary + IDs only: no attachment, no destination address, nothing else from the mailbox."""
    it = next(i for i in publication(shield, [request])["items"])
    nda = "NDA on file" if it["nda"] else "no NDA on file"
    subject = f"[Shield Demo] {it['first_name']} — investor follow-up"
    body = (f"{it['first_name']} ({it['role']}, {nda}) asked for the latest {it['category']}.\n\n"
            f"Request ID: {it['request']}\nEligible document ID: {it['file']}\n\n"
            "To prepare the follow-up, reply with the request ID, the document ID and a short note.\n"
            "Synthetic demo content published by Shield. The document and the recipient's address stay in Shield.\n")
    return {"subject": subject, "body": body, "request": it["request"], "file": it["file"]}


def record_published(runtime_dir: Path, rec: dict) -> None:
    """Called only after a mailbox accepted the message (evidence: the provider's message id)."""
    from .journal import secure_append, secure_dir
    from .ledger import now_iso
    secure_dir(runtime_dir)
    secure_append(runtime_dir / "publications.jsonl", json.dumps({"ts": now_iso(), **rec}))


def published_records(shield: Shield) -> list[dict]:
    p = shield.settings.runtime_dir / "publications.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def parse(text: str) -> dict:
    """Untrusted paste from the assistant. Only REQ_n, FILE_n and a short note are taken; everything else is ignored."""
    reqs, files = REQ_RX.findall(text or ""), FILE_RX.findall(text or "")
    m = NOTE_RX.search(text or "")
    note = (m.group(1).strip().splitlines()[0] if m else "")[:300]
    ignored = []
    if re.search(r"[\w.+-]+@[\w-]+\.\w+", text or ""):
        ignored.append("an email address (Shield resolves the recipient itself)")
    if re.search(r"https?://|www\.", text or ""):
        ignored.append("a link")
    return {"request": reqs[0] if reqs else None, "file": files[0] if files else None, "note": note,
            "ambiguous": len(set(reqs)) > 1 or len(set(files)) > 1, "ignored": ignored}


def intake(shield: Shield, text: str, source: str = "Instinct (WhatsApp, pasted)") -> dict:
    parsed = parse(text)
    if not parsed["request"] or not parsed["file"]:
        return {"error": "Need one request ID (REQ_n) and one document ID (FILE_n).", "parsed": parsed}
    if parsed["ambiguous"]:
        return {"error": "More than one request or document ID; paste one proposal at a time.", "parsed": parsed}
    reg = registry(shield)
    shield.note_client(SESSION, source)
    # separate fact from "Shield published": what the assistant returned (IDs only; the note's text stays out of the ledger)
    shield.ledger.emit("assistant_reply", session_id=SESSION, source=source, request=parsed["request"],
                       file=parsed["file"], note_chars=len(parsed["note"]), ignored=len(parsed["ignored"]))
    a = shield.guard.propose_send_document(SESSION, reg, parsed["request"], parsed["file"], parsed["note"])
    a.args.update({"source": source, "ignored": parsed["ignored"]})
    view = shield.guard.view_for_model(a)
    return {**view, "parsed": parsed}
