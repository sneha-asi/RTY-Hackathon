# Shield — one page

*Team Axon · Track `ai-agents`. Detail: [PRD](PRD.md) (what and why) · [HLD](HLD.md) (components and boundaries) · [LLD](LLD.md) (modules and tests). IDs B1–B6 and I1–I10 are the same in all four documents.*

## What Shield does

**An executive sets one standing policy for what their AI assistant can learn and what it can propose. The assistant can prepare a confidential share without opening the file. The executive approves the exact outgoing message, and Shield verifies what was sent.**

## The problem

An executive's inbox holds sensitive records next to routine work: term sheets, cap tables, layoff plans and tax IDs sit beside meeting requests and investor follow-ups. Much of it is other people's data. Outgoing messages also carry authority: an email from an executive commits the company or hands over a confidential file.

Personal assistants like Instinct, Muse and OpenClaw ask for access to all of it. Instinct emailed an investor on a user's behalf "without checking with me first". Today the choice is to give the assistant everything or not use one. The longer incident list is in the PRD.

## Business first principles

- **B1** An assistant's value and its potential damage both grow with access. Shield's job is to make *more* delegation safe.
- **B2** The user bears the loss, while vendors audit their own controls. So Shield is owned by the user.
- **B3** People use more than one assistant. So there is **one policy across supported assistants**.
- **B4** Trust needs evidence. So Shield shows what was released, withheld, approved and verified.
- **B5** Friction kills delegation. Preparation runs without interruptions; only the send needs approval.
- **B6** **Executives are the target users**, because they deal with a lot of sensitive information and their messages carry authority. **Investor follow-ups are the demo workflow.**

## Technical first principles: one policy for disclosure and action

The executive enables a standing policy once (M0: *investor follow-ups*). The same policy decides what Shield discloses to the assistant **and** which proposals it accepts.

| | Invariant | In M0 |
|---|---|---|
| I1 | Need-to-know at the interface | Under the policy, the assistant gets only handles (`THREAD_1`, `FILE_2`), structured attributes and summaries Shield writes. No email or document text, no addresses, no file contents |
| I2 | Untrusted content is data | Hidden text is stripped; the seeded malicious examples are quarantined. A safeguard, not the guarantee |
| I3 | No ambient authority | The assistant can read (scoped) and propose; execution and approval stay outside it |
| I4 | Proposals are bound to the request | `propose_send_document(request_handle, file_handle)`. Shield resolves the recipient from the request and checks the file fits the request and the policy |
| I5 | No outbound channel in model text | The assistant's note is checked for links, images, identifiers (addresses, handles) and sensitive patterns (PAN, card, API key, amounts); any hit blocks the proposal |
| I6 | Executive approves the exact message | M0 sends to **one To recipient** (Cc/Bcc on the roadmap). Shield seals the recipient, the exact message bytes and the attachment hash, and sends the same bytes it checked |
| I7 | Done is a provider fact | Only **Verified in Sent** counts. Uncertain delivery shows VERIFICATION_PENDING and is never resent, even after a restart. Sent but the record differs, or still unconfirmed → UNVERIFIED. FAILED means definitely not sent |
| I8 | Decisions recorded without content | Receipts: "Shield released the cap table 0 times and withheld it once today." |
| I9 | Fail closed | Any error blocks or withholds |
| I10 | Claims follow the access path | See below |

## Where the guarantees hold

- **Raw records and credentials stay in a user-controlled Shield process.** The assistant reaches only the filtered MCP listener; the approval console stays local.
- **Full enforcement requires Shield to be the assistant's sole route to the protected account.** Shield reports this as sole path yes / no / unknown.
- **Direct uploads to the assistant fall outside that path.**
- **Instinct and Muse are roadmap experiments until tested** (mirror inbox, edge proxy, watch and revoke). OpenClaw likewise, unless its tools can point at Shield. The demo uses Claude over MCP.

## The demo: one request, one approval

**Demo data.** The demo runs entirely on a synthetic sandbox mailbox, calendar and drive (no real accounts, no third-party data). Verification reads the sandbox mailbox's own Sent record, exactly as it would read Gmail's. The Gmail adapter exists and is optional.

The executive types one request in the assistant: *"Handle my investor follow-ups."* Preparation runs with no interruptions:

```
search(purpose=share_document)              → 3 requests as handles + summaries
propose_send_document(THREAD_1, FILE_2)     Priya (investor, NDA)    → projections v3  → awaiting approval
propose_send_document(THREAD_2, FILE_2)     Karan (investor, no NDA) → teaser instead (policy fallback)
propose_send_document(THREAD_3, FILE_2)     unknown sender, data room → 🛑 BLOCKED
```

On stage, one approval for Priya's send: the executive sees the exact recipient, subject, body and attachment, approves, and Shield shows **✅ Verified in Sent**. That means Gmail's Sent record matched the approved recipient, subject, body and attachment SHA-256.

What the dashboard reports, kept separate:

- **Released:** thread summaries and file handles the assistant received.
- **Quarantine notices:** hidden-instruction items, shown by sender handle and reason only.
- **Withheld:** counts by label (financial, hr, identity, health…).
- **Exposure:** sensitive values the assistant received. The target is 0, labelled a target until measured on the run.

## Build status

Done and tested on the sandbox mailbox (102 tests): request-bound proposals, the five checks, exact-message seal, owner-only approval, no-resend with a durable journal, `VERIFICATION_PENDING`/`UNVERIFIED`, separate MCP listener, receipts, owner console. Also done: the Direct-vs-Shielded comparison (measured). Remaining: rehearsal and the backup video. A live Gmail send is optional.

## Why it scores

- **Working product:** one request in the assistant, one approval, a verified send on the synthetic sandbox mailbox.
- **Problem insight:** executives hold sensitive records beside routine work, and their messages carry authority; vendor controls are self-audited and per assistant.
- **Depth:** the demo validates the core enforcement path, and the test suite checks the M0 invariants.
