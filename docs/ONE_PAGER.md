# Shield — one page

*Claude's read of the PRD, so we can confirm we're aligned before coding.*

## The idea in one sentence

A layer the user owns that sits around **everything** an AI assistant can reach (email, calendar, files, messages, browser, money, devices), so the model **sees only labels, never the real data, and can only ask; code decides what actually happens, a human approves the risky parts, and Shield checks the real world to prove it happened.**

## The problem

Assistants like Instinct, Muse and OpenClaw ask for access to almost everything. Anything they read (an email, an invite, a doc, a web page) can carry hidden instructions. An assistant with **private data + untrusted content + a way to act outward** will eventually be turned against its user (the "lethal trifecta"). Copilot, Gemini and ChatGPT have all been hijacked this way; OpenClaw deleted an inbox; Instinct emailed an investor unasked. Making the model resist doesn't work: 99% detection still loses. The more an assistant can reach, the worse it gets.

## The insight

Don't make the model smarter. **Take the dangerous things out of its hands, for every account:**

| The model never gets… | Instead it gets… |
|---|---|
| Real addresses, file contents, account numbers, PAN/keys | Handles: `CONTACT_1 · investor · NDA ✔`, `FILE_2 · projections · v3` |
| Hidden or instruction-like text | `[quarantined · SENDER_4]` |
| Raw send / pay / delete / share tools | `propose_*` tools. Code runs WHO · WHAT · POLICY · CONTENT · LOCK |
| Freedom to put links/images in outgoing text | Blocked (closes the EchoLeak leak channel) |
| A say in whether it worked | Code checks the real record (sent folder, statement, calendar) |

## Shielding assistants we can't sit in front of

| Mode | For | How |
|---|---|---|
| **Enforce** | Assistants that take connectors (Claude, ChatGPT, Cursor, MCP agents) | Assistant talks to Shield instead of the account. Full guarantees |
| **Enforce at the edge** | Agents on your laptop or in your browser | Local proxy / extension blocks unapproved destinations and leaks |
| **Contain** | Closed assistants with their own logins (Instinct, Muse) | Give them a Shield-managed mirror: filtered inbox, free/busy calendar, safe-files folder, capped virtual card |
| **Watch & verify** | Every account, always | Compare the account's own records with what you approved; alert and one-click revoke |

Restrict wherever we can; where we can't prevent, we shrink what's reachable; where we can't shrink, we watch and give a kill switch. We never claim more than that.

## What we build today (hackathon slice)

**Enforce mode, for email + files + calendar**, on a synthetic sandbox plus one real Gmail send. It's the slice that shows every guarantee end to end with a real agent using the tool.

```
"Send Priya the projections"
  → search(purpose=share_document)    model sees 3 handles, 0 sensitive values
  → propose_send_document(CONTACT_1, FILE_2)
  → WHO ✔ Priya Rao · WHAT ✔ Projections v3 · POLICY ✔ NDA · CONTENT ✔ · LOCK 🔒
  → approve on dashboard → Gmail sends → Shield re-reads it → ✅ VERIFIED
```

| Demo scene | Result | Proves |
|---|---|---|
| Direct vs Shielded, same task, same model | Exposure: many → 0 | Need-to-know works; task still done |
| Poisoned invite / white-on-white email | Quarantined | Cleaner |
| Unknown "investor" wants the data room | 🛑 BLOCKED (WHO) | Code picks recipients |
| Reply with a hidden image URL | 🛑 BLOCKED (CONTENT) | Leak channel closed |
| File swapped after approval | ❌ FAILED (LOCK) | Approval means exact bytes |
| "Did any AI see my cap table today?" | "No, withheld 2×" | Audit trail |

The other modes and sources are one roadmap slide at the close.

## Why it scores on the three judging criteria

- **Working product:** Claude, connected over MCP, does a real task; a real email lands with ✅ VERIFIED.
- **Problem insight:** the trifecta explains *why* every assistant gets hijacked, and why "access to everything" makes it worse.
- **Depth:** handles + deterministic checks + payload seal + read-back verification + a measured Direct-vs-Shielded comparison on 5 recreated attacks.

## Open points before coding

1. **Name.** Docs now say **Shield**, standalone. `team.json` still says "Axon Voice" with a phone-call one-liner, and the team is registered as "Axon". The team name can stay; the project title and one-liner should change to Shield.
2. **Time.** Code freeze is 7:00 PM. Build order: handles + broker → cleaner → guard (5 checks + seal) → sandbox executor + verifier → MCP server with Claude doing the Priya task → tests → minimal dashboard → one real Gmail send. Cut first if needed: 3-run harness, ngrok, calendar tools.
3. **Branch.** Judges read the default branch; this work is on `claude/focused-rubin-b43hc6` and must be merged before 7.
