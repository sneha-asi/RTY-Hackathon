"""Two listeners (LLD §10, HLD §4):
- owner app (this module, bind 127.0.0.1): login, approval, dashboard data, SSE, dev endpoints. Never tunnelled.
- MCP app (`mcp_app`): only the filtered MCP surface. The only thing exposed to a remote client."""
from __future__ import annotations

import asyncio
import hmac
import json
import secrets
from pathlib import Path

from fastapi import Cookie, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse

from .config import load_dotenv

load_dotenv()

from . import receipts  # noqa: E402
from .guard import Conflict, Unauthorized  # noqa: E402
from .mcp_server import build_mcp  # noqa: E402
from .service import Shield  # noqa: E402

shield = Shield()
mcp = build_mcp(shield)
SESSIONS: set[str] = set()
STATIC = Path(__file__).resolve().parent / "static"


mcp_app = mcp.streamable_http_app()  # MCP-only ASGI app; run on its own port (see run.py)
app = FastAPI(title="Shield owner console")


def _user(token: str | None) -> str | None:
    return "owner" if token and token in SESSIONS else None


def _action_full(a) -> dict:
    """Dashboard-only view: includes the real resolved payload (behind login)."""
    d = {"id": a.id, "session_id": a.session_id, "state": a.state.value, "reason": a.reason,
         "status_text": shield.guard.status_text(a), "warnings": a.warnings,
         "checks": [c.model_dump() for c in a.checks], "args": a.args, "created_at": a.created_at,
         "verification": a.verification, "seal": a.payload_hash}
    if a.payload:
        p = a.payload
        d["payload"] = {"to": p.to, "cc": p.cc, "bcc": p.bcc, "subject": p.subject, "body": p.body,
                        "file_name": p.file_name, "attachment_sha256": p.attachment_sha256,
                        "message_id": p.message_id}
    return d


@app.post("/api/login")
async def login(req: Request, resp: Response):
    body = await req.json()
    if not hmac.compare_digest(str(body.get("secret", "")), shield.settings.user_secret):
        raise HTTPException(401, "wrong secret")
    tok = secrets.token_urlsafe(24)
    SESSIONS.add(tok)
    resp.set_cookie("shield_owner", tok, httponly=True, samesite="strict")
    return {"ok": True}


@app.get("/api/state")
def state(shield_owner: str | None = Cookie(default=None)):
    authed = _user(shield_owner) is not None
    if not authed:
        return {"authed": False}
    actions = sorted(shield.guard.actions.values(), key=lambda a: a.created_at, reverse=True)
    exposure = sum(v["sensitive_values"] for v in shield.model_view)
    return {
        "authed": authed,
        "counters": {
            "tool_calls": len(shield.model_view),
            "released": sum(1 for v in shield.model_view for i in v["result"].get("items", []) if i.get("status") == "released")
                        + sum(len(v["result"].get("files", [])) for v in shield.model_view),
            "sensitive_values_exposed": exposure,
            "quarantined": len({e["item_id"] for e in shield.ledger.all() if e["kind"] == "quarantine"}),
            "blocked": sum(a.state.value == "BLOCKED" for a in actions),
            "verified": sum(a.state.value == "VERIFIED" for a in actions),
        },
        "actions": [_action_full(a) if authed else {"id": a.id, "state": a.state.value,
                                                    "status_text": shield.guard.status_text(a)} for a in actions],
        "model_view": shield.model_view[-20:] if authed else [],
        "mail_backend": shield.settings.mail_backend,
        # I10: the sandbox mailbox is reachable only through Shield; for a real provider exclusivity can't be
        # checked from here (a missing visible grant doesn't prove it), so it is reported as unknown.
        "sole_path": "yes (sandbox mailbox)" if shield.settings.mail_backend == "fake" else "unknown",
        "policy": next((k for k, v in shield.policies.items() if v.get("enabled")), None),
        "assistants": _assistants(),
        "harness": HARNESS,
        "sent_folder": _sent_folder(),
    }


ROADMAP_ASSISTANTS = [
    {"name": "Instinct", "mode": "mirror account + watch & revoke", "status": "roadmap, not tested"},
    {"name": "Muse", "mode": "edge proxy + mirror + watch & revoke", "status": "roadmap, not tested"},
    {"name": "OpenClaw", "mode": "MCP if its tools can point at Shield, else edge proxy", "status": "roadmap, not tested"},
]


def _assistants() -> list[dict]:
    """Connected MCP assistants (enforced, same policy) plus the roadmap targets (I10: claims follow the path)."""
    sole = "yes (sandbox mailbox)" if shield.settings.mail_backend == "fake" else "unknown"
    live = [{"name": c["name"], "version": c.get("version", ""), "mode": "MCP connector", "status": "enforced",
             "sole_path": sole, "calls": c["calls"], "last_seen": c.get("last_seen", "")}
            for c in shield.clients.values()]
    return live + ROADMAP_ASSISTANTS


def _sent_folder() -> list[dict]:
    """The mailbox's own Sent record, as the verifier reads it (sandbox mailbox only)."""
    from .mail import parse_raw
    out = []
    for m in getattr(shield.mail, "outbox", []):
        s = parse_raw(m["raw"], m["id"], m["bcc"])
        out.append({"to": s.to, "subject": s.subject, "message_id": s.message_id_header,
                    "attachments": [{"name": n, "sha256": h[:16]} for n, h in s.attachments]})
    return out


HARNESS: dict = {"status": "not run"}


@app.post("/api/harness/run")
async def harness_run(req: Request, shield_owner: str | None = Cookie(default=None)):
    if not _user(shield_owner):
        raise HTTPException(401, "login required")
    from . import harness
    body = await req.json()
    runner = body.get("runner", "scripted")
    HARNESS.clear()
    HARNESS["status"] = "running"
    try:
        HARNESS.update(await asyncio.to_thread(harness.run_comparison, runner))
        HARNESS["status"] = "done"
    except Exception as e:  # e.g. no API key for the model runner
        HARNESS.update({"status": "error", "error": f"{type(e).__name__}: {e}"})
    return HARNESS


@app.get("/api/actions/{aid}")
def action_detail(aid: str, shield_owner: str | None = Cookie(default=None)):
    """Owner-only: the real resolved payload plus this action's ledger events (the receipt)."""
    if not _user(shield_owner):
        raise HTTPException(401, "login required")
    a = shield.guard.actions.get(aid)
    if a is None:
        raise HTTPException(404)
    d = _action_full(a)
    d["client"] = shield.clients.get(a.session_id, {}).get("name", a.session_id)
    d["receipt"] = [e for e in shield.ledger.all() if e.get("action_id") == aid]
    d["sent_label"] = shield.guard.sent_label
    return d


@app.post("/api/actions/{aid}/approve")
async def approve(aid: str, req: Request, shield_owner: str | None = Cookie(default=None)):
    body = await req.json()
    if aid not in shield.guard.actions:
        raise HTTPException(404)
    try:
        a = await asyncio.to_thread(shield.guard.approve, aid, _user(shield_owner), str(body.get("seal", "")))
    except Unauthorized:
        raise HTTPException(401, "login required")
    except Conflict:
        raise HTTPException(409, "seal does not match the action")
    return _action_full(a)


@app.post("/api/actions/{aid}/reject")
def reject(aid: str, shield_owner: str | None = Cookie(default=None)):
    if aid not in shield.guard.actions:
        raise HTTPException(404)
    try:
        return _action_full(shield.guard.reject(aid, _user(shield_owner)))
    except Unauthorized:
        raise HTTPException(401, "login required")


@app.get("/api/receipts")
def receipt(q: str, shield_owner: str | None = Cookie(default=None)):
    if not _user(shield_owner):
        raise HTTPException(401, "login required")
    return receipts.answer(shield, q)


@app.get("/api/events")
async def events(since: int = 0, shield_owner: str | None = Cookie(default=None)):
    if not _user(shield_owner):
        raise HTTPException(401, "login required")
    async def gen():
        seq, epoch = since, shield.ledger.epoch
        while True:
            if shield.ledger.epoch != epoch:
                yield "event: reset\ndata: {}\n\n"
                seq, epoch = 0, shield.ledger.epoch
            for ev in shield.ledger.since(seq):
                seq = ev["seq"] + 1
                yield f"id: {ev['seq']}\nevent: ledger\ndata: {json.dumps(ev)}\n\n"
            await asyncio.sleep(0.4)
    return StreamingResponse(gen(), media_type="text/event-stream")


def _dev(req: Request, token: str | None):
    """Dev endpoints: enabled by SHIELD_ENABLE_DEV, owner only (cookie or X-Shield-Secret header for scripts)."""
    if not shield.settings.enable_dev:
        raise HTTPException(404)
    header = req.headers.get("x-shield-secret", "")
    if not (_user(token) or (header and hmac.compare_digest(header, shield.settings.user_secret))):
        raise HTTPException(401, "login required")


@app.post("/dev/reset")
def dev_reset(req: Request, shield_owner: str | None = Cookie(default=None)):
    _dev(req, shield_owner)
    shield.reset(wipe_journal=True)
    return {"ok": True}


@app.post("/dev/tamper/{file_id}")
def dev_tamper(file_id: str, req: Request, shield_owner: str | None = Cookie(default=None)):
    _dev(req, shield_owner)
    f = shield.seed.file(file_id)
    if not f:
        raise HTTPException(404)
    p = shield.seed.runtime_files / f.filename
    p.write_bytes(p.read_bytes() + b"\n% tampered after approval\n")
    return {"ok": True, "file": f.filename}


@app.post("/dev/mail_fault")
async def dev_mail_fault(req: Request, shield_owner: str | None = Cookie(default=None)):
    _dev(req, shield_owner)
    body = await req.json()
    if hasattr(shield.mail, "fail_mode"):
        shield.mail.fail_mode = body.get("mode")
        shield.mail.lag = int(body.get("lag", 0))
    return {"ok": True}


@app.get("/api/watch")
async def watch(shield_owner: str | None = Cookie(default=None)):
    """Mode 4: what an assistant did directly in the mailbox (Sent and Drafts), assessed by Shield."""
    if not _user(shield_owner):
        raise HTTPException(401, "login required")
    from .watch import REVOKE_URL
    if shield.watcher is None:
        return {"enabled": False}
    try:
        alerts = await asyncio.to_thread(shield.watcher.scan)
        err = None
    except Exception as e:
        alerts, err = list(shield.watcher.alerts.values()), f"{type(e).__name__}: {e}"
    return {"enabled": True, "source": shield.watcher.source.label, "revoke_url": REVOKE_URL, "error": err,
            "alerts": [a.__dict__ for a in alerts]}


@app.post("/api/watch/drafts/{alert_id:path}/delete")
def watch_delete_draft(alert_id: str, shield_owner: str | None = Cookie(default=None)):
    if not _user(shield_owner):
        raise HTTPException(401, "login required")
    try:
        return shield.watcher.delete_draft(alert_id).__dict__
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e))


@app.post("/dev/watch/simulate")
async def dev_watch_simulate(req: Request, shield_owner: str | None = Cookie(default=None)):
    _dev(req, shield_owner)
    from .watch import FakeWatchSource, simulate
    if not isinstance(shield.watcher.source, FakeWatchSource):
        raise HTTPException(400, "simulation only with SHIELD_WATCH=fake")
    body = await req.json()
    simulate(shield.watcher.source, shield, body.get("scenario", "forward_cap_table"))
    return {"ok": True}


@app.get("/api/mirror/publication")
def mirror_publication(shield_owner: str | None = Cookie(default=None)):
    """The safe text Shield publishes into the restricted demo inbox (Contain mode)."""
    if not _user(shield_owner):
        raise HTTPException(401, "login required")
    from . import mirror
    return mirror.publication(shield)


@app.post("/api/intake")
async def intake(req: Request, shield_owner: str | None = Cookie(default=None)):
    """Owner pastes the assistant's reply (e.g. from WhatsApp). Untrusted: only REQ_n / FILE_n / note are used."""
    if not _user(shield_owner):
        raise HTTPException(401, "login required")
    from . import mirror
    body = await req.json()
    return mirror.intake(shield, str(body.get("text", "")), str(body.get("source") or "Instinct (WhatsApp, pasted)"))


@app.get("/intake")
def intake_page():
    return FileResponse(STATIC / "intake.html")


@app.get("/review/{aid}")
def review_page(aid: str):
    """The single approval page every assistant links to. Static shell; data comes from the owner-only API."""
    return FileResponse(STATIC / "review.html")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")

