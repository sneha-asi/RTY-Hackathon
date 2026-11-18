# Work plan to code freeze (7:00 PM IST)

**Claude builds the M0 layer; Codex reviews.** The one-pager, PRD, HLD and LLD are the source of truth. Rules from [AGENTS.md](../AGENTS.md) apply: small commits, push often, no force-push, no history rewrite, no secrets in git.

## Built (on `main`, 126 tests)

Run `cd backend && python -m pytest -q`, then `python run.py`.

| Part | Where | Tests |
|---|---|---|
| Standing policy, request-bound proposals | `data/policy.json`, `app/handles.py`, `app/broker.py`, `app/guard.py` | `test_slice`, `test_policy_and_boundaries` |
| Read path: cleaner, detectors, summaries, quarantine | `app/cleaner.py`, `app/labels.py`, `app/broker.py` | `test_cleaner`, `test_detectors`, `test_handles_ledger` |
| Write path: five checks, exact-MIME seal, owner approval, at-most-once send, `VERIFICATION_PENDING` / `UNVERIFIED` | `app/guard.py`, `app/journal.py`, `app/mail.py` | `test_slice`, `test_policy_and_boundaries` |
| Two listeners: MCP `:8765/mcp`, owner console `127.0.0.1:8000` | `app/main.py`, `app/mcp_server.py`, `run.py`, `app/static/index.html` | `test_policy_and_boundaries` |
| Ledger, receipts | `app/ledger.py`, `app/receipts.py` | `test_handles_ledger`, `test_policy_and_boundaries` |
| Direct-vs-Shielded comparison | `app/direct_tools.py`, `app/harness.py` | `test_harness_scoring` |

**Demo data:** synthetic sandbox mailbox, calendar and drive; verification reads the sandbox Sent record. The Gmail adapter is optional.

## Codex review (from a fresh `git pull` of `main`)

1. Does the code match the docs? Check invariants I1–I10 against the files above.
2. Look for bugs in the guard: state transitions, seal, no-resend, request binding.
3. Can any Shielded tool result leak a planted value (`data/sensitive_values.json`)?
4. Is any owner endpoint reachable from the MCP listener?

Send findings back to Claude; Claude fixes and pushes.

## Remaining (Claude)

1. Demo runbook (`docs/DEMO.md`) and reset script.
2. Fixes from Codex's review.
3. Rehearsal at 6:30–6:50; final push by 6:55.
