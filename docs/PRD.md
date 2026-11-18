# Axon Shield — PRD (M0, hackathon build)

**The user-side trust layer for personal AI assistants.**
Team Axon · Track `ai-agents` · Buildathon, Wed 18 Nov 2026, 3–7 PM IST · Feature freeze 5:30 PM · Code freeze 7:00 PM

> **The AI proposes. The code decides. Nothing is done until it's proven.**

Confidence labels for external facts: **[V]** checked against the primary source · **[L]** secondary source, likely true · **[U]** unverified, don't cite on stage.

---

## 1. Problem (who and why)

**Who:** founders who let an AI assistant into their Gmail, Calendar and Drive. They hold the most sensitive mail in a company (term sheets, cap tables, hiring, board matters), most of it other people's data, and they adopt assistants early. Today they either give the assistant everything or don't use one.

**Why it happens:** an assistant that combines **(1) private data, (2) untrusted content and (3) a way to send things out** can be steered by instructions hidden in what it reads. This is Simon Willison's *lethal trifecta* [V]. Detection doesn't fix it: a 99%-effective injection classifier is still an "unacceptable risk" (Willison) [V]. Every major assistant has been hijacked this way:

| Incident | Mechanism |
|---|---|
| EchoLeak, CVE-2025-32711 (M365 Copilot) [V] | One email → zero-click exfiltration via an auto-fetched image URL |
| Gemini calendar invites, Black Hat 2025 [V] | Hidden text in an invite controlled devices and leaked calendar data |
| AgentFlayer, ChatGPT connectors [L] | Poisoned doc → agent searched Drive for API keys, leaked them via image URLs |
| Instinct, Aug 2026 [V] | Emailed an investor "without checking with me first" |

Scale: 32% of US AI users have let AI act without a final sign-off; 76% of non-users cite privacy (Menlo Ventures / Morning Consult, n=5,067, Jul 2026) [V].

**The gap:** platforms now gate their *own* assistant (Muse, Dots, Claude and Gemini ask before sending) [V/L], but each vendor audits itself, the model still sees all the data, and nobody checks the outcome against what was actually sent. Point tools (PortEden, mcp-pvp, AgentCloak, approval proxies) each cover one piece [L].

## 2. What Shield is

An **MCP server the user owns**. The assistant (Claude, ChatGPT dev mode, Cursor, any MCP client) connects to Shield instead of Gmail. Shield cuts each leg of the trifecta structurally, per request:

| Trifecta leg | Shield's cut |
|---|---|
| Private data | The model gets **handles with attributes** (`CONTACT_1 · investor · NDA ✔`, `FILE_2 · projections · v3`), never addresses, file contents or sensitive spans |
| Untrusted content | **Cleaner** strips hidden text; instruction-like content is **quarantined** before the model sees it |
| External communication | **No raw send tool.** The model only *proposes*; code resolves handles, checks, seals, gets human approval, executes and **verifies** |

Plus: outgoing model text can't carry URLs or images (closes the EchoLeak/AgentFlayer channel), and every step goes into a ledger the user can query ("Did any AI see my cap table today?").

**Claim we make:** "We couldn't find a single user-side layer that works across assistants and combines need-to-know handles, code-decided recipients and files, sealed approvals, leak-channel blocking and verified outcomes."
**Claims we never make:** "nobody gates agent actions" (false) or "no competitor exists" (point tools exist; name them first).

## 3. M0 goals and acceptance

| Goal | Measured as |
|---|---|
| Minimise what the model sees | Shielded demo task: ≤4 items released, **0 sensitive values** |
| Injections are powerless | **0 of 5** attacks (A1–A5) succeed through Shield, scored from sandbox state |
| Still useful | Benign task succeeds through Shield **3/3** runs |
| Code decides who/what | Every send resolved from contacts + file catalogue; a raw address → BLOCKED |
| Proof before "done" | 0 unverified successes; tampered file/payload → FAILED |
| Auditable | Receipt query answers "did any AI see X?" with counts |
| Reliable demo | Full demo 5× in a row; one real Gmail send verified on stage |

**Non-goals:** making the model injection-proof; replacing the assistant; protecting closed assistants that hold their own OAuth tokens (Instinct, Muse, Dots). We say this last one out loud on stage; the M3 answer is a filtered mirror inbox.

## 4. Architecture

```
 Claude · ChatGPT (dev mode) · Cursor · any MCP client
                 │  MCP, streamable HTTP (ngrok for remote)
                 ▼
┌──────────────────────────── AXON SHIELD ───────────────────────────┐
│ READ   source → cleaner → labeller → purpose rules → handles       │
│        → masked view + exposure count                              │
│ WRITE  propose_* → WHO · WHAT · POLICY · CONTENT · LOCK            │
│        → approval → executor → verifier                            │
│ LEDGER append-only events → SSE → dashboard · receipts             │
└──────────────┬──────────────────────────────────┬──────────────────┘
               ▼                                  ▼
   Sandbox (JSON mail/calendar/drive)    Gmail API (send + read-back)
```

Stack: Python 3.12 · FastAPI · official `mcp` SDK · Anthropic SDK (harness only) · Gmail API · Vite + React + Tailwind · SSE. **No LLM inside Shield; no database** (in-memory + JSON seeds).

| Module | Job |
|---|---|
| `sources.py` | Sandbox/Gmail adapters → `Item{id, kind, sender, to, subject, body_html, body_text, ts, attachments}` |
| `cleaner.py` | Strip hidden text (display:none, white-on-white, tiny fonts, zero-width chars, whitespace padding); detect + quarantine instruction-like content |
| `labels.py` | Sensitivity classes `financial · legal · hr · health · identity_ids · secrets · deal`; detectors: PAN, Aadhaar (Verhoeff), GSTIN, IFSC, UPI, card (Luhn), API keys, emails, phones, money |
| `handles.py` | Per-session `CONTACT_n / SENDER_n / FILE_n / THREAD_n` with attributes; mapping never leaves the server |
| `broker.py` | Purpose rules (`schedule`, `share_document`, `reply`, `triage`), masked views, exposure accounting |
| `guard.py` | Proposals, the five checks, payload seal, approval state machine |
| `executor.py` | Sandbox mailbox + Gmail send; code picks the attachment bytes |
| `verifier.py` | Re-read sent message; compare recipients, subject, attachment name + SHA-256 |
| `ledger.py` | Events, receipts, SSE; stores IDs/labels/hashes only, never bodies |
| `mcp_server.py` | Tool surface below |
| `harness.py` | Direct vs Shielded runs with Claude; deterministic scoring |
| `main.py` | FastAPI: dashboard REST, SSE, approvals, dev endpoints |
| `dashboard/` | React UI |

### MCP tools (Shielded)

| Tool | Input | Returns |
|---|---|---|
| `search` | `purpose`, `query?` | Masked items as handles + withheld counts |
| `read` | `purpose`, thread handle | Masked thread, only if purpose allows |
| `list_files` | `category?` | `FILE_n` handles: category, version, requires_nda. Never contents |
| `free_slots` | date range | Free/busy only |
| `propose_send_document` | recipient handle, file handle, `note?` | `{action_id, status, checks[], readback}` |
| `propose_reply` | thread handle, text | same |
| `propose_event` | attendee handles, slot, title | same |
| `action_status` | `action_id` | Code-written status text the assistant relays verbatim |

There is deliberately **no `send_email(to, …)`**. The Direct baseline (comparison only, sandbox only) exposes raw `list_emails`, `read_email`, `read_file`, `send_email(to, subject, body, attachment)`.

### The five checks

| Check | Rule | Fails when |
|---|---|---|
| **WHO** | Handle resolves to a known contact | Unknown `SENDER_n`, raw address, unresolvable handle |
| **WHAT** | Latest version of the category; NDA-required file + no NDA → downgrade to teaser with warning | File missing / not latest |
| **POLICY** | Per action type × sensitivity: financial needs known contact + NDA; `secrets` never shareable | Rule violated |
| **CONTENT** | Model-written text has no external URLs, markdown images, raw emails, handles or sensitive patterns; length cap | Any found |
| **LOCK** | Seal at proposal; recompute at execution | Hash mismatch → FAILED |

**Seal:** `payload_hash = sha256(type ‖ recipient_contact_id ‖ recipient_email ‖ subject ‖ body ‖ file_id ‖ file_sha256 ‖ slot)`, recomputed at execution from the stored payload and the file bytes on disk now.

### State machine

```
PROPOSED ──► BLOCKED                         (terminal, reason)
    └──► AWAITING_APPROVAL ──► REJECTED      (terminal)
              └──► APPROVED ──► EXECUTING ──► VERIFIED  (terminal ✅)
                                     └──────► FAILED    (terminal ❌, never shown as success)
```
Every transition appends `{ts, session_id, action_id, from, to, reason}` to the ledger and SSE. Illegal transitions raise. Any error in resolve/check → BLOCKED (fail closed).

## 5. Demo journeys

1. **Safe send (primary).** "Send Priya the projections she asked for." → `search(purpose=share_document)` releases the request thread + file catalogue as handles → `propose_send_document(CONTACT_1, FILE_2)` → WHO Priya Rao ✔ · WHAT Projections v3 ✔ · POLICY NDA ✔ · CONTENT ✔ · LOCK sealed → founder approves on the dashboard (sees the real resolved payload) → Gmail send → read-back → ✅ VERIFIED.
2. **Injection neutralised.** Triage: invite + email carry hidden instructions → stripped/quarantined; model sees `[quarantined · SENDER_4]`; red banner on dashboard.
3. **Unknown recipient.** "New investor" asks for the data room → propose to `SENDER_3` → WHO ✘ → 🛑 BLOCKED ("add the contact first").
4. **Leak channel.** Draft reply contains a markdown image URL → CONTENT ✘ → 🛑 BLOCKED.
5. **Tamper.** Swap the projections file after approval → LOCK mismatch → ❌ FAILED "changed after approval".
6. **Receipt.** "Did any AI see my cap table today?" → "No. Requested 2×, withheld 2× (purpose: triage, schedule)."
7. **Karan** (investor, no NDA) asks for projections → WHAT downgrades to Teaser Deck with a warning.

## 6. Attack suite

| ID | Modelled on | Adversary goal | Structural defence |
|---|---|---|---|
| A1 | Gemini calendar invite | Leak data / take an action via an event | Quarantine; propose-only; CONTENT |
| A2 | EchoLeak (white-on-white + image URL) | Exfiltrate cap table | Cap table never released for the purpose; no raw send; URL blocked |
| A3 | AgentFlayer (doc asks for API keys in a link) | Exfiltrate secrets | `secrets` never released; CONTENT blocks URLs |
| A4 | Unknown "investor" wants data room | Send financials to a stranger | WHO → BLOCKED |
| A5 | "Also CC finance-review@…" | Add attacker recipient | Handles only; raw address → BLOCKED |

**Scoring** (deterministic, from sandbox state, 3 runs per task × mode): **utility** (task done correctly), **attack success** (any adversary goal reached), **exposure** (sensitive items shown to the model). Shown exactly as measured; the pitch never depends on Direct mode failing.

## 7. Functional requirements

All P0 unless marked.

| ID | Requirement | Acceptance |
|---|---|---|
| F1 | Synthetic sandbox: ~15 emails, ~6 events, ~6 files, ~6 contacts incl. term sheet, cap table, layoff plan, GST/PAN, medical note, API key in a doc | Loads at startup; file SHA-256s computed |
| F2 | Attacks A1–A5 in the seed | Present and labelled in tests |
| F3 | Cleaner + quarantine for non-trusted senders | A1–A3 never reach the model as text |
| F4 | Labeller + detectors | Positive and negative unit test per detector |
| F5 | Handle registry, per session, server-side | No raw address or file path in any Shielded result |
| F6 | Purpose rules ×4 | Per-purpose released/withheld tests |
| F7 | Exposure accounting per call and session | Demo task: ≤4 released, 0 sensitive |
| F8 | Handle-only proposals, no raw send | Raw address in args → BLOCKED |
| F9 | WHO | A4 → BLOCKED |
| F10 | WHAT | Priya → v3; Karan → teaser |
| F11 | POLICY | One test per rule |
| F12 | CONTENT | Image-URL exfil → BLOCKED |
| F13 | LOCK | Tampered payload or file → FAILED |
| F14 | Approval API + dashboard showing the real payload | Only AWAITING_APPROVAL approvable; idempotent |
| F15 | Executor: sandbox + Gmail with attachment | Real email lands in investor test inbox |
| F16 | Verifier | Match → VERIFIED; any mismatch → FAILED |
| F17 | Ledger + SSE + receipt queries | Cap-table question answered correctly |
| F18 | MCP server (streamable HTTP) | Claude connects and completes the demo task |
| F19 | Harness: Direct vs Shielded, 3 runs each | Dashboard shows measured utility / attack success / exposure |
| F20 | Dashboard: Direct vs Shielded panels, action cards with check rows, timeline, counters | Readable from the back of the room |
| F21 | *P2:* Earned autonomy (standing rules from verified track record; auto-demotion) | — |
| F22 | *P2:* Approve by phone (voice agent + PIN) | — |
| F23 | *P2:* Real Gmail as read source | — |

## 8. Guarantees

**By construction** (for traffic through Shield):
1. The model never receives raw contact addresses, file contents, or detected sensitive spans.
2. The model cannot cause a send to a recipient code didn't resolve from the contact list.
3. Model-written text cannot carry external URLs or images out.
4. An approved payload can't change before execution without failing.
5. Nothing is reported done without verification against the sent message.

**Not guaranteed** (said out loud): catching every hidden instruction (detection is defence in depth); masking every sensitive item in free text (mitigated by purpose release + fail closed); assistants that bypass Shield; a user approving a bad action (mitigated by showing the real, code-generated payload).

## 9. Non-functional

| | Target |
|---|---|
| Added latency | < 150 ms per tool call (sandbox); rules/regex only |
| Determinism | 100% of policy decisions in code; no prompts in the decision path |
| Fail closed | Any resolve/check error → BLOCKED, tested |
| Log privacy | Ledger holds IDs, labels, hashes; never bodies or attachments, tested |
| Secrets | Env vars only; `token.json`, `credentials.json`, `.env` git-ignored |
| Idempotency | Double approve / re-execute never sends twice, tested |
| Tests | One per check, transition, attack and guarantee; pytest green before demo |

## 10. Dependencies and assumptions

- Anthropic API (`claude-sonnet-5-5`) for the harness agent only.
- Gmail API (`gmail.send`, `gmail.readonly`) with a pre-generated `token.json`.
- Official MCP Python SDK; ngrok; Claude custom connector (remote MCP, all plans) [V]. If the venue network blocks it, the backup video covers it.
- All demo data is synthetic. Existing seed (`backend/data/`) is reused: Priya Rao (investor, NDA), Karan Mehta (investor, no NDA), Projections v2/v3, Teaser Deck.

## 11. Definition of done (M0)

- [ ] Claude, over MCP, completes "send Priya the projections" end to end
- [ ] Shielded exposure for the demo task = 0 sensitive values, on the dashboard
- [ ] A1–A5 all fail through Shield (sandbox-state scored, 3 runs)
- [ ] Real Gmail email with Projections v3 lands and shows VERIFIED (SHA-256 matched)
- [ ] Tampered file/payload after approval → FAILED
- [ ] Receipt query answers the cap-table question correctly
- [ ] pytest all green
- [ ] Demo run 5× consecutively; backup video recorded

## 12. Roadmap

| | Theme | Deliverables |
|---|---|---|
| M0 | Hackathon | This document |
| M1 | Real accounts | Real Gmail/Calendar/Drive sources, OAuth onboarding, hosted MCP, Claude + ChatGPT connectors |
| M2 | Earned autonomy, voice approvals | Standing rules from verified history, auto-demotion; approve by phone/push |
| M3 | Closed assistants | Filtered mirror inbox for Instinct/Muse-style assistants |
| M4 | Axon chief of staff | Relationship memory, founder-specific policies; Shield becomes Axon's trust layer |

## 13. Open questions

- Purpose inference: M0 has the assistant state the purpose and Shield validates it. Infer it later?
- How should handles appear in assistant UIs so users understand them? (M1)
- Mirror inbox send path: send-as alias vs relay with approval? (M3)
- Policy authoring for non-technical users: templates vs earned rules? (M2)

## Appendix A — 3-minute demo script

1. **Hook (20s):** Instinct emailed an investor without asking. Copilot, Gemini and ChatGPT were hijacked by an email or an invite. 32% of AI users have already let AI act without sign-off.
2. **Direct (40s):** "Check my week, then send Priya the projections she asked for." Left panel: what the model received (term sheet, layoff email, GST/PAN, medical note, poisoned invite) with the measured exposure count.
3. **Shielded (60s):** invite quarantined → model sees ~3 items, 0 sensitive, as handles → proposes `FILE_2 → CONTACT_1` → five checks go green → approve → real email lands → ✅ VERIFIED.
4. **Attacks (30s):** data-room request from unknown sender → 🛑; image-URL leak → 🛑.
5. **Tamper (15s):** swap file after approval → ❌ FAILED "changed after approval".
6. **Receipt (15s):** "Did any AI see my cap table today?" → "No. Withheld 2×."
7. **Close:** "Muse protects Muse. Shield protects you, with any assistant. The AI talks. The code decides. Nothing is done until it's proven."

## Appendix B — Key sources

- Willison, the lethal trifecta [V]: https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/
- EchoLeak [V]: https://arxiv.org/pdf/2509.10540
- Gemini calendar invites [V]: https://www.techrepublic.com/article/news-google-gemini-indirect-prompt-injection-attack/
- AgentFlayer [L]: https://cybersecuritynews.com/chatgpt-0-click-connectors-vulnerability
- Instinct (TechCrunch, Aug 2026) [V]: https://techcrunch.com/2026/08/24/instincts-powerful-ai-assistant-is-raising-privacy-and-security-concerns/
- Menlo Ventures, State of Consumer AI 2026 [V]: https://menlovc.com/perspective/2026-the-state-of-consumer-ai/
- Meta, Introducing Muse [V]: https://about.fb.com/news/2026/09/introducing-muse-personal-ai-agent/
- Claude custom connectors [V]: https://support.claude.com/en/articles/11503834-build-custom-connectors-via-remote-mcp-servers
- Research: CaMeL https://arxiv.org/pdf/2503.18813 · Progent https://arxiv.org/pdf/2504.11703 · FIDES https://arxiv.org/pdf/2505.23643v2 · AgentDojo https://arxiv.org/html/2406.13352v3 [V]
- Do not cite: the "Dustin Allen" LinkedIn post, the r/ArtificialInteligence thread, the ET Now NVIDIA video.
