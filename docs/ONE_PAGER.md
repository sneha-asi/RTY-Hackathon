# Axon Shield — one page

*Claude's read of the PRD, so we can confirm we're aligned before coding.*

## The idea in one sentence

A server the user owns that sits between any AI assistant and their Gmail/Calendar/Drive, so the model **sees only labels, never the real data, and can only ask; code decides what is sent, a human approves, and Shield checks the sent mail to prove it happened.**

## The problem

AI assistants now read founders' inboxes and can send mail. Anything they read (an email, a calendar invite, a shared doc) can contain hidden instructions. An agent with **private data + untrusted content + a way to send** will eventually leak (the "lethal trifecta"). Copilot, Gemini and ChatGPT have all been hijacked this way. Asking the model to resist doesn't work; 99% detection still loses.

## The insight

Don't make the model smarter. **Take the dangerous things out of its hands:**

| The model never gets… | Instead it gets… |
|---|---|
| Real email addresses, file contents, PAN/GST/keys | Handles: `CONTACT_1 · investor · NDA ✔`, `FILE_2 · projections · v3` |
| Hidden or instruction-like text | `[quarantined · SENDER_4]` |
| A `send_email` tool | `propose_send_document(CONTACT_1, FILE_2)` |
| Freedom to put links/images in outgoing text | CONTENT check blocks them |
| A say in whether it worked | Code re-reads the sent mail and compares the SHA-256 |

## How a request flows

```
"Send Priya the projections"
  → search(purpose=share_document)    model sees 3 handles, 0 sensitive values
  → propose_send_document(CONTACT_1, FILE_2)
  → WHO ✔ Priya Rao · WHAT ✔ Projections v3 · POLICY ✔ NDA · CONTENT ✔ · LOCK 🔒 sealed
  → founder approves on the dashboard (sees the real address and file)
  → Gmail sends → Shield re-reads the sent message → ✅ VERIFIED
```

## What we demo (and what each proves)

| Scene | Result | Proves |
|---|---|---|
| Direct vs Shielded, same task, same model | Exposure: many → 0 | Need-to-know works and the task still gets done |
| Poisoned invite / white-on-white email | Quarantined | Cleaner |
| Unknown "investor" wants the data room | 🛑 BLOCKED (WHO) | Code picks recipients |
| Reply with a hidden image URL | 🛑 BLOCKED (CONTENT) | EchoLeak channel closed |
| File swapped after approval | ❌ FAILED (LOCK) | Approval means the exact bytes |
| "Did any AI see my cap table today?" | "No, withheld 2×" | Audit trail |

## Why it wins on the three judging criteria

- **Working product:** Claude, connected over MCP, does a real task and a real Gmail lands with ✅ VERIFIED.
- **Problem insight:** the trifecta explains *why* every assistant gets hijacked; we cut it structurally rather than detect.
- **Depth:** handles + five deterministic checks + payload seal + read-back verification + a measured Direct-vs-Shielded harness on 5 recreated attacks.

## What it is not

Not an assistant. Not a model-hardening trick. No LLM inside Shield. It can't protect closed assistants (Instinct, Muse) that log in to Gmail themselves; we say so on stage (M3: mirror inbox).

---

## Where the repo stands, and what I'd flag before coding

1. **The repo is currently "Axon Voice", not Shield.** `team.json` (title + one-liner) and the two existing backend commits describe a phone-call agent (caller PIN, spoken-name resolution). The seed data (Priya/Karan, Projections v2/v3, Teaser), PDFs, `models.py` state machine and file lookup carry over. Caller auth and mishearing logic don't. `team.json` should be updated to Shield.
2. **Time.** It's ~5:05 PM IST. The PRD's feature freeze is 5:30, code freeze 7:00. The PRD's full P0 list won't fit in what's left. My recommended cut, in build order:
   1. **Must:** handles + broker (2 purposes: `share_document`, `triage`) · cleaner (hidden text + quarantine) · guard with all five checks + seal · sandbox executor + verifier · ledger · MCP server with Claude completing the Priya task · tests for each check and attack.
   2. **Then:** minimal dashboard (action card with check rows + approve button + "what the AI saw" panel), receipt query, one real Gmail send.
   3. **Cut or fake honestly:** full detector set (keep emails, PAN, GSTIN, API keys, money), `propose_event`/`free_slots`, the 3-run harness (one scripted Direct run is enough to show exposure), ngrok/remote connector (run Claude locally via the SDK).
3. **README "Your project" section** is still empty and is judged; it needs the 3-sentence problem statement before 7.
