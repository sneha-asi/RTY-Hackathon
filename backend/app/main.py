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
            "sensitive_values_exposed": exposure,
            "quarantined": len({e["item_id"] for e in shield.ledger.all() if e["kind"] == "quarantine"}),
            "blocked": sum(a.state.value == "BLOCKED" for a in actions),
            "verified": sum(a.state.value == "VERIFIED" for a in actions),
        },
        "actions": [_action_full(a) if authed else {"id": a.id, "state": a.state.value,
                                                    "status_text": shield.guard.status_text(a)} for a in actions],
        "model_view": shield.model_view[-20:] if authed else [],
        "mail_backend": shield.settings.mail_backend,
    }


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


def _dev():
    if not shield.settings.enable_dev:
        raise HTTPException(404)


@app.post("/dev/reset")
def dev_reset():
    _dev()
    shield.reset(wipe_journal=True)
    return {"ok": True}


@app.post("/dev/tamper/{file_id}")
def dev_tamper(file_id: str):
    _dev()
    f = shield.seed.file(file_id)
    if not f:
        raise HTTPException(404)
    p = shield.seed.runtime_files / f.filename
    p.write_bytes(p.read_bytes() + b"\n% tampered after approval\n")
    return {"ok": True, "file": f.filename}


@app.post("/dev/mail_fault")
async def dev_mail_fault(req: Request):
    _dev()
    body = await req.json()
    if hasattr(shield.mail, "fail_mode"):
        shield.mail.fail_mode = body.get("mode")
        shield.mail.lag = int(body.get("lag", 0))
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")

