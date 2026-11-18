"""A second, independent MCP client ("second-assistant") for the demo: it connects to the same Shield endpoint and
gets the same policy, the same handles-only view and the same blocks as Claude. Usage: python scripts/second_assistant.py"""
# Run from anywhere: imports Shield from backend/, and relative paths (tokens, credentials.json, .env) resolve in backend/.
import os as _os
import sys as _sys
from pathlib import Path as _Path

_BACKEND = _Path(__file__).resolve().parents[2] / "backend"
_sys.path.insert(0, str(_BACKEND))
_os.chdir(_BACKEND)
import asyncio
import json
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import Implementation

URL = os.getenv("SHIELD_MCP_URL", "http://127.0.0.1:8765/mcp")


async def main():
    async with streamablehttp_client(URL) as (r, w, _):
        async with ClientSession(r, w, client_info=Implementation(name="second-assistant", version="1.0")) as s:
            await s.initialize()
            j = lambda res: json.loads(res.content[0].text)
            res = j(await s.call_tool("search", {"purpose": "share_document", "query": "investor"}))
            print("What this assistant sees:")
            for i in res["items"]:
                print(f"  {i['handle']:9} {i['status']:11} {i['summary'] or i['reason']}")
            print(f"  withheld: {res['withheld']}")
            files = j(await s.call_tool("list_files", {"category": "projections"}))
            v3 = next(f["handle"] for f in files["files"] if f["latest"])
            stranger = next(i["handle"] for i in res["items"] if (i["summary"] or "").startswith("SENDER_"))
            v = j(await s.call_tool("propose_send_document", {"request": stranger, "file": v3}))
            print(f"\nSame stranger request from this assistant → {v['state']}: {v['status_text']}")
            print("Try it raw:", j(await s.call_tool("propose_send_document",
                                                     {"request": "growth@quickcap-partners.io", "file": v3}))["state"])


if __name__ == "__main__":
    asyncio.run(main())
