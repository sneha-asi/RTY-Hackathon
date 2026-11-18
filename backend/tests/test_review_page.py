"""One approval page for every assistant (review_url). The link identifies the action and grants nothing."""
from fastapi.testclient import TestClient
from starlette.testclient import TestClient as RawClient

from app import main, tools


def _propose(sh, session, client_name):
    sh.note_client(session, client_name)
    res = tools.search(sh, session, "share_document", "investor")
    priya = next(i for i in res["items"] if (i["summary"] or "").startswith("Priya"))
    v3 = next(f["handle"] for f in tools.list_files(sh, session, "projections")["files"] if f["latest"])
    return tools.propose_send_document(sh, session, priya["handle"], v3, "Ahead of Friday")


def test_proposals_from_two_clients_open_the_same_review_page():
    sh = main.shield
    sh.reset(wipe_journal=True)
    v1 = _propose(sh, "mcp:claude", "claude-code")
    v2 = _propose(sh, "mcp:openclaw", "openclaw")
    for v in (v1, v2):
        assert v["state"] == "AWAITING_APPROVAL"
        assert v["review_url"] == f"{sh.settings.review_base}/review/{v['action_id']}"
        assert sh.settings.user_secret not in v["review_url"] and "?" not in v["review_url"]  # no credential in the link
        assert "@" not in str(v)  # the real address stays out of the tool result
    owner = TestClient(main.app)
    owner.post("/api/login", json={"secret": sh.settings.user_secret})
    for v, name in ((v1, "claude-code"), (v2, "openclaw")):
        page = owner.get(f"/review/{v['action_id']}")
        assert page.status_code == 200 and "Approve &amp; send" in page.text
        d = owner.get(f"/api/actions/{v['action_id']}").json()
        assert d["client"] == name and d["payload"]["to"] == [sh.seed.contact("c1").email]
        assert any(e["kind"] == "transition" for e in d["receipt"])
    approved = owner.post(f"/api/actions/{v1['action_id']}/approve", json={"seal": owner.get(f"/api/actions/{v1['action_id']}").json()["seal"]})
    assert approved.json()["state"] == "VERIFIED"
    assert tools.action_status(sh, "mcp:claude", v1["action_id"])["state"] == "VERIFIED"


def test_no_client_credential_can_view_or_approve():
    sh = main.shield
    sh.reset(wipe_journal=True)
    v = _propose(sh, "mcp:claude", "claude-code")
    aid = v["action_id"]
    anon = TestClient(main.app)  # following the link without the owner's Shield session
    assert anon.get(f"/api/actions/{aid}").status_code == 401
    assert anon.post(f"/api/actions/{aid}/approve", json={"seal": "x"}).status_code == 401
    mcp = RawClient(main.mcp_app)  # the only listener a remote assistant can reach
    for path in (f"/review/{aid}", f"/api/actions/{aid}", f"/api/actions/{aid}/approve"):
        assert mcp.get(path).status_code == 404
    assert tools.action_status(sh, "mcp:someone-else", aid)["state"] == "UNKNOWN"  # other sessions can't even see it
    assert sh.guard.actions[aid].state.value == "AWAITING_APPROVAL"
