"""Shield entry point: `python -m app` (or `shield` once installed). Starts both listeners in one process (shared state):
  owner console  http://127.0.0.1:8000   (approval, dashboard; never tunnel this)
  MCP surface    http://127.0.0.1:8765/mcp (the only port to expose to a remote client)"""
import asyncio
import os

import uvicorn

from app.main import app, mcp_app  # noqa: E402


def preflight():
    from app.main import shield
    problem = shield.settings.secret_problem()
    if problem and os.getenv("SHIELD_ALLOW_WEAK_SECRET") != "1":
        raise SystemExit(f"Refusing to start: {problem}. Set it in backend/.env.")
    if os.getenv("SHIELD_MCP_HOST", "127.0.0.1") not in ("127.0.0.1", "localhost"):
        print("note: MCP listener is not on localhost. Tunnel/expose ONLY the MCP port, never the owner port.")
    print(f"Shield · mail: {shield.settings.mail_backend} · watch: {shield.settings.watch} · dev endpoints: "
          f"{'ON' if shield.settings.enable_dev else 'off'}")
    if shield.settings.mail_backend == "gmail":
        try:
            print(f"Shield sends as: {shield.mail.whoami()}  (approved sends come from this account)")
        except Exception as e:
            print(f"warning: could not read the sender account: {type(e).__name__}: {e}")


async def main():
    owner = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=int(os.getenv("SHIELD_OWNER_PORT", "8000")), log_level="info"))
    mcp_srv = uvicorn.Server(uvicorn.Config(mcp_app, host=os.getenv("SHIELD_MCP_HOST", "127.0.0.1"),
                                            port=int(os.getenv("SHIELD_MCP_PORT", "8765")), log_level="info"))
    # mcp_app's own lifespan runs the MCP session manager
    await asyncio.gather(owner.serve(), mcp_srv.serve())


def cli() -> None:
    preflight()
    asyncio.run(main())


if __name__ == "__main__":
    cli()
