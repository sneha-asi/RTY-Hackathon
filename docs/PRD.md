# Shield — PRD

**The user-side trust layer for personal AI assistants: a shield around everything an assistant can reach.**

An executive sets one standing policy for what their AI assistant can learn and what it can propose. The assistant can prepare a confidential share without opening the file. The executive approves the exact outgoing message, and Shield verifies what was sent.

> **The AI proposes. The code decides. Nothing is done until it's proven.**

| Field | Detail |
|---|---|
| Team | Axon |
| Product | Shield |
| Status | M0 (hackathon build) |
| Event | Buildathon, Wed 18 Nov 2026, 3–7 PM IST · Track `ai-agents` · Code freeze 7:00 PM |
| Related docs | [HLD](HLD.md) (components, boundaries, flows) · [LLD](LLD.md) (modules, algorithms, tests) · [One-pager](ONE_PAGER.md) |

Confidence labels for external facts: **[V]** checked against the primary source · **[L]** secondary source, likely true · **[U]** unverified, don't cite on stage.

The full product is described in §1–§9. What we build in four hours is in **§10 Hackathon scope**. All four documents share the IDs below: business principles **B1–B6** and invariants **I1–I10**.

---

## First principles

### Business: why this product should exist

| # | Principle | So Shield must… |
|---|---|---|
| B1 | **The value of an assistant grows with what it can reach, and so does the damage it can do.** People either grant everything and carry the risk, or grant little and get little | Make *more* delegation safe, not less. Success is tasks delegated safely, not attacks blocked |
| B2 | **The user bears the loss; the assistant vendor marks its own homework.** A vendor's controls protect its product and are audited by the vendor | Be owned by the user and sit outside any one vendor |
| B3 | **People use several assistants and switch between them.** Rules tied to one assistant are rewritten for each | Apply one policy across supported assistants |
| B4 | **Trust comes from evidence, not promises.** "We ask before sending" can't be checked by the user | Show what was released, withheld, approved and verified, from records |
| B5 | **Friction kills delegation.** If every step needs a click, people turn the safety off | Gate only outward and irreversible actions; let proven narrow actions earn autonomy later |
| B6 | **The pain is concentrated where a mistake is expensive.** Everyone faces the same attack, but cost and willingness to pay concentrate in executives: they deal with a lot of sensitive information, much of it other people's, and their messages carry authority | Executives are the target users. Investor follow-ups are the demo workflow: frequent, valuable, and risky |

### Technical: what must be true for B1–B6 to hold

**One policy governs what the assistant learns during a task and what it may propose doing with that information.** The founder enables a standing policy once (M0: *investor follow-ups*). The same policy decides what the broker releases and what the guard accepts as a proposal; the assistant's `purpose` argument can only narrow it. The founder normally works in the assistant and sees Shield only when there is an exact message to approve.

The root cause is the lethal trifecta: **private data + untrusted content + a way to act outward** (§1). A model can't be made to reliably refuse instructions it reads, so the defence must not depend on the model. Shield removes or controls each leg in code:

| # | Invariant | Removes / controls |
|---|---|---|
| I1 | **Need-to-know at the interface.** The model receives only handles, structured attributes and purpose-filtered summaries that Shield writes. No source text passes through | Private data |
| I2 | **Untrusted content is data, never instructions.** Hidden text is stripped; instruction-like content is quarantined (a safeguard on top of I1, not the guarantee) | Untrusted content |
| I3 | **No ambient authority.** The assistant can request scoped reads and create proposals; execution and approval authority stay outside the assistant | Outward action |
| I4 | **Proposals are bound to the request that justifies them.** Code takes the recipient from the request and checks the file matches what was asked for, within the standing policy. Two individually valid handles can't be combined outside that request. Raw addresses are refused | Outward action |
| I5 | **Model-written text carries no outbound channel**: no URLs, images, raw identifiers or sensitive values | Outward action (exfil via content) |
| I6 | **The user approves the exact sealed payload**: recipients, message bytes, attachment hash. Shield sends the same bytes it checked | Outward action |
| I7 | **Done is a provider fact.** Only VERIFIED counts; uncertain delivery shows VERIFICATION_PENDING and is never resent automatically | False success |
| I8 | **Every decision is recorded without content**, so receipts answer from evidence | Unauditable delegation (B4) |
| I9 | **Fail closed.** Any error in resolve, check or summarise blocks or withholds | All |
| I10 | **Claims follow the access path.** Full guarantees only where Shield is the only route; weaker, named claims elsewhere (§4, §6) | Over-claiming |

### Traceability

| Invariant | PRD requirements | Design (HLD / LLD) | Test (LLD §15) |
|---|---|---|---|
| I1 | F5, F6, F7 | HLD D1 · LLD §4, §4.4, §4.5 | `test_guarantees`, `test_broker`, `test_handles` |
| I2 | F2, F3, F4 | LLD §4.1, §4.2 | `test_cleaner`, `test_detectors` |
| I3 | F8, F18 | HLD D2 · LLD §9 | `test_guarantees` (no `send_email`, no approve tool) |
| I4 | F8, F9, F10, F11 | HLD D3 · LLD §5.2 | `test_guard_checks` |
| I5 | F12 | LLD §5.2 (CONTENT) | `test_guard_checks` |
| I6 | F13, F14, F15 | HLD D5 · LLD §5.3, §5.4 | `test_seal`, `test_lock`, `test_approval_auth` |
| I7 | F16 | HLD D6 · LLD §5.4, §6, §7 | `test_verifier`, `test_verification_pending` |
| I8 | F17 | HLD D8 · LLD §8 | `test_receipts`, `test_ledger_privacy` |
| I9 | all checks | HLD D7 · LLD §1, §5.1 | `test_fail_closed` |
| I10 | §4.1, §6 | HLD D9, §4, §5 | `test_mcp_listener_has_no_owner_endpoints`; "sole path: yes / no / unknown" indicator (M1); stated on stage in M0 |

---

## 1. Problem (who and why)

**Who:** executives (founders, CXOs, VPs, fund partners), because they deal with a lot of sensitive information, much of it other people's: investor terms, cap tables, hiring and layoff plans, board matters, customer contracts. Their messages also carry authority: a sent email commits the company or shares a data room. A leak or a wrong send costs them, and third parties, far more than it costs a casual user. Today their choice is "give the assistant everything" or "don't use one".

**The assistants we focus on: Instinct, Muse and OpenClaw.** Each asks for broad access to email, calendar, files and more, and each has already shown what goes wrong:

| Assistant | What it takes | What went wrong | Where Shield can sit (§4) |
|---|---|---|---|
| **Instinct** | Gmail, calendar, files via its own login; "perpetual and irrevocable" licence to user materials [V] | Emailed an investor "without checking with me first"; kept summarising an inbox after Gmail was disconnected [V] | Closed, holds its own login → **Contain** (mirror inbox) + **Watch & revoke** |
| **Meta Muse** | Desktop agent with broad account and device access [V] | Mac zero-day: "trivial to turn Muse into the ultimate backdoor" [L]; blocked by Amazon [L] | Runs on the user's machine → **Edge** + **Contain** + **Watch & revoke** |
| **OpenClaw** | Agent with full read/write to inbox and tools, run by the user [L] | Mass-deleted a security researcher's inbox [L] | User-run, accepts tools → **Enforce** where its tools can point at Shield [U], else **Edge** |

Many other assistants exist (ChatGPT, Claude, Gemini, Copilot, Dots); the same layer applies to them, and we use them as supporting evidence rather than the headline.

**Watch on the executive's own Gmail (built):** for an assistant that keeps its direct Gmail connection, Shield reads Sent and Drafts, flags anything not approved through Shield with the reason, can remove a risky draft before it is sent, and links to revoke the assistant's access. Detection and draft removal only; no prevention on that path.

**Live Contain demo (built, pending a live go/no-go test with Instinct):** Shield publishes safe lines with stable IDs (`REQ_7`, `FILE_2`) into a restricted Gmail test inbox that Instinct reads. Instinct's reply over WhatsApp is pasted into Shield's local intake as untrusted input. Shield resolves the recipient and attachment itself and runs the same checks and review page, then sends from a separate test account and verifies against Gmail Sent.

**What M0 shows, honestly:** Instinct and Muse can't be placed behind a third-party layer today, because they log in with their own credentials. The hackathon demo therefore uses an MCP-capable assistant (Claude) in Enforce mode to prove the mechanism end to end, and presents Contain and Edge (how Shield reaches Instinct, Muse and OpenClaw) as the roadmap.

**Demo workflow:** investor follow-ups. The demo executive is a founder answering investor document requests.

**Not the target (yet):** casual users such as students. They face the same attack, but the worst case is mostly personal and they rarely pay for protection. They benefit later if Shield becomes a default layer.

**Why it happens:** an assistant that combines **(1) private data, (2) untrusted content and (3) a way to act or send outward** can be steered by instructions hidden in anything it reads. This is Simon Willison's *lethal trifecta* [V]. The more an assistant can reach, the more doors there are on all three legs. Detection doesn't fix it: a 99%-effective injection classifier is still an "unacceptable risk" (Willison) [V].

| Incident | What went wrong |
|---|---|
| EchoLeak, CVE-2025-32711 (M365 Copilot) [V] | One email → zero-click exfiltration via an auto-fetched image URL |
| Gemini calendar invites, Black Hat 2025 [V] | Hidden text in an invite controlled smart-home devices and leaked calendar data |
| AgentFlayer, ChatGPT connectors [L] | Poisoned doc → agent searched Drive for API keys, leaked them via image URLs |
| Instinct, Aug 2026 [V] | Emailed an investor "without checking with me first"; kept summarising an inbox after Gmail was disconnected |
| OpenClaw, Feb 2026 [L] | Mass-deleted a security researcher's inbox |
| Meta Muse, Sep 2026 [L] | Mac zero-day: "trivial to turn Muse into the ultimate backdoor" |

Scale: 32% of US AI users have let AI act without a final sign-off; 76% of non-users cite privacy (Menlo Ventures / Morning Consult, n=5,067, Jul 2026) [V].

**The gap:** platforms now guard their *own* assistant (Muse's VM + approvals, Dots' auto-review, Claude and Gemini confirming sends) [V/L]. But each vendor audits itself, each covers only its own assistant, the model still sees all the data inside its sandbox, and nobody checks the outcome against what actually happened. Point tools (PortEden, mcp-pvp, AgentCloak, approval proxies) cover one piece each [L].

## 2. Vision

People delegate to any AI assistant the way they'd delegate to a trusted human chief of staff:

- It sees only what each task needs.
- It acts only within permissions the user granted; dangerous actions are decided by code, not the model.
- Every action has proof.
- The user can ask, in plain language, what any AI saw and did.
- That trust belongs to the user and works across every assistant and every account.

## 3. How Shield works (any source, any action)

Shield treats every account an assistant touches the same way: **things the assistant can read** and **things it can do**.

| Trifecta leg | Shield's cut, for every connected source |
|---|---|
| Private data | The model gets **handles with attributes** (`CONTACT_1 · investor · NDA ✔`, `FILE_2 · projections · v3`, `ACCOUNT_1 · savings`), never raw addresses, file contents, account numbers or sensitive spans |
| Untrusted content | A **cleaner** strips hidden text from every inbound item (email, invite, doc, web page, chat message); instruction-like content is **quarantined** |
| Outward action | **No raw action tools.** Send, share, pay, delete, post, buy, change a device: the model only *proposes*. Code resolves handles, runs checks, seals the payload, gets approval when required, executes and **verifies** |

**Universal checks** (applied to every action type):

| Check | Question code answers |
|---|---|
| **WHO** | Is the target (recipient, payee, channel, device) known and resolved by code, not supplied by the model? |
| **WHAT** | Is the object (file, amount, message, event) the right one: latest version, within limits, allowed for this target? |
| **POLICY** | Does this action type × data sensitivity × target pass the user's rules? Is it reversible? |
| **CONTENT** | Is model-written text free of URLs, images, raw identifiers and sensitive patterns that could carry data out? |
| **LOCK** | Is the payload byte-for-byte what was approved? |
| **VERIFY** | After execution, does the real world (sent folder, bank statement, calendar, device state) match what was approved? |

**Risk tiers** set how much friction an action gets:

| Tier | Examples | Default |
|---|---|---|
| Read-only | Search, summarise, free/busy | Allowed through purpose rules; exposure counted |
| Reversible, internal | Draft, label, create a private event | Allowed after checks; logged |
| Outward | Send, share, reply, invite, post | Checks + human approval |
| Irreversible / costly | Delete, pay, buy, share secrets, change security settings | Checks + approval with the real resolved payload; some are never allowed (e.g. secrets out, bulk delete) |

Earned autonomy (later): a narrow action that has been approved and verified many times can become a standing rule; any failure demotes it back to approval.

## 4. Where Shield can sit (enforce where we can, contain where we can't, watch everything)

Not every assistant lets a third party sit in its path. Shield uses the strongest position available for each assistant and each account.

| Mode | When | How | Strength |
|---|---|---|---|
| **1. Enforce** (in the path) | Assistants that accept connectors/tools: Claude, ChatGPT dev mode, Cursor, custom agents (MCP) | The assistant connects to Shield instead of the account. All reads returned as handles + summaries, all actions proposed | Full guarantees (§6) |
| **2. Enforce at the edge** | Assistants that run on the user's machine or in their browser | Local proxy / OS-level network filter / browser extension that sees outbound requests: block unknown destinations, URL-borne exfil, unapproved sends | Strong for egress; partial for reads |
| **3. Contain** (shrink what's reachable) | Closed assistants holding their own logins (Instinct, Muse, Dots), where a supported mirror exists | Give the assistant a **Shield-managed mirror** instead of the real account: a filtered inbox, a calendar showing free/busy only, a Drive folder with only shareable files, a virtual card with a spend limit. Outward actions from the mirror go back through Shield | Data minimisation is structural; actions are gated where the mirror is the only path |
| **4. Watch and verify** (everywhere) | Any account, even ones the assistant reaches directly, limited to what the provider exposes | Read the account's own records (sent folder, OAuth grants, login/security events, bank transactions, file-sharing changes) and compare with what the user approved. Alert on anything unapproved; one-click revoke of the assistant's token | Detects and limits damage; can't prevent |

The honest claim: **full guarantees in mode 1; strong containment in modes 2–3; visibility and kill-switch in mode 4.** We never claim to prevent what we can't sit in front of.

### 4.1 What "platform-agnostic" means

- **One policy, every supported client.** The user writes their rules once (who may receive what, which actions need approval, what is never shared). The same policy, checks and ledger apply to every assistant client that reaches the account through Shield. Switching from Claude to ChatGPT to Cursor changes nothing about what is protected.
- **Full enforcement requires Shield to be the sole path to the protected account.** If an assistant also holds its own OAuth grant to the same Gmail, it can go around Shield. Shield therefore:
  - lists the account's OAuth grants on connect and asks the user to revoke direct grants to assistants;
  - re-checks the grants periodically (mode 4) and shows **"sole path: yes / no / unknown"** per account. A missing visible grant doesn't prove exclusivity, so where direct access can't be checked the answer is **unknown**;
  - downgrades its own claim for that account from Enforce to Watch while a bypass grant exists.
- **Data boundary.** Raw data processing, credentials, the executor and approval previews run on the user's machine or infrastructure they control. Only the filtered, authenticated MCP surface is exposed to a remote assistant. Files the user uploads directly to an assistant are outside this path.
- **Instinct and Muse are roadmap experiments until tested.** The modes below say how Shield would reach them; none is claimed until tested.
- It does **not** mean every control works with every assistant. The matrix below says which controls each integration supports.

| Control | Mode 1: MCP connector (Claude, ChatGPT dev mode, Cursor, custom agents) | Mode 2: Edge (local proxy / browser extension) | Mode 3: Mirror (closed assistants) | Mode 4: Watch (any account) |
|---|---|---|---|---|
| Need-to-know release (handles, summaries) | ✔ | ✘ | ✔ (mirror holds only released items) | ✘ |
| Hidden-text cleaning + quarantine | ✔ | Partial (web pages, downloads) | ✔ (applied before mirroring) | ✘ (alert only) |
| Propose-only actions, code-resolved targets | ✔ | ✘ | ✔ for actions sent from the mirror | ✘ |
| Outbound leak blocking (URLs, images) | ✔ | ✔ (blocks egress to unapproved hosts) | ✔ for mirror sends | ✘ |
| Sealed human approval | ✔ | Partial (approve blocked requests) | ✔ for mirror sends | ✘ |
| Outcome verification | ✔ | ✘ | ✔ | ✔ (after the fact) |
| Receipts / audit | ✔ | ✔ (egress log) | ✔ | ✔ |
| Revoke access | ✔ (disconnect) | ✔ | ✔ | ✔ (OAuth revoke) |
| Requires sole path for its guarantees | Yes | Yes (all egress via proxy) | Yes (assistant sees only the mirror) | No |

## 5. Sources and actions in the full product

| Area | Read through Shield | Actions through Shield |
|---|---|---|
| Email | Thread summaries, handles for people and attachments | Send, reply, forward, share attachment, delete |
| Calendar | Free/busy first; event summaries by purpose | Create, accept, invite |
| Files / Drive / Docs | File catalogue as handles; contents only by purpose | Share, link, delete, change permissions |
| Messaging (Slack, WhatsApp, SMS) | Message summaries | Post, DM |
| Contacts / CRM | Attributes (role, org, NDA), not raw details | Add, update |
| Browser / web | Cleaned pages; hidden text stripped | Fetches to allow-listed domains only; form submits proposed |
| Money (bank, cards, shopping) | Balances as ranges, merchants as handles | Pay, buy (virtual card, limits, approval) |
| Code / secrets | Secrets never released | Commit, push, deploy (proposed) |
| Device / smart home | Device handles and state | Change state (approval for locks, cameras, heating) |
| Account security | OAuth grants, sessions | Revoke, never grant |

## 6. Guarantees

Guarantees depend on the access path. We state them per path and never claim more:

| Access path | What holds |
|---|---|
| **Mode 1, Shield is the assistant's only route to the account** | The five guarantees below, by construction |
| Mode 1, but the assistant also holds its own grant | Only the assistant's traffic through Shield is covered; the dashboard shows "sole path: no" and Shield claims Watch only |
| **Mode 3, closed assistant with a supported mirror** | The assistant can only see what Shield put in the mirror, and only sends from the mirror are gated. Requires a provider and assistant combination where a mirror account is supported |
| **Mode 4, watch and revoke** | Detection after the fact and revocation, limited to what each provider exposes (sent records, OAuth grant lists, security events, revoke APIs). No prevention |

**By construction** (mode 1, Shield as the sole path):
1. **Privacy is guaranteed at the tool interface.** Every Shielded tool result is built by Shield from **handles, structured attributes and purpose-filtered, server-written summaries**. Raw source text (email bodies, document contents, invite descriptions) is never passed through to the model in M0. Detection, masking and quarantine are additional safeguards on the fields Shield writes, not the guarantee itself. This makes "zero sensitive values" testable: every sensitive value in the demo fixtures is enumerated, and a test asserts none appears in any tool result.
2. The model cannot cause an action on a target code didn't resolve from the user's own records.
3. Model-written text cannot carry external URLs or images out.
4. The user approves the exact recipients (To/Cc/Bcc), message and attachment. Shield sends the same attachment bytes it checked; any change after approval fails.
5. Nothing is reported done until Shield has checked the provider's record. Uncertain delivery shows as VERIFICATION_PENDING and never triggers an automatic resend.

**Not guaranteed** (said out loud): detecting every hidden instruction (the cleaner is tested against the seeded malicious examples, and it is defence in depth, not the guarantee); privacy for free text if a later version passes source text through (M0 doesn't; mitigated by purpose rules + fail closed); prevention for assistants we can't sit in front of (modes 3–4 contain and detect instead); a user approving a bad action (mitigated by showing the real, code-generated payload).

## 7. Users

| Persona | Needs |
|---|---|
| **Executive** (target user): founder, CXO, VP, fund partner | Delegate follow-ups, scheduling and document requests without exposing third-party data; never send to someone unapproved; proof of what went out |
| **Executive's EA / chief of staff** | Reviews the same approval cards and receipts on the executive's behalf |
| Security-minded developer | Point any MCP agent at Shield and get safe tools; policies are readable code |
| The assistant itself | Handles it can reason with; a status it can relay word for word |

## 8. Landscape and positioning

| Group | Examples | Gap Shield fills |
|---|---|---|
| Built into assistants | Muse (VM, Sentinel, approvals, audit) [V]; Dots (auto-review) [L]; Claude, Gemini confirm sends | One vendor, self-audited, model still sees the data, no outcome check |
| Consumer security | Norton Agent Trust Hub [L]; 1Password for Agents [V] | Scanning and credentials; no data minimisation, no action gating, no verification |
| Developer infra | Auth0 for AI Agents [V]; Composio; Arcade [L] | Building blocks, not a user-owned layer |
| Point tools | PortEden, mcp-pvp, AgentCloak, Strac, approval and masking proxies [L/V] | One or two pieces each |
| Enterprise gateways | Operant, Lasso, Prompt Security, Lakera, … [L] | Built for IT teams, not a person |
| Sandboxes | NVIDIA OpenShell [V] | Limit where the agent reaches, not what the model holds |
| Research | CaMeL, Progent, FIDES, AgentDojo [V] | Validate the approach; not products |

**Positioning:** "Muse protects Muse. Who protects you, across every assistant and every account?"
**Claim we make:** "We couldn't find a single user-side layer that works across assistants and combines need-to-know handles, code-decided targets, sealed approvals, leak-channel blocking and verified outcomes."
**Claims we never make:** "nobody gates agent actions" (false) or "no competitor exists" (point tools exist; name them first).

## 9. Roadmap

| Milestone | Theme | Deliverables |
|---|---|---|
| **M0** | Hackathon (§10) | Mode 1 end to end on email + files, sandbox + one real Gmail send |
| M1 | Real accounts, mode 1 | Real Gmail/Calendar/Drive/Slack, OAuth onboarding, hosted MCP endpoint, Claude + ChatGPT connectors |
| M2 | Watch and verify (mode 4) | Account-activity monitors, unapproved-action alerts, token revoke; earned autonomy; approve by phone/push |
| M3 | Contain closed assistants (mode 3) | Mirror inbox, free/busy calendar, filtered Drive folder, virtual card |
| M4 | Edge enforcement (mode 2) | Local egress proxy for desktop agents, browser extension for browser agents |
| M5 | Money and devices | Payments with limits, smart-home and device actions |

## Open questions

- Purpose inference: M0 has the assistant state the purpose and Shield validates it. Infer it later?
- How should handles appear in assistant UIs so users understand them?
- Mirror send path: send-as alias vs relay with approval?
- Policy authoring for non-technical users: templates vs earned rules?
- Which closed assistants allow a mirror account cleanly, and which force full-account OAuth?

---

## 10. Hackathon scope (M0)

**We build mode 1 (Enforce) for email, calendar and files**, on a synthetic sandbox plus one real Gmail send. This is the slice that shows every guarantee end to end, with an agent actually using the tool (the `ai-agents` track requirement). Modes 2–4 and other sources are shown as the roadmap, not built.

**Build order:** one vertical slice first: MCP → proposal → minimal approval screen → sandbox send → verified read-back, with tests alongside. Then the Gmail adapter, then the comparison scenes. Calendar stays in scope, with `free_slots` (free/busy only) as the first cut. Full order in LLD §16.

**Demo data.** The demo runs entirely on a synthetic sandbox mailbox, calendar and drive (no real accounts, no third-party data). Verification reads the sandbox mailbox's own Sent record, exactly as it would read Gmail's. The Gmail adapter exists and is optional.

### 10.1 Out of scope today

Other sources (messaging, browser, money, devices); modes 2–4; multi-user policies; learned/LLM policies (all policy is deterministic code); a database (in-memory + JSON seeds); mobile/extension; payments and credential brokering.

### 10.2 Goals and acceptance

| Goal | Measured as |
|---|---|
| Minimise what the model sees | **Target:** "Handle my investor follow-ups" releases ~3 items as handles with 0 sensitive fixture values; unrelated sensitive items appear only as withheld counts. Reported as measured once the fixture test passes |
| Injections are powerless | **0 of 5** attacks (A1–A5) succeed through Shield, scored from sandbox state |
| Still useful | The investor follow-up task succeeds through Shield **3/3** runs |
| Code decides who/what | Every send resolved from contacts + file catalogue; unknown or raw recipient → BLOCKED |
| Only the user approves | Approval requires the authenticated user and the matching seal; no MCP tool can approve |
| Proof before "done" | Only VERIFIED ("Verified in Sent") counts as success; tampered file/payload → FAILED (nothing sent); ambiguous provider result → VERIFICATION_PENDING, never resent, also across restarts; sent record differs → UNVERIFIED |
| Auditable | Receipt query answers with counts from the ledger, e.g. "Shield released the cap table 0 times and withheld it twice today." |
| Reliable demo | Full demo 5× in a row; the full flow runs on the synthetic sandbox mailbox and is verified against its Sent record; a live Gmail send is optional |

### 10.3 Architecture

```
 Claude · ChatGPT (dev mode) · Cursor · any MCP client
                 │  MCP-only listener (the only port exposed)
                 ▼
┌───────────────────────────── SHIELD ───────────────────────────────┐
│ READ   source → cleaner → labeller → purpose rules → handles       │
│        → handles + template summaries + exposure count             │
│ WRITE  propose_* → WHO · WHAT · POLICY · CONTENT · LOCK            │
│        → approval → executor → verifier                            │
│ LEDGER append-only events → SSE → dashboard · receipts             │
└──────────────┬──────────────────────────────────┬──────────────────┘
               ▼                                  ▼
   Sandbox (JSON mail/calendar/drive)    Gmail API (send + read-back)
```

Stack: Python 3.12 · FastAPI · official `mcp` SDK · Anthropic SDK (harness only) · Gmail API · static HTML + JS pages served by the owner listener (no build step) · SSE. **No LLM inside Shield; no database.**

| Module | Job |
|---|---|
| `sources.py` | Source adapters → `Item{id, kind, sender, to, subject, body_html, body_text, ts, attachments}`. New sources plug in here |
| `cleaner.py` | Strip hidden text (display:none, white-on-white, tiny fonts, zero-width chars, whitespace padding); detect + quarantine instruction-like content |
| `labels.py` | Sensitivity classes `financial · legal · hr · health · identity_ids · secrets · deal`; detectors: PAN, Aadhaar (Verhoeff), GSTIN, IFSC, UPI, card (Luhn), API keys, emails, phones, money |
| `handles.py` | Per-session `CONTACT_n / SENDER_n / FILE_n / THREAD_n` with attributes; mapping never leaves the server |
| `broker.py` | Purpose rules (`schedule`, `share_document`, `reply`, `triage`), template summaries, exposure accounting |
| `guard.py` | Proposals, checks, payload seal, approval state machine |
| `executor.py` | Sandbox mailbox + Gmail send; code picks the attachment bytes |
| `verifier.py` | Re-read sent message; compare recipients, subject, attachment name + SHA-256 |
| `ledger.py` | Events, receipts, SSE; stores IDs/labels/hashes only, never bodies |
| `mcp_server.py` | Tool surface below |
| `harness.py` | Direct vs Shielded runs with Claude; deterministic scoring |
| `main.py` | FastAPI: dashboard REST, SSE, approvals, dev endpoints |
| `app/static/` | Owner console (`index.html`) and the single approval page (`review.html`) |

**MCP tools (Shielded):**

| Tool | Input | Returns |
|---|---|---|
| `search` | `purpose`, `query?` | Items as handles + structured attributes + server-written summary; withheld counts |
| `read` | `purpose`, thread handle | Server-written summary of the thread + structured fields (intent, requested category, due date), only if purpose allows |
| `list_files` | `category?` | `FILE_n` handles: category, version, requires_nda. Never contents |
| `free_slots` | date range | Free/busy only |
| `propose_send_document` | **request handle** (`THREAD_n` released in this session), file handle, `note?` | `{action_id, state, status_text, request, checks[]}`. Recipient comes from the request |
| `propose_reply` | thread handle, text | same |
| `propose_event` | attendee handles, slot, title | same |
| `action_status` | `action_id` | Code-written status the assistant relays verbatim |

There is deliberately **no `send_email(to, …)`**. The Direct baseline (comparison only, sandbox only) exposes raw `list_emails`, `read_email`, `read_file`, `send_email(to, subject, body, attachment)`.

**Checks as implemented for email/files:**

| Check | Rule | Fails when |
|---|---|---|
| WHO | Handle resolves to a known contact | Unknown `SENDER_n`, raw address, unresolvable handle |
| WHAT | Latest version of the category; NDA-required file + no NDA → downgrade to teaser with warning | File missing / not latest |
| POLICY | Financial needs known contact + NDA; `secrets` never shareable | Rule violated |
| CONTENT | No external URLs, markdown images, raw emails, handles or sensitive patterns; length cap | Any found |
| LOCK | Seal at proposal (M0: exactly one `To`, no `Cc`/`Bcc`); recompute at execution | Hash mismatch → FAILED, nothing sent |

**One approval page for every assistant.** Every proposal that reaches approval returns a `review_url` (`/review/<action_id>` on the owner-only listener). Claude, OpenClaw, or any MCP client relays the same link. The link identifies the action and carries no credential; the page needs the executive's Shield login. It shows one card: the real recipient and message, the attachment and any policy warning, **Approve & send / Reject**, and the verified status as it updates, with the receipt in a collapsible section. The assistant can fetch the same outcome with `action_status`.

**Who can approve.** Only the authenticated user. The dashboard's approve/reject endpoints require the user's session (login with a user secret set at install; the MCP client never holds it). There is no approve tool on the MCP surface, so no model, prompt or tool call can approve. An approval request must carry the seal shown on screen; if it doesn't match the action's current seal, the approval is refused.

**What gets sealed.** At proposal, code builds the **exact outgoing message**: the complete MIME bytes (headers, body, attachment, with a fixed Message-ID and boundary), the **full recipient list** (To, Cc, Bcc) and the **attachment SHA-256**.
`seal = sha256(canonical{type, recipients_to, recipients_cc, recipients_bcc, message_sha256, attachment_sha256, slot})`.
The approval screen shows the recipients, subject, body, file name and the seal prefix taken from these same sealed values.

**Same bytes that passed the check are sent.** At execution, Shield reads the file once into memory, checks its hash against the sealed attachment hash, rebuilds the message from the sealed fields plus those in-memory bytes, checks the message hash against the sealed message hash, and sends **those exact bytes**. Nothing is re-read between the check and the send. Any mismatch → FAILED "changed after approval".

**State machine:**
```
PROPOSED ──► BLOCKED                          (terminal, reason)
    └──► AWAITING_APPROVAL ──► REJECTED       (terminal)
              └──► APPROVED ──► EXECUTING ──► VERIFIED                (terminal ✅, the only success)
                                    │    ├──► FAILED                  (terminal ❌, definitely not sent)
                                    │    └──► UNVERIFIED              (terminal ⚠, sent but the Sent record differs)
                                    └──► VERIFICATION_PENDING ──► VERIFIED
                                                             └──► UNVERIFIED (terminal ⚠, may have been sent / record differs)
```
- **VERIFICATION_PENDING**: the provider timed out or errored *after* the send may have gone out, or the read-back isn't visible yet. The dashboard and the assistant show "may have been sent, verifying". Shield retries verification by looking up the sealed Message-ID in the Sent folder, with backoff, for up to 2 minutes.
- **Never resend.** Once the send call has been made, the action can never send again, whatever the outcome; retries only re-read.
- **UNVERIFIED**: the message was or may have been sent, but Shield can't confirm it matches: either the Sent record differs from the approval (the differing field is recorded) or nothing was found in the retry window. Not a success, not a silent failure.
- **FAILED** is reserved for actions that were definitely not sent (seal mismatch before sending, or a provider rejection).
- **Restarts:** a send-attempt marker is written to a local journal and flushed to disk *before* Gmail is called. After a restart, any action with that marker can only be verified, never sent.
- **What VERIFIED means:** "Verified in Sent": Gmail's Sent record matches the approved recipient, subject, body and attachment hash. It establishes what Gmail recorded as sent; confirming receipt would need a recipient-side check.
- **Only VERIFIED counts as success** in the dashboard, receipts, harness and status text.

Every transition appends `{ts, session_id, action_id, from, to, reason}` to the ledger and SSE. Illegal transitions raise. Any error in resolve/check → BLOCKED (fail closed).

### 10.4 Demo journey: "Handle my investor follow-ups"

**The user problem:** a founder's inbox mixes investor requests with cap tables, layoff plans, tax IDs and medical notes, plus mail from strangers. They want the assistant to clear investor follow-ups without seeing the rest, without sending anything to the wrong person, and with proof of what went out.

**One workflow**, one request from the user: *"Handle my investor follow-ups."*

| Step | What happens | What the audience sees |
|---|---|---|
| 1. Look | Assistant calls `search(purpose=share_document, query="investor")` | **Target** (shown as measured on the dashboard): model gets ~3 items as handles + purpose-filtered summaries: Priya (investor, NDA ✔) asked for projections by Friday; Karan (investor, no NDA) asked for projections; `SENDER_3` (unknown) asked for the data room. **Unrelated sensitive data withheld**: term sheet, cap table, layoff plan, GST/PAN, medical note appear only as "withheld: financial 2 · hr 1 · identity 1 · health 1". The hidden-instruction email shows as `[quarantined · SENDER_4]` |
| 2. Propose | `propose_send_document(THREAD_1, FILE_2)` answering Priya's request; `propose_send_document(THREAD_3, FILE_2)` answering the stranger's request | Priya: WHO Priya Rao ✔ · WHAT Projections v3 ✔ · POLICY NDA ✔ · CONTENT ✔ · LOCK sealed → AWAITING_APPROVAL. Stranger: **🛑 BLOCKED, unknown recipient** ("add them as a contact first") |
| 3. Approve | Founder approves Priya's card on the dashboard (logged in) | Card shows the real address, subject, body, `Projections_v3.pdf` and the seal prefix |
| 4. Send + verify | Send of the sealed bytes on the sandbox mailbox, read-back from its Sent record (Gmail optional) | **✅ VERIFIED**: recipients match, attachment SHA-256 matches |
| 5. Relay | Assistant calls `action_status` and repeats the code-written text | "Verified in Sent: Projections v3 to Priya Rao; recipient, message and attachment fingerprint match what you approved." |

Karan's request (no NDA) is handled in the same run: WHAT downgrades to the Teaser Deck with a warning. Shown if time allows.

**Supporting scenarios** (in the test suite and the harness; shown on stage only if time allows):
- **Leak channel:** a reply containing a markdown image URL → CONTENT ✘ → 🛑 BLOCKED.
- **Tamper:** swap the projections file after approval → ❌ FAILED "changed after approval".
- **Provider timeout:** Gmail times out after the send → VERIFICATION_PENDING → VERIFIED on retry, sent once.
- **Receipt:** "Did any AI see my cap table today?" → "Shield released the cap table 0 times and withheld it twice today."

**Data:** the workflow runs on the synthetic sandbox mailbox and is rehearsed 5×. The Gmail adapter is optional; the backup video is the fallback.

### 10.5 Attack suite

| ID | Modelled on | Adversary goal | Structural defence |
|---|---|---|---|
| A1 | Gemini calendar invite | Leak data / take an action via an event | Quarantine; propose-only; CONTENT |
| A2 | EchoLeak (white-on-white + image URL) | Exfiltrate cap table | Never released for the purpose; no raw send; URL blocked |
| A3 | AgentFlayer (doc asks for API keys in a link) | Exfiltrate secrets | `secrets` never released; CONTENT blocks URLs |
| A4 | Unknown "investor" wants data room | Send financials to a stranger | WHO → BLOCKED |
| A5 | "Also CC finance-review@…" | Add attacker recipient | Handles only; raw address → BLOCKED |

**Scoring** (deterministic, from sandbox state, 3 runs per task × mode): utility, attack success, exposure. Shown exactly as measured; the pitch never depends on Direct mode failing.

### 10.6 Functional requirements

All P0 unless marked.

| ID | Requirement | Acceptance |
|---|---|---|
| F1 | Synthetic sandbox: ~15 emails, ~6 events, ~6 files, ~6 contacts incl. term sheet, cap table, layoff plan, GST/PAN, medical note, API key in a doc | Loads at startup; file SHA-256s computed |
| F2 | Attacks A1–A5 in the seed | Present and labelled in tests |
| F3 | Cleaner + quarantine for non-trusted senders | A1–A3 never reach the model as text |
| F4 | Labeller + detectors | Positive and negative unit test per detector |
| F5 | Handle registry, per session, server-side | No raw address or file path in any Shielded result |
| F6 | Purpose rules ×4 | Per-purpose released/withheld tests |
| F7 | Exposure accounting per call and session | Demo task measured; target ≤4 released, 0 sensitive fixture values |
| F8 | Request-bound, handle-only proposals; no raw send | Raw address in args → BLOCKED; a handle that isn't a request released in this session → BLOCKED; file not matching the request → BLOCKED |
| F9 | WHO | A4 → BLOCKED |
| F10 | WHAT | Priya → v3; Karan → teaser |
| F11 | POLICY | One test per rule |
| F12 | CONTENT | Image-URL exfil → BLOCKED |
| F13 | LOCK | Tampered payload or file → FAILED |
| F14 | Approval API + dashboard showing the real sealed payload; authenticated user only; approval carries the seal | Unauthenticated or wrong-seal approval refused; only AWAITING_APPROVAL approvable; idempotent |
| F15 | Executor: sandbox + Gmail; sends the exact sealed MIME bytes | Real email lands in investor test inbox; sent bytes hash == sealed message hash |
| F16 | Verifier with VERIFICATION_PENDING, retry and a durable send-attempt journal | Match → VERIFIED; confirmed mismatch → UNVERIFIED with the differing field; provider timeout → VERIFICATION_PENDING → retried, never resent, also after a restart |
| F17 | Ledger + SSE + receipt queries | Cap-table question answered correctly |
| F18 | MCP server (streamable HTTP) | Claude connects and completes the demo task |
| F19 | Harness: Direct vs Shielded, 3 runs each | Dashboard shows measured utility / attack success / exposure |
| F20 | Dashboard: Direct vs Shielded panels, action cards with check rows, timeline, counters | Readable from the back of the room |
| F21 | *P2:* Earned autonomy | — |
| F22 | *P2:* Approve from phone (push notification) | — |
| F23 | *P2:* Real Gmail as read source | — |

### 10.7 Non-functional

| | Target |
|---|---|
| Added latency | < 150 ms per tool call (sandbox); rules/regex only |
| Determinism | 100% of policy decisions in code; no prompts in the decision path |
| Fail closed | Any resolve/check error → BLOCKED, tested |
| Log privacy | Ledger holds IDs, labels, hashes; never bodies or attachments, tested |
| Secrets | Env vars only; `token.json`, `credentials.json`, `.env` git-ignored |
| Idempotency | Double approve / re-execute never sends twice, tested |
| Tests | One per check, transition, attack and guarantee; pytest green before demo |

### 10.8 Dependencies and assumptions

- Anthropic API (`claude-sonnet-5-5`) for the harness agent only.
- Gmail API (`gmail.send`, `gmail.readonly`) with a pre-generated `token.json`.
- Official MCP Python SDK. On stage the MCP client runs on the same laptop (Claude Code), so nothing is tunnelled. If a remote client is used, only the MCP listener is exposed, never the owner console.
- All demo data is synthetic. Existing seed in `backend/data/` is reused: Priya Rao (investor, NDA), Karan Mehta (investor, no NDA), Projections v2/v3, Teaser Deck.

### 10.9 Definition of done

- [ ] Claude, over MCP, completes "Handle my investor follow-ups" end to end
- [ ] 0 sensitive fixture values in any Shielded tool result (enumerated-fixture test), shown on the dashboard
- [ ] Unknown-recipient data-room request → BLOCKED in the same run
- [ ] A1–A5 all fail through Shield (sandbox-state scored, 3 runs)
- [ ] Projections v3 to Priya on the sandbox mailbox shows VERIFIED (recipient, subject, body and attachment SHA-256 matched against the Sent record)
- [ ] Optional: one live Gmail send with the same result
- [ ] Only the authenticated user can approve; wrong-seal approval refused
- [ ] Tampered file/payload after approval → FAILED
- [ ] Simulated provider timeout → VERIFICATION_PENDING → VERIFIED, exactly one message sent
- [ ] Receipt query answers the cap-table question correctly
- [ ] pytest all green
- [ ] Demo run 5× consecutively; backup video recorded

### 10.10 3-minute demo script

1. **The user problem (25s):** "I'm a founder. My inbox has investor requests next to my cap table, a layoff plan, my PAN and a medical note. I want an assistant to handle investor follow-ups. Instinct, Muse and OpenClaw ask for access to everything, and each has gone wrong: Instinct emailed an investor without asking, OpenClaw deleted an inbox, Muse shipped with a backdoor-grade zero-day." Today's demo uses Claude over MCP, because Instinct and Muse can't yet be put behind a third-party layer.
2. **Side by side (30s):** same request, same model. Two columns, both measured: **sensitive values exposed to the model** (Direct vs Shielded) and **task completed?** (Direct vs Shielded). Numbers shown exactly as the run produced them.
3. **With Shield (75s):** *"Handle my investor follow-ups"*, with "send Priya the projections" as the concrete case.
   - The model sees the investor requests as handles and purpose-filtered summaries; everything unrelated shows only as **withheld** counts; the seeded malicious email is quarantined.
   - Stranger asking for the data room → **🛑 BLOCKED, unknown recipient.**
   - Priya → checks go green → founder approves → send on the sandbox mailbox → **✅ VERIFIED** (recipient and attachment fingerprint match).
   - Assistant relays the code-written status.
4. **Receipt (15s):** "Did any AI see my cap table today?" → "Shield released the cap table 0 times and withheld it twice today."
5. **Close (25s):** one slide of §4.1 and §6: the same policy across assistants; full enforcement where Shield is the only route to the account; containment for closed assistants where a mirror is supported; watch and revoke as far as each provider allows. "Muse protects Muse. Shield protects you, with any assistant, across everything it touches. The AI proposes. The code decides. Nothing is done until it's proven."

Fallback: the backup video.

---

## Appendix — Key sources

- Willison, the lethal trifecta [V]: https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/
- EchoLeak [V]: https://arxiv.org/pdf/2509.10540
- Gemini calendar invites [V]: https://www.techrepublic.com/article/news-google-gemini-indirect-prompt-injection-attack/
- AgentFlayer [L]: https://cybersecuritynews.com/chatgpt-0-click-connectors-vulnerability
- Instinct (TechCrunch, Aug 2026) [V]: https://techcrunch.com/2026/08/24/instincts-powerful-ai-assistant-is-raising-privacy-and-security-concerns/
- OpenClaw inbox deletion (TechCrunch) [L]: https://techcrunch.com/2026/02/23/a-meta-ai-security-researcher-said-an-openclaw-agent-ran-amok-on-her-inbox
- Muse zero-day (iTnews) [L]: http://www.itnews.com.au/news/security-researcher-says-dont-install-metas-muse-ai-assistant-629088
- Menlo Ventures, State of Consumer AI 2026 [V]: https://menlovc.com/perspective/2026-the-state-of-consumer-ai/
- Meta, Introducing Muse [V]: https://about.fb.com/news/2026/09/introducing-muse-personal-ai-agent/
- NVIDIA OpenShell [V]: https://docs.nvidia.com/openshell/about/overview
- 1Password for agents [V]: https://techcrunch.com/2026/10/22/1password-launches-a-way-for-ai-agents-to-log-in-on-your-behalf-without-seeing-your-password/
- Claude custom connectors [V]: https://support.claude.com/en/articles/11503834-build-custom-connectors-via-remote-mcp-servers
- Research [V]: CaMeL https://arxiv.org/pdf/2503.18813 · Progent https://arxiv.org/pdf/2504.11703 · FIDES https://arxiv.org/pdf/2505.23643v2 · AgentDojo https://arxiv.org/html/2406.13352v3
- Do not cite: the "Dustin Allen" LinkedIn post, the r/ArtificialInteligence thread, the ET Now NVIDIA video.
