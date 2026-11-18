# Shield — High-Level Design

| Field | Detail |
|---|---|
| Team | Axon |
| Product | Shield |
| Status | M0 (hackathon build) |
| Stack | Python 3.12 · FastAPI · official `mcp` SDK · Gmail API · static HTML + JS pages served by the owner listener (no build step) · SSE |
| Related docs | [PRD](PRD.md) (what and why) · [LLD](LLD.md) (how, in detail) · [One-pager](ONE_PAGER.md) |

---

## 1. What this system does

**For whom:** executives (demo workflow: investor follow-ups), because they deal with a lot of sensitive information, much of it other people's (PRD §1). **Against what:** personal assistants that ask for access to everything, with **Instinct, Muse and OpenClaw** as the focus.

Shield sits between a person's AI assistants and the accounts those assistants can reach. Two kinds of traffic pass through it, and each has one path:

| Traffic | Path | Result |
|---|---|---|
| The assistant **reads** | source → cleaner → labeller → purpose rules → handles + summaries | The model gets only what the task needs (PRD invariant **I1**) |
| The assistant **wants to act** | `propose_*` → checks → seal → user approval → executor → verifier | Code decides; the user approves exact bytes; only VERIFIED counts (**I3–I7**) |

Everything both paths decide is written to an append-only ledger, which feeds the dashboard and the receipts (**I8**).

## 2. From first principles to design principles

The PRD's first principles (PRD § "First principles") lead to these design principles. Each one exists because of an invariant.

| # | Design principle | Because |
|---|---|---|
| D1 | **Shield writes every byte the model receives.** Tool results are assembled from handles, enums, catalogue values, parsed dates and fixed templates. No source text is passed through | I1: privacy must be testable at the interface, not hoped for from detection |
| D0 | **One standing policy drives both paths.** The founder enables it once; the broker releases only what it covers and the guard accepts only proposals it covers, bound to the request that justified them. `purpose` can only narrow it | PRD "one policy" principle; I1, I4 |
| D2 | **The assistant can request scoped reads and create proposals; execution and approval authority stay outside the assistant** | I3: the external-action leg of the trifecta is removed, not filtered |
| D3 | **Targets come from the request; objects must match it.** The recipient is the sender of a request released in this session; the file must be the category asked for (teaser is the only policy-approved substitute); raw addresses are refused | I4 |
| D4 | **No LLM inside Shield.** Every decision is a pure function of seed data, session state and the proposal | Determinism; avoids "AI guarding AI"; < 150 ms per call |
| D5 | **Approval binds to a seal.** The user approves a hash of the exact recipients, message bytes and attachment bytes; the executor sends only bytes that re-hash to it | I6 |
| D6 | **Done is a provider fact.** Success requires reading the provider's own record; an uncertain send moves to VERIFICATION_PENDING and is never resent | I7 |
| D7 | **Fail closed.** Any exception in resolve, check or summarise → BLOCKED or withheld | I9 |
| D8 | **Log decisions, not content.** The ledger stores IDs, labels, hashes and reasons | I8 |
| D9 | **Claims follow the access path.** Per account: "sole path: yes / no / unknown"; unknown whenever direct access can't be checked | I10 |

## 3. Component architecture

**Shared policy.** The standing policy (`data/policy.json`, M0: `investor_followups`) is bound to each MCP session when it starts. It feeds both the broker (which purposes, roles and categories may be released) and the guard (which requests may be answered, with which file categories, to which roles). A proposal names a *request* handle; the guard checks the request was released in this session under this policy.

```
            standing policy (founder enables once: investor_followups)
                  │                                   │
                  ▼                                   ▼
   BROKER: what may be learned             GUARD: what may be proposed
   (purposes, roles, categories)           (request → recipient, category match, NDA fallback)
```

```
   Assistant client (Claude · ChatGPT dev mode · Cursor · any MCP client)
                      │  MCP, streamable HTTP            ▲ status text (code-written)
                      ▼                                  │
 ┌──────────────────────────────── SHIELD ─────────────────────────────────┐
 │  MCP surface (tools.py / mcp_server.py)   — no action tools, no approve   │
 │        │ read tools                         │ propose_* tools             │
 │        ▼                                    ▼                             │
 │  BROKER (read path)                  GUARD (write path)                   │
 │  cleaner → labels → purpose rules    WHO · WHAT · POLICY · CONTENT · LOCK │
 │  → handles → summaries → exposure    → seal → AWAITING_APPROVAL           │
 │        │                                    │  ▲ approve(seal) — user only│
 │        │                                    ▼  │                          │
 │        │                             EXECUTOR → VERIFIER                  │
 │        │                             send sealed bytes · read provider    │
 │        ▼                                    ▼                             │
 │  LEDGER (append-only) ──► SSE ──► DASHBOARD (approval, exposure, receipts)│
 └───────────┬───────────────────────────────────┬─────────────────────────┘
             ▼                                   ▼
   Sources (sandbox JSON: mail, calendar, files)   Mail provider (FakeMail · Gmail API)
```

| Component | Responsibility | Can see raw data? | Talks to model? |
|---|---|---|---|
| MCP surface | Exposes read and `propose_*` tools; attaches session id | No (passes handles) | Yes |
| Broker | Cleans, labels, applies purpose rules, builds handles and summaries, counts exposure | Yes | Only through the MCP surface, with D1 output |
| Handle registry | Per-session mapping of handle ↔ contact, sender, file, thread, event | Yes (server-side) | No |
| Guard | Resolves handles, runs checks, builds and seals the exact message, owns the state machine | Yes | Status text only |
| Executor | Sends the sealed bytes through the provider adapter | Yes | No |
| Verifier | Finds the sent message by sealed Message-ID; compares recipients, subject, attachment hash | Yes | No |
| Ledger | Append-only events; receipts; SSE feed | No (IDs, labels, hashes) | No |
| Dashboard | Login, approval cards with real resolved payload, exposure panels, timeline, receipts | Yes (the user's own data, behind login) | No |
| Comparison harness | Same task, same model, Direct vs Shielded; scores from sandbox state | Direct mode only | Yes (harness agent) |

## 4. Deployment boundary and trust boundaries

```
 ┌──────────── user-controlled machine / infrastructure ────────────┐
 │  raw data · credentials (token.json) · broker · guard · executor   │
 │  verifier · ledger · send journal                                  │
 │  OWNER LISTENER 127.0.0.1:8000 (login, /review/<id>, console, SSE) │  ← never tunnelled
 │  MCP LISTENER  :8765/mcp       (filtered tools only)               │  ← the only exposed surface
 └────────────────────────────────────────┬──────────────────────────┘
                                          ▼
                         remote assistant client (MCP)
```

The MCP listener is a separate ASGI app with no owner routes; a tunnel to it cannot reach approval, dashboard data, SSE or dev endpoints (tested). Files a user uploads directly to an assistant are outside this boundary.


| Boundary | What may cross | What may not | Enforced by |
|---|---|---|---|
| Shield → model | Handles, structured attributes, purpose-filtered summaries, withheld counts, quarantine notices, code-written status text | Source text, addresses, file bytes, detected sensitive values | Broker output types (D1); fixture-enumerated test |
| Model → Shield | Read tool calls; proposals made of handles plus a short note | Raw addresses, URLs, images, approvals | Argument gate; CONTENT check; no approve tool |
| User → Shield | Login; approve or reject with the seal shown | Approval without login or with a different seal | Owner session cookie; seal equality (401 / 409) |
| Shield → provider | The sealed message bytes, once | A second send for the same action, including after a restart | Send-attempt marker written to a local journal and fsynced before the call |
| Provider → Shield | Send result; Sent-folder record by Message-ID | — | Verifier compares against sealed values |
| Shield → logs | IDs, labels, hashes, reasons | Bodies, addresses, attachments | Ledger schema; ledger-privacy test |
| Secrets | `.env`, `token.json`, user secret | Anything in git | `.gitignore`; env-only config |

**One approval page for every assistant.** Every proposal that reaches approval returns a `review_url` (`/review/<action_id>` on the owner-only listener). Claude, OpenClaw, or any MCP client relays the same link. The link identifies the action and carries no credential; the page needs the executive's Shield login. It shows one card: the real recipient and message, the attachment and any policy warning, **Approve & send / Reject**, and the verified status as it updates, with the receipt in a collapsible section. The assistant can fetch the same outcome with `action_status`.

## 5. Access paths

The full product has four modes (PRD §4). M0 implements mode 1.

| Mode | M0 | What holds |
|---|---|---|
| 1. Enforce (MCP; Shield is the only route) | **Built** | All invariants I1–I10. Sole path shown as yes / no / unknown |
| 2. Enforce at the edge (local proxy / extension) | Roadmap | Egress blocking, partial read control |
| 3. Contain (supported mirror for closed assistants) | **Demo built**: safe publication with stable IDs into a restricted test inbox + untrusted paste intake → same checks and review page; live Instinct handoff pending the go/no-go test | Minimisation by construction; mirror sends gated |
| 4. Watch and revoke | **Built for Gmail**: reads Sent and Drafts, flags anything not approved through Shield (confidential file, unknown recipient, sensitive values, links), removes risky drafts, links to revoke access | After-the-fact detection, as far as each provider exposes |

How each focus assistant is reached (PRD §1):

| Assistant | Mode(s) | M0 |
|---|---|---|
| Instinct (closed, own login) | 3 Contain (mirror inbox) + 4 Watch & revoke | Roadmap experiment until tested |
| Muse (desktop agent) | 2 Edge + 3 Contain + 4 Watch & revoke | Roadmap experiment until tested |
| OpenClaw (user-run) | 1 Enforce if its tools can point at Shield [U]; else 2 Edge | Roadmap |
| Claude (MCP connector) | 1 Enforce | **Demo client**: proves the mechanism end to end |

## 6. Core flows

The demo runs these flows for one request, *"Handle my investor follow-ups"*; the full step-by-step trace is in LLD §17.1.

**Read**
```
search(purpose, query) → for each item: clean → label → purpose rule → (release | withhold | quarantine)
  release  → ReleasedItem{handles, intent, category, due, template summary}
  withhold → count by label
  quarantine → notice with sender handle + pattern names
→ exposure accounting → ledger("release")
```

**Act**
```
propose_send_document(THREAD_1, FILE_2, note)     # the request handle, not a recipient
  → argument gate → WHO → WHAT → POLICY → CONTENT          (all run; any fail → BLOCKED)
  → read file once → build exact MIME → seal               (LOCK)
  → AWAITING_APPROVAL → review_url (/review/<id>, owner listener) returned to the assistant
user approve(seal)
  → re-read once → hash checks → send those bytes          (send_attempted = true first)
  → verifier: find by Message-ID in the mailbox's Sent record → VERIFIED | UNVERIFIED (record differs) | VERIFICATION_PENDING → retry → VERIFIED | UNVERIFIED
```

**Action lifecycle**
```
PROPOSED ─► BLOCKED
   └─► AWAITING_APPROVAL ─► REJECTED
            └─► APPROVED ─► FAILED (seal mismatch, nothing sent)
                   └─► EXECUTING ─► VERIFIED ✅ (only success)
                          │    ├──► FAILED (definitely not sent: provider rejected)
                          │    └──► UNVERIFIED (sent, record differs)
                          └─► VERIFICATION_PENDING ─► VERIFIED │ UNVERIFIED (may have been sent / record differs)
```

## 7. Data architecture (M0)

All data is in memory, plus JSON seed files and a git-ignored runtime directory. There is no database.

| Store | Contents | Lifetime |
|---|---|---|
| Seed | contacts, files (+ sha256 at startup), emails, events, policy | Process; reloaded on `/dev/reset` |
| Runtime files | Copy of `files/` that the executor and LOCK read | Process; restored on reset (tamper target) |
| Handle registry | Per session: handle → ref + attributes | Session |
| Actions | Action records, payloads, seals, states | Process |
| Ledger | Append-only events; mirrored to `runtime/ledger.jsonl` | Process + file |
| Outbox (FakeMail) | Raw sent bytes + envelope | Process |

## 8. Observability

| Layer | What |
|---|---|
| Ledger events | release, quarantine, request_denied, transition, check, verify, harness, all with a one-line reason |
| SSE | Every ledger event pushed to the dashboard |
| Dashboard counters | Items released · sensitive values exposed (measured) · proposals blocked · actions verified |
| Receipts | "Shield released X n times and withheld it m times today", from ledger counts only |

## 9. Implementation status

All on `main`; 126 tests (`cd backend && python -m pytest -q`).

| Slice (LLD §16) | Status |
|---|---|
| 1. MCP → request-bound proposal → owner console approval → sandbox mailbox → read-back → VERIFIED | **Done** |
| 2. VERIFICATION_PENDING, no-resend with a durable journal and restart recovery, tamper → FAILED, mismatch → UNVERIFIED | **Done** |
| 3. Seed (16 emails, 4 events, 6 files), cleaner, detectors, fail-closed summaries, A1–A5 attack suite, fixture privacy test | **Done** |
| 4. Gmail adapter | Code done; optional (the demo uses the synthetic sandbox mailbox) |
| 5. Ledger, receipts, SSE, owner console (policy and sole-path indicator, Sent folder) | **Done** |
| 6. Direct-vs-Shielded comparison (scripted runner; model runner needs an API key) | **Done**: 21 planted values exposed without Shield, 0 with; task done in both |
| 7. Calendar first cut (`free_slots`, free/busy only, policy-gated) | **Done** |
| Assistants strip: connected MCP clients (by their MCP client name) shown as enforced under one policy; Instinct, Muse, OpenClaw shown as roadmap, not tested | **Done** |
| Tools: `search`, `read`, `list_files`, `free_slots`, `propose_send_document`, `propose_reply`, `action_status` | **Done** |
