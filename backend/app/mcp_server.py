"""MCP surface (LLD §9). No send tool, no approve tool (I3)."""
from __future__ import annotations

from mcp.server.fastmcp import Context, FastMCP

from . import tools
from .service import Shield

INSTRUCTIONS = (
    "Shield protects the user's email, files and calendar. You see people, files and threads as handles "
    "(CONTACT_n, SENDER_n, FILE_n, THREAD_n) with attributes and short summaries, never raw addresses or contents. "
    "You cannot send anything directly: to answer a document request, call propose_send_document with the request's THREAD handle and a FILE handle, then tell the user to approve it "
    "in Shield, and relay action_status text word for word. Always pass a purpose to search: "
    "share_document, schedule, reply or triage."
)


def _sid(ctx: Context | None) -> str:
    """Handles and actions are bound to the client's MCP session. No shared default session."""
    try:
        sid = ctx.request_context.request.headers.get("mcp-session-id")
    except Exception:
        sid = None
    if not sid:
        raise ValueError("no MCP session; reconnect")
    return "mcp:" + sid


def build_mcp(shield: Shield) -> FastMCP:
    mcp = FastMCP("shield", instructions=INSTRUCTIONS, streamable_http_path="/mcp")

    @mcp.tool()
    def search(purpose: str, query: str = "", ctx: Context = None) -> dict:
        """Find items for a purpose (share_document | schedule | reply | triage). Returns handles + summaries; unrelated items only as withheld counts."""
        return tools.search(shield, _sid(ctx), purpose, query)

    @mcp.tool()
    def list_files(category: str = "", ctx: Context = None) -> dict:
        """List shareable files as FILE_n handles with category, version, latest and requires_nda. Never contents."""
        return tools.list_files(shield, _sid(ctx), category)

    @mcp.tool()
    def free_slots(start: str, end: str, ctx: Context = None) -> dict:
        """Busy times between two dates (YYYY-MM-DD). Free/busy only."""
        return tools.free_slots(shield, _sid(ctx), start, end)

    @mcp.tool()
    def propose_send_document(request: str, file: str, note: str = "", ctx: Context = None) -> dict:
        """Propose answering a document request (THREAD_n from search) with a file (FILE_n). Shield takes the recipient
        from the request, checks the file matches what was asked for, and asks the user to approve. Note: plain text, no links."""
        return tools.propose_send_document(shield, _sid(ctx), request, file, note)

    @mcp.tool()
    def action_status(action_id: str, ctx: Context = None) -> dict:
        """Current state of a proposed action, with status text to relay word for word."""
        return tools.action_status(shield, _sid(ctx), action_id)

    return mcp
