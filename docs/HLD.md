# Shield — High-Level Design

| Field | Detail |
|---|---|
| Team | Axon |
| Product | Shield |
| Status | M0 (hackathon build) |
| Stack | Python 3.12 · FastAPI · official `mcp` SDK · Gmail API · Vite + React + Tailwind · SSE |
| Related docs | [PRD](PRD.md) (what and why) · [LLD](LLD.md) (how, in detail) · [One-pager](ONE_PAGER.md) |

---

## 1. What this system does

**For whom:** executives (founders first), because they deal with a lot of sensitive information, much of it other people's (PRD §1). **Against what:** personal assistants that ask for access to everything, with **Instinct, Muse and OpenClaw** as the focus.

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
| D2 | **The model holds no capability.** No tool performs an action; every action tool only creates a proposal | I3: the external-action leg of the trifecta is removed, not filtered |
| D3 | **Targets and objects come from the user's records.** Handles resolve server-side to contacts and catalogue files; raw addresses are refused | I4 |
| D4 | **No LLM inside Shield.** Every decision is a pure function of seed data, session state and the proposal | Determinism; avoids "AI guarding AI"; < 150 ms per call |
| D5 | **Approval binds to a seal.** The user approves a hash of the exact recipients, message bytes and attachment bytes; the executor sends only bytes that re-hash to it | I6 |
| D6 | **Done is a provider fact.** Success requires reading the provider's own record; an uncertain send moves to VERIFICATION_PENDING and is never resent | I7 |
| D7 | **Fail closed.** Any exception in resolve, check or summarise → BLOCKED or withheld | I9 |
| D8 | **Log decisions, not content.** The ledger stores IDs, labels, hashes and reasons | I8 |
| D9 | **Claims follow the access path.** The dashboard shows per account whether Shield is the sole path and which mode applies | I10 |

## 3. Component architecture

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

## 4. Trust boundaries

| Boundary | What may cross | What may not | Enforced by |
|---|---|---|---|
| Shield → model | Handles, structured attributes, purpose-filtered summaries, withheld counts, quarantine notices, code-written status text | Source text, addresses, file bytes, detected sensitive values | Broker output types (D1); fixture-enumerated test |
| Model → Shield | Read tool calls; proposals made of handles plus a short note | Raw addresses, URLs, images, approvals | Argument gate; CONTENT check; no approve tool |
| User → Shield | Login; approve or reject with the seal shown | Approval without login or with a different seal | Owner session cookie; seal equality (401 / 409) |
| Shield → provider | The sealed message bytes, once | A second send for the same action | `send_attempted` flag set before the call |
| Provider → Shield | Send result; Sent-folder record by Message-ID | — | Verifier compares against sealed values |
| Shield → logs | IDs, labels, hashes, reasons | Bodies, addresses, attachments | Ledger schema; ledger-privacy test |
| Secrets | `.env`, `token.json`, user secret | Anything in git | `.gitignore`; env-only config |

## 5. Access paths

The full product has four modes (PRD §4). M0 implements mode 1.

| Mode | M0 | What holds |
|---|---|---|
| 1. Enforce (MCP; Shield is the only route) | **Built** | All invariants I1–I10 |
| 2. Enforce at the edge (local proxy / extension) | Roadmap | Egress blocking, partial read control |
| 3. Contain (supported mirror for closed assistants) | Roadmap | Minimisation by construction; mirror sends gated |
| 4. Watch and revoke | Roadmap | After-the-fact detection, as far as each provider exposes |

How each focus assistant is reached (PRD §1):

| Assistant | Mode(s) | M0 |
|---|---|---|
| Instinct (closed, own login) | 3 Contain (mirror inbox) + 4 Watch & revoke | Roadmap |
| Muse (desktop agent) | 2 Edge + 3 Contain + 4 Watch & revoke | Roadmap |
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
propose_send_document(CONTACT_1, FILE_2, note)
  → argument gate → WHO → WHAT → POLICY → CONTENT          (all run; any fail → BLOCKED)
  → read file once → build exact MIME → seal               (LOCK)
  → AWAITING_APPROVAL → dashboard card
user approve(seal)
  → re-read once → hash checks → send those bytes          (send_attempted = true first)
  → verifier: find by Message-ID → VERIFIED | FAILED | VERIFICATION_PENDING → retry → VERIFIED | UNVERIFIED
```

**Action lifecycle**
```
PROPOSED ─► BLOCKED
   └─► AWAITING_APPROVAL ─► REJECTED
            └─► APPROVED ─► FAILED (seal mismatch, nothing sent)
                   └─► EXECUTING ─► VERIFIED ✅ (only success)
                          │    └──► FAILED (definitely not sent, or sent but mismatched)
                          └─► VERIFICATION_PENDING ─► VERIFIED │ FAILED │ UNVERIFIED (may have been sent)
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

| Slice (LLD §16) | Tests | Status |
|---|---|---|
| 1. Vertical slice: MCP → proposal → approval page → FakeMail → read-back → VERIFIED | seal, state machine, approval auth, verifier | Not started |
| 2. VERIFICATION_PENDING + no-resend; tamper | verification_pending, lock | Not started |
| 3. Full seed, cleaner, labels, fixture privacy test | detectors, cleaner, guarantees | Not started |
| 4. Gmail adapter, one live send | manual + verifier | Not started |
| 5. Ledger receipts, SSE, dashboard | receipts, ledger privacy | Not started |
| 6. Comparison scenes | harness scoring | Not started |
| 7. Calendar first cut (free/busy) | broker | Not started |

Existing in repo: seed contacts and files, demo PDFs, settings loader, append-only event log.
