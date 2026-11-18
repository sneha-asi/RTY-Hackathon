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
| 4 | Open the **review link** the assistant relays (or **Review & approve** on the console). Read the card aloud: real address, subject, body, `Projections_v3.pdf`, any policy warning. Click **Approve & send** | Card turns ✅ VERIFIED: "Verified in Sent (sandbox): … recipient, message and attachment fingerprint match." The **Sent folder** panel shows the message with the same sha256 prefix |
| 5 | Ask the assistant "Was it sent?". It calls `action_status` and relays the code-written text | The review page already shows VERIFIED; the receipt section lists every step |
| 6 | **Ask Shield:** "Did any AI see my cap table today?" | "Shield released the cap table 0 times and withheld it N times today." |

| 7 | **Second assistant, same policy:** `cd backend && python scripts/second_assistant.py` (or connect Codex, below) | The **Assistants** strip shows two enforced assistants under one policy. The second one sees the same summaries and counts, and the same stranger request is 🛑 BLOCKED. Instinct, Muse and OpenClaw are shown as roadmap, not tested |

Only Priya's card is approved on stage. Leave Karan's card awaiting approval (or reject it) so there's one approval.

## Optional extras (if time)

- **Tamper.** After step 3, before approving, run `curl -X POST -H "X-Shield-Secret: $SHIELD_USER_SECRET" http://127.0.0.1:8000/dev/tamper/proj_v3` → approve → ❌ FAILED "changed after approval", nothing in Sent. Run the reset script afterwards.
- **Timeout.** Before approving, run `curl -X POST -H "X-Shield-Secret: $SHIELD_USER_SECRET" -H "Content-Type: application/json" -d '{"mode":"timeout_after_send"}' http://127.0.0.1:8000/dev/mail_fault` → approve → ⏳ VERIFICATION PENDING → ✅ VERIFIED, one message in Sent.
- **Codex as the second assistant.** If your Codex CLI supports HTTP MCP servers (check `codex mcp --help`), point it at `http://127.0.0.1:8765/mcp`, for example in `~/.codex/config.toml`:

  ```toml
  [mcp_servers.shield]
  url = "http://127.0.0.1:8765/mcp"
  ```

  Then ask it the same request. Otherwise use `scripts/second_assistant.py`, a plain MCP client that names itself `second-assistant`.

## If something breaks

- No tools in the assistant: check `python run.py` is running and that the URL ends in `/mcp`.
- Console shows the login again: re-enter the secret (cookies reset when the server restarts).
- Fallback: the backup video.

## Live mode: Instinct over WhatsApp (Contain), real Gmail test accounts

Use **three Google test accounts**, never a personal one. Keep FakeMail (`SHIELD_MAIL=fake`) as the offline rehearsal and fallback; the approval flow is identical.

| Account | Who can use it | Holds |
|---|---|---|
| Restricted demo inbox | Instinct (its Gmail connector) | Only Shield's safe publication: "Priya requested projections. Request REQ_7. Eligible document FILE_2." |
| Sender | Shield only (`GMAIL_TOKEN`, `FOUNDER_TEST_GMAIL`) | Nothing until Shield sends |
| Recipient | You, on stage (`INVESTOR_TEST_GMAIL`) | Receives the approved email |

The projections, cap table, recipient mapping and policy stay on your laptop in Shield.

**Setup.** Put `credentials.json` (OAuth client, type Desktop) in `backend/`, then:

```bash
python scripts/gmail_token.py --out token_restricted.json --scopes insert
```

Log in as the **restricted demo inbox** account when the browser opens.

```bash
python scripts/gmail_token.py --out token.json --scopes send,readonly
```

Log in as the **sender** account this time.

```bash
python scripts/seed_restricted_inbox.py --token token_restricted.json
```

Connect Instinct to the restricted demo inbox only. Use a demo Instinct profile if you can; any other connected mailbox is outside Shield's coverage.

**Go/no-go first.** In WhatsApp, ask Instinct: "Check my demo inbox and prepare Priya's investor follow-up. Reply with the request ID, the document ID and a short note." It must return `REQ_7` and `FILE_2`. If it can't, use the MCP flow above instead.

**Rehearse the real send once.** In `.env`, set `SHIELD_MAIL=gmail`, `FOUNDER_TEST_GMAIL` (the sender) and `INVESTOR_TEST_GMAIL` (the recipient), then:

```bash
python scripts/gmail_smoke.py --yes
```

Expect `VERIFIED`, and the email in the recipient inbox.

**On stage:**

1. Show the WhatsApp request and Instinct's reply (`REQ_7`, `FILE_2`, a note).
2. In the console, click **Review a proposal from Instinct** (or open http://127.0.0.1:8000/intake). The page shows exactly what Shield published to the restricted inbox. Paste Instinct's reply and click **Review proposal**.
3. Shield ignores everything except the IDs and the note. It resolves Priya's real address and `Projections_v3.pdf` itself, runs the checks, and opens the same review page.
4. Click **Approve & send** once. The page shows **Verified in Gmail Sent**. Open the recipient inbox to show delivery.

**What this proves, and what it doesn't.** Instinct prepared a real follow-up without access to the confidential file. Shield accounts for what it published and what it sent. It does not cover any other mailbox connected to Instinct, and it cannot inspect Instinct's internal context.

### Before and after with Instinct (two demo inboxes, never your personal Gmail)

| Scene | Instinct is connected to | What you show |
|---|---|---|
| **Without Shield** | A demo *executive* inbox seeded with the full synthetic mailbox (`scripts/seed_unprotected_inbox.py`) | Ask Instinct: "Handle my investor follow-ups." It can read the term sheet, cap table, PAN and medical note, and it sees the hidden-instruction emails and the stranger's data-room request. Show whatever it actually does |
| **With Shield** | The restricted demo inbox (Shield's safe publication only) | The same request returns only `REQ_7` / `FILE_2`. The proposal goes through Shield: review page, one approval, Verified in Gmail Sent. The stranger is never in its view |

Switch Instinct's Gmail connection between the two scenes, or use two Instinct profiles. Disconnect your personal Gmail from the Instinct profile used on stage: whatever Instinct can reach directly is outside Shield's protection.

## Recording: Instinct on your own Gmail, then Shield (the video)

Everything runs on your laptop; the Gmail tokens never leave it. All seeded mail is **synthetic**, labelled **Shield demo**, with subjects prefixed **[DEMO]**. Remove it all afterwards with `cleanup_demo_mail.py`.

**Setup (once):**

```bash
python scripts/gmail_token.py --out token_watch.json --scopes readonly,modify,compose
```

Log in as the Gmail account Instinct is connected to.

```bash
python scripts/seed_unprotected_inbox.py --token token_watch.json --label "Shield demo"
```

This adds 16 [DEMO] emails: investor requests, term sheet, cap table attached to "Board prep", layoff plan, PAN/GST, a medical note, the hidden-instruction emails, and a stranger asking for the data room. In `backend/.env`, set `SHIELD_WATCH=gmail` and `WATCH_GMAIL_TOKEN=token_watch.json`, then run `python run.py`.

**Scene 1: Without Shield (~60s).** In WhatsApp, ask Instinct: "Check my inbox and handle my investor follow-ups." Show what it reads and does. The **Watch** panel on the Shield console checks your Sent and Drafts every few seconds:

- If Instinct **drafts** a reply to the stranger, or attaches the cap table: ⚠ **RISKY DRAFT, NOT SENT YET**, with the reasons. Click **Remove draft before it's sent**.
- If Instinct **sends**: 🚨 **SENT WITHOUT SHIELD**, with the reasons (unknown recipient, confidential file, link). Click **Revoke the assistant's access**, which opens Google's connected-apps page.
- If Instinct does neither, say so. It still read the cap table, PAN and medical note, and saw the injected instructions. That's the exposure Shield removes in scene 2.

**Scene 2: With Shield (~90s).** Instinct now works from the restricted inbox (Contain, above) or Claude via MCP. Show:

1. It only knows `REQ_7` and `FILE_2`.
2. Paste its reply into **Review a proposal from Instinct**.
3. The same review page shows the real recipient and attachment.
4. **Approve & send** once → **Verified in Gmail Sent**.

**Scene 3: Proof (~20s).** "Did any AI see my cap table today?" and the Direct-vs-Shielded comparison (21 vs 0).

**Say this out loud:** Shield can't block an assistant inside its own direct Gmail connection. On that path it watches and lets you remove or revoke. Prevention comes from moving the assistant onto Shield's path.

**Rehearse offline** (`SHIELD_WATCH=fake`):

```bash
curl -X POST -H "X-Shield-Secret: $SHIELD_USER_SECRET" -H "Content-Type: application/json" -d '{"scenario":"forward_cap_table"}' http://127.0.0.1:8000/dev/watch/simulate
```

Run it again with `"draft_data_room"` for the draft case.

**After recording:**

```bash
python scripts/cleanup_demo_mail.py --token token_watch.json
```
