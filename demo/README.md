# Demo: runbook for rehearsal, recording and fallback

This is the single runbook. Synthetic fixtures are in [`fixtures/`](fixtures/): contacts, inbox, calendar, sample files, published IDs and the planted sensitive values the tests check. Scripts are in [`scripts/`](scripts/). Run them from anywhere; tokens, `credentials.json` and `.env` live in `backend/`.

**Primary live flow:** an executive asks Instinct over WhatsApp to prepare an investor follow-up. Instinct reads one labelled synthetic email in the executive's Gmail and replies with a request ID and a document ID. The executive pastes that reply into Shield, which resolves the real recipient and deck locally. The executive approves the exact email once, and Shield shows **Verified in Gmail Sent**.

**Fallbacks:**
- **Live FakeMail:** the same screens on the in-memory mailbox, for offline rehearsal or if Gmail misbehaves.
- **MCP flow:** Claude connects to Shield directly, if Instinct can't retrieve the seeded request.

**Scope, as shown on screen:** "Instinct has direct Gmail access · Shield controls sends approved here." Shield controls the send submitted through its approval page. Instinct's own direct reads and sends sit outside that flow. Don't claim Gmail is "protected", or anything about everything Instinct saw.

---

## 0. One-time setup (your laptop)

```bash
cd backend && pip install -e ".[gmail,test]" && cp .env.live.example .env
```

In `backend/.env`:

- `SHIELD_USER_SECRET`: 12+ characters. Shield refuses to start without it.
- Leave `SHIELD_ENABLE_DEV=0` for the recording. Set it to `1` only for rehearsal tricks.
- `INVESTOR_TEST_GMAIL`: a test recipient inbox **you control**. This is "Priya" for the recording.
- `FOUNDER_TEST_GMAIL` and `GMAIL_TOKEN`: the account Shield sends from (step 2).

Put `credentials.json` in `backend/`: a Google Cloud OAuth client of type **Desktop**, with the Gmail API enabled. Your Google account must be a test user on the OAuth consent screen.

## 1. Seed one labelled synthetic email into your Gmail

Sign in as **the Gmail account Instinct reads** when the browser opens:

```bash
python demo/scripts/gmail_token.py --out token_watch.json --scopes readonly,modify,compose
```

Preview first, then publish:

```bash
python demo/scripts/seed_demo_request.py --token token_watch.json --dry-run
```

```bash
python demo/scripts/seed_demo_request.py --token token_watch.json
```

This inserts **"[Shield Demo] Priya — investor follow-up"**, labelled `Shield demo`. It contains a safe summary, `REQ_7` and `FILE_2`, and no attachment or destination address. Shield records the publication with Gmail's message id as evidence.

## 2. Choose and confirm the sender account

Shield sends only from the account in `GMAIL_TOKEN`. Use a separate test sender if you have one; otherwise your own account works, but say so on camera. Sign in as **the sender** when the browser opens:

```bash
python demo/scripts/gmail_token.py --out token.json --scopes send,readonly
```

```bash
python demo/scripts/gmail_whoami.py --token token.json
```

That prints the sender address. `python -m app` prints it again at startup ("Shield sends as: …").

## 3. Go/no-go: the WhatsApp handoff

Ask Instinct in WhatsApp:

> Find the email titled "[Shield Demo] Priya — investor follow-up." Prepare the follow-up and reply here with the request ID, document ID, and a short note.

**Pass** = it returns `REQ_7` and `FILE_2`. If it doesn't, use the MCP flow (section 7).

## 4. Rehearse on FakeMail first

Set `SHIELD_MAIL=fake` in `.env`, then, from `backend/`:

```bash
python -m app
```

1. Open http://127.0.0.1:8000/intake and log in. You should see the connection label, "✔ Published to <your Gmail> · Gmail id …", and the exact seeded email.
2. Paste Instinct's **actual** WhatsApp reply and click **Review proposal**. The page shows "Proposal received → Awaiting approval", then the review card.
3. Check the review card:
   - "Shield hasn't sent this message."
   - **From the assistant (untrusted):** `REQ_7`, `FILE_2`, the note.
   - **Resolved by Shield, locally:** Priya Rao and the test address, `Projections_v3.pdf`, the policy decision.
   - The exact outgoing message and its seal.
4. Click **Approve & send**. The steps run Sending → Checking Sent → **Verified**, with ✔ recipients · subject · body · attachment, and a four-line receipt:
   - Seeded
   - Assistant returned
   - You approved
   - Sent recorded

## 5. Rehearse one real Gmail send

Set `SHIELD_MAIL=gmail` in `.env`, then:

```bash
python demo/scripts/gmail_smoke.py --yes
```

Expect `VERIFIED` ("Verified in Gmail Sent"), and the email in the recipient inbox. Then restart `python -m app` with `SHIELD_MAIL=gmail`.

## 6. Recording (WhatsApp on the left, Shield on the right)

| Moment | Show |
|---|---|
| Before asking Instinct | `/intake`: the connection label, plus the exact synthetic summary and IDs seeded into Gmail |
| WhatsApp | The request to Instinct, and its reply with `REQ_7`, `FILE_2` and a note |
| After pasting | "Proposal received → Awaiting approval". The pasted IDs next to what Shield resolved locally: test recipient, subject, body, attachment, policy decision |
| Before approval | "Shield hasn't sent this message." **Approve & send** / **Reject** |
| After approval | Sending → Checking Gmail Sent → **Verified in Gmail Sent**, with the matched fields and the attachment fingerprint |
| End | The receipt (seeded · Instinct returned · you approved · Gmail recorded). Then open the recipient test inbox to show delivery |

Say: "The WhatsApp reply only had a file ID. Shield resolved it locally to the actual deck, I approved this exact email, and Gmail's Sent record matches it."

## 7. MCP flow (fallback, or a second assistant)

```bash
claude mcp add --transport http shield http://127.0.0.1:8765/mcp
```

Ask: "Handle my investor follow-ups." Proposals return a `review_url` to the same review page. `python demo/scripts/second_assistant.py` shows a second MCP client under the same policy. OpenClaw: connect it to the same URL per https://docs.openclaw.ai/tools/mcp (untested). Only the MCP port may ever be tunnelled; never the owner port (8000).

## 8. Optional, off the critical path

- **Comparison:** "Run comparison" on the console is a **scripted** run of the tool calls a typical assistant makes, measured on the same synthetic data (21 sensitive values without Shield, 0 with). Call it scripted on screen. It isn't a model run unless the same model actually ran both modes.
- **Watch scene:** set `SHIELD_WATCH=gmail` and `WATCH_GMAIL_TOKEN=token_watch.json`. A test send from Instinct shows as "Sent message observed · No matching Shield approval", and risky drafts can be removed. A Sent record alone doesn't prove which app sent it; proving that needs an account-level watcher.
- **Rehearsal tricks** (`SHIELD_ENABLE_DEV=1`): tamper the file after the review card appears → FAILED, nothing sent. Fault injection → VERIFICATION_PENDING → VERIFIED with one send.

## 9. After recording

```bash
python demo/scripts/cleanup_demo_mail.py --token token_watch.json
```

This moves everything labelled `Shield demo` to Trash and removes the label. Tokens and `.env` stay on your laptop; they're git-ignored.
