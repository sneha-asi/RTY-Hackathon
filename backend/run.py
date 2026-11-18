"""Start both listeners in one process (shared state):
  owner console  http://127.0.0.1:8000   (approval, dashboard; never tunnel this)
  MCP surface    http://127.0.0.1:8765/mcp (the only port to expose to a remote client)"""
import asyncio
import os

import uvicorn

from app.main import app, mcp_app


async def main():
    owner = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=int(os.getenv("SHIELD_OWNER_PORT", "8000")), log_level="info"))
    mcp_srv = uvicorn.Server(uvicorn.Config(mcp_app, host=os.getenv("SHIELD_MCP_HOST", "127.0.0.1"),
                                            port=int(os.getenv("SHIELD_MCP_PORT", "8765")), log_level="info"))
    # mcp_app's own lifespan runs the MCP session manager
    await asyncio.gather(owner.serve(), mcp_srv.serve())


if __name__ == "__main__":
    asyncio.run(main())
