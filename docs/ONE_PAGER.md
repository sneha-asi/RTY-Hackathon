# Shield — one page

*Team Axon · Track `ai-agents`. The shared understanding we're building from. Detail: [PRD](PRD.md) (what and why) · [HLD](HLD.md) (components and boundaries) · [LLD](LLD.md) (modules and tests). IDs B1–B6 and I1–I10 are the same in all four documents.*

## The idea in one sentence

A layer the user owns that sits between AI assistants and **everything they can reach** (email, calendar, files, messages, browser, money, devices). The model gets only what the task needs and can only *propose* actions. Code decides who and what, the user approves the exact action, and Shield checks the provider's record before calling anything done.

## Business first principles

- **B1** An assistant's value and its potential damage both grow with access. Shield's job is to make *more* delegation safe; success is tasks delegated safely.
- **B2** The user bears the loss, while vendors audit themselves. So Shield is owned by the user.
- **B3** People use several assistants. So one policy applies across all of them.
- **B4** Trust needs evidence. So Shield shows what was released, withheld, approved and verified.
- **B5** Friction kills delegation. So only outward and irreversible actions are gated.
- **B6** Start with founders (most third-party data, earliest adopters) and one job: *"Handle my investor follow-ups."*

## The problem

Assistants like Instinct, Muse and OpenClaw ask for access to almost everything. Content they read (an email, an invite, a doc) can carry hidden instructions. An assistant that combines **private data + untrusted content + a way to act outward** can be steered against its user: the "lethal trifecta". Copilot, Gemini and ChatGPT have each been hijacked through content they read; Instinct emailed an investor unasked. A model can't be made to reliably refuse what it reads, so Shield doesn't depend on the model.

## Technical first principles: the invariants

| | Invariant | In M0 |
|---|---|---|
| I1 | Need-to-know at the interface | The model gets only handles (`CONTACT_1 · investor · NDA ✔`, `FILE_2 · projections · v3`), structured attributes and purpose-filtered summaries Shield writes. No email or document text passes through |
| I2 | Untrusted content is data | The cleaner strips hidden text and quarantines the seeded malicious examples. It's a safeguard, not the guarantee |
| I3 | No ambient authority | No send tool; only `propose_*` |
| I4 | Code chooses targets | Handles resolve to the user's contacts and file catalogue; raw addresses are refused |
| I5 | No outbound channel in model text | No URLs, images, raw identifiers or sensitive values in the note |
| I6 | User approves exact sealed payload | Recipients (To/Cc/Bcc), message bytes and attachment hash are sealed; Shield sends the same bytes it checked |
| I7 | Done is a provider fact | Only VERIFIED counts; uncertain delivery shows VERIFICATION_PENDING and is never resent automatically |
| I8 | Decisions recorded without content | Receipts: "Shield released the cap table 0 times and withheld it twice today." |
| I9 | Fail closed | Any error blocks or withholds |
| I10 | Claims follow the access path | See below |

## Where the guarantees hold (I10)

| Access path | What we claim |
|---|---|
| Shield is the assistant's **only route** to the account (MCP connector) | Full enforcement: I1–I9 |
| Closed assistant with a **supported mirror** | Containment: it sees only what Shield mirrors; only mirror sends are gated |
| Any account | Monitoring and revocation, **as far as each provider exposes** |

## The demo: "Handle my investor follow-ups"

The concrete case is **"send Priya the projections"**:

```
search(purpose=share_document)         → investor requests as handles + summaries; the rest withheld
propose_send_document(CONTACT_1, FILE_2)
  → WHO ✔ Priya Rao · WHAT ✔ Projections v3 · POLICY ✔ NDA · CONTENT ✔ · LOCK 🔒
propose_send_document(SENDER_3, FILE_2)   (stranger asking for the data room) → 🛑 BLOCKED
user approves exact payload → live Gmail send → Shield reads the Sent record → ✅ VERIFIED
```

- **Comparison:** same request, same model, Direct vs Shielded. We show **sensitive values exposed** and **task completed** for both, exactly as measured.
- **Target until tested:** about 3 handles released, 0 sensitive values.
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
- **Problem insight:** B1–B6 explain who needs this and why vendors can't supply it; the trifecta explains why detection isn't enough.
- **Depth:** I1–I10 are each implemented in code and each has a test (traceability in PRD § "First principles").
