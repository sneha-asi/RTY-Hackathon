# Shield — one page

*Team Axon · Track `ai-agents`. The shared understanding we're building from. Full detail: [PRD](PRD.md), [LLD](LLD.md).*

## The idea in one sentence

A layer the user owns that sits between AI assistants and **everything they can reach** (email, calendar, files, messages, browser, money, devices). The model gets only what the task needs and can only *propose* actions. Code decides who and what, the user approves the exact action, and Shield checks the provider's record before calling anything done.

## The problem

Assistants like Instinct, Muse and OpenClaw ask for access to almost everything. Content they read (an email, an invite, a doc) can carry hidden instructions. An assistant that combines **private data + untrusted content + a way to act outward** can be steered against its user: the "lethal trifecta". Copilot, Gemini and ChatGPT have each been hijacked through content they read; Instinct emailed an investor unasked. Detection alone can't close this, so Shield doesn't rely on it.

## What reaches the model (M0)

Shield returns only **handles, structured attributes and purpose-filtered summaries** that Shield writes itself. No raw email or document text is passed through.

| The model never gets… | Instead it gets… |
|---|---|
| Addresses, file contents, account numbers, PAN, keys | Handles: `CONTACT_1 · investor · NDA ✔`, `FILE_2 · projections · v3` |
| Email bodies | A summary such as "Priya Rao (investor, NDA on file) asked for projections, due Fri." |
| Items outside the task's purpose | Withheld counts only: "withheld: financial 2 · hr 1 · health 1" |
| Raw send / share tools | `propose_*` tools; code runs WHO · WHAT · POLICY · CONTENT · LOCK |

The cleaner strips hidden text and **quarantines the seeded malicious examples** in our test set. It is an extra safeguard, not the guarantee: the guarantee comes from what the tool interface returns.

## Approval and verification

- The **user** (logged in to Shield, never the assistant) approves the **exact recipients (To/Cc/Bcc), message and attachment**.
- Shield sends **the same attachment bytes it checked**; anything changed after approval → FAILED.
- If delivery is uncertain (timeout after send), the action shows **VERIFICATION_PENDING** and Shield checks the provider's Sent record. **An uncertain send never triggers an automatic resend.**
- Only **VERIFIED** counts as success.

## Where the guarantees hold

| Access path | What we claim |
|---|---|
| Shield is the assistant's **only route** to the account (MCP connector) | Full enforcement: the guarantees above |
| Closed assistant, **supported mirror** available | Containment: it sees only what Shield mirrors; only mirror sends are gated |
| Any account | Monitoring and revocation, **as far as each provider exposes** grants, sent records and revoke APIs |

The same policy applies across every supported assistant. We never claim more than the path allows.

## The demo: "Handle my investor follow-ups"

The concrete case is **"send Priya the projections"**:

```
search(purpose=share_document)        → investor requests as handles + summaries; the rest withheld
propose_send_document(CONTACT_1, FILE_2)
  → WHO ✔ Priya Rao · WHAT ✔ Projections v3 · POLICY ✔ NDA · CONTENT ✔ · LOCK 🔒
propose_send_document(SENDER_3, FILE_2)   (stranger asking for the data room) → 🛑 BLOCKED
user approves exact payload → live Gmail send → Shield reads the Sent record → ✅ VERIFIED
```

- **Comparison:** same request, same model, Direct vs Shielded. We show **sensitive values exposed** and **task completed** for both, exactly as measured.
- **Target until tested:** about 3 handles released, 0 sensitive values.
- **Receipt:** "Shield released the cap table 0 times and withheld it twice today."
- **Fallback:** the same flow in the sandbox, rehearsed.

## Build order

1. **Vertical slice:** MCP → proposal → minimal approval screen → sandbox send → verified read-back, with tests alongside.
2. VERIFICATION_PENDING + no-resend; tamper → FAILED.
3. Full seed, cleaner and fixture-based privacy test.
4. Gmail adapter (one live send).
5. Dashboard and receipts.
6. Comparison scenes.
7. Calendar first cut: free/busy only.

## Why it scores

- **Working product:** Claude over MCP completes a real task; a real email lands, ✅ VERIFIED.
- **Problem insight:** the trifecta explains why access to everything is dangerous, and why detection isn't enough.
- **Depth:** a tool interface that never returns raw text, sealed exact-payload approval, no-resend verification, and measured comparisons.
