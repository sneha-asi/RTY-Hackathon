# Demo runbook

One request in the assistant, uninterrupted preparation, one approval. All data is synthetic (sandbox mailbox, calendar, drive).

## Setup (once)

```bash
cd backend
```

```bash
pip install -r requirements.txt && cp .env.example .env
```

Set `SHIELD_USER_SECRET` in `.env`. Leave `SHIELD_MAIL=fake`.

```bash
python run.py
```

Connect the assistant to the **MCP listener only** (never to the console port):

```bash
claude mcp add --transport http shield http://127.0.0.1:8765/mcp
```

Open the owner console at http://127.0.0.1:8000 and log in with `SHIELD_USER_SECRET`.

## Before each run

```bash
backend/scripts/demo_reset.sh
```

Start a fresh assistant conversation, so its handles are new.

## The run (about 3 minutes)

| # | Do | The console shows |
|---|---|---|
| 1 | Click **Run comparison** in the console | Without Shield: ~21 sensitive values the AI received, task done. With Shield: 0, task done. Measured, not hard-coded |
| 2 | In the assistant: **"Handle my investor follow-ups."** | **What the AI received:** Priya and Karan (investors) and SENDER_1 (unknown) as one-line summaries. Three red QUARANTINED notices. A `withheld:` line with counts only |
| 3 | (The assistant proposes; no interruptions) | **Actions:** Priya: WHO/WHAT/POLICY/CONTENT/LOCK all ✔, AWAITING APPROVAL. Karan: WHAT ⚠, teaser instead (no NDA). Stranger: 🛑 BLOCKED, unknown recipient; data room not covered by the policy |
| 4 | Read Priya's card aloud: real address, subject, body, `Projections_v3.pdf`, seal. Click **Approve exactly this** | Card turns ✅ VERIFIED: "Verified in Sent (sandbox): … recipient, message and attachment fingerprint match." The **Sent folder** panel shows the message with the same sha256 prefix |
| 5 | The assistant relays the status text word for word | — |
| 6 | **Ask Shield:** "Did any AI see my cap table today?" | "Shield released the cap table 0 times and withheld it N times today." |

Only Priya's card is approved on stage. Leave Karan's card awaiting approval (or reject it) so there's one approval.

## Optional extras (if time)

- **Tamper.** After step 3, before approving, run `curl -X POST -H "X-Shield-Secret: $SHIELD_USER_SECRET" http://127.0.0.1:8000/dev/tamper/proj_v3` → approve → ❌ FAILED "changed after approval", nothing in Sent. Run the reset script afterwards.
- **Timeout.** Before approving, run `curl -X POST -H "X-Shield-Secret: $SHIELD_USER_SECRET" -H "Content-Type: application/json" -d '{"mode":"timeout_after_send"}' http://127.0.0.1:8000/dev/mail_fault` → approve → ⏳ VERIFICATION PENDING → ✅ VERIFIED, one message in Sent.
- **Second assistant.** Any MCP client can connect to the same `http://127.0.0.1:8765/mcp` under the same policy (B3).

## If something breaks

- No tools in the assistant: check `python run.py` is running and that the URL ends in `/mcp`.
- Console shows the login again: re-enter the secret (cookies reset when the server restarts).
- Fallback: the backup video.
